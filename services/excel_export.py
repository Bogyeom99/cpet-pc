from __future__ import annotations

import html
import re
from typing import Any

from services.xlsx_io import build_xlsx


def _plain_text(value: str) -> str:
    value = value or ""
    value = re.sub(r"(?i)<br\s*/?>", "\n", value)
    value = re.sub(r"(?i)</p>\s*<p[^>]*>", "\n", value)
    value = re.sub(r"(?i)</div>\s*<div[^>]*>", "\n", value)
    value = re.sub(r"(?i)<div[^>]*>", "", value)
    value = re.sub(r"(?i)</div>", "\n", value)
    value = re.sub(r"(?s)<[^>]+>", "", value)
    return html.unescape(value).strip()


def build_excel_export(
    report_data: dict[str, Any],
    stage_summary: list[dict[str, Any]],
    lactate_points: list[dict[str, Any]],
    lt1: Any,
    lt2: Any,
) -> bytes:
    athlete_rows = [
        ["선수 정보", ""],
        ["측정날짜", report_data.get("test_date", "")],
        ["이름", report_data.get("name", "")],
        ["성별", report_data.get("sex", "")],
        ["구분", report_data.get("category", "")],
        [],
        ["선수 체격 및 신체조성", ""],
        ["신장(cm)", report_data.get("height", "")],
        ["체중(kg)", report_data.get("weight", "")],
        ["BMI(kg/m²)", report_data.get("bmi", "")],
    ]

    unit = report_data.get("load_unit", "")
    load_rows = [
        ["운동 부하 검사", "", "", "", "", "", "", "", ""],
        ["최대 산소 섭취량(ml/kg/min)", report_data.get("vo2max", "")],
        ["최대 심박수(beats/min)", report_data.get("hrmax", "")],
        ["운동 시간", report_data.get("exercise_time", "")],
        [
            f"최대 {report_data.get('load_name', '')}({unit})",
            report_data.get("max_load", ""),
        ],
        ["경사도(%)", report_data.get("grade_percent", "")],
        ["부하 단위", unit],
        [],
        ["스테이지별 결과", "", "", "", "", "", "", "", ""],
        [
            "Stage",
            f"Load({unit})",
            "운동시간(초)",
            "HR 최소",
            "HR 최대",
            "HR 평균",
            "VO2 최소",
            "VO2 최대",
            "VO2 평균",
        ],
    ]

    columns = [
        "Stage",
        "Load",
        "Duration_sec",
        "HR_min",
        "HR_max",
        "HR_mean",
        "VO2_min",
        "VO2_max",
        "VO2_mean",
    ]
    for row in stage_summary:
        load_rows.append([row.get(key, "") for key in columns])

    lactate_rows = [
        ["혈중 젖산염", "", "", ""],
        ["Stage", f"Load({unit})", "Lactate(mmol/L)", "비고"],
    ]
    for point in lactate_points:
        lactate_rows.append(
            [
                point.get("label", ""),
                point.get("load", ""),
                point.get("lactate", ""),
                "",
            ]
        )

    lactate_rows.extend(
        [
            [],
            ["LT 결과", "", "", "", ""],
            ["구분", "산출 여부", f"부하({unit})", "심박수(bpm)", "%HRmax"],
        ]
    )

    report_lt = {
        "LT1": report_data.get("lt1", {}),
        "LT2": report_data.get("lt2", {}),
    }

    for name, result in [("LT1", lt1), ("LT2", lt2)]:
        display = report_lt.get(name, {})
        if result is None:
            values = [name, "미선택", "", "", ""]
        elif result.valid:
            values = [
                name,
                "산출",
                result.threshold_load,
                display.get("hr", ""),
                display.get("pct_hrmax", ""),
            ]
        else:
            values = [
                name,
                "산출 불가",
                "",
                "",
                result.reason or "",
            ]
        lactate_rows.append(values)

    text_rows = [
        ["결과지 평가 문구", ""],
        [
            "1페이지 평가 문구",
            _plain_text(report_data.get("page1_comment", "")),
        ],
        [
            "젖산 평가 문구",
            _plain_text(report_data.get("lactate_comment", "")),
        ],
        [
            "LT1 분석 문구",
            _plain_text(report_data.get("lt1_comment", "")),
        ],
        [
            "LT2 분석 문구",
            _plain_text(report_data.get("lt2_comment", "")),
        ],
    ]

    return build_xlsx(
        [
            ("선수정보", athlete_rows),
            ("운동부하검사", load_rows),
            ("젖산_LT", lactate_rows),
            ("평가문구", text_rows),
        ],
        header_rows={
            "선수정보": {1, 7},
            "운동부하검사": {1, 9, 10},
            "젖산_LT": {1, 2, len(lactate_points) + 4, len(lactate_points) + 5},
            "평가문구": {1},
        },
    )
