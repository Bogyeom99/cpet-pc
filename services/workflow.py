from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from services import excel_parser
from services.excel_export import build_excel_export
from services.graph_service import (
    make_hr_vo2_graph,
    make_hr_vo2_lactate_graph,
    make_lactate_graph,
)
from services.lt_analysis import LactatePoint, estimate_lt
from services.report_service import build_report_html


round_half_up = excel_parser.round_half_up
is_rest = excel_parser.is_rest
is_recovery = excel_parser.is_recovery
is_allout = excel_parser.is_allout
parse_load = excel_parser.parse_load


def zone_for_hr(hr: float, hrmax: float) -> str:
    ratio = hr / hrmax if hrmax else 0
    if ratio < 0.60:
        return "Z1"
    if ratio < 0.70:
        return "Z2"
    if ratio < 0.80:
        return "Z3"
    if ratio < 0.90:
        return "Z4"
    return "Z5"


def format_duration(sec: float) -> str:
    seconds = int(round(float(sec)))
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def clean_json_value(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if pd.isna(value):
        return None
    return value


def summary_records(summary: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        item: dict[str, Any] = {
            "Stage": clean_json_value(row.get("Stage")),
            "Duration": format_duration(row.get("Duration_sec", 0)),
            "HR_min": clean_json_value(row.get("HR_min")),
            "HR_max": clean_json_value(row.get("HR_max")),
            "HR_mean": clean_json_value(row.get("HR_mean")),
            "VO2_min": clean_json_value(row.get("VO2_min")),
            "VO2_max": clean_json_value(row.get("VO2_max")),
            "VO2_mean": clean_json_value(row.get("VO2_mean")),
        }
        rows.append(item)
    return rows


def initial_lactate_rows(
    segments: list[Any],
    imported_lactate: list[dict[str, Any]],
    max_load: float,
) -> list[dict[str, Any]]:
    load_segments = [
        segment
        for segment in segments
        if (
            segment.load is not None
            and not segment.is_rest
            and not segment.is_recovery
        )
    ]
    allout_segment = next(
        (
            segment
            for segment in segments
            if getattr(segment, "is_allout", False)
        ),
        None,
    )
    recovery_segments = [
        segment
        for segment in segments
        if getattr(segment, "is_recovery", False)
    ]

    rest_lactate = None
    allout_lactate = None
    lactate_by_load: dict[float, float] = {}
    recovery_lactate_map: dict[str, float] = {}

    for item in imported_lactate:
        stage_name = str(item.get("stage", "")).strip()
        value = item.get("lactate")

        if is_rest(stage_name):
            rest_lactate = value
            continue
        if is_allout(stage_name):
            allout_lactate = value
            continue
        if is_recovery(stage_name):
            recovery_lactate_map[stage_name.lower()] = value
            continue

        load_value = parse_load(stage_name)
        if load_value is not None:
            lactate_by_load[round(float(load_value), 6)] = value

    rows: list[dict[str, Any]] = []
    has_rest = any(segment.is_rest for segment in segments)
    if has_rest or rest_lactate is not None:
        rows.append(
            {
                "stage": "Rest",
                "load": None,
                "lactate": rest_lactate,
            }
        )

    numeric_segments = [
        segment
        for segment in load_segments
        if not getattr(segment, "is_allout", False)
    ]

    for segment in numeric_segments:
        rows.append(
            {
                "stage": str(segment.label),
                "load": float(segment.load),
                "lactate": lactate_by_load.get(
                    round(float(segment.load), 6)
                ),
            }
        )

    if allout_segment is not None:
        allout_load = (
            float(allout_segment.load)
            if allout_segment.load is not None
            else (float(max_load) if max_load > 0 else None)
        )
        allout_value = allout_lactate
        if allout_value is None and allout_load is not None:
            allout_value = lactate_by_load.get(
                round(allout_load, 6)
            )
        rows.append(
            {
                "stage": "All-Out",
                "load": allout_load,
                "lactate": allout_value,
            }
        )

    for segment in recovery_segments:
        label = str(segment.label).strip()
        rows.append(
            {
                "stage": label,
                "load": None,
                "lactate": recovery_lactate_map.get(
                    label.lower()
                ),
            }
        )

    known_recovery = {
        str(row["stage"]).strip().lower()
        for row in rows
        if is_recovery(row["stage"])
    }
    for item in imported_lactate:
        label = str(item.get("stage", "")).strip()
        if (
            is_recovery(label)
            and label.lower() not in known_recovery
        ):
            rows.append(
                {
                    "stage": label,
                    "load": None,
                    "lactate": item.get("lactate"),
                }
            )

    return rows


def analyze(
    parsed: dict[str, Any],
    meta: dict[str, Any],
    lactate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    chart_points: list[dict[str, Any]] = []
    lt_points: list[LactatePoint] = []

    for row in lactate_rows:
        raw_lactate = row.get("lactate")
        if raw_lactate in (None, ""):
            continue

        lactate = float(raw_lactate)
        stage = str(row.get("stage", "")).strip()
        raw_load = row.get("load")
        load = (
            None
            if raw_load in (None, "")
            else float(raw_load)
        )

        chart_points.append(
            {
                "label": stage,
                "load": load,
                "lactate": lactate,
            }
        )

        if (
            not is_rest(stage)
            and not is_recovery(stage)
            and load is not None
        ):
            lt_points.append(
                LactatePoint(
                    label=stage,
                    load=load,
                    lactate=lactate,
                )
            )

    lt1, lt2 = estimate_lt(
        lt_points,
        bool(meta.get("show_lt1", True)),
        bool(meta.get("show_lt2", True)),
    )

    lactate_png = (
        make_lactate_graph(chart_points)
        if chart_points
        else None
    )

    lt1_load = (
        lt1.threshold_load
        if lt1 and lt1.valid
        else None
    )
    lt2_load = (
        lt2.threshold_load
        if lt2 and lt2.valid
        else None
    )

    basic_png = None
    combined_analysis_png = None
    combined_report_png = None
    threshold_hr = {"LT1": None, "LT2": None}

    if float(meta.get("hrmax") or 0) > 0:
        basic_png, _ = make_hr_vo2_graph(
            parsed["df"],
            parsed["segments"],
            float(meta["hrmax"]),
            None,
            None,
        )

        (
            combined_analysis_png,
            threshold_hr,
        ) = make_hr_vo2_lactate_graph(
            parsed["df"],
            parsed["segments"],
            float(meta["hrmax"]),
            chart_points,
            lt1_load,
            lt2_load,
            lt_label_mode="report",
        )

        combined_report_png, _ = make_hr_vo2_lactate_graph(
            parsed["df"],
            parsed["segments"],
            float(meta["hrmax"]),
            chart_points,
            lt1_load,
            lt2_load,
            lt_label_mode="report",
        )

    return {
        "lt1": lt1,
        "lt2": lt2,
        "chart_points": chart_points,
        "basic_png": basic_png,
        "combined_analysis_png": combined_analysis_png,
        "combined_report_png": combined_report_png,
        "lactate_png": lactate_png,
        "threshold_hr": threshold_hr,
    }


def lt_api_item(
    result: Any,
    key: str,
    threshold_hr: dict[str, float | None],
    meta: dict[str, Any],
) -> dict[str, Any]:
    if not result:
        return {
            "name": key,
            "show": False,
            "valid": False,
        }

    hr = threshold_hr.get(key)
    if result.valid:
        return {
            "name": key,
            "show": True,
            "valid": True,
            "load": float(result.threshold_load),
            "hr": (
                round_half_up(hr)
                if hr is not None
                else None
            ),
            "pct_hrmax": (
                float(hr) / float(meta["hrmax"]) * 100
                if hr is not None and float(meta.get("hrmax") or 0) > 0
                else None
            ),
        }

    return {
        "name": key,
        "show": True,
        "valid": False,
        "reason": result.reason or "산출 불가",
    }


def _report_lt_item(
    result: Any,
    key: str,
    threshold_hr: dict[str, float | None],
    meta: dict[str, Any],
) -> dict[str, Any]:
    if not result:
        return {"name": key, "show": False}

    hr = threshold_hr.get(key)
    if result.valid and hr is not None:
        return {
            "name": key,
            "show": True,
            "valid": True,
            "load": float(result.threshold_load),
            "hr": round_half_up(hr),
            "pct_hrmax": (
                float(hr) / float(meta["hrmax"]) * 100
            ),
        }

    return {
        "name": key,
        "show": True,
        "valid": False,
        "reason": result.reason or "산출 불가",
    }


def _default_lt_comment(
    item: dict[str, Any],
    name: str,
    meta: dict[str, Any],
) -> str:
    if not item.get("show"):
        return ""
    if not item.get("valid"):
        return f"산출 불가: {item.get('reason', '')}"

    zone = zone_for_hr(item["hr"], meta["hrmax"])
    load_word = (
        "속도"
        if meta["load_type"] == "Speed"
        else "파워"
    )
    exact_load_text = f"{item['load']:.2f}"
    approx_load_text = (
        f"{round_half_up(item['load'])}"
        if meta["load_type"] == "Speed"
        else exact_load_text
    )
    recommendation_load_text = (
        f"약 {approx_load_text}"
        if meta["load_type"] == "Speed"
        else exact_load_text
    )

    if name == "LT1":
        return (
            "혈중 젖산염과 운동 부하를 통해 산출된 "
            "LT1(제1젖산역치; 유산소 대사) 지점은 "
            f"{exact_load_text}{meta['load_unit']}로 나타났습니다. "
            f"이는 심박수 기준 {item['hr']}bpm"
            f"({zone} 구간, %HRmax 약 {item['pct_hrmax']:.0f}%)에 "
            f"해당하는 강도입니다. 즉, 경사도 "
            f"{meta['grade_percent']:.1f}%, {load_word} 약 "
            f"{approx_load_text}{meta['load_unit']} 이하 구간까지는 "
            "젖산의 생성과 제거가 균형을 이루는 안정적 유산소 대사 "
            "구간으로 해석할 수 있으며, 이 지점을 초과할 경우 젖산 "
            "축적이 본격화되는 것으로 판단됩니다. 따라서 유산소 능력 "
            f"향상을 위해 경사도 {meta['grade_percent']:.1f}%에서 "
            f"훈련 시 {recommendation_load_text}{meta['load_unit']} 이하로 "
            "진행이 적합할 것으로 판단됩니다."
        )

    return (
        "혈중 젖산염과 운동 부하를 통해 산출된 "
        "LT2(제2젖산역치; 무산소 대사) 지점은 "
        f"{exact_load_text}{meta['load_unit']}로 나타났습니다. "
        f"이는 심박수 기준 {item['hr']}bpm"
        f"({zone} 구간, %HRmax 약 {item['pct_hrmax']:.0f}%)에 "
        f"해당하는 강도입니다. 즉, 경사도 "
        f"{meta['grade_percent']:.1f}%, {load_word} 약 "
        f"{approx_load_text}{meta['load_unit']} 구간부터 젖산의 "
        "제거보다 생성이 빠르게 증가하는 고강도 구간으로 해석할 수 "
        "있으며, 이 지점부터 젖산 내성 훈련을 위한 구간으로 "
        f"판단됩니다. 따라서 젖산 내성 훈련을 위해 경사도 "
        f"{meta['grade_percent']:.1f}%에서 훈련 시 "
        f"{recommendation_load_text}{meta['load_unit']} 이상의 진행이 "
        "적합할 것으로 판단됩니다."
    )


def build_report_data(
    parsed: dict[str, Any],
    meta: dict[str, Any],
    analysis: dict[str, Any],
    comments: dict[str, str] | None = None,
) -> dict[str, Any]:
    summary = parsed["summary"]
    stages: list[dict[str, Any]] = []

    for _, row in summary.iterrows():
        hr_mean = pd.to_numeric(
            row.get("HR_mean"),
            errors="coerce",
        )
        hr_min = pd.to_numeric(
            row.get("HR_min"),
            errors="coerce",
        )
        hr_max_value = pd.to_numeric(
            row.get("HR_max"),
            errors="coerce",
        )

        if (
            pd.isna(hr_mean)
            or pd.isna(hr_min)
            or pd.isna(hr_max_value)
        ):
            stages.append(
                {
                    "stage": row["Stage"],
                    "hr_range": "-",
                    "hr_mean": "-",
                    "zone": "-",
                }
            )
            continue

        stages.append(
            {
                "stage": row["Stage"],
                "hr_range": (
                    f"{round_half_up(hr_min)}-"
                    f"{round_half_up(hr_max_value)}"
                ),
                "hr_mean": round_half_up(hr_mean),
                "zone": zone_for_hr(
                    float(hr_mean),
                    float(meta["hrmax"]),
                ),
            }
        )

    zones: list[dict[str, Any]] = []
    for idx, (low, high) in enumerate(
        [
            (0.50, 0.60),
            (0.60, 0.70),
            (0.70, 0.80),
            (0.80, 0.90),
            (0.90, 1.00),
        ],
        start=1,
    ):
        zones.append(
            {
                "name": f"Zone {idx}",
                "pct": f"{int(low * 100)}-{int(high * 100)}",
                "range": (
                    f"{round_half_up(float(meta['hrmax']) * low)}-"
                    f"{round_half_up(float(meta['hrmax']) * high)}"
                ),
            }
        )

    lt1_item = _report_lt_item(
        analysis["lt1"],
        "LT1",
        analysis["threshold_hr"],
        meta,
    )
    lt2_item = _report_lt_item(
        analysis["lt2"],
        "LT2",
        analysis["threshold_hr"],
        meta,
    )

    valid_loads = [
        float(value)
        for value in summary["Load"].dropna().tolist()
    ]
    first_load = (
        valid_loads[0]
        if valid_loads
        else float(meta["max_load"])
    )
    increment = (
        valid_loads[1] - valid_loads[0]
        if len(valid_loads) >= 2
        else 0
    )

    if meta["load_type"] == "Speed":
        protocol_text = (
            f"프로토콜(경사 {float(meta['grade_percent']):.1f}% 고정, "
            f"시작 {first_load:g} {meta['load_unit']}"
        )
    else:
        protocol_text = (
            f"프로토콜(시작 {first_load:g} {meta['load_unit']}"
        )
    if increment > 0:
        protocol_text += (
            f", {float(meta['stage_duration_min']):g}분마다 "
            f"{increment:g} {meta['load_unit']} 증가"
        )
    protocol_text += (
        ")을 통한 운동부하검사 결과, "
        f"{meta['athlete']['name']} 선수의 최대심박수 "
        f"{int(meta['hrmax'])} bpm, 최대산소섭취량 "
        f"{float(meta['vo2max']):.2f} ml/kg/min으로 측정되었습니다."
    )

    rest_point = next(
        (
            point
            for point in analysis["chart_points"]
            if str(point.get("label", "")).lower() == "rest"
        ),
        None,
    )
    if rest_point:
        lactate_default = (
            f"젖산 역치 측정 결과 {meta['athlete']['name']} 선수의 "
            f"안정 시 혈중 젖산염은 "
            f"{float(rest_point['lactate']):.2f} mmol/L로 측정되었습니다. "
            "이후 운동 강도 증가에 따른 혈중 젖산염 변화는 "
            "그래프와 같습니다."
        )
    else:
        lactate_default = (
            f"젖산 역치 측정 결과 {meta['athlete']['name']} 선수의 "
            "운동 강도 증가에 따른 혈중 젖산염 변화는 "
            "그래프와 같습니다."
        )

    defaults = {
        "page1_comment": protocol_text,
        "lactate_comment": lactate_default,
        "lt1_comment": _default_lt_comment(
            lt1_item,
            "LT1",
            meta,
        ),
        "lt2_comment": _default_lt_comment(
            lt2_item,
            "LT2",
            meta,
        ),
    }
    if comments:
        for key in defaults:
            value = comments.get(key)
            if isinstance(value, str):
                defaults[key] = value

    test_date = meta["test_date"]
    if hasattr(test_date, "strftime"):
        report_date = test_date.strftime("%Y.%m.%d.")
    else:
        report_date = str(test_date).replace("-", ".") + "."

    return {
        "name": meta["athlete"]["name"],
        "sex": meta["athlete"]["sex"],
        "category": meta["athlete"]["category"],
        "test_date": report_date,
        "height": f"{float(meta['height']):.1f}",
        "weight": f"{float(meta['weight']):.1f}",
        "bmi": f"{float(meta['bmi']):.1f}",
        "vo2max": f"{float(meta['vo2max']):.2f}",
        "hrmax": int(meta["hrmax"]),
        "exercise_time": meta["exercise_time"],
        "load_name": (
            "속도"
            if meta["load_type"] == "Speed"
            else "파워"
        ),
        "load_unit": meta["load_unit"],
        "max_load": f"{float(meta['max_load']):g}",
        "grade_percent": f"{float(meta['grade_percent']):.1f}",
        "stages": stages,
        "zones": zones,
        "lactates": analysis["chart_points"],
        "lt1": lt1_item,
        "lt2": lt2_item,
        **defaults,
    }


def build_report_htmls(
    parsed: dict[str, Any],
    meta: dict[str, Any],
    analysis: dict[str, Any],
    comments: dict[str, str] | None = None,
) -> tuple[dict[str, Any], str, str]:
    report_data = build_report_data(
        parsed,
        meta,
        analysis,
        comments,
    )

    editable_html = build_report_html(
        report_data,
        analysis["basic_png"],
        analysis["lactate_png"],
        analysis["combined_report_png"],
        editable=True,
    )
    final_html = build_report_html(
        report_data,
        analysis["basic_png"],
        analysis["lactate_png"],
        analysis["combined_report_png"],
    )
    return report_data, editable_html, final_html


def build_excel_bytes(
    report_data: dict[str, Any],
    parsed: dict[str, Any],
    analysis: dict[str, Any],
) -> bytes:
    return build_excel_export(
        report_data,
        parsed["summary"],
        analysis["chart_points"],
        analysis["lt1"],
        analysis["lt2"],
    )
