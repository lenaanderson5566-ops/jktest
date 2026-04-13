from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import groupby
from typing import Callable

from apps.masterdata.models import (
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

    strategies: list[tuple[str, str, Callable[[list[BoxItem]], list[BoxItem]], str]] = [
        ('joint_opt', '联合优化方案', _sequence_joint_opt, 'balanced'),
        ('work_desc', '总工作量降序', _sequence_work_desc, 'balanced'),
        ('station1_focus', '1号位集中导向', _sequence_work_desc, 'station_1'),
        ('station3_focus', '3号位集中导向', _sequence_work_desc, 'station_3'),
        ('line_cluster', '线路聚集导向', _sequence_line_cluster, 'balanced'),
        ('short_box_first', '短箱优先', _sequence_short_first, 'balanced'),
        ('long_box_first', '长箱优先', _sequence_long_first, 'balanced'),
        ('station_complement', '工位互补导向', _sequence_work_desc, 'complement'),
    ]

    results: list[StrategyResult] = []
    for key, name, seq_fn, alloc_mode in strategies:
        sequenced = seq_fn(boxes)
        metrics = _simulate(sequenced, stations, transfer_map, support_map, eff_map, alloc_mode)
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

    boxes = [
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
    return boxes


def _split_org_blocks(boxes: list[BoxItem]) -> list[list[BoxItem]]:
    ordered = sorted(boxes, key=lambda b: (b.organization_id, b.seq_no, b.box_key))
    return [list(group) for _, group in groupby(ordered, key=lambda b: b.organization_id)]


def _sequence_work_desc(boxes: list[BoxItem]) -> list[BoxItem]:
    blocks = _split_org_blocks(boxes)
    blocks.sort(key=lambda block: sum(x.total_bundles for x in block), reverse=True)
    return [x for block in blocks for x in block]


def _sequence_line_cluster(boxes: list[BoxItem]) -> list[BoxItem]:
    blocks = _split_org_blocks(boxes)
    blocks.sort(key=lambda block: (block[0].route_no, -sum(x.total_bundles for x in block)))
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


def _sequence_joint_opt(boxes: list[BoxItem]) -> list[BoxItem]:
    blocks = _split_org_blocks(boxes)
    if len(blocks) <= 2:
        return [x for block in blocks for x in block]

    used = [False] * len(blocks)
    sequence: list[list[BoxItem]] = []
    last_route = None
    for _ in range(len(blocks)):
        best_idx = None
        best_score = None
        for i, block in enumerate(blocks):
            if used[i]:
                continue
            block_work = sum(x.total_bundles for x in block)
            route_penalty = 0 if last_route in (None, block[0].route_no) else 8
            score = block_work + route_penalty
            if best_score is None or score < best_score:
                best_score = score
                best_idx = i
        used[best_idx] = True
        sequence.append(blocks[best_idx])
        last_route = blocks[best_idx][0].route_no

    return [x for block in sequence for x in block]


def _simulate(
    boxes: list[BoxItem],
    stations: list[PackingStation],
    transfer_map: dict[tuple[int, int], float],
    support_map: dict[str, list[int]],
    eff_map: dict[tuple[int, str], float],
    alloc_mode: str,
) -> dict:
    if not boxes:
        return {}

    station_available = {s.id: 0.0 for s in stations}
    station_busy = {s.id: 0.0 for s in stations}
    station_wait = {s.id: 0.0 for s in stations}
    station_first_start = {s.id: None for s in stations}
    station_last_end = {s.id: 0.0 for s in stations}
    station_load_counter = {s.id: 0.0 for s in stations}

    box_entry_interval = 5.0
    route_switches = 0
    prev_route = None
    station_order_map = {s.id: idx for idx, s in enumerate(stations, start=1)}

    last_box_finish = 0.0
    for box_idx, box in enumerate(boxes):
        if prev_route and prev_route != box.route_no:
            route_switches += 1
        prev_route = box.route_no

        release_time = box_idx * box_entry_interval
        prev_finish = release_time
        prev_station_id = None

        allocation = _allocate_for_box(box, stations, support_map, station_load_counter, alloc_mode, station_order_map)

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

    return {
        'total_finish_seconds': round(last_box_finish, 2),
        'station_busy_seconds': {s.station_name: round(station_busy[s.id], 2) for s in stations},
        'station_wait_seconds': {s.station_name: round(station_wait[s.id], 2) for s in stations},
        'station_span_seconds': spans,
        'line_continuity': continuity,
        'route_switches': route_switches,
    }


def _allocate_for_box(
    box: BoxItem,
    stations: list[PackingStation],
    support_map: dict[str, list[int]],
    station_load_counter: dict[int, float],
    alloc_mode: str,
    station_order_map: dict[int, int],
) -> dict[int, dict[str, int]]:
    allocation: dict[int, dict[str, int]] = defaultdict(dict)

    preferred_station_no = None
    if alloc_mode == 'station_1':
        preferred_station_no = 1
    elif alloc_mode == 'station_3':
        preferred_station_no = 3

    for denom, qty in box.denoms.items():
        compatible = support_map.get(denom, [])
        if not compatible:
            continue

        if alloc_mode in ('station_1', 'station_3'):
            selected = min(
                compatible,
                key=lambda sid: (0 if station_order_map.get(sid) == preferred_station_no else 1, station_order_map.get(sid, 999)),
            )
        elif alloc_mode == 'complement':
            selected = min(compatible, key=lambda sid: station_load_counter[sid])
        else:
            selected = min(compatible, key=lambda sid: station_order_map.get(sid, 999))

        allocation[selected][denom] = allocation[selected].get(denom, 0) + qty
        station_load_counter[selected] += qty

    return allocation
