from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import groupby
from typing import Callable

from apps.masterdata.models import (
    GlobalConfig,
    PackingStation,
    StationDenominationEfficiency,
    StationDenominationSupport,
    TransferSegment,
)
from apps.orders.models import PipelineBoxTask


@dataclass
class BoxItem:
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
class StrategyResult:
    key: str
    name: str
    metrics: dict


def build_strategy_comparison() -> dict:
    boxes = _load_boxes()
    if not boxes:
        return {'results': [], 'has_data': False}

    stations = list(PackingStation.objects.filter(enabled=True).order_by('station_order'))
    if not stations:
        return {'results': [], 'has_data': True}

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

    station_order_map = {s.id: idx for idx, s in enumerate(stations, start=1)}
    entry_interval = _float_config('BOX_ENTRY_INTERVAL_SECONDS', 5.0)

    strategies: list[tuple[str, str, Callable[[list[BoxItem]], list[BoxItem]], str]] = [
        ('joint_opt', '联合优化方案', lambda rows: _sequence_joint_opt(rows, support_map, station_order_map), 'balanced'),
        ('work_desc', '总工作量降序', _sequence_work_desc, 'balanced'),
        ('station1_focus', '1号位集中导向', lambda rows: _sequence_station_focus(rows, support_map, station_order_map, 1), 'station_1'),
        ('station3_focus', '3号位集中导向', lambda rows: _sequence_station_focus(rows, support_map, station_order_map, 3), 'station_3'),
        ('line_cluster', '线路聚集导向', _sequence_line_cluster, 'balanced'),
        ('short_box_first', '短箱优先', _sequence_short_first, 'balanced'),
        ('long_box_first', '长箱优先', _sequence_long_first, 'balanced'),
        ('station_complement', '工位互补导向', _sequence_work_desc, 'complement'),
    ]

    results: list[StrategyResult] = []
    for key, name, seq_fn, alloc_mode in strategies:
        sequenced = seq_fn(boxes)
        metrics = _simulate(sequenced, stations, transfer_map, support_map, eff_map, alloc_mode, station_order_map, entry_interval)
        metrics['sequence_preview'] = [f"{b.organization_name}-{b.seq_no}" for b in sequenced[:8]]
        results.append(StrategyResult(key=key, name=name, metrics=metrics))

    return {
        'has_data': True,
        'results': results,
    }


