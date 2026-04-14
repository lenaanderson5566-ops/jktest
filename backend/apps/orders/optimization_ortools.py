from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from itertools import groupby

from apps.masterdata.models import (
    GlobalConfig,
    PackingStation,
    StationDenominationEfficiency,
    StationDenominationSupport,
    TransferSegment,
)
from apps.orders.models import PipelineBoxTask


@dataclass
class OrToolsBoxItem:
    box_key: tuple
    order_no: str
    organization_id: int
    organization_name: str
    route_id: int
    route_no: str
    seq_no: int
    total_bundles: int
    denoms: dict[str, int]


@dataclass
class OrToolsStrategyResult:
    key: str
    name: str
    metrics: dict


def build_strategy_comparison_ortools(include_details: bool = False) -> dict:
    boxes = _load_boxes()
    if not boxes:
        return {
            'results': [],
            'has_data': False,
            'summary': {'total_organizations': 0, 'total_boxes': 0, 'denomination_bundles': []},
        }

    denomination_totals: dict[str, int] = defaultdict(int)
    for box in boxes:
        for denom, qty in box.denoms.items():
            denomination_totals[denom] += qty
    summary = {
        'total_organizations': len({box.organization_id for box in boxes}),
        'total_boxes': len(boxes),
        'denomination_bundles': [
            {'denomination': denom, 'bundle_count': total}
            for denom, total in sorted(denomination_totals.items(), key=lambda x: Decimal(x[0]))
        ],
    }

    stations = list(PackingStation.objects.filter(enabled=True).order_by('station_order'))
    if not stations:
        return {'results': [], 'has_data': True, 'summary': summary}

    transfer_map = {
        (seg.from_station_id, seg.to_station_id): float(seg.fixed_transfer_seconds)
        for seg in TransferSegment.objects.filter(enabled=True)
    }
    support_map: dict[str, list[int]] = defaultdict(list)
    for row in StationDenominationSupport.objects.filter(enabled=True):
        support_map[str(row.denomination)].append(row.station_id)
    eff_map: dict[tuple[int, str], float] = {}
    for row in StationDenominationEfficiency.objects.filter(enabled=True):
        eff_map[(row.station_id, str(row.denomination))] = float(row.unit_boxing_seconds)

    sequenced, solver_info = _sequence_by_ortools(boxes)
    metrics = _simulate(
        sequenced, stations, transfer_map, support_map, eff_map, collect_details=include_details
    )
    metrics['sequence_preview'] = [f"{b.organization_name}-{b.seq_no}" for b in sequenced[:8]]
    metrics.update(solver_info)

    return {
        'has_data': True,
        'results': [OrToolsStrategyResult(key='ortools_opt', name='ORTools 独立优化方案', metrics=metrics)],
        'summary': summary,
    }


def _load_boxes() -> list[OrToolsBoxItem]:
    tasks = (
        PipelineBoxTask.objects.select_related('order', 'order__organization', 'order__route')
        .order_by('order__organization_id', 'order__route_id', 'seq_no', 'id')
    )
    grouped: dict[tuple, dict] = {}
    for task in tasks:
        key = (task.order.order_no, task.order.organization_id, task.order.route_id, task.seq_no)
        if key not in grouped:
            grouped[key] = {
                'order_no': task.order.order_no,
                'organization_id': task.order.organization_id,
                'organization_name': task.order.organization.org_name,
                'route_id': task.order.route_id,
                'route_no': task.order.route.route_no,
                'seq_no': task.seq_no,
                'total_bundles': 0,
                'denoms': defaultdict(int),
            }
        row = grouped[key]
        denom = str(task.order.denomination)
        row['denoms'][denom] += int(task.bundle_count)
        row['total_bundles'] += int(task.bundle_count)

    return [
        OrToolsBoxItem(
            box_key=key,
            order_no=value['order_no'],
            organization_id=value['organization_id'],
            organization_name=value['organization_name'],
            route_id=value['route_id'],
            route_no=value['route_no'],
            seq_no=value['seq_no'],
            total_bundles=value['total_bundles'],
            denoms=dict(value['denoms']),
        )
        for key, value in grouped.items()
    ]


