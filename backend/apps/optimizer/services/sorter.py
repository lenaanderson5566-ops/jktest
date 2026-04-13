from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import random
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
from apps.orders.models import OrganizationOrder, SplitType
from apps.runs.models import RunResultSummary, SortedOrderResult


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
    source_order: OrganizationOrder
    source_seq_no: int
    source_box_seq_no: int
    denomination: Decimal
    bundle_count: int


class SortingEngine:
    """流水线排序计算引擎。"""

    CONFIG_KEYS = {
        'DEFAULT_MODE_NO': 'DEFAULT_OPTIMIZE_MODE_NO',
        'ROUTE_SWITCH_PENALTY': 'ROUTE_SWITCH_PENALTY',
        'BOX_INTERVAL': 'BOX_INTERVAL_SECONDS',
        'MAX_ITERATIONS': 'MAX_ITERATIONS',
        'MAX_RESTARTS': 'MAX_RESTARTS',
        'TRACE_ENABLED': 'SORT_TRACE_ENABLED',
    }

    def __init__(self, mode: OptimizeMode):
        self.mode = mode
        self.stations = list(PackingStation.objects.filter(enabled=True).order_by('station_order'))
        self.transfer_map = self._build_transfer_map()
        self.efficiency_map = self._build_efficiency_map()
        self.weights = self._load_weights()
        self.box_interval = self._load_float_config(self.CONFIG_KEYS['BOX_INTERVAL'], default=2.0)
        self.max_iterations = max(2, int(self._load_float_config(self.CONFIG_KEYS['MAX_ITERATIONS'], default=100)))
        self.max_restarts = max(1, int(self._load_float_config(self.CONFIG_KEYS['MAX_RESTARTS'], default=5)))
        self.trace_enabled = bool(int(self._load_float_config(self.CONFIG_KEYS['TRACE_ENABLED'], default=0)))
        self.eval_count = 0

    def run(self, boxes: Sequence[PipelineBoxAggregate]) -> RunResultSummary:
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

    def _box_workload_seconds(self, box: PipelineBoxAggregate) -> float:
        return sum(self._box_station_process_seconds(box, station) for station in self.stations)

    def _box_station_process_seconds(self, box: PipelineBoxAggregate, station: PackingStation) -> float:
        duration = float(station.fixed_boxing_seconds)
        eff_map = self.efficiency_map.get(station.id, {})
        max_units, unit_seconds = eff_map.get(
            box.denomination,
            (int(station.max_units_per_action), float(station.unit_boxing_seconds)),
        )
        bundles = max(0, int(box.bundle_count))
        if bundles <= 0:
            return duration
        batches = (bundles + max_units - 1) // max_units if max_units > 0 else bundles
        return duration + float(batches) * unit_seconds

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

        score = (
            self.weights[ParameterCategory.TOTAL_TIME_WEIGHT] * total_seconds
            + concentration
            + self.weights[ParameterCategory.ROUTE_CONTINUITY_WEIGHT] * route_switch
        )

        return {
            'score': score,
            'total_seconds': total_seconds,
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
            if trial_eval['score'] < best_eval['score']:
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
                if trial_eval['score'] < best_eval['score']:
                    best, best_eval = trial, trial_eval
                    improved = True
                    self._trace(f"iteration improvement at index={i}, score={best_eval['score']:.4f}")
            if not improved:
                break
        return best, best_eval

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
    def _persist(self, sequence: Sequence[PipelineBoxAggregate], evaluation: dict) -> RunResultSummary:
        batch_no = f'BATCH-{timezone.now().strftime("%Y%m%d%H%M%S")}-{str(uuid4())[:8]}'
        summary = RunResultSummary.objects.create(
            batch_no=batch_no,
            optimize_mode=self.mode,
            total_seconds=Decimal(str(round(evaluation['total_seconds'], 2))),
            score=Decimal(str(round(evaluation['score'], 4))),
            is_best=True,
            remark=(
                '自动排序计算结果; '
                f'eval_count={self.eval_count}; max_iterations={self.max_iterations}; max_restarts={self.max_restarts}; '
                f'total_w={self.weights.get(ParameterCategory.TOTAL_TIME_WEIGHT, 0)}; '
                f'route_w={self.weights.get(ParameterCategory.ROUTE_CONTINUITY_WEIGHT, 0)}; '
                f'station_focus={len(self.station_focus_weights)}'
            )[:255],
        )

        base_dt = timezone.now()
        for index, (order, start_seconds, finish_seconds) in enumerate(evaluation['timings'], start=1):
            SortedOrderResult.objects.create(
                batch=summary,
                seq_no=order.source_seq_no,
                order=order.source_order,
                order_date=order.order_date,
                organization=order.organization,
                route=order.route,
                final_position=index,
                est_start_time=base_dt + timedelta(seconds=start_seconds),
                est_finish_time=base_dt + timedelta(seconds=finish_seconds),
                est_total_seconds=Decimal(str(round(finish_seconds - start_seconds, 2))),
                remark=f'按箱排序-原箱序号:{order.source_box_seq_no}',
            )

        return summary


def run_sorting_for_date(order_date, mode_no: str | None = None) -> RunResultSummary:
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
    boxes: list[PipelineBoxAggregate] = []
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
            boxes.append(
                PipelineBoxAggregate(
                    order_no=row.order_no,
                    order_date=row.order_date,
                    organization=row.organization,
                    organization_id=row.organization_id,
                    route=row.route,
                    route_id=row.route_id,
                    source_order=row,
                    source_seq_no=len(boxes) + 1,
                    source_box_seq_no=box.seq_no,
                    denomination=Decimal(str(row.denomination)),
                    bundle_count=int(box.bundle_count),
                )
            )
    if not boxes:
        raise ValueError(f'{order_date} 没有可进入流水线的订单明细。')

    engine = SortingEngine(mode)
    return engine.run(boxes)
