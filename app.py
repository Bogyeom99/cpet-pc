from __future__ import annotations

import base64
import datetime as dt
import threading
import webbrowser
from io import BytesIO
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_file,
)

from services import excel_parser
from services.athlete_store import (
    add_athlete,
    list_athletes,
    list_measurements,
    save_measurement,
)
from services.input_template import (
    build_input_template,
    parse_lactate_sheet,
)
from services.report_service import html_to_pdf
from services.workflow import (
    analyze,
    build_excel_bytes,
    build_report_htmls,
    initial_lactate_rows,
    lt_api_item,
    summary_records,
)


ROOT = Path(__file__).resolve().parent

app = Flask(__name__)
app.config.update(
    MAX_CONTENT_LENGTH=100 * 1024 * 1024,
    JSON_AS_ASCII=False,
)

STATE: dict[str, Any] = {
    "parsed": None,
    "meta": None,
    "analysis": None,
    "report_data": None,
    "editable_html": None,
    "final_html": None,
}


def _json_error(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _athlete_by_id(athlete_id: int) -> dict[str, Any] | None:
    for athlete in list_athletes():
        if int(athlete["id"]) == int(athlete_id):
            return athlete
    return None


def _meta_from_mapping(
    values: Any,
    athlete: dict[str, Any],
) -> dict[str, Any]:
    load_type = str(values.get("load_type") or "Speed")
    return {
        "athlete": athlete,
        "test_date": str(
            values.get("test_date")
            or dt.date.today().isoformat()
        ),
        "height": _to_float(values.get("height")),
        "weight": _to_float(values.get("weight")),
        "bmi": _to_float(values.get("bmi")),
        "vo2max": _to_float(values.get("vo2max")),
        "hrmax": _to_int(values.get("hrmax")),
        "exercise_time": str(
            values.get("exercise_time") or ""
        ),
        "load_type": load_type,
        "load_unit": (
            "km/h"
            if load_type == "Speed"
            else "watt"
        ),
        "max_load": _to_float(values.get("max_load")),
        "grade_percent": _to_float(
            values.get("grade_percent")
        ),
        "stage_duration_min": max(
            1,
            _to_int(values.get("stage_duration_min"), 3),
        ),
        "rest_duration_min": max(
            1,
            _to_int(values.get("rest_duration_min"), 1),
        ),
        "show_lt1": _to_bool(
            values.get("show_lt1"),
            True,
        ),
        "show_lt2": _to_bool(
            values.get("show_lt2"),
            True,
        ),
    }


def _image_data_url(png: bytes | None) -> str | None:
    if not png:
        return None
    return (
        "data:image/png;base64,"
        + base64.b64encode(png).decode("ascii")
    )


@app.after_request
def _security_headers(response: Response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/athletes")
def api_athletes():
    try:
        return jsonify(
            {
                "ok": True,
                "athletes": list_athletes(),
            }
        )
    except Exception as exc:
        return _json_error(
            f"선수 목록을 불러오지 못했습니다: {exc}",
            500,
        )


@app.post("/api/athletes")
def api_add_athlete():
    data = request.get_json(silent=True) or {}
    try:
        athlete = add_athlete(
            name=str(data.get("name") or ""),
            sex=str(data.get("sex") or "남"),
            category=str(
                data.get("category")
                or "국가대표 후보"
            ),
        )
        return jsonify(
            {
                "ok": True,
                "athlete": athlete,
                "athletes": list_athletes(),
            }
        )
    except Exception as exc:
        return _json_error(str(exc))


@app.get("/api/measurements/<int:athlete_id>")
def api_measurements(athlete_id: int):
    try:
        return jsonify(
            {
                "ok": True,
                "measurements": list_measurements(
                    athlete_id
                ),
            }
        )
    except Exception as exc:
        return _json_error(
            f"측정 기록을 불러오지 못했습니다: {exc}",
            500,
        )


@app.post("/api/measurement")
def api_save_measurement():
    data = request.get_json(silent=True) or {}
    athlete_id = _to_int(data.get("athlete_id"))
    athlete = _athlete_by_id(athlete_id)
    if athlete is None:
        return _json_error("선수를 먼저 선택하세요.")

    meta = _meta_from_mapping(data, athlete)

    try:
        saved = save_measurement(
            athlete_id=athlete_id,
            test_date=meta["test_date"],
            height=meta["height"],
            weight=meta["weight"],
            bmi=meta["bmi"],
            vo2max=meta["vo2max"],
            hrmax=meta["hrmax"],
            exercise_time=meta["exercise_time"],
            load_type=meta["load_type"],
            max_load=meta["max_load"],
            grade_percent=meta["grade_percent"],
            stage_duration_min=meta[
                "stage_duration_min"
            ],
            rest_duration_min=meta[
                "rest_duration_min"
            ],
        )
        return jsonify(
            {
                "ok": True,
                "measurement": saved,
            }
        )
    except Exception as exc:
        return _json_error(
            f"측정 정보 저장 중 오류가 발생했습니다: {exc}",
            500,
        )


@app.get("/api/template")
def api_template():
    return send_file(
        BytesIO(build_input_template()),
        as_attachment=True,
        download_name="NGC_CPET_입력양식.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


@app.post("/api/upload")
def api_upload():
    athlete_id = _to_int(request.form.get("athlete_id"))
    athlete = _athlete_by_id(athlete_id)
    if athlete is None:
        return _json_error("선수를 먼저 선택하세요.")

    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return _json_error("Excel 파일을 선택하세요.")

    meta = _meta_from_mapping(request.form, athlete)
    raw_bytes = uploaded.read()

    if not raw_bytes:
        return _json_error("Excel 파일이 비어 있습니다.")

    try:
        workbook = BytesIO(raw_bytes)
        df, segments, summary = excel_parser.parse_excel(
            workbook,
            stage_duration_min=meta[
                "stage_duration_min"
            ],
            rest_duration_min=meta[
                "rest_duration_min"
            ],
            allout_load=(
                meta["max_load"]
                if meta["max_load"] > 0
                else None
            ),
        )

        lactate_rows = parse_lactate_sheet(
            BytesIO(raw_bytes)
        )

        parsed = {
            "df": df,
            "segments": segments,
            "summary": summary,
            "lactate_rows": lactate_rows,
        }

        STATE.update(
            {
                "parsed": parsed,
                "meta": meta,
                "analysis": None,
                "report_data": None,
                "editable_html": None,
                "final_html": None,
            }
        )

        return jsonify(
            {
                "ok": True,
                "summary": summary_records(summary),
                "lactates": initial_lactate_rows(
                    segments,
                    lactate_rows,
                    meta["max_load"],
                ),
                "lactate_imported": bool(lactate_rows),
            }
        )
    except Exception as exc:
        STATE.update(
            {
                "parsed": None,
                "analysis": None,
                "report_data": None,
                "editable_html": None,
                "final_html": None,
            }
        )
        return _json_error(str(exc))


@app.post("/api/analyze")
def api_analyze():
    parsed = STATE.get("parsed")
    meta = STATE.get("meta")
    if parsed is None or meta is None:
        return _json_error(
            "검사 입력에서 Excel 파일을 먼저 업로드하세요."
        )

    data = request.get_json(silent=True) or {}
    rows = data.get("lactates") or []

    meta = {
        **meta,
        "show_lt1": _to_bool(
            data.get("show_lt1"),
            meta.get("show_lt1", True),
        ),
        "show_lt2": _to_bool(
            data.get("show_lt2"),
            meta.get("show_lt2", True),
        ),
    }

    try:
        analysis = analyze(
            parsed,
            meta,
            rows,
        )
        if (
            analysis.get("basic_png") is None
            or analysis.get("combined_report_png") is None
        ):
            return _json_error(
                "최대 심박수를 입력해야 결과 그래프를 생성할 수 있습니다."
            )

        report_data, editable_html, final_html = (
            build_report_htmls(
                parsed,
                meta,
                analysis,
            )
        )

        STATE.update(
            {
                "meta": meta,
                "analysis": analysis,
                "report_data": report_data,
                "editable_html": editable_html,
                "final_html": final_html,
            }
        )

        return jsonify(
            {
                "ok": True,
                "lt1": lt_api_item(
                    analysis["lt1"],
                    "LT1",
                    analysis["threshold_hr"],
                    meta,
                ),
                "lt2": lt_api_item(
                    analysis["lt2"],
                    "LT2",
                    analysis["threshold_hr"],
                    meta,
                ),
                "lactate_graph": _image_data_url(
                    analysis["lactate_png"]
                ),
                "basic_graph": _image_data_url(
                    analysis["basic_png"]
                ),
                "combined_graph": _image_data_url(
                    analysis["combined_analysis_png"]
                ),
                "report_ready": True,
            }
        )
    except Exception as exc:
        return _json_error(
            f"분석 중 오류가 발생했습니다: {exc}"
        )


@app.get("/report-preview")
def report_preview():
    html_text = STATE.get("editable_html")
    if not html_text:
        return Response(
            "분석 결과를 먼저 생성하세요.",
            status=409,
            mimetype="text/plain",
        )
    return Response(
        html_text,
        mimetype="text/html",
    )


@app.post("/api/report-comments")
def api_report_comments():
    parsed = STATE.get("parsed")
    meta = STATE.get("meta")
    analysis = STATE.get("analysis")
    if (
        parsed is None
        or meta is None
        or analysis is None
    ):
        return _json_error("분석 결과를 먼저 생성하세요.")

    data = request.get_json(silent=True) or {}
    comments = {
        key: str(data.get(key) or "")
        for key in [
            "page1_comment",
            "lactate_comment",
            "lt1_comment",
            "lt2_comment",
        ]
    }

    try:
        report_data, editable_html, final_html = (
            build_report_htmls(
                parsed,
                meta,
                analysis,
                comments,
            )
        )
        STATE.update(
            {
                "report_data": report_data,
                "editable_html": editable_html,
                "final_html": final_html,
            }
        )
        return jsonify({"ok": True})
    except Exception as exc:
        return _json_error(
            f"결과지 수정 내용을 저장하지 못했습니다: {exc}"
        )


@app.get("/download/pdf")
def download_pdf():
    final_html = STATE.get("final_html")
    meta = STATE.get("meta")
    if not final_html or not meta:
        return _json_error("결과지를 먼저 생성하세요.", 409)

    try:
        pdf = html_to_pdf(final_html)
        file_name = (
            f"{meta['test_date']}_"
            f"{meta['athlete']['name']}_피드백.pdf"
        )
        return send_file(
            BytesIO(pdf),
            as_attachment=True,
            download_name=file_name,
            mimetype="application/pdf",
        )
    except Exception as exc:
        return _json_error(
            f"PDF 생성에 실패했습니다: {exc}",
            500,
        )


@app.get("/download/excel")
def download_excel():
    parsed = STATE.get("parsed")
    analysis = STATE.get("analysis")
    report_data = STATE.get("report_data")
    meta = STATE.get("meta")
    if (
        parsed is None
        or analysis is None
        or report_data is None
        or meta is None
    ):
        return _json_error("결과지를 먼저 생성하세요.", 409)

    try:
        excel_bytes = build_excel_bytes(
            report_data,
            parsed,
            analysis,
        )
        file_name = (
            f"{meta['test_date']}_"
            f"{meta['athlete']['name']}_결과.xlsx"
        )
        return send_file(
            BytesIO(excel_bytes),
            as_attachment=True,
            download_name=file_name,
            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
    except Exception as exc:
        return _json_error(
            f"Excel 결과 생성에 실패했습니다: {exc}",
            500,
        )


def _open_browser() -> None:
    webbrowser.open("http://127.0.0.1:8501")


if __name__ == "__main__":
    threading.Timer(1.0, _open_browser).start()
    app.run(
        host="127.0.0.1",
        port=8501,
        debug=False,
        use_reloader=False,
        threaded=True,
    )