def _split_org_blocks(boxes: list[OrToolsBoxItem]) -> list[list[OrToolsBoxItem]]:
    ordered = sorted(boxes, key=lambda b: (b.organization_id, b.seq_no, b.box_key))
    return [list(group) for _, group in groupby(ordered, key=lambda b: b.organization_id)]


def _sequence_by_ortools(boxes: list[OrToolsBoxItem]) -> tuple[list[OrToolsBoxItem], dict]:
    blocks = _split_org_blocks(boxes)
    if len(blocks) <= 1:
        return [x for block in blocks for x in block], {'solver_status': 'trivial', 'solver_backend': 'none'}

    try:
        from ortools.sat.python import cp_model
    except Exception:
        fallback = sorted(blocks, key=lambda b: sum(x.total_bundles for x in b), reverse=True)
        return [x for block in fallback for x in block], {'solver_status': 'fallback_no_ortools', 'solver_backend': 'none'}

    max_blocks = int(_config_value('ORTOOLS_MAX_BLOCKS', 40))
    if len(blocks) > max_blocks:
        fallback = sorted(blocks, key=lambda b: (b[0].route_no, -sum(x.total_bundles for x in b)))
        return [x for block in fallback for x in block], {'solver_status': 'fallback_large_instance', 'solver_backend': 'heuristic'}

    model = cp_model.CpModel()
    n = len(blocks)
    x = {(b, p): model.NewBoolVar(f'x_{b}_{p}') for b in range(n) for p in range(n)}
    for b in range(n):
        model.Add(sum(x[(b, p)] for p in range(n)) == 1)
    for p in range(n):
        model.Add(sum(x[(b, p)] for b in range(n)) == 1)

    routes = sorted({block[0].route_no for block in blocks})
    route_rank = {route: i for i, route in enumerate(routes)}
    block_work = [sum(item.total_bundles for item in block) for block in blocks]
    obj_terms = []
    for b in range(n):
        # 主目标：按线路聚集（同线路块尽量连续区间），并让大工作量靠前。
        route_weight = route_rank[blocks[b][0].route_no] * (n + 1)
        work_weight = max(block_work) - block_work[b]
        for p in range(n):
            obj_terms.append((route_weight * p + work_weight * (p + 1)) * x[(b, p)])
    model.Minimize(sum(obj_terms))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(_config_value('ORTOOLS_MAX_TIME_SECONDS', 1.2))
    solver.parameters.num_search_workers = int(_config_value('ORTOOLS_NUM_WORKERS', 2))
    solver.parameters.random_seed = int(_config_value('ORTOOLS_RANDOM_SEED', 42))
    solver.parameters.cp_model_presolve = True
    solver.parameters.linearization_level = 0
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        fallback = sorted(blocks, key=lambda b: (b[0].route_no, -sum(x.total_bundles for x in b)))
        return [x for block in fallback for x in block], {'solver_status': 'fallback_no_solution', 'solver_backend': 'heuristic'}

    ordered: list[tuple[int, int]] = []
    for p in range(n):
        for b in range(n):
            if solver.Value(x[(b, p)]) == 1:
                ordered.append((p, b))
                break
    ordered.sort(key=lambda t: t[0])
    sequence_blocks = [blocks[b] for _, b in ordered]
    sequence = [item for block in sequence_blocks for item in block]
    status_map = {
        cp_model.OPTIMAL: 'optimal',
        cp_model.FEASIBLE: 'feasible',
        cp_model.INFEASIBLE: 'infeasible',
        cp_model.MODEL_INVALID: 'invalid',
        cp_model.UNKNOWN: 'unknown',
    }
    return sequence, {'solver_status': status_map.get(status, 'unknown'), 'solver_backend': 'ortools_cp_sat'}


def _config_value(key: str, default):
    row = GlobalConfig.objects.filter(config_key=key, enabled=True).first()
    if not row or row.config_value is None:
        return default
    try:
        return type(default)(row.config_value)
    except (TypeError, ValueError):
        return default


