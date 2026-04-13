from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from decimal import Decimal
import logging
import random
from typing import Dict, List, Sequence
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.masterdata.models import PackingStation, StationDenominationEfficiency, StationDenominationSupport, TransferSegment
from apps.optimizer.models import (
    GlobalConfig,
    OptimizeMode,
    OptimizeModeParameter,
    ParameterCategory,
)
from apps.orders.models import OrganizationOrder, SplitType
from apps.runs.models import SortedOrderResult


logger = logging.getLogger(__name__)


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
class PipelineBoxAggregate:
    order_no: str
    order_date: object
    organization: object
    organization_id: int
    route: object
    route_id: int
    source_orders: List[OrganizationOrder] = field(default_factory=list)
    source_seq_no: int = 0
    source_box_seq_no: int = 0
    denomination_bundles: Dict[Decimal, int] = field(default_factory=dict)
    denomination_items: Dict[tuple[str, Decimal], int] = field(default_factory=dict)

    @property
    def source_order(self) -> OrganizationOrder:
        return self.source_orders[0]

    @property
    def bundle_count(self) -> int:
        return int(sum(self.denomination_items.values()))

    @property
    def denominations(self) -> List[Decimal]:
        return sorted({denom for _, denom in self.denomination_items.keys()}, reverse=True)


