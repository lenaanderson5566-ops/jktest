from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Sequence
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.masterdata.models import PackingStation, StationDenominationEfficiency, TransferSegment
from apps.optimizer.models import (
    GlobalConfig,
    OptimizeMode,
    OptimizeModeParameter,
    ParameterCategory,
)
from apps.orders.models import OrganizationOrder
from apps.runs.models import RunResultStationDetail, RunResultSummary, SortedOrderResult


DENOMINATION_FIELDS = {
    Decimal('100'): 'qty_100',
    Decimal('50'): 'qty_50',
    Decimal('20'): 'qty_20',
    Decimal('10'): 'qty_10',
    Decimal('5'): 'qty_5',
    Decimal('1'): 'qty_coin_1',
    Decimal('0.5'): 'qty_coin_05',
    Decimal('0.1'): 'qty_coin_01',
    Decimal('0.01'): 'qty_coin_001',
}


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


class SortingEngine:
    """流水线排序计算引擎。"""

    def __init__(self, mode: OptimizeMode):
        self.mode = mode
        self.stations = list(PackingStation.objects.filter(enabled=True).order_by('station_order'))
        self.transfer_map = self._build_transfer_map()
        self.efficiency_map = self._build_efficiency_map()
        self.weights = self._load_weights()
        self.box_interval = self._load_float_config('固定上箱间隔', 2.0)
        self.max_iterations = int(self._load_float_config('最大迭代次数', 100))

    def run(self, orders: Sequence[OrganizationOrder]) -> RunResultSummary:
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

    def _load_weights(self) -> Dict[str, float]:
        weights = {
            ParameterCategory.TOTAL_TIME_WEIGHT: 1.0,
            ParameterCategory.STATION_SPAN_WEIGHT: 0.1,
            ParameterCategory.MANUAL_STATION_DURATION_WEIGHT: 0.2,
            ParameterCategory.STATION_CONCENTRATION_WEIGHT: 0.2,
            ParameterCategory.ROUTE_CONTINUITY_WEIGHT: 0.2,
        }
        rows = OptimizeModeParameter.objects.filter(mode=self.mode, enabled=True)
        for row in rows:
            weights[row.category] = float(row.value)
        return weights

    @staticmethod
    def _load_float_config(key: str, default: float) -> float:
        row = GlobalConfig.objects.filter(config_key=key, enabled=True).first()
        if not row:
            return default
        try:
            return float(row.config_value)
        except (TypeError, ValueError):
            return default

    def _order_workload_seconds(self, order: OrganizationOrder) -> float:
        return sum(self._station_process_seconds(order, station) for station in self.stations)

    def _station_process_seconds(self, order: OrganizationOrder, station: PackingStation) -> float:
        duration = float(station.fixed_boxing_seconds)
        eff_map = self.efficiency_map.get(station.id, {})

        for denomination, field_name in DENOMINATION_FIELDS.items():
            units = getattr(order, field_name, 0)
            if not units:
                continue

            max_units, unit_seconds = eff_map.get(
                denomination,
                (int(station.max_units_per_action), float(station.unit_boxing_seconds)),
            )
            batches = (units + max_units - 1) // max_units if max_units > 0 else units
            duration += float(batches) * unit_seconds

        return duration

    def _evaluate(self, sequence: Sequence[OrganizationOrder]) -> dict:
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
        station_spans = sum(m.span_seconds for m in station_metrics.values())
        manual_busy = sum(
            station_metrics[s.id].busy_seconds
            for s in self.stations
            if s.station_type == 'MANUAL'
        )
        concentration = max((m.busy_seconds for m in station_metrics.values()), default=0.0)
        route_switch = self._route_switch_count(sequence)

        score = (
            self.weights[ParameterCategory.TOTAL_TIME_WEIGHT] * total_seconds
            + self.weights[ParameterCategory.STATION_SPAN_WEIGHT] * station_spans
            + self.weights[ParameterCategory.MANUAL_STATION_DURATION_WEIGHT] * manual_busy
            + self.weights[ParameterCategory.STATION_CONCENTRATION_WEIGHT] * concentration
            + self.weights[ParameterCategory.ROUTE_CONTINUITY_WEIGHT] * route_switch
        )

        return {
            'score': score,
            'total_seconds': total_seconds,
            'station_metrics': station_metrics,
            'timings': order_timings,
        }

    @staticmethod
    def _route_switch_count(sequence: Sequence[OrganizationOrder]) -> int:
        switches = 0
        prev = None
        for order in sequence:
            if prev is not None and prev != order.route_id:
                switches += 1
            prev = order.route_id
        return switches

    def _local_search(self, base_sequence: List[OrganizationOrder]) -> tuple[List[OrganizationOrder], dict]:
        best = list(base_sequence)
        best_eval = self._evaluate(best)

        for _ in range(self.max_iterations):
            improved = False
            for i in range(len(best) - 1):
                trial = list(best)
                trial[i], trial[i + 1] = trial[i + 1], trial[i]
                trial_eval = self._evaluate(trial)
                if trial_eval['score'] < best_eval['score']:
                    best, best_eval = trial, trial_eval
                    improved = True
            if not improved:
                break

        return best, best_eval

    @transaction.atomic
    def _persist(self, sequence: Sequence[OrganizationOrder], evaluation: dict) -> RunResultSummary:
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
                order=order,
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

    orders = list(
        OrganizationOrder.objects.filter(order_date=order_date).select_related('organization', 'route').order_by('order_no')
    )
    if not orders:
        raise ValueError(f'{order_date} 没有可排序订单。')

    engine = SortingEngine(mode)
    return engine.run(orders)