def _simulate(
    boxes: list[OrToolsBoxItem],
    stations: list[PackingStation],
    transfer_map: dict[tuple[int, int], float],
    support_map: dict[str, list[int]],
    eff_map: dict[tuple[int, str], float],
    collect_details: bool = False,
) -> dict:
    station_available = {s.id: 0.0 for s in stations}
    station_busy = {s.id: 0.0 for s in stations}
    station_wait = {s.id: 0.0 for s in stations}
    station_first_start = {s.id: None for s in stations}
    station_last_end = {s.id: 0.0 for s in stations}
    station_alloc_qty = {s.id: 0 for s in stations}

    route_switches = 0
    prev_route = None
    last_box_finish = 0.0
    box_details: list[dict] = []

    for box_idx, box in enumerate(boxes):
        if prev_route and prev_route != box.route_no:
            route_switches += 1
        prev_route = box.route_no

        release_time = box_idx * 5.0
        prev_finish = release_time
        prev_station_id = None
        allocation = _allocate_for_box(box, stations, support_map)
        box_station_steps: list[dict] = []

        for station in stations:
            station_id = station.id
            quantities = allocation.get(station_id, {})
            if not quantities:
                continue
            transfer_time = transfer_map.get((prev_station_id, station_id), 0.0) if prev_station_id else 0.0
            start_time = max(station_available[station_id], prev_finish + transfer_time, release_time)
            proc_time = float(station.fixed_boxing_seconds)
            for denom, qty in quantities.items():
                proc_time += eff_map.get((station_id, denom), float(station.unit_boxing_seconds)) * qty
                station_alloc_qty[station_id] += qty
            end_time = start_time + proc_time

            if station_first_start[station_id] is None:
                station_first_start[station_id] = start_time
            elif start_time > station_last_end[station_id]:
                station_wait[station_id] += start_time - station_last_end[station_id]

            station_available[station_id] = end_time
            station_last_end[station_id] = end_time
            station_busy[station_id] += proc_time

            box_station_steps.append({
                'station_name': station.station_name,
                'start': round(start_time, 2),
                'end': round(end_time, 2),
                'process_seconds': round(proc_time, 2),
                'allocations': {denom: int(qty) for denom, qty in quantities.items()},
            })
            prev_finish = end_time
            prev_station_id = station_id

        if collect_details:
            box_details.append({
                'box_index': box_idx + 1,
                'order_no': box.order_no,
                'organization_name': box.organization_name,
                'route_no': box.route_no,
                'box_seq_no': box.seq_no,
                'release_time': round(release_time, 2),
                'finish_time': round(prev_finish, 2),
                'total_bundles': box.total_bundles,
                'denoms': dict(box.denoms),
                'station_steps': box_station_steps,
            })
        last_box_finish = max(last_box_finish, prev_finish)

    spans = {
        s.station_name: round((station_last_end[s.id] - station_first_start[s.id]), 2)
        for s in stations if station_first_start[s.id] is not None
    }
    continuity = round(1 - (route_switches / max(1, len(boxes) - 1)), 4)
    route_cluster_score = round((len(boxes) - route_switches) / max(1, len(boxes)), 4)
    return {
        'total_finish_seconds': round(last_box_finish, 2),
        'station_busy_seconds': {s.station_name: round(station_busy[s.id], 2) for s in stations},
        'station_wait_seconds': {s.station_name: round(station_wait[s.id], 2) for s in stations},
        'station_span_seconds': spans,
        'station_allocated_qty': {s.station_name: int(station_alloc_qty[s.id]) for s in stations},
        'line_continuity': continuity,
        'route_cluster_score': route_cluster_score,
        'route_switches': route_switches,
        'box_details': box_details if collect_details else [],
    }


def _allocate_for_box(
    box: OrToolsBoxItem,
    stations: list[PackingStation],
    support_map: dict[str, list[int]],
) -> dict[int, dict[str, int]]:
    station_ids = [s.id for s in stations]
    allocation: dict[int, dict[str, int]] = defaultdict(dict)
    for denom, qty in box.denoms.items():
        candidates = [sid for sid in support_map.get(denom, []) if sid in station_ids]
        target = candidates[0] if candidates else station_ids[0]
        allocation[target][denom] = allocation[target].get(denom, 0) + qty
    return allocation