class SortingEngine:
    """流水线排序计算引擎。"""

    CONFIG_KEYS = {
        'DEFAULT_MODE_NO': 'DEFAULT_OPTIMIZE_MODE_NO',
        'ROUTE_SWITCH_PENALTY': 'ROUTE_SWITCH_PENALTY',
        'BOX_INTERVAL': 'BOX_INTERVAL_SECONDS',
        'MAX_ITERATIONS': 'MAX_ITERATIONS',
        'MAX_RESTARTS': 'MAX_RESTARTS',
        'TRACE_ENABLED': 'SORT_TRACE_ENABLED',
        'SCHEDULE_START_TIME': 'SCHEDULE_START_TIME',
        'ADJ_COMPLEMENT_WEIGHT': 'ADJ_COMPLEMENT_WEIGHT',
        'T12_SMOOTH_WEIGHT': 'T12_SMOOTH_WEIGHT',
    }

    def __init__(self, mode: OptimizeMode):
        self.mode = mode
        self.stations = list(PackingStation.objects.filter(enabled=True).order_by('station_order'))
        self.transfer_map = self._build_transfer_map()
        self.efficiency_map = self._build_efficiency_map()
        self.support_map = self._build_support_map()
        self.weights = self._load_weights()
        self.box_interval = self._load_float_config(self.CONFIG_KEYS['BOX_INTERVAL'], default=2.0)
        self.max_iterations = max(2, int(self._load_float_config(self.CONFIG_KEYS['MAX_ITERATIONS'], default=100)))
        self.max_restarts = max(1, int(self._load_float_config(self.CONFIG_KEYS['MAX_RESTARTS'], default=5)))
        self.trace_enabled = bool(int(self._load_float_config(self.CONFIG_KEYS['TRACE_ENABLED'], default=0)))
        self.schedule_start_time = self._load_time_config(self.CONFIG_KEYS['SCHEDULE_START_TIME'], default=time(hour=8, minute=0))
        self.adj_complement_weight = self._load_float_config(self.CONFIG_KEYS['ADJ_COMPLEMENT_WEIGHT'], default=0.15)
        self.t12_smooth_weight = self._load_float_config(self.CONFIG_KEYS['T12_SMOOTH_WEIGHT'], default=0.05)
        self.eval_count = 0

    def run(self, boxes: Sequence[PipelineBoxAggregate]) -> dict:
        self.eval_count = 0
        self._trace(
            f'start mode={self.mode.mode_no}, boxes={len(boxes)}, '
            f'max_iterations={self.max_iterations}, max_restarts={self.max_restarts}, '
            f'box_interval={self.box_interval}'
        )
        base_sequence = sorted(boxes, key=self._box_workload_seconds, reverse=True)
        best_sequence, best_eval = self._local_search(base_sequence)
        best_sequence = self._enforce_organization_continuity(best_sequence)
        best_eval = self._evaluate(best_sequence)
        self._trace(
            f"finish mode={self.mode.mode_no}, best_score={best_eval['score']:.4f}, "
            f"total_seconds={best_eval['total_seconds']:.2f}, eval_count={self.eval_count}"
        )
        return self._persist(best_sequence, best_eval)

    def _build_transfer_map(self) -> Dict[tuple[int, int], float]:
        mapping: Dict[tuple[int, int], float] = {}
        segments = TransferSegment.objects.filter(enabled=True)
        for item in segments:
            mapping[(item.from_station_id, item.to_station_id)] = float(item.fixed_transfer_seconds)
        return mapping

    def _build_efficiency_map(self) -> Dict[int, Dict[tuple[str, Decimal], tuple[int, float]]]:
        result: Dict[int, Dict[tuple[str, Decimal], tuple[int, float]]] = {}
        rows = StationDenominationEfficiency.objects.filter(enabled=True)
        for row in rows:
            result.setdefault(row.station_id, {})[(row.currency_type, Decimal(row.denomination))] = (
                int(row.max_units_per_action),
                float(row.unit_boxing_seconds),
            )
        return result

    def _build_support_map(self) -> Dict[int, set[tuple[str, Decimal]]]:
        result: Dict[int, set[tuple[str, Decimal]]] = {}
        rows = StationDenominationSupport.objects.filter(enabled=True)
        for row in rows:
            result.setdefault(row.station_id, set()).add((row.currency_type, Decimal(row.denomination)))
        return result

    def _load_weights(self) -> Dict[str, float]:
        weights = {
            ParameterCategory.TOTAL_TIME_WEIGHT: 1.0,
            ParameterCategory.STATION_CONCENTRATION_WEIGHT: 0.2,
            ParameterCategory.ROUTE_CONTINUITY_WEIGHT: self._load_float_config(self.CONFIG_KEYS['ROUTE_SWITCH_PENALTY'], default=0.2),
        }
        self.station_focus_weights: Dict[int, float] = {}
        rows = OptimizeModeParameter.objects.filter(mode=self.mode, enabled=True)
        for row in rows:
            if row.category == ParameterCategory.STATION_CONCENTRATION_WEIGHT and row.station_id:
                self.station_focus_weights[row.station_id] = float(row.value)
                continue
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

    @staticmethod
    def _load_time_config(key: str, default: time) -> time:
        row = GlobalConfig.objects.filter(config_key=key, enabled=True).first()
        if not row:
            return default
        value = str(row.config_value or '').strip()
        for fmt in ('%H:%M:%S', '%H:%M'):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue
        return default

    def _box_workload_seconds(self, box: PipelineBoxAggregate) -> float:
        return sum(self._box_station_process_seconds(box, station) for station in self.stations)

    def _box_station_process_seconds(self, box: PipelineBoxAggregate, station: PackingStation) -> float:
        eff_map = self.efficiency_map.get(station.id, {})
        support_set = self.support_map.get(station.id, set())

        matched_items: list[tuple[str, Decimal, int]] = []
        for (currency_type, denom), qty in box.denomination_items.items():
            bundles = max(0, int(qty))
            if bundles <= 0:
                continue
            # 只对该工位真正支持的面额计时；若未维护支持表，则回退为按效率表或工位默认能力处理
            if support_set:
                if (currency_type, denom) not in support_set:
                    continue
            elif eff_map and (currency_type, denom) not in eff_map:
                continue
            matched_items.append((currency_type, denom, bundles))

        if not matched_items:
            return 0.0

        duration = float(station.fixed_boxing_seconds)
        for currency_type, denom, bundles in matched_items:
            max_units, unit_seconds = eff_map.get(
                (currency_type, denom),
                (int(station.max_units_per_action), float(station.unit_boxing_seconds)),
            )
            batches = (bundles + max_units - 1) // max_units if max_units > 0 else bundles
            duration += float(batches) * unit_seconds
        return duration

    def _evaluate(self, sequence: Sequence[PipelineBoxAggregate]) -> dict:
        self.eval_count += 1
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

                process = self._box_station_process_seconds(order, station)
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
        concentration = self._station_concentration_penalty(station_metrics)
        route_switch = self._route_switch_count(sequence)
        route_switch_penalty = self.weights[ParameterCategory.ROUTE_CONTINUITY_WEIGHT] * route_switch
        adjacent_complement_penalty = self._adjacent_complement_penalty(sequence)
        t12_smooth_penalty = self._adjacent_t12_smooth_penalty(sequence)

        score = (
            self.weights[ParameterCategory.TOTAL_TIME_WEIGHT] * total_seconds
            + concentration
            + route_switch_penalty
            + adjacent_complement_penalty
            + t12_smooth_penalty
        )

        return {
            'score': score,
            'total_seconds': total_seconds,
            'concentration_penalty': concentration,
            'route_switch_count': route_switch,
            'route_switch_penalty': route_switch_penalty,
            'adjacent_complement_penalty': adjacent_complement_penalty,
            't12_smooth_penalty': t12_smooth_penalty,
            'station_metrics': station_metrics,
            'timings': order_timings,
        }

    def _station_concentration_penalty(self, station_metrics: Dict[int, StationMetrics]) -> float:
        if self.station_focus_weights:
            penalty = 0.0
            for station_id, weight in self.station_focus_weights.items():
                penalty += weight * station_metrics.get(station_id, StationMetrics()).span_seconds
            return penalty
        concentration = max((m.span_seconds for m in station_metrics.values()), default=0.0)
        return self.weights[ParameterCategory.STATION_CONCENTRATION_WEIGHT] * concentration


    def _front_two_station_times(self, box: PipelineBoxAggregate) -> tuple[float, float]:
        if not self.stations:
            return 0.0, 0.0
        t1 = self._box_station_process_seconds(box, self.stations[0])
        t2 = self._box_station_process_seconds(box, self.stations[1]) if len(self.stations) > 1 else 0.0
        return t1, t2

    def _adjacent_complement_penalty(self, sequence: Sequence[PipelineBoxAggregate]) -> float:
        if len(sequence) < 2 or self.adj_complement_weight <= 0:
            return 0.0
        penalty = 0.0
        for left, right in zip(sequence, sequence[1:]):
            left_t1, left_t2 = self._front_two_station_times(left)
            right_t1, right_t2 = self._front_two_station_times(right)
            left_balance = left_t1 - left_t2
            right_balance = right_t1 - right_t2
            # 越接近相反数越互补；若同号且都偏向同一工位，额外惩罚。
            pair_penalty = abs(left_balance + right_balance)
            if left_balance * right_balance > 0:
                pair_penalty += min(abs(left_balance), abs(right_balance))
            penalty += pair_penalty
        return self.adj_complement_weight * penalty

    def _adjacent_t12_smooth_penalty(self, sequence: Sequence[PipelineBoxAggregate]) -> float:
        if len(sequence) < 2 or self.t12_smooth_weight <= 0:
            return 0.0
        penalty = 0.0
        prev_t12 = None
        for box in sequence:
            t1, t2 = self._front_two_station_times(box)
            t12 = t1 + t2
            if prev_t12 is not None:
                penalty += abs(prev_t12 - t12)
            prev_t12 = t12
        return self.t12_smooth_weight * penalty

    @staticmethod
    def _route_switch_count(sequence: Sequence[PipelineBoxAggregate]) -> int:
        switches = 0
        prev = None
        for order in sequence:
            if prev is not None and prev != order.route_id:
                switches += 1
            prev = order.route_id
        return switches

    def _local_search(self, base_sequence: List[PipelineBoxAggregate]) -> tuple[List[PipelineBoxAggregate], dict]:
        best, best_eval = self._hill_climb(list(base_sequence))
        self._trace(f"base hill-climb score={best_eval['score']:.4f}")
        rng = random.Random(42)
        restarts = max(0, self.max_restarts)
        for idx in range(restarts):
            seed_sequence = list(base_sequence)
            rng.shuffle(seed_sequence)
            trial_best, trial_eval = self._hill_climb(seed_sequence)
            self._trace(f"restart={idx + 1}/{restarts}, trial_score={trial_eval['score']:.4f}")
            if self._is_better_eval(trial_eval, best_eval):
                best, best_eval = trial_best, trial_eval
                self._trace(f"new best from restart={idx + 1}, score={best_eval['score']:.4f}")
        return best, best_eval

    def _hill_climb(self, sequence: List[PipelineBoxAggregate]) -> tuple[List[PipelineBoxAggregate], dict]:
        best = list(sequence)
        best_eval = self._evaluate(best)
        for _ in range(self.max_iterations):
            improved = False
            for i in range(len(best) - 1):
                trial = list(best)
                trial[i], trial[i + 1] = trial[i + 1], trial[i]
                trial_eval = self._evaluate(trial)
                if self._is_better_eval(trial_eval, best_eval):
                    best, best_eval = trial, trial_eval
                    improved = True
                    self._trace(f"iteration improvement at index={i}, score={best_eval['score']:.4f}")
                if i + 2 < len(best):
                    inserted = list(best)
                    moved = inserted.pop(i)
                    inserted.insert(i + 2, moved)
                    inserted_eval = self._evaluate(inserted)
                    if self._is_better_eval(inserted_eval, best_eval):
                        best, best_eval = inserted, inserted_eval
                        improved = True
                        self._trace(f"iteration insertion improvement from index={i}, score={best_eval['score']:.4f}")
            if not improved:
                break
        return best, best_eval

    def _is_better_eval(self, left: dict, right: dict) -> bool:
        if left['score'] < right['score'] - 1e-9:
            return True
        if abs(left['score'] - right['score']) > 1e-9:
            return False
        left_tuple = (
            left.get('concentration_penalty', 0.0),
            left.get('adjacent_complement_penalty', 0.0),
            left.get('t12_smooth_penalty', 0.0),
            left.get('route_switch_count', 0),
            left.get('total_seconds', 0.0),
        )
        right_tuple = (
            right.get('concentration_penalty', 0.0),
            right.get('adjacent_complement_penalty', 0.0),
            right.get('t12_smooth_penalty', 0.0),
            right.get('route_switch_count', 0),
            right.get('total_seconds', 0.0),
        )
        return left_tuple < right_tuple

    def _trace(self, message: str):
        if self.trace_enabled:
            logger.info('SortingEngine %s', message)

    @staticmethod
    def _enforce_organization_continuity(sequence: Sequence[PipelineBoxAggregate]) -> List[PipelineBoxAggregate]:
        grouped: dict[int, list[PipelineBoxAggregate]] = {}
        org_order: list[int] = []
        for item in sequence:
            if item.organization_id not in grouped:
                grouped[item.organization_id] = []
                org_order.append(item.organization_id)
            grouped[item.organization_id].append(item)
        compacted: list[PipelineBoxAggregate] = []
        for org_id in org_order:
            compacted.extend(grouped[org_id])
        return compacted

    @transaction.atomic
    def _persist(self, sequence: Sequence[PipelineBoxAggregate], evaluation: dict) -> dict:
        batch_no = f'BATCH-{timezone.now().strftime("%Y%m%d%H%M%S")}-{str(uuid4())[:8]}'
        run_at = timezone.now()
        total_seconds = Decimal(str(round(evaluation['total_seconds'], 2)))
        score = Decimal(str(round(evaluation['score'], 4)))
        remark = (
            '自动排序计算结果; '
            f'eval_count={self.eval_count}; max_iterations={self.max_iterations}; max_restarts={self.max_restarts}; '
            f'total_w={self.weights.get(ParameterCategory.TOTAL_TIME_WEIGHT, 0)}; '
            f'route_w={self.weights.get(ParameterCategory.ROUTE_CONTINUITY_WEIGHT, 0)}; '
            f'adj_w={self.adj_complement_weight}; '
            f't12_w={self.t12_smooth_weight}; '
            f'station_focus={len(self.station_focus_weights)}'
        )[:255]

        base_dt = self._resolve_schedule_base_datetime(sequence) or run_at
        for index, (order, start_seconds, finish_seconds) in enumerate(evaluation['timings'], start=1):
            start_seconds = round(start_seconds, 2)
            finish_seconds = round(finish_seconds, 2)
            denom_desc = ', '.join(
                f'{currency_type}:{format(denom, "f")}x{qty}'
                for (currency_type, denom), qty in sorted(order.denomination_items.items(), key=lambda item: (item[0][0], item[0][1]), reverse=True)
            )
            SortedOrderResult.objects.create(
                batch_no=batch_no,
                optimize_mode=self.mode,
                seq_no=index,
                order=order.source_order,
                order_date=order.order_date,
                organization=order.organization,
                route=order.route,
                final_position=index,
                est_start_time=base_dt + timedelta(seconds=start_seconds),
                est_finish_time=base_dt + timedelta(seconds=finish_seconds),
                est_total_seconds=Decimal(str(finish_seconds)),
                remark=(f'{remark}; 按逻辑箱聚合排序-原箱序号:{order.source_box_seq_no}; 面额明细:{denom_desc}')[:255],
            )

        return {
            'batch_no': batch_no,
            'run_at': run_at,
            'total_seconds': total_seconds,
            'score': score,
        }

    def _resolve_schedule_base_datetime(self, sequence: Sequence[PipelineBoxAggregate]):
        if not sequence:
            return None
        order_date = sequence[0].order_date
        base_naive = datetime.combine(order_date, self.schedule_start_time)
        tz = timezone.get_current_timezone()
        return timezone.make_aware(base_naive, tz)


