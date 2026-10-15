from __future__ import annotations

import math
import re
from typing import Any

from services.excel_parser import Segment


COLOR_HR = "#E31A1C"
COLOR_VO2 = "#2679D9"
COLOR_LAC = "#00A6E8"
COLOR_LAC_COMBINED = "#6F42C1"
COLOR_LT1 = "#228B22"
COLOR_LT2 = "#006400"

LEFT_PAD_SEC = 120.0
RIGHT_PAD_SEC = 120.0


def _finite_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    result: list[float] = []
    for row in rows:
        value = row.get(key)
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            result.append(number)
    return result


def threshold_x(
    segments: list[Segment],
    load_value: float,
) -> float:
    stages = sorted(
        [
            segment
            for segment in segments
            if (
                not segment.is_rest
                and not segment.is_recovery
                and segment.load is not None
            )
        ],
        key=lambda segment: float(segment.load),
    )

    if len(stages) < 2:
        raise ValueError("LT 위치 계산에 필요한 운동 Stage가 부족합니다.")

    first_load = float(stages[0].load)
    last_load = float(stages[-1].load)
    if not first_load <= load_value <= last_load:
        raise ValueError("LT 값이 측정 부하 범위를 벗어났습니다.")

    for left, right in zip(stages[:-1], stages[1:]):
        left_load = float(left.load)
        right_load = float(right.load)
        if left_load <= load_value <= right_load:
            load_span = right_load - left_load
            if abs(load_span) < 1e-12:
                return (left.center + right.center) / 2.0
            ratio = (load_value - left_load) / load_span
            if ratio < 0.5:
                return (
                    left.center
                    + (left.right - left.center)
                    * (ratio / 0.5)
                )
            return (
                right.left
                + (right.center - right.left)
                * ((ratio - 0.5) / 0.5)
            )

    return stages[-1].center


def hr_at_x(
    rows: list[dict[str, Any]],
    x_value: float,
) -> float | None:
    valid: list[tuple[float, float]] = []
    for row in rows:
        x = row.get("_x")
        hr = row.get("Heart Rate")
        try:
            x_value_row = float(x)
            hr_value = float(hr)
        except (TypeError, ValueError):
            continue
        if math.isfinite(x_value_row) and math.isfinite(hr_value):
            valid.append((x_value_row, hr_value))

    if not valid:
        return None
    valid.sort(key=lambda item: item[0])

    if x_value < valid[0][0] or x_value > valid[-1][0]:
        return None

    for (x0, y0), (x1, y1) in zip(valid[:-1], valid[1:]):
        if x0 <= x_value <= x1:
            if abs(x1 - x0) < 1e-12:
                return (y0 + y1) / 2.0
            ratio = (x_value - x0) / (x1 - x0)
            return y0 + (y1 - y0) * ratio

    return valid[-1][1]


def _lactate_x_for_stage(
    segments: list[Segment],
    stage_label: str,
    load_value: float | None,
) -> float | None:
    label = str(stage_label).strip()
    normalized = label.upper().replace("_", " ")

    if normalized in {"REST", "R"}:
        return -LEFT_PAD_SEC / 2.0

    exercise = [
        segment
        for segment in segments
        if (
            segment.load is not None
            and not segment.is_rest
            and not segment.is_recovery
        )
    ]
    if not exercise:
        return None

    if normalized in {
        "AO",
        "ALL-OUT",
        "ALL OUT",
        "ALLOUT",
    }:
        allout = [
            segment
            for segment in segments
            if segment.is_allout
        ]
        return allout[0].right if allout else exercise[-1].right

    if normalized.startswith("REC"):
        recovery = [
            segment
            for segment in segments
            if segment.is_recovery
        ]
        if not recovery:
            return None

        for segment in recovery:
            if str(segment.label).strip().upper() == normalized:
                return segment.right

        match = re.search(r"(\d+(?:\.\d+)?)", label)
        if match:
            requested = float(match.group(1)) * 60.0
            return min(
                recovery[0].left + requested,
                recovery[-1].right,
            )
        return recovery[-1].right

    if load_value is not None:
        for segment in exercise:
            if abs(float(segment.load) - float(load_value)) < 1e-9:
                return segment.right

    for segment in exercise:
        if str(segment.label).strip() == label:
            return segment.right

    return None


