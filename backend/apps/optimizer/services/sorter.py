from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import random
from typing import Dict, List, Sequence
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.masterdata.models import PackingStation, StationDenominationEfficiency, TransferSegment
from apps.optimizer.models import (
    GlobalConfig,
    OptimizeMode,
    OptimizeModeType,
    OptimizeModeParameter,
    ParameterCategory,
)
from apps.orders.models import OrganizationOrder, SplitType
from apps.runs.models import RunResultStationDetail, RunResultSummary, SortedOrderResult


@dataclass
class StationMetrics:
    busy_seconds: float = 0.0
    first_start: float | None = None
    last_finish: float = 0.0
    wait_seconds: float = 0.0

    @property
    def span_seconds(self) -> float:
        if self.first_start is None:
            return 0.0
        return max(0.0, self.last_finish - self.first_start)

    @property
    def idle_seconds(self) -> float:
        return max(0.0, self.span_seconds - self.busy_seconds)


@dataclass
class OrderAggregate:
    order_no: str
    order_date: object
    organization: object
    route: object
    route_id: int
    source_order: OrganizationOrder
    quantities: Dict[Decimal, int]


class SortingEngine:
    """流水线排序计算引擎。"""

    def __init__(self, mode: OptimizeMode):
        self.mode = mode
        self.stations = list(PackingStation.objects.filter(enabled=True).order_by('station_order'))
        self.transfer_map = self._build_transfer_map()
        self.efficiency_map = self._build_efficiency_map()
        self.weights, self.station_concentration_weights = self._load_weights()
        self.box_interval = self._load_float_config('固定上箱间隔', 2.0)
        self.route_switch_penalty = self._load_float_config('线路切换惩罚系数', 1.0)
        self.max_iterations = int(self._load_float_config('最大迭代次数', 100))
        self.max_restarts = int(self._load_float_config('最大重启次数', 5))
        self._normalize_factors = {
            'total_seconds': 1.0,
            'station_concentration': 1.0,
            'route_continuity_cost': 1.0,
        }

    def run(self, orders: Sequence[OrderAggregate]) -> RunResultSummary:
        if self.mode.mode_type == OptimizeModeType.BY_ROUTE:
            best_sequence, best_eval = self._optimize_by_route(orders)
        else:
            base_sequence = sorted(orders, key=self._order_workload_seconds, reverse=True)
            best_sequence, best_eval = self._local_search(base_sequence)
        return self._persist(best_sequence, best_eval)

    def _build_transfer_map(self) -> Dict[tuple[int, int], float]:
        mapping: Dict[tuple[int, int], float] = {}
        segments = TransferSegment.objects.filter(enabled=True)
        for item in segments:
            mapping[(item.from_station_id, item.to_station_id)] = float(item.fixed_transfer_seconds)
        return mapping

    def _build_efficiency_map(self) -> Dict[int, Dict[Decimal, tuple[int, float]]]:
        result: Dict[int, Dict[Decimal, tuple[int, float]]] = {}
        rows = StationDenominationEfficiency.objects.filter(enabled=True)
        for row in rows:
            result.setdefault(row.station_id, {})[Decimal(row.denomination)] = (
                int(row.max_units_per_action),
                float(row.unit_boxing_seconds),
            )
        return result

    def _load_weights(self) -> tuple[Dict[str, float], Dict[int, float]]:
        weights = {
            ParameterCategory.TOTAL_TIME_WEIGHT: 1.0,
            ParameterCategory.STATION_CONCENTRATION_WEIGHT: 0.2,
            ParameterCategory.ROUTE_CONTINUITY_WEIGHT: 0.2,
        }
        station_weights: Dict[int, float] = {}
        rows = OptimizeModeParameter.objects.filter(mode=self.mode, enabled=True)
        for row in rows:
            if row.category == ParameterCategory.STATION_CONCENTRATION_WEIGHT and row.station_id:
                station_weights[row.station_id] = float(row.value)
                continue
            weights[row.category] = float(row.value)
        return weights, station_weights

    @staticmethod
    def _load_float_config(key: str, default: float) -> float:
        row = GlobalConfig.objects.filter(config_key=key, enabled=True).first()
        if not row:
            return default
        try:
            return float(row.config_value)
        except (TypeError, ValueError):
            return default

    def _order_workload_seconds(self, order: OrderAggregate) -> float:
        return sum(self._station_process_seconds(order, station) for station in self.stations)

    def _station_process_seconds(self, order: OrderAggregate, station: PackingStation) -> float:
        duration = float(station.fixed_boxing_seconds)
        eff_map = self.efficiency_map.get(station.id, {})
        for denomination, units in order.quantities.items():
            if not units:
                continue

            max_units, unit_seconds = eff_map.get(
                denomination,
                (int(station.max_units_per_action), float(station.unit_boxing_seconds)),
            )
            batches = (units + max_units - 1) // max_units if max_units > 0 else units
            duration += float(batches) * unit_seconds

        return duration

    def _evaluate(self, sequence: Sequence[OrderAggregate]) -> dict:
        station_available = {station.id: 0.0 for station in self.stations}
        station_metrics = {station.id: StationMetrics() for station in self.stations}
        last_upbox_ready = 0.0
        order_timings = []

        for order in sequence:
            prev_finish = None
            prev_station_id = None
            order_start = None
            order_finish = 0.0

            for index, station in enumerate(self.stations):
                transfer = 0.0
                if prev_station_id is not None:
                    transfer = self.transfer_map.get((prev_station_id, station.id), 0.0)

                ready_by_flow = (prev_finish + transfer) if prev_finish is not None else max(0.0, last_upbox_ready)
                start = max(station_available[station.id], ready_by_flow)

                process = self._station_process_seconds(order, station)
                finish = start + process

                metrics = station_metrics[station.id]
                metrics.busy_seconds += process
                if metrics.first_start is None:
                    metrics.first_start = start
                metrics.last_finish = max(metrics.last_finish, finish)
                metrics.wait_seconds += max(0.0, start - ready_by_flow)

                station_available[station.id] = finish
                prev_finish = finish
                prev_station_id = station.id

                if index == 0:
                    order_start = start
                    last_upbox_ready = start + self.box_interval
                order_finish = finish

            order_timings.append((order, order_start or 0.0, order_finish))

        total_seconds = max(station_available.values(), default=0.0)
        concentration = self._station_concentration(station_metrics)
        route_switch_cost = self._route_switch_cost(sequence)

        normalized_total = total_seconds / max(self._normalize_factors['total_seconds'], 1e-6)
        normalized_concentration = concentration / max(self._normalize_factors['station_concentration'], 1e-6)
        normalized_route_cost = route_switch_cost / max(self._normalize_factors['route_continuity_cost'], 1e-6)

        score = (
            self.weights[ParameterCategory.TOTAL_TIME_WEIGHT] * normalized_total
            + self.weights[ParameterCategory.STATION_CONCENTRATION_WEIGHT] * normalized_concentration
            + self.weights[ParameterCategory.ROUTE_CONTINUITY_WEIGHT] * normalized_route_cost
        )

        return {
            'score': score,
            'total_seconds': total_seconds,
            'station_concentration': concentration,
            'route_continuity_cost': route_switch_cost,
            'station_metrics': station_metrics,
            'timings': order_timings,
        }

    def _station_concentration(self, station_metrics: Dict[int, StationMetrics]) -> float:
        if self.station_concentration_weights:
            score = 0.0
            for station in self.stations:
                weight = self.station_concentration_weights.get(station.id, 0.0)
                if weight <= 0:
                    continue
                span_seconds = station_metrics[station.id].span_seconds
                score += weight * span_seconds
            if score > 0:
                return score
        return max((m.span_seconds for m in station_metrics.values()), default=0.0)

    def _route_switch_cost(self, sequence: Sequence[OrderAggregate]) -> float:
        switches = 0.0
        prev_route_id = None
        for order in sequence:
            if prev_route_id is not None and prev_route_id != order.route_id:
                switches += self.route_switch_penalty
            prev_route_id = order.route_id
        return switches

    def _set_normalization_factors(self, reference_eval: dict) -> None:
        self._normalize_factors = {
            'total_seconds': max(reference_eval['total_seconds'], 1.0),
            'station_concentration': max(reference_eval['station_concentration'], 1.0),
            'route_continuity_cost': max(reference_eval['route_continuity_cost'], 1.0),
        }

    def _optimize_by_route(self, orders: Sequence[OrderAggregate]) -> tuple[List[OrderAggregate], dict]:
        route_groups: Dict[int, List[OrderAggregate]] = {}
        for order in orders:
            route_groups.setdefault(order.route_id, []).append(order)

        route_sequences: Dict[int, List[OrderAggregate]] = {}
        for route_id, group_orders in route_groups.items():
            base_sequence = sorted(group_orders, key=self._order_workload_seconds, reverse=True)
            seq, _ = self._local_search(base_sequence)
            route_sequences[route_id] = seq

        route_order = sorted(
            route_sequences.keys(),
            key=lambda rid: sum(self._order_workload_seconds(order) for order in route_sequences[rid]),
            reverse=True,
        )
        sequence = [order for route_id in route_order for order in route_sequences[route_id]]
        reference_eval = self._evaluate(sequence)
        self._set_normalization_factors(reference_eval)
        eval_result = self._evaluate(sequence)
        return sequence, eval_result

    @staticmethod
    def _build_initial_sequences(base_sequence: List[OrderAggregate], max_restarts: int) -> List[List[OrderAggregate]]:
        sequences: List[List[OrderAggregate]] = [list(base_sequence)]

        by_route = sorted(base_sequence, key=lambda o: (o.route_id, -len(o.quantities), o.order_no))
        sequences.append(by_route)

        rng = random.Random(20260413)
        while len(sequences) < max_restarts:
            trial = list(base_sequence)
            rng.shuffle(trial)
            sequences.append(trial)
        return sequences

    def _iter_neighbors(self, sequence: List[OrderAggregate]) -> List[List[OrderAggregate]]:
        n = len(sequence)
        if n <= 1:
            return []

        neighbors: List[List[OrderAggregate]] = []

        for i in range(n - 1):
            trial = list(sequence)
            trial[i], trial[i + 1] = trial[i + 1], trial[i]
            neighbors.append(trial)

        stride = max(1, n // 8)
        for i in range(0, n - 1, stride):
            j = min(n - 1, i + stride)
            if i == j:
                continue
            trial = list(sequence)
            trial[i], trial[j] = trial[j], trial[i]
            neighbors.append(trial)

        for i in range(0, n - 1, stride):
            j = min(n - 1, i + stride)
            if i == j:
                continue
            trial = list(sequence)
            moved = trial.pop(j)
            trial.insert(i, moved)
            neighbors.append(trial)

        return neighbors

    def _local_search(self, base_sequence: List[OrderAggregate]) -> tuple[List[OrderAggregate], dict]:
        reference_eval = self._evaluate(base_sequence)
        self._set_normalization_factors(reference_eval)

        global_best = list(base_sequence)
        global_best_eval = self._evaluate(global_best)

        restart_count = max(2, self.max_restarts)
        for start_sequence in self._build_initial_sequences(base_sequence, restart_count):
            current = list(start_sequence)
            current_eval = self._evaluate(current)

            for _ in range(self.max_iterations):
                improved = False
                for trial in self._iter_neighbors(current):
                    trial_eval = self._evaluate(trial)
                    if trial_eval['score'] < current_eval['score']:
                        current, current_eval = trial, trial_eval
                        improved = True
                if not improved:
                    break

            if current_eval['score'] < global_best_eval['score']:
                global_best, global_best_eval = current, current_eval

        return global_best, global_best_eval

    @transaction.atomic
    def _persist(self, sequence: Sequence[OrderAggregate], evaluation: dict) -> RunResultSummary:
        batch_no = f'BATCH-{timezone.now().strftime("%Y%m%d%H%M%S")}-{str(uuid4())[:8]}'
        summary = RunResultSummary.objects.create(
            batch_no=batch_no,
            optimize_mode=self.mode,
            total_seconds=Decimal(str(round(evaluation['total_seconds'], 2))),
            score=Decimal(str(round(evaluation['score'], 4))),
            is_best=True,
            remark='自动排序计算结果',
        )

        for station in self.stations:
            m = evaluation['station_metrics'][station.id]
            RunResultStationDetail.objects.create(
                batch=summary,
                station=station,
                station_span=Decimal(str(round(m.span_seconds, 2))),
                busy_seconds=Decimal(str(round(m.busy_seconds, 2))),
                idle_seconds=Decimal(str(round(m.idle_seconds, 2))),
                wait_seconds=Decimal(str(round(m.wait_seconds, 2))),
            )

        base_dt = timezone.now()
        for index, (order, start_seconds, finish_seconds) in enumerate(evaluation['timings'], start=1):
            SortedOrderResult.objects.create(
                batch=summary,
                seq_no=index,
                order=order.source_order,
                order_date=order.order_date,
                organization=order.organization,
                route=order.route,
                final_position=index,
                est_start_time=base_dt + timedelta(seconds=start_seconds),
                est_finish_time=base_dt + timedelta(seconds=finish_seconds),
                est_total_seconds=Decimal(str(round(finish_seconds - start_seconds, 2))),
                remark='自动排序结果',
            )

        return summary


def run_sorting_for_date(order_date, mode_no: str | None = None) -> RunResultSummary:
    if isinstance(order_date, str):
        order_date = datetime.strptime(order_date, '%Y-%m-%d').date()
    mode = None
    if mode_no:
        mode = OptimizeMode.objects.filter(mode_no=mode_no, enabled=True).first()
    if mode is None:
        default_mode_no = GlobalConfig.objects.filter(config_key='默认优化模式编号', enabled=True).values_list('config_value', flat=True).first()
        if default_mode_no:
            mode = OptimizeMode.objects.filter(mode_no=default_mode_no, enabled=True).first()
    if mode is None:
        mode = OptimizeMode.objects.filter(enabled=True).first()
    if mode is None:
        raise ValueError('未找到可用优化模式，请先配置 OptimizeMode。')

    order_rows = list(
        OrganizationOrder.objects.filter(order_date=order_date)
        .select_related('organization', 'route')
        .prefetch_related('split_details')
        .order_by('order_no', 'organization_id', 'route_id', 'denomination')
    )
    if not order_rows:
        raise ValueError(f'{order_date} 没有可排序订单。')
    grouped: Dict[tuple[str, object, int, int], OrderAggregate] = {}
    for row in order_rows:
        group_key = (row.order_no, row.order_date, row.organization_id, row.route_id)
        agg = grouped.get(group_key)
        if agg is None:
            agg = OrderAggregate(
                order_no=row.order_no,
                order_date=row.order_date,
                organization=row.organization,
                route=row.route,
                route_id=row.route_id,
                source_order=row,
                quantities={},
            )
            grouped[group_key] = agg
        pipeline_qty = sum(
            int(item.bundle_count)
            for item in row.split_details.all()
            if item.split_type == SplitType.PIPELINE_BOX
        )
        if pipeline_qty <= 0:
            continue
        agg.quantities[Decimal(str(row.denomination))] = agg.quantities.get(Decimal(str(row.denomination)), 0) + pipeline_qty
    orders = [item for item in grouped.values() if item.quantities]
    if not orders:
        raise ValueError(f'{order_date} 没有可进入流水线的订单明细。')

    engine = SortingEngine(mode)
    return engine.run(orders)