def run_sorting_for_date(order_date, mode_no: str | None = None) -> dict:
    if isinstance(order_date, str):
        order_date = datetime.strptime(order_date, '%Y-%m-%d').date()
    mode = None
    if mode_no:
        mode = OptimizeMode.objects.filter(mode_no=mode_no, enabled=True).first()
    if mode is None:
        default_mode_no = GlobalConfig.objects.filter(
            config_key=SortingEngine.CONFIG_KEYS['DEFAULT_MODE_NO'],
            enabled=True,
        ).values_list('config_value', flat=True).first()
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
    aggregated_boxes: dict[tuple[str, object, int, int, int], PipelineBoxAggregate] = {}
    for row in order_rows:
        pipeline_boxes = sorted(
            [
                detail
                for detail in row.split_details.all()
                if detail.split_type == SplitType.PIPELINE_BOX and int(detail.bundle_count) > 0
            ],
            key=lambda item: item.seq_no,
        )
        for box in pipeline_boxes:
            box_key = (row.order_no, row.order_date, row.organization_id, row.route_id, int(box.seq_no))
            aggregate = aggregated_boxes.get(box_key)
            if aggregate is None:
                aggregate = PipelineBoxAggregate(
                    order_no=row.order_no,
                    order_date=row.order_date,
                    organization=row.organization,
                    organization_id=row.organization_id,
                    route=row.route,
                    route_id=row.route_id,
                    source_orders=[],
                    source_seq_no=len(aggregated_boxes) + 1,
                    source_box_seq_no=int(box.seq_no),
                    denomination_bundles={},
                    denomination_items={},
                )
                aggregated_boxes[box_key] = aggregate
            aggregate.source_orders.append(row)
            denom = Decimal(str(row.denomination))
            aggregate.denomination_bundles[denom] = aggregate.denomination_bundles.get(denom, 0) + int(box.bundle_count)
            item_key = (row.currency_type, denom)
            aggregate.denomination_items[item_key] = aggregate.denomination_items.get(item_key, 0) + int(box.bundle_count)

    boxes = sorted(
        aggregated_boxes.values(),
        key=lambda item: (item.order_no, item.organization_id, item.route_id, item.source_box_seq_no),
    )
    if not boxes:
        raise ValueError(f'{order_date} 没有可进入流水线的订单明细。')

    engine = SortingEngine(mode)
    return engine.run(boxes)
