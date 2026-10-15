from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QDate, QUrl, Qt
from PySide6.QtGui import QColor, QDesktopServices, QPixmap
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from services import excel_parser
from services.athlete_store import (
    add_athlete,
    list_athletes,
    list_measurements,
    save_measurement,
)
from services.input_template import build_input_template, parse_lactate_sheet
from services.workflow import (
    analyze,
    build_excel_bytes,
    build_report_htmls,
    initial_lactate_rows,
    lt_api_item,
    summary_records,
)


ROOT = Path(__file__).resolve().parent.parent


class LocalOnlyInterceptor(QWebEngineUrlRequestInterceptor):
    """Block all network schemes from the embedded report preview."""

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:
        scheme = info.requestUrl().scheme().lower()
        if scheme in {"http", "https", "ftp", "ws", "wss"}:
            info.block(True)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("NGC CPET PC")
        self.resize(1500, 950)

        self.athletes: list[dict[str, Any]] = []
        self.measurements: list[dict[str, Any]] = []
        self.parsed: dict[str, Any] | None = None
        self.meta: dict[str, Any] | None = None
        self.analysis: dict[str, Any] | None = None
        self.report_data: dict[str, Any] | None = None
        self.final_html: str | None = None
        self.editable_html: str | None = None
        self.lactate_rows: list[dict[str, Any]] = []

        self._build_ui()
        self.refresh_athletes()

    # ---------- UI shell ----------

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 14, 18, 18)
        root.setSpacing(10)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("NGC CPET 피드백지 제작")
        title.setStyleSheet(
            "font-size: 24px; font-weight: 800; color: #123A79;"
        )
        subtitle = QLabel(
            "선수 정보와 측정 자료는 외부 서버 없이 이 PC 안에서만 처리됩니다."
        )
        subtitle.setStyleSheet("color: #667085;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        local_badge = QLabel("LOCAL ONLY")
        local_badge.setStyleSheet(
            "background:#ECFDF3; color:#067647; padding:6px 10px;"
            "border-radius:10px; font-weight:800;"
        )

        header.addLayout(title_box)
        header.addStretch()
        header.addWidget(local_badge)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_athlete_tab(), "1 선수 등록")
        self.tabs.addTab(self._build_measurement_tab(), "2 검사 입력")
        self.tabs.addTab(self._build_analysis_tab(), "3 분석")
        self.tabs.addTab(self._build_report_tab(), "4 결과지")
        root.addWidget(self.tabs, 1)

        self.setCentralWidget(central)
        self.statusBar().showMessage("준비됨")

    # ---------- Athlete tab ----------

    def _build_athlete_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        form_box = QGroupBox("선수 등록")
        form = QGridLayout(form_box)

        self.athlete_name = QLineEdit()
        self.athlete_sex = QComboBox()
        self.athlete_sex.addItems(["남", "여"])
        self.athlete_category = QComboBox()
        self.athlete_category.addItems(
            ["국가대표 후보", "청소년 대표", "꿈나무"]
        )

        form.addWidget(QLabel("선수 이름"), 0, 0)
        form.addWidget(QLabel("성별"), 0, 1)
        form.addWidget(QLabel("구분"), 0, 2)
        form.addWidget(QLabel(""), 0, 3)

        form.addWidget(self.athlete_name, 1, 0)
        form.addWidget(self.athlete_sex, 1, 1)
        form.addWidget(self.athlete_category, 1, 2)

        register_button = QPushButton("선수 등록")
        register_button.clicked.connect(self.register_athlete)
        form.addWidget(register_button, 1, 3)

        actions = QHBoxLayout()
        refresh_button = QPushButton("선수 목록 새로고침")
        refresh_button.clicked.connect(self.refresh_athletes)
        actions.addWidget(refresh_button)
        actions.addStretch()

        self.athlete_table = QTableWidget(0, 3)
        self.athlete_table.setHorizontalHeaderLabels(
            ["이름", "성별", "구분"]
        )
        self.athlete_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.athlete_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        self.athlete_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        note = QLabel(
            "등록한 선수와 측정 기록은 data/cpet.db에 저장됩니다."
        )
        note.setStyleSheet("color:#667085;")

        layout.addWidget(note)
        layout.addWidget(form_box)
        layout.addLayout(actions)
        layout.addWidget(self.athlete_table, 1)
        return page

    # ---------- Measurement tab ----------

    def _build_measurement_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)

        top = QGridLayout()
        self.measurement_athlete = QComboBox()
        self.measurement_athlete.currentIndexChanged.connect(
            self.on_measurement_athlete_changed
        )
        self.saved_measurement = QComboBox()
        self.saved_measurement.currentIndexChanged.connect(
            self.on_saved_measurement_changed
        )

        top.addWidget(QLabel("선수 선택"), 0, 0)
        top.addWidget(QLabel("기존 측정 기록"), 0, 1)
        top.addWidget(self.measurement_athlete, 1, 0)
        top.addWidget(self.saved_measurement, 1, 1)
        top.setColumnStretch(0, 1)
        top.setColumnStretch(1, 1)
        outer.addLayout(top)

        fields_box = QGroupBox("검사 기본 정보")
        grid = QGridLayout(fields_box)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        self.test_date = QDateEdit()
        self.test_date.setCalendarPopup(True)
        self.test_date.setDisplayFormat("yyyy-MM-dd")
        self.test_date.setDate(QDate.currentDate())

        self.height = self._double_spin(0.1, 1)
        self.weight = self._double_spin(0.1, 1)
        self.bmi = self._double_spin(0.1, 1)
        self.vo2max = self._double_spin(0.01, 2, maximum=200)
        self.hrmax = QSpinBox()
        self.hrmax.setRange(0, 300)
        self.exercise_time = QLineEdit()
        self.exercise_time.setPlaceholderText("예: 30분")

        self.load_type = QComboBox()
        self.load_type.addItems(["Speed", "Power"])
        self.load_type.currentTextChanged.connect(
            self.update_load_label
        )

        self.max_load = self._double_spin(0.1, 2, maximum=5000)
        self.grade_percent = self._double_spin(0.1, 1, maximum=100)
        self.stage_duration = QSpinBox()
        self.stage_duration.setRange(1, 60)
        self.stage_duration.setValue(3)
        self.rest_duration = QSpinBox()
        self.rest_duration.setRange(1, 60)
        self.rest_duration.setValue(1)

        row1 = [
            ("측정 날짜", self.test_date),
            ("신장(cm)", self.height),
            ("체중(kg)", self.weight),
            ("BMI(kg/m²)", self.bmi),
        ]
        row2 = [
            ("최대 산소 섭취량(ml/kg/min)", self.vo2max),
            ("최대 심박수(beats/min)", self.hrmax),
            ("운동 시간", self.exercise_time),
            ("부하 단위", self.load_type),
        ]
        self.max_load_label = QLabel("최대 Speed(km/h)")

        for col, (label, widget) in enumerate(row1):
            grid.addWidget(QLabel(label), 0, col)
            grid.addWidget(widget, 1, col)

        for col, (label, widget) in enumerate(row2):
            grid.addWidget(QLabel(label), 2, col)
            grid.addWidget(widget, 3, col)

        grid.addWidget(self.max_load_label, 4, 0)
        grid.addWidget(QLabel("경사도(%)"), 4, 1)
        grid.addWidget(QLabel("일반 운동 Stage 시간(분)"), 4, 2)
        grid.addWidget(QLabel("Rest 시간(분)"), 4, 3)
        grid.addWidget(self.max_load, 5, 0)
        grid.addWidget(self.grade_percent, 5, 1)
        grid.addWidget(self.stage_duration, 5, 2)
        grid.addWidget(self.rest_duration, 5, 3)

        for col in range(4):
            grid.setColumnStretch(col, 1)

        outer.addWidget(fields_box)

        action_row = QHBoxLayout()
        save_button = QPushButton("측정 정보 저장")
        save_button.clicked.connect(self.save_current_measurement)
        template_button = QPushButton("Excel 입력 양식 저장")
        template_button.clicked.connect(self.save_input_template)
        action_row.addWidget(save_button)
        action_row.addWidget(template_button)
        action_row.addStretch()
        outer.addLayout(action_row)

        upload_box = QGroupBox("Excel 원자료")
        upload_layout = QGridLayout(upload_box)
        self.excel_path = QLineEdit()
        self.excel_path.setReadOnly(True)
        browse_button = QPushButton("Excel 파일 선택")
        browse_button.clicked.connect(self.choose_excel_file)
        parse_button = QPushButton("Excel 읽기")
        parse_button.clicked.connect(self.parse_selected_excel)

        upload_layout.addWidget(self.excel_path, 0, 0)
        upload_layout.addWidget(browse_button, 0, 1)
        upload_layout.addWidget(parse_button, 0, 2)

        self.summary_table = QTableWidget(0, 8)
        self.summary_table.setHorizontalHeaderLabels(
            [
                "Stage",
                "Duration",
                "HR min",
                "HR max",
                "HR mean",
                "VO2 min",
                "VO2 max",
                "VO2 mean",
            ]
        )
        self.summary_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.summary_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        upload_layout.addWidget(self.summary_table, 1, 0, 1, 3)

        outer.addWidget(upload_box, 1)
        return page

    # ---------- Analysis tab ----------

    def _build_analysis_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        options = QHBoxLayout()
        self.show_lt1 = QCheckBox("LT1 계산 및 표시")
        self.show_lt1.setChecked(True)
        self.show_lt2 = QCheckBox("LT2 계산 및 표시")
        self.show_lt2.setChecked(True)
        options.addWidget(self.show_lt1)
        options.addWidget(self.show_lt2)
        options.addStretch()
        layout.addLayout(options)

        lactate_box = QGroupBox("혈중 젖산염 입력")
        lactate_layout = QVBoxLayout(lactate_box)
        self.lactate_table = QTableWidget(0, 3)
        self.lactate_table.setHorizontalHeaderLabels(
            ["Stage", "Load", "혈중 젖산염(mmol/L)"]
        )
        self.lactate_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        lactate_layout.addWidget(self.lactate_table)

        analyze_button = QPushButton("분석 실행")
        analyze_button.clicked.connect(self.run_analysis)
        lactate_layout.addWidget(analyze_button)
        layout.addWidget(lactate_box)

        self.lt1_result = QLabel("LT1: 분석 전")
        self.lt2_result = QLabel("LT2: 분석 전")
        results = QHBoxLayout()
        results.addWidget(self.lt1_result)
        results.addWidget(self.lt2_result)
        layout.addLayout(results)

        graph_splitter = QSplitter(Qt.Vertical)

        self.lactate_graph = self._graph_panel("혈중 젖산염 그래프")
        self.basic_graph = self._graph_panel(
            "1페이지용 HR 및 VO2 그래프"
        )
        self.combined_graph = self._graph_panel(
            "2페이지용 HR, VO2 및 Lactate 그래프"
        )

        graph_splitter.addWidget(self.lactate_graph["container"])
        graph_splitter.addWidget(self.basic_graph["container"])
        graph_splitter.addWidget(self.combined_graph["container"])
        graph_splitter.setSizes([300, 360, 360])
        layout.addWidget(graph_splitter, 1)
        return page

    # ---------- Report tab ----------

    def _build_report_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        toolbar = QToolBar()
        toolbar.setMovable(False)

        apply_button = QPushButton("수정 내용 적용")
        apply_button.clicked.connect(self.apply_report_edits)
        pdf_button = QPushButton("PDF 결과지 저장")
        pdf_button.clicked.connect(self.save_report_pdf)
        excel_button = QPushButton("Excel 결과 저장")
        excel_button.clicked.connect(self.save_report_excel)

        for text, command in [
            ("굵게", "bold"),
            ("기울임", "italic"),
            ("밑줄", "underline"),
        ]:
            button = QPushButton(text)
            button.clicked.connect(
                lambda _checked=False, cmd=command: self.exec_report_command(
                    cmd
                )
            )
            toolbar.addWidget(button)

        toolbar.addSeparator()

        for text, color in [
            ("빨강", "#D7191C"),
            ("파랑", "#2679D9"),
            ("검정", "#111111"),
        ]:
            button = QPushButton(text)
            button.clicked.connect(
                lambda _checked=False, value=color: self.set_report_color(
                    value
                )
            )
            toolbar.addWidget(button)

        clear_button = QPushButton("서식 지우기")
        clear_button.clicked.connect(
            lambda: self.exec_report_command("removeFormat")
        )
        toolbar.addWidget(clear_button)
        toolbar.addSeparator()
        toolbar.addWidget(apply_button)
        toolbar.addSeparator()
        toolbar.addWidget(pdf_button)
        toolbar.addWidget(excel_button)

        layout.addWidget(toolbar)

        self.report_status = QLabel(
            "분석을 실행하면 결과지가 표시됩니다."
        )
        self.report_status.setStyleSheet("color:#667085;")
        layout.addWidget(self.report_status)

        self.report_view = QWebEngineView()

        profile = QWebEngineProfile.defaultProfile()
        self.interceptor = LocalOnlyInterceptor(self)
        profile.setUrlRequestInterceptor(self.interceptor)

        self.report_view.setContextMenuPolicy(Qt.NoContextMenu)
        layout.addWidget(self.report_view, 1)
        return page

    # ---------- Helpers ----------

    def _double_spin(
        self,
        step: float,
        decimals: int,
        *,
        maximum: float = 1000,
    ) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(0, maximum)
        widget.setDecimals(decimals)
        widget.setSingleStep(step)
        return widget

    def _graph_panel(self, title: str) -> dict[str, Any]:
        container = QGroupBox(title)
        layout = QVBoxLayout(container)
        label = QLabel("분석 결과 없음")
        label.setAlignment(Qt.AlignCenter)
        label.setMinimumHeight(220)
        label.setStyleSheet("background:#FAFAFA; color:#667085;")
        layout.addWidget(label)
        return {"container": container, "label": label}

    def _current_athlete(self) -> dict[str, Any] | None:
        athlete_id = self.measurement_athlete.currentData()
        if athlete_id is None:
            return None
        for athlete in self.athletes:
            if int(athlete["id"]) == int(athlete_id):
                return athlete
        return None

    def _current_meta(self) -> dict[str, Any]:
        athlete = self._current_athlete()
        if athlete is None:
            raise ValueError("선수를 먼저 선택하세요.")

        load_type = self.load_type.currentText()
        qdate = self.test_date.date()
        return {
            "athlete": athlete,
            "test_date": dt.date(
                qdate.year(),
                qdate.month(),
                qdate.day(),
            ),
            "height": self.height.value(),
            "weight": self.weight.value(),
            "bmi": self.bmi.value(),
            "vo2max": self.vo2max.value(),
            "hrmax": self.hrmax.value(),
            "exercise_time": self.exercise_time.text().strip(),
            "load_type": load_type,
            "load_unit": "km/h" if load_type == "Speed" else "watt",
            "max_load": self.max_load.value(),
            "grade_percent": self.grade_percent.value(),
            "stage_duration_min": self.stage_duration.value(),
            "rest_duration_min": self.rest_duration.value(),
            "show_lt1": self.show_lt1.isChecked(),
            "show_lt2": self.show_lt2.isChecked(),
        }

    def _error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def _success(self, message: str) -> None:
        self.statusBar().showMessage(message, 5000)

    # ---------- Athlete actions ----------

    def refresh_athletes(self) -> None:
        try:
            current_id = self.measurement_athlete.currentData()
            self.athletes = list_athletes()

            self.athlete_table.setRowCount(len(self.athletes))
            for row, athlete in enumerate(self.athletes):
                for col, key in enumerate(["name", "sex", "category"]):
                    self.athlete_table.setItem(
                        row,
                        col,
                        QTableWidgetItem(str(athlete[key])),
                    )

            self.measurement_athlete.blockSignals(True)
            self.measurement_athlete.clear()
            for athlete in self.athletes:
                self.measurement_athlete.addItem(
                    (
                        f"{athlete['name']} "
                        f"({athlete['sex']} / {athlete['category']})"
                    ),
                    int(athlete["id"]),
                )

            if current_id is not None:
                idx = self.measurement_athlete.findData(current_id)
                if idx >= 0:
                    self.measurement_athlete.setCurrentIndex(idx)
            self.measurement_athlete.blockSignals(False)
            self.on_measurement_athlete_changed()
        except Exception as exc:
            self._error(
                "선수 목록 오류",
                f"선수 목록을 불러오지 못했습니다.\n{exc}",
            )

    def register_athlete(self) -> None:
        try:
            athlete = add_athlete(
                self.athlete_name.text(),
                self.athlete_sex.currentText(),
                self.athlete_category.currentText(),
            )
            self.athlete_name.clear()
            self.refresh_athletes()
            idx = self.measurement_athlete.findData(
                int(athlete["id"])
            )
            if idx >= 0:
                self.measurement_athlete.setCurrentIndex(idx)
            self._success(f"{athlete['name']} 선수를 저장했습니다.")
        except Exception as exc:
            self._error("선수 저장 오류", str(exc))

    # ---------- Measurement actions ----------

    def on_measurement_athlete_changed(self, *_args: Any) -> None:
        athlete = self._current_athlete()
        self.measurements = []
        self.saved_measurement.blockSignals(True)
        self.saved_measurement.clear()
        self.saved_measurement.addItem("새 측정", None)

        if athlete is not None:
            try:
                self.measurements = list_measurements(
                    int(athlete["id"])
                )
                for item in self.measurements:
                    self.saved_measurement.addItem(
                        str(item["test_date"]),
                        int(item["id"]),
                    )
            except Exception as exc:
                self._error("측정 기록 오류", str(exc))

        self.saved_measurement.blockSignals(False)
        self.fill_measurement(None)

    def on_saved_measurement_changed(self, *_args: Any) -> None:
        measurement_id = self.saved_measurement.currentData()
        selected = next(
            (
                item
                for item in self.measurements
                if item["id"] == measurement_id
            ),
            None,
        )
        self.fill_measurement(selected)

    def fill_measurement(
        self,
        measurement: dict[str, Any] | None,
    ) -> None:
        if measurement is None:
            self.test_date.setDate(QDate.currentDate())
            self.height.setValue(0)
            self.weight.setValue(0)
            self.bmi.setValue(0)
            self.vo2max.setValue(0)
            self.hrmax.setValue(0)
            self.exercise_time.clear()
            self.load_type.setCurrentText("Speed")
            self.max_load.setValue(0)
            self.grade_percent.setValue(0)
            self.stage_duration.setValue(3)
            self.rest_duration.setValue(1)
            return

        date_value = dt.date.fromisoformat(
            str(measurement["test_date"])
        )
        self.test_date.setDate(
            QDate(
                date_value.year,
                date_value.month,
                date_value.day,
            )
        )
        self.height.setValue(float(measurement.get("height") or 0))
        self.weight.setValue(float(measurement.get("weight") or 0))
        self.bmi.setValue(float(measurement.get("bmi") or 0))
        self.vo2max.setValue(float(measurement.get("vo2max") or 0))
        self.hrmax.setValue(int(measurement.get("hrmax") or 0))
        self.exercise_time.setText(
            str(measurement.get("exercise_time") or "")
        )
        self.load_type.setCurrentText(
            str(measurement.get("load_type") or "Speed")
        )
        self.max_load.setValue(float(measurement.get("max_load") or 0))
        self.grade_percent.setValue(
            float(measurement.get("grade_percent") or 0)
        )
        self.stage_duration.setValue(
            max(
                1,
                int(
                    round(
                        float(
                            measurement.get(
                                "stage_duration_min"
                            )
                            or 3
                        )
                    )
                ),
            )
        )
        self.rest_duration.setValue(
            max(
                1,
                int(
                    round(
                        float(
                            measurement.get(
                                "rest_duration_min"
                            )
                            or 1
                        )
                    )
                ),
            )
        )

    def update_load_label(self, load_type: str) -> None:
        if load_type == "Power":
            self.max_load_label.setText("최대 Power(watt)")
        else:
            self.max_load_label.setText("최대 Speed(km/h)")

    def save_current_measurement(self) -> None:
        try:
            meta = self._current_meta()
            athlete = meta["athlete"]
            saved = save_measurement(
                athlete_id=int(athlete["id"]),
                test_date=meta["test_date"].isoformat(),
                height=meta["height"],
                weight=meta["weight"],
                bmi=meta["bmi"],
                vo2max=meta["vo2max"],
                hrmax=meta["hrmax"],
                exercise_time=meta["exercise_time"],
                load_type=meta["load_type"],
                max_load=meta["max_load"],
                grade_percent=meta["grade_percent"],
                stage_duration_min=meta["stage_duration_min"],
                rest_duration_min=meta["rest_duration_min"],
            )
            self.on_measurement_athlete_changed()
            idx = self.saved_measurement.findData(
                int(saved["id"])
            )
            if idx >= 0:
                self.saved_measurement.setCurrentIndex(idx)
            self._success("측정 정보를 저장했습니다.")
        except Exception as exc:
            self._error("측정 정보 저장 오류", str(exc))

    def save_input_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Excel 입력 양식 저장",
            str(ROOT / "NGC_CPET_입력양식.xlsx"),
            "Excel Workbook (*.xlsx)",
        )
        if not path:
            return
        try:
            Path(path).write_bytes(build_input_template())
            self._success("Excel 입력 양식을 저장했습니다.")
        except Exception as exc:
            self._error("양식 저장 오류", str(exc))

    def choose_excel_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Excel 파일 선택",
            str(ROOT),
            "Excel Workbook (*.xlsx *.xlsm)",
        )
        if path:
            self.excel_path.setText(path)

    def parse_selected_excel(self) -> None:
        path = self.excel_path.text().strip()
        if not path:
            self._error("Excel 입력", "Excel 파일을 먼저 선택하세요.")
            return

        try:
            meta = self._current_meta()
            with open(path, "rb") as handle:
                df, segments, summary = excel_parser.parse_excel(
                    handle,
                    stage_duration_min=meta["stage_duration_min"],
                    rest_duration_min=meta["rest_duration_min"],
                    allout_load=(
                        meta["max_load"]
                        if meta["max_load"] > 0
                        else None
                    ),
                )

            with open(path, "rb") as handle:
                imported_lactate = parse_lactate_sheet(handle)

            self.parsed = {
                "df": df,
                "segments": segments,
                "summary": summary,
                "lactate_rows": imported_lactate,
            }
            self.meta = meta
            self.analysis = None
            self.report_data = None
            self.final_html = None
            self.editable_html = None

            rows = summary_records(summary)
            self.summary_table.setRowCount(len(rows))
            keys = [
                "Stage",
                "Duration",
                "HR_min",
                "HR_max",
                "HR_mean",
                "VO2_min",
                "VO2_max",
                "VO2_mean",
            ]
            for row_index, row in enumerate(rows):
                for col, key in enumerate(keys):
                    value = row.get(key)
                    self.summary_table.setItem(
                        row_index,
                        col,
                        QTableWidgetItem(
                            "-" if value is None else str(value)
                        ),
                    )

            self.lactate_rows = initial_lactate_rows(
                segments,
                imported_lactate,
                meta["max_load"],
            )
            self.populate_lactate_table()
            self.tabs.setCurrentIndex(2)
            self._success("Excel 자료를 읽었습니다.")
        except Exception as exc:
            self._error("Excel 읽기 오류", str(exc))

    # ---------- Analysis actions ----------

    def populate_lactate_table(self) -> None:
        self.lactate_table.setRowCount(len(self.lactate_rows))
        for row, item in enumerate(self.lactate_rows):
            stage = QTableWidgetItem(str(item["stage"]))
            load = QTableWidgetItem(
                "-"
                if item["load"] is None
                else f"{float(item['load']):g}"
            )
            stage.setFlags(stage.flags() & ~Qt.ItemIsEditable)
            load.setFlags(load.flags() & ~Qt.ItemIsEditable)

            lactate = QTableWidgetItem(
                ""
                if item.get("lactate") is None
                else f"{float(item['lactate']):.2f}"
            )

            self.lactate_table.setItem(row, 0, stage)
            self.lactate_table.setItem(row, 1, load)
            self.lactate_table.setItem(row, 2, lactate)

    def collect_lactate_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in range(self.lactate_table.rowCount()):
            base = self.lactate_rows[row]
            item = self.lactate_table.item(row, 2)
            text = item.text().strip() if item else ""
            lactate = None if not text else float(text)
            rows.append(
                {
                    "stage": base["stage"],
                    "load": base["load"],
                    "lactate": lactate,
                }
            )
        return rows

    def run_analysis(self) -> None:
        if self.parsed is None:
            self._error(
                "분석",
                "검사 입력에서 Excel 파일을 먼저 읽으세요.",
            )
            return

        try:
            self.meta = self._current_meta()
            rows = self.collect_lactate_rows()
            self.analysis = analyze(
                self.parsed,
                self.meta,
                rows,
            )

            unit = self.meta["load_unit"]
            for label, key in [
                (self.lt1_result, "LT1"),
                (self.lt2_result, "LT2"),
            ]:
                item = lt_api_item(
                    self.analysis[key.lower()],
                    key,
                    self.analysis["threshold_hr"],
                    self.meta,
                )
                if not item.get("show"):
                    label.setText(f"{key}: 표시하지 않음")
                elif item.get("valid"):
                    hr_text = (
                        f" | {item['hr']} bpm"
                        if item.get("hr") is not None
                        else ""
                    )
                    label.setText(
                        f"{key} = {item['load']:.2f} {unit}{hr_text}"
                    )
                    label.setStyleSheet(
                        "background:#ECFDF3; padding:10px;"
                        "border:1px solid #B7E4C7;"
                    )
                else:
                    label.setText(
                        f"{key} 산출 불가: {item.get('reason', '')}"
                    )
                    label.setStyleSheet(
                        "background:#FFF8E8; padding:10px;"
                        "border:1px solid #F0D4A0;"
                    )

            self._set_graph(
                self.lactate_graph["label"],
                self.analysis.get("lactate_png"),
            )
            self._set_graph(
                self.basic_graph["label"],
                self.analysis.get("basic_png"),
            )
            self._set_graph(
                self.combined_graph["label"],
                self.analysis.get("combined_analysis_png"),
            )

            if (
                self.analysis.get("basic_png") is not None
                and self.analysis.get("combined_report_png") is not None
            ):
                (
                    self.report_data,
                    self.editable_html,
                    self.final_html,
                ) = build_report_htmls(
                    self.parsed,
                    self.meta,
                    self.analysis,
                )
                self.report_view.setHtml(
                    self.editable_html,
                    QUrl.fromLocalFile(str(ROOT) + "/"),
                )
                self.report_status.setText(
                    "점선 영역을 직접 수정한 뒤 수정 내용 적용을 누르세요."
                )
            else:
                self.report_status.setText(
                    "최대 심박수를 입력해야 결과지를 생성할 수 있습니다."
                )

            self._success("분석이 완료되었습니다.")
        except Exception as exc:
            self._error("분석 오류", str(exc))

    def _set_graph(
        self,
        label: QLabel,
        png: bytes | None,
    ) -> None:
        if not png:
            label.setText("그래프 없음")
            label.setPixmap(QPixmap())
            return
        pixmap = QPixmap()
        pixmap.loadFromData(png)
        label.setPixmap(
            pixmap.scaled(
                1250,
                520,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    # ---------- Report actions ----------

    def exec_report_command(self, command: str) -> None:
        script = (
            "(() => {"
            "const s=window.getSelection();"
            "if(!s || s.rangeCount===0 || s.isCollapsed) return false;"
            f"document.execCommand('{command}', false, null);"
            "return true;"
            "})()"
        )
        self.report_view.page().runJavaScript(script)

    def set_report_color(self, color: str) -> None:
        script = (
            "(() => {"
            "const s=window.getSelection();"
            "if(!s || s.rangeCount===0 || s.isCollapsed) return false;"
            f"document.execCommand('foreColor', false, '{color}');"
            "return true;"
            "})()"
        )
        self.report_view.page().runJavaScript(script)

    def _collect_report_comments(
        self,
        callback: Callable[[dict[str, str]], None],
    ) -> None:
        script = """
        (() => {
          const out = {};
          document.querySelectorAll('[data-edit-key]').forEach((el) => {
            out[el.dataset.editKey] = el.innerHTML;
          });
          return out;
        })()
        """
        self.report_view.page().runJavaScript(
            script,
            lambda result: callback(
                result if isinstance(result, dict) else {}
            ),
        )

    def apply_report_edits(self) -> None:
        if (
            self.parsed is None
            or self.meta is None
            or self.analysis is None
        ):
            self._error("결과지", "분석을 먼저 실행하세요.")
            return

        def done(comments: dict[str, str]) -> None:
            try:
                (
                    self.report_data,
                    self.editable_html,
                    self.final_html,
                ) = build_report_htmls(
                    self.parsed,
                    self.meta,
                    self.analysis,
                    comments,
                )
                self.report_view.setHtml(
                    self.editable_html,
                    QUrl.fromLocalFile(str(ROOT) + "/"),
                )
                self.report_status.setText(
                    "수정 내용이 적용되었습니다."
                )
                self._success("결과지 수정 내용을 적용했습니다.")
            except Exception as exc:
                self._error("결과지 수정 오류", str(exc))

        self._collect_report_comments(done)

    def save_report_excel(self) -> None:
        if (
            self.parsed is None
            or self.meta is None
            or self.analysis is None
        ):
            self._error("Excel 결과", "분석을 먼저 실행하세요.")
            return

        def export(comments: dict[str, str]) -> None:
            try:
                report_data, editable, final = build_report_htmls(
                    self.parsed,
                    self.meta,
                    self.analysis,
                    comments,
                )
                self.report_data = report_data
                self.editable_html = editable
                self.final_html = final

                data = build_excel_bytes(
                    report_data,
                    self.parsed,
                    self.analysis,
                )
                default_name = (
                    f"{self.meta['test_date']}_"
                    f"{self.meta['athlete']['name']}_결과.xlsx"
                )
                path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Excel 결과 저장",
                    str(ROOT / default_name),
                    "Excel Workbook (*.xlsx)",
                )
                if not path:
                    return
                Path(path).write_bytes(data)
                self._success("Excel 결과를 저장했습니다.")
            except Exception as exc:
                self._error("Excel 결과 저장 오류", str(exc))

        self._collect_report_comments(export)

    def save_report_pdf(self) -> None:
        if (
            self.parsed is None
            or self.meta is None
            or self.analysis is None
        ):
            self._error("PDF 결과", "분석을 먼저 실행하세요.")
            return

        def print_pdf(comments: dict[str, str]) -> None:
            try:
                (
                    self.report_data,
                    _editable,
                    final_html,
                ) = build_report_htmls(
                    self.parsed,
                    self.meta,
                    self.analysis,
                    comments,
                )
                self.final_html = final_html

                default_name = (
                    f"{self.meta['test_date']}_"
                    f"{self.meta['athlete']['name']}_피드백.pdf"
                )
                path, _ = QFileDialog.getSaveFileName(
                    self,
                    "PDF 결과지 저장",
                    str(ROOT / default_name),
                    "PDF (*.pdf)",
                )
                if not path:
                    return

                page = QWebEnginePage(
                    self.report_view.page().profile(),
                    self,
                )

                def do_print(ok: bool) -> None:
                    if not ok:
                        self._error(
                            "PDF 결과",
                            "PDF용 결과지 HTML을 불러오지 못했습니다.",
                        )
                        page.deleteLater()
                        return

                    def finished(file_path: str, success: bool) -> None:
                        if success:
                            self._success("PDF 결과지를 저장했습니다.")
                        else:
                            self._error(
                                "PDF 결과",
                                "PDF 결과지 저장에 실패했습니다.",
                            )
                        page.deleteLater()

                    page.pdfPrintingFinished.connect(finished)
                    page.printToPdf(path)

                page.loadFinished.connect(do_print)
                page.setHtml(
                    final_html,
                    QUrl.fromLocalFile(str(ROOT) + "/"),
                )
            except Exception as exc:
                self._error("PDF 결과 저장 오류", str(exc))

        self._collect_report_comments(print_pdf)