def _load_boxes() -> list[BoxItem]:
    tasks = (
        PipelineBoxTask.objects.select_related('order', 'order__organization', 'order__route')
        .order_by('order__organization_id', 'order__route_id', 'seq_no', 'id')
    )
    grouped: dict[tuple, dict] = {}
    for task in tasks:
        key = (
            task.order.order_no,
            task.order.organization_id,
            task.order.route_id,
            task.seq_no,
        )
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
        BoxItem(
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


def _split_org_blocks(boxes: list[BoxItem]) -> list[list[BoxItem]]:
    ordered = sorted(boxes, key=lambda b: (b.organization_id, b.seq_no, b.box_key))
    return [list(group) for _, group in groupby(ordered, key=lambda b: b.organization_id)]


def _sequence_work_desc(boxes: list[BoxItem]) -> list[BoxItem]:
    blocks = _split_org_blocks(boxes)
    blocks.sort(key=lambda block: sum(x.total_bundles for x in block), reverse=True)
    return [x for block in blocks for x in block]


def _sequence_line_cluster(boxes: list[BoxItem]) -> list[BoxItem]:
    blocks = _split_org_blocks(boxes)
    blocks.sort(key=lambda block: (block[0].route_no, block[0].organization_id, -sum(x.total_bundles for x in block)))
    return [x for block in blocks for x in block]


def _sequence_short_first(boxes: list[BoxItem]) -> list[BoxItem]:
    blocks = _split_org_blocks(boxes)
    blocks.sort(key=lambda block: sum(x.total_bundles for x in block))
    merged: list[BoxItem] = []
    for block in blocks:
        merged.extend(sorted(block, key=lambda x: x.total_bundles))
    return merged


def _sequence_long_first(boxes: list[BoxItem]) -> list[BoxItem]:
    blocks = _split_org_blocks(boxes)
    blocks.sort(key=lambda block: sum(x.total_bundles for x in block), reverse=True)
    merged: list[BoxItem] = []
    for block in blocks:
        merged.extend(sorted(block, key=lambda x: x.total_bundles, reverse=True))
    return merged


def _sequence_station_focus(
    boxes: list[BoxItem],
    support_map: dict[str, list[int]],
    station_order_map: dict[int, int],
    target_order: int,
) -> list[BoxItem]:
    blocks = _split_org_blocks(boxes)

    def score(block: list[BoxItem]) -> tuple[int, int]:
        focus_qty = 0
        total_qty = 0
        for box in block:
            for denom, qty in box.denoms.items():
                total_qty += qty
                for sid in support_map.get(denom, []):
                    if station_order_map.get(sid) == target_order:
                        focus_qty += qty
                        break
        return -focus_qty, -total_qty

    blocks.sort(key=score)
    return [x for block in blocks for x in block]


def _sequence_joint_opt(
    boxes: list[BoxItem],
    support_map: dict[str, list[int]],
    station_order_map: dict[int, int],
) -> list[BoxItem]:
    blocks = _split_org_blocks(boxes)
    if len(blocks) <= 2:
        return [x for block in blocks for x in block]

    remaining = blocks[:]
    sequence: list[list[BoxItem]] = []
    last_route = None

    while remaining:
        best_idx = 0
        best_score = None
        for i, block in enumerate(remaining):
            total_qty = sum(x.total_bundles for x in block)
            route_penalty = 0 if (last_route is None or block[0].route_no == last_route) else 30
            # 对前段工位友好（降低前段拥堵）
            front_station_fit = 0
            for box in block:
                for denom, qty in box.denoms.items():
                    if any(station_order_map.get(sid, 999) <= 2 for sid in support_map.get(denom, [])):
                        front_station_fit += qty
            score = route_penalty + total_qty - (0.2 * front_station_fit)
            if best_score is None or score < best_score:
                best_idx = i
                best_score = score

        selected = remaining.pop(best_idx)
        sequence.append(selected)
        last_route = selected[0].route_no

    return [x for block in sequence for x in block]


def _simulate(
    boxes: list[BoxItem],
    stations: list[PackingStation],
    transfer_map: dict[tuple[int, int], float],
    support_map: dict[str, list[int]],
    eff_map: dict[tuple[int, str], float],
    alloc_mode: str,
    station_order_map: dict[int, int],
    box_entry_interval: float,
) -> dict:
    if not boxes:
        return {}

    station_available = {s.id: 0.0 for s in stations}
    station_busy = {s.id: 0.0 for s in stations}
    station_wait = {s.id: 0.0 for s in stations}
    station_first_start = {s.id: None for s in stations}
    station_last_end = {s.id: 0.0 for s in stations}
    station_load_counter = {s.id: 0.0 for s in stations}
    station_alloc_qty = {s.id: 0 for s in stations}

    route_switches = 0
    prev_route = None

    last_box_finish = 0.0
    for box_idx, box in enumerate(boxes):
        if prev_route and prev_route != box.route_no:
            route_switches += 1
        prev_route = box.route_no

        release_time = box_idx * box_entry_interval
        prev_finish = release_time
        prev_station_id = None

        allocation = _allocate_for_box(
            box,
            stations,
            support_map,
            station_load_counter,
            alloc_mode,
            station_order_map,
            eff_map,
        )

        for station in stations:
            station_id = station.id
            quantities = allocation.get(station_id, {})
            if not quantities:
                continue

            transfer_time = transfer_map.get((prev_station_id, station_id), 0.0) if prev_station_id else 0.0
            start_time = max(station_available[station_id], prev_finish + transfer_time, release_time)
            proc_time = float(station.fixed_boxing_seconds)
            for denom, qty in quantities.items():
                unit_time = eff_map.get((station_id, denom), float(station.unit_boxing_seconds))
                proc_time += unit_time * qty
                station_alloc_qty[station_id] += qty
            end_time = start_time + proc_time

            if station_first_start[station_id] is None:
                station_first_start[station_id] = start_time
            elif start_time > station_last_end[station_id]:
                station_wait[station_id] += start_time - station_last_end[station_id]

            station_available[station_id] = end_time
            station_last_end[station_id] = end_time
            station_busy[station_id] += proc_time

            prev_finish = end_time
            prev_station_id = station_id

        last_box_finish = max(last_box_finish, prev_finish)

    spans = {
        s.station_name: round((station_last_end[s.id] - station_first_start[s.id]), 2)
        for s in stations
        if station_first_start[s.id] is not None
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
    }


def _allocate_for_box(
    box: BoxItem,
    stations: list[PackingStation],
    support_map: dict[str, list[int]],
    station_load_counter: dict[int, float],
    alloc_mode: str,
    station_order_map: dict[int, int],
    eff_map: dict[tuple[int, str], float],
) -> dict[int, dict[str, int]]:
    allocation: dict[int, dict[str, int]] = defaultdict(dict)

    preferred_station_no = None
    if alloc_mode == 'station_1':
        preferred_station_no = 1
    elif alloc_mode == 'station_3':
        preferred_station_no = 3

    station_default_unit = {s.id: float(s.unit_boxing_seconds) for s in stations}

    for denom, qty in box.denoms.items():
        compatible = support_map.get(denom, [])
        if not compatible:
            continue

        # 仅一个兼容工位时，任何策略都会给出相同分配，这是业务数据天然结果
        if len(compatible) == 1:
            selected = compatible[0]
            allocation[selected][denom] = allocation[selected].get(denom, 0) + qty
            station_load_counter[selected] += qty
            continue

        ranked = sorted(
            compatible,
            key=lambda sid: (eff_map.get((sid, denom), station_default_unit.get(sid, 1.0)), station_load_counter[sid]),
        )

        if alloc_mode in ('station_1', 'station_3'):
            preferred = [sid for sid in compatible if station_order_map.get(sid) == preferred_station_no]
            lead = preferred[0] if preferred else ranked[0]

            avg_load = sum(station_load_counter[sid] for sid in compatible) / max(1, len(compatible))
            lead_load = station_load_counter[lead]
            overload_ratio = max(0.0, (lead_load - avg_load) / max(1.0, avg_load))
            # 集中导向但抑制目标工位过载，避免跨度被不必要拉长
            lead_ratio = max(0.55, 0.8 - (0.25 * overload_ratio))

            lead_qty = int(round(qty * lead_ratio))
            lead_qty = min(max(1, lead_qty), qty)
            remain = qty - lead_qty

            allocation[lead][denom] = allocation[lead].get(denom, 0) + lead_qty
            station_load_counter[lead] += lead_qty

            if remain > 0:
                follower = ranked[0] if ranked[0] != lead else ranked[1]
                allocation[follower][denom] = allocation[follower].get(denom, 0) + remain
                station_load_counter[follower] += remain
            continue

        if alloc_mode == 'complement':
            # 轮询分配到当前累计负载最小工位
            for _ in range(qty):
                sid = min(compatible, key=lambda c: station_load_counter[c])
                allocation[sid][denom] = allocation[sid].get(denom, 0) + 1
                station_load_counter[sid] += 1
            continue

        # balanced：优先快工位，但按负载做比例回退
        lead = ranked[0]
        second = ranked[1]
        split = int(round(qty * 0.65))
        split = min(max(1, split), qty)
        allocation[lead][denom] = allocation[lead].get(denom, 0) + split
        station_load_counter[lead] += split
        if qty - split > 0:
            allocation[second][denom] = allocation[second].get(denom, 0) + (qty - split)
            station_load_counter[second] += (qty - split)

    return allocation


def _float_config(key: str, default: float) -> float:
    row = GlobalConfig.objects.filter(config_key=key, enabled=True).first()
    if not row:
        return default
    try:
        value = float(str(row.config_value).strip())
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default
