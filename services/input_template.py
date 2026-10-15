from __future__ import annotations

from typing import Any

from services.xlsx_io import build_xlsx, read_xlsx


DATA_COLUMNS = ["Time", "VO2/kg", "Heart Rate", "Stage"]
LACTATE_COLUMNS = ["Stage", "Lactate"]


def parse_lactate_sheet(uploaded_file: Any) -> list[dict]:
    workbook = read_xlsx(uploaded_file)
    sheet_name = next(
        (
            name
            for name in workbook
            if str(name).strip().lower()
            in {"lactate", "젖산", "젖산염"}
        ),
        None,
    )
    if sheet_name is None:
        return []

    rows = workbook[sheet_name]
    if not rows:
        return []

    headers = [
        "" if value is None else str(value).strip().lower()
        for value in rows[0]
    ]
    stage_aliases = {"stage", "단계", "스테이지"}
    lactate_aliases = {
        "lactate",
        "lactate(mmol/l)",
        "blood lactate",
        "젖산",
        "혈중 젖산염",
    }

    stage_index = next(
        (i for i, value in enumerate(headers) if value in stage_aliases),
        None,
    )
    lactate_index = next(
        (i for i, value in enumerate(headers) if value in lactate_aliases),
        None,
    )

    if stage_index is None or lactate_index is None:
        raise ValueError(
            "Lactate 시트에는 Stage와 Lactate 열이 필요합니다."
        )

    result: list[dict] = []
    for row in rows[1:]:
        stage = row[stage_index] if stage_index < len(row) else None
        lactate = row[lactate_index] if lactate_index < len(row) else None

        if stage in (None, "") and lactate in (None, ""):
            continue
        if stage in (None, "") or lactate in (None, ""):
            continue

        try:
            value = float(lactate)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Lactate 시트의 '{stage}' 젖산값을 숫자로 읽을 수 없습니다."
            ) from exc

        result.append(
            {
                "stage": str(stage).strip(),
                "lactate": value,
            }
        )

    return result


def build_input_template() -> bytes:
    guide_rows = [
        ["NGC CPET Excel 입력 양식", "", "", ""],
        [],
        ["구분", "작성 방법", "", ""],
        ["Data 시트", "운동 중 연속 측정 자료를 입력합니다.", "", ""],
        ["필수 열", "Time / VO2/kg / Heart Rate / Stage", "", ""],
        [
            "Stage 작성",
            "운동 Stage에는 실제 부하값만 입력합니다. 마지막 숫자 Stage는 자동으로 All-Out으로 처리됩니다.",
            "",
            "",
        ],
        [
            "Time 작성",
            "Excel 시간값 또는 초 단위 연속시간을 사용할 수 있습니다.",
            "",
            "",
        ],
        [
            "Lactate 시트",
            "각 Stage 종료 후 측정한 혈중 젖산염 값을 입력합니다.",
            "",
            "",
        ],
        [
            "Lactate 작성",
            "단위는 mmol/L이며 미측정 Stage는 비워도 됩니다.",
            "",
            "",
        ],
        [
            "주의",
            "일반 운동 Stage와 Rest는 프로그램에서 설정한 시간으로 정규화하며 All-Out과 Recovery는 실제 기록시간을 사용합니다.",
            "",
            "",
        ],
    ]

    data_rows = [
        DATA_COLUMNS,
        [0, 18.2, 88, 4],
        [1, 18.6, 89, 4],
        [2, 19.1, 90, 4],
        [180, 21.0, 105, "R"],
        [181, 20.8, 104, "R"],
        [240, 23.2, 112, 5.5],
        [241, 23.7, 113, 5.5],
        [420, 35.0, 156, 16],
        [421, 35.4, 158, 16],
    ]

    lactate_rows = [
        LACTATE_COLUMNS,
        ["Rest", 1.20],
        [4, 1.40],
        [5.5, 1.70],
        [7, 2.10],
        [8.5, 2.80],
        [10, 4.00],
        [11.5, 6.20],
        [13, 8.40],
        [14.5, 10.20],
        [16, 12.30],
        ["Recovery 1min", 10.80],
        ["Recovery 5min", 6.50],
    ]

    return build_xlsx(
        [
            ("작성안내", guide_rows),
            ("Data", data_rows),
            ("Lactate", lactate_rows),
        ],
        header_rows={
            "작성안내": {1, 3},
            "Data": {1},
            "Lactate": {1},
        },
    )