def _thresholds(
    rows: list[dict[str, Any]],
    segments: list[Segment],
    lt1_load: float | None,
    lt2_load: float | None,
) -> tuple[list[dict[str, Any]], dict[str, float | None]]:
    lines: list[dict[str, Any]] = []
    threshold_hr: dict[str, float | None] = {
        "LT1": None,
        "LT2": None,
    }

    for name, load, color in [
        ("LT1", lt1_load, COLOR_LT1),
        ("LT2", lt2_load, COLOR_LT2),
    ]:
        if load is None:
            continue
        x_value = threshold_x(segments, float(load))
        hr = hr_at_x(rows, x_value)
        threshold_hr[name] = hr
        lines.append(
            {
                "name": name,
                "load": float(load),
                "x": x_value,
                "hr": hr,
                "color": color,
            }
        )

    return lines, threshold_hr


def make_hr_vo2_graph(
    rows: list[dict[str, Any]],
    segments: list[Segment],
    hrmax: float,
    lt1_load: float | None = None,
    lt2_load: float | None = None,
) -> tuple[dict[str, Any], dict[str, float | None]]:
    thresholds, threshold_hr = _thresholds(
        rows,
        segments,
        lt1_load,
        lt2_load,
    )

    hr_values = _finite_values(rows, "Heart Rate")
    vo2_values = _finite_values(rows, "VO2/kg")

    model = {
        "kind": "hr_vo2",
        "rows": rows,
        "segments": segments,
        "hrmax": float(hrmax),
        "hr_ymin": 50.0,
        "hr_ymax": max(
            225.0,
            math.ceil(
                max([float(hrmax)] + hr_values + [0.0]) / 25.0
            )
            * 25.0,
        ),
        "vo2_ymin": 0.0,
        "vo2_ymax": max(
            100.0,
            math.ceil(max(vo2_values + [0.0]) / 10.0) * 10.0,
        ),
        "thresholds": thresholds,
        "left_pad": LEFT_PAD_SEC,
        "right_pad": RIGHT_PAD_SEC,
    }
    return model, threshold_hr


def make_lactate_graph(
    points: list[dict[str, Any]],
) -> dict[str, Any]:
    visible = []
    for point in points:
        value = point.get("lactate")
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(number):
            continue
        visible.append(
            {
                "label": str(point.get("label", "")),
                "load": point.get("load"),
                "lactate": number,
            }
        )

    if not visible:
        raise ValueError(
            "표시할 혈중 젖산염 데이터가 없습니다."
        )

    return {
        "kind": "lactate",
        "points": visible,
        "color": COLOR_LAC,
    }


def make_hr_vo2_lactate_graph(
    rows: list[dict[str, Any]],
    segments: list[Segment],
    hrmax: float,
    lactate_points: list[dict[str, Any]],
    lt1_load: float | None = None,
    lt2_load: float | None = None,
    lt_label_mode: str = "report",
) -> tuple[dict[str, Any], dict[str, float | None]]:
    model, threshold_hr = make_hr_vo2_graph(
        rows,
        segments,
        hrmax,
        lt1_load,
        lt2_load,
    )
    model = dict(model)
    model["kind"] = "combined"
    model["lt_label_mode"] = lt_label_mode

    positioned: list[dict[str, Any]] = []
    for point in lactate_points:
        value = point.get("lactate")
        try:
            lactate = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(lactate):
            continue

        x_value = _lactate_x_for_stage(
            segments,
            str(point.get("label", "")),
            point.get("load"),
        )
        if x_value is None:
            continue

        positioned.append(
            {
                "label": str(point.get("label", "")),
                "load": point.get("load"),
                "lactate": lactate,
                "x": x_value,
            }
        )

    model["lactate_points"] = positioned
    model["lactate_color"] = COLOR_LAC_COMBINED
    return model, threshold_hr
