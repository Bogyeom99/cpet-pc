from __future__ import annotations

import datetime as dt
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk
from typing import Any

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
from services.win_pdf import save_report_pdf
from services.workflow import (
    analyze,
    build_excel_bytes,
    build_report_data,
    initial_lactate_rows,
    lt_api_item,
    summary_records,
)
from ui.graph_canvas import GraphCanvas


ROOT = Path(__file__).resolve().parent.parent


class ScrollableFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(
            self,
            background="#F4F6F8",
            highlightthickness=0,
        )
        self.scrollbar = ttk.Scrollbar(
            self,
            orient="vertical",
            command=self.canvas.yview,
        )
        self.inner = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window(
            (0, 0),
            window=self.inner,
            anchor="nw",
        )

        self.canvas.configure(
            yscrollcommand=self.scrollbar.set
        )
        self.canvas.pack(
            side="left",
            fill="both",
            expand=True,
        )
        self.scrollbar.pack(
            side="right",
            fill="y",
        )

        self.inner.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            ),
        )
        self.canvas.bind(
            "<Configure>",
            self._resize_inner,
        )

    def _resize_inner(self, event):
        self.canvas.itemconfigure(
            self.window_id,
            width=event.width,
        )


class MainWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("NGC CPET PC")
        self.geometry("1500x930")
        self.minsize(1180, 760)

        self.athletes: list[dict[str, Any]] = []
        self.measurements: list[dict[str, Any]] = []
        self.parsed: dict[str, Any] | None = None
        self.meta: dict[str, Any] | None = None
        self.analysis: dict[str, Any] | None = None
        self.report_data: dict[str, Any] | None = None
        self.lactate_rows: list[dict[str, Any]] = []
        self.lactate_entries: list[tk.Entry] = []
        self.report_texts: dict[str, tk.Text] = {}
        self._current_report_text: tk.Text | None = None

        self._setup_style()
        self._build_ui()
        self.refresh_athletes()

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        style.configure(
            "Title.TLabel",
            font=("Malgun Gothic", 20, "bold"),
            foreground="#123A79",
        )
        style.configure(
            "Muted.TLabel",
            font=("Malgun Gothic", 9),
            foreground="#667085",
        )
        style.configure(
            "Section.TLabel",
            font=("Malgun Gothic", 11, "bold"),
            foreground="#111111",
        )
        style.configure(
            "TNotebook.Tab",
            padding=(18, 9),
            font=("Malgun Gothic", 9, "bold"),
        )
        style.configure(
            "Primary.TButton",
            font=("Malgun Gothic", 9, "bold"),
        )

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=(18, 12, 18, 16))
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 10))

        title_box = ttk.Frame(header)
        title_box.pack(side="left")
        ttk.Label(
            title_box,
            text="NGC CPET 피드백지 제작",
            style="Title.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            title_box,
            text=(
                "선수 정보와 측정 자료는 외부 저장소 없이 "
                "이 PC 안에서만 처리됩니다."
            ),
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(3, 0))

        badge = tk.Label(
            header,
            text="LOCAL ONLY",
            bg="#ECFDF3",
            fg="#067647",
            font=("Malgun Gothic", 9, "bold"),
            padx=10,
            pady=5,
        )
        badge.pack(side="right", padx=8)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)

        self.athlete_tab = ttk.Frame(
            self.notebook,
            padding=14,
        )
        self.measurement_tab = ttk.Frame(
            self.notebook,
            padding=14,
        )
        self.analysis_tab = ttk.Frame(
            self.notebook,
            padding=14,
        )
        self.report_tab = ttk.Frame(
            self.notebook,
            padding=0,
        )

        self.notebook.add(
            self.athlete_tab,
            text="1 선수 등록",
        )
        self.notebook.add(
            self.measurement_tab,
            text="2 검사 입력",
        )
        self.notebook.add(
            self.analysis_tab,
            text="3 분석",
        )
        self.notebook.add(
            self.report_tab,
            text="4 결과지",
        )

        self._build_athlete_tab()
        self._build_measurement_tab()
        self._build_analysis_tab()
        self._build_report_tab()

        self.status_var = tk.StringVar(value="준비됨")
        status = ttk.Label(
            root,
            textvariable=self.status_var,
            style="Muted.TLabel",
        )
        status.pack(fill="x", pady=(7, 0))

    # ---------- Athlete ----------

    def _build_athlete_tab(self) -> None:
        ttk.Label(
            self.athlete_tab,
            text=(
                "등록한 선수와 측정 기록은 "
                "data/cpet.db에 저장됩니다."
            ),
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 10))

        form = ttk.LabelFrame(
            self.athlete_tab,
            text="선수 등록",
            padding=12,
        )
        form.pack(fill="x")

        for col in range(4):
            form.columnconfigure(col, weight=1)

        ttk.Label(form, text="선수 이름").grid(
            row=0,
            column=0,
            sticky="w",
            padx=5,
        )
        ttk.Label(form, text="성별").grid(
            row=0,
            column=1,
            sticky="w",
            padx=5,
        )
        ttk.Label(form, text="구분").grid(
            row=0,
            column=2,
            sticky="w",
            padx=5,
        )

        self.athlete_name_var = tk.StringVar()
        self.athlete_sex_var = tk.StringVar(value="남")
        self.athlete_category_var = tk.StringVar(
            value="국가대표 후보"
        )

        ttk.Entry(
            form,
            textvariable=self.athlete_name_var,
        ).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=5,
            pady=5,
        )

        ttk.Combobox(
            form,
            textvariable=self.athlete_sex_var,
            values=["남", "여"],
            state="readonly",
        ).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=5,
            pady=5,
        )

        ttk.Combobox(
            form,
            textvariable=self.athlete_category_var,
            values=[
                "국가대표 후보",
                "청소년 대표",
                "꿈나무",
            ],
            state="readonly",
        ).grid(
            row=1,
            column=2,
            sticky="ew",
            padx=5,
            pady=5,
        )

        ttk.Button(
            form,
            text="선수 등록",
            style="Primary.TButton",
            command=self.register_athlete,
        ).grid(
            row=1,
            column=3,
            sticky="ew",
            padx=5,
            pady=5,
        )

        actions = ttk.Frame(self.athlete_tab)
        actions.pack(fill="x", pady=10)
        ttk.Button(
            actions,
            text="선수 목록 새로고침",
            command=self.refresh_athletes,
        ).pack(side="left")

        columns = ("name", "sex", "category")
        self.athlete_tree = ttk.Treeview(
            self.athlete_tab,
            columns=columns,
            show="headings",
            height=15,
        )
        for key, label in [
            ("name", "이름"),
            ("sex", "성별"),
            ("category", "구분"),
        ]:
            self.athlete_tree.heading(
                key,
                text=label,
            )
            self.athlete_tree.column(
                key,
                anchor="center",
                stretch=True,
            )
        self.athlete_tree.pack(
            fill="both",
            expand=True,
        )

    # ---------- Measurement ----------

    def _build_measurement_tab(self) -> None:
        selector = ttk.Frame(self.measurement_tab)
        selector.pack(fill="x", pady=(0, 12))
        selector.columnconfigure(0, weight=1)
        selector.columnconfigure(1, weight=1)

        ttk.Label(
            selector,
            text="선수 선택",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=5,
        )
        ttk.Label(
            selector,
            text="기존 측정 기록",
        ).grid(
            row=0,
            column=1,
            sticky="w",
            padx=5,
        )

        self.measurement_athlete_var = tk.StringVar()
        self.measurement_athlete_combo = ttk.Combobox(
            selector,
            textvariable=self.measurement_athlete_var,
            state="readonly",
        )
        self.measurement_athlete_combo.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=5,
            pady=5,
        )
        self.measurement_athlete_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.on_measurement_athlete_changed(),
        )

        self.saved_measurement_var = tk.StringVar()
        self.saved_measurement_combo = ttk.Combobox(
            selector,
            textvariable=self.saved_measurement_var,
            state="readonly",
        )
        self.saved_measurement_combo.grid(
            row=1,
            column=1,
            sticky="ew",
            padx=5,
            pady=5,
        )
        self.saved_measurement_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.on_saved_measurement_changed(),
        )

        fields = ttk.LabelFrame(
            self.measurement_tab,
            text="검사 기본 정보",
            padding=10,
        )
        fields.pack(fill="x")
        for col in range(4):
            fields.columnconfigure(col, weight=1)

        self.test_date_var = tk.StringVar(
            value=dt.date.today().isoformat()
        )
        self.height_var = tk.StringVar(value="0")
        self.weight_var = tk.StringVar(value="0")
        self.bmi_var = tk.StringVar(value="0")
        self.vo2max_var = tk.StringVar(value="0")
        self.hrmax_var = tk.StringVar(value="0")
        self.exercise_time_var = tk.StringVar()
        self.load_type_var = tk.StringVar(value="Speed")
        self.max_load_var = tk.StringVar(value="0")
        self.grade_var = tk.StringVar(value="0")
        self.stage_duration_var = tk.StringVar(value="3")
        self.rest_duration_var = tk.StringVar(value="1")

        self._field(
            fields,
            0,
            0,
            "측정 날짜",
            self.test_date_var,
        )
        self._field(
            fields,
            0,
            1,
            "신장(cm)",
            self.height_var,
        )
        self._field(
            fields,
            0,
            2,
            "체중(kg)",
            self.weight_var,
        )
        self._field(
            fields,
            0,
            3,
            "BMI(kg/m²)",
            self.bmi_var,
        )

        self._field(
            fields,
            2,
            0,
            "최대 산소 섭취량(ml/kg/min)",
            self.vo2max_var,
        )
        self._field(
            fields,
            2,
            1,
            "최대 심박수(beats/min)",
            self.hrmax_var,
        )
        self._field(
            fields,
            2,
            2,
            "운동 시간",
            self.exercise_time_var,
        )

        ttk.Label(
            fields,
            text="부하 단위",
        ).grid(
            row=2,
            column=3,
            sticky="w",
            padx=5,
            pady=(6, 2),
        )
        load_combo = ttk.Combobox(
            fields,
            textvariable=self.load_type_var,
            values=["Speed", "Power"],
            state="readonly",
        )
        load_combo.grid(
            row=3,
            column=3,
            sticky="ew",
            padx=5,
            pady=(0, 7),
        )
        load_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.update_load_label(),
        )

        self.max_load_label = ttk.Label(
            fields,
            text="최대 Speed(km/h)",
        )
        self.max_load_label.grid(
            row=4,
            column=0,
            sticky="w",
            padx=5,
            pady=(6, 2),
        )
        ttk.Entry(
            fields,
            textvariable=self.max_load_var,
        ).grid(
            row=5,
            column=0,
            sticky="ew",
            padx=5,
            pady=(0, 7),
        )

        self._field(
            fields,
            4,
            1,
            "경사도(%)",
            self.grade_var,
        )
        self._field(
            fields,
            4,
            2,
            "일반 운동 Stage 시간(분)",
            self.stage_duration_var,
        )
        self._field(
            fields,
            4,
            3,
            "Rest 시간(분)",
            self.rest_duration_var,
        )

        actions = ttk.Frame(self.measurement_tab)
        actions.pack(fill="x", pady=10)

        ttk.Button(
            actions,
            text="측정 정보 저장",
            command=self.save_current_measurement,
        ).pack(side="left", padx=(0, 7))

        ttk.Button(
            actions,
            text="Excel 입력 양식 저장",
            command=self.save_input_template,
        ).pack(side="left")

        excel_box = ttk.LabelFrame(
            self.measurement_tab,
            text="Excel 원자료",
            padding=10,
        )
        excel_box.pack(
            fill="both",
            expand=True,
        )
        excel_box.columnconfigure(0, weight=1)
        excel_box.rowconfigure(2, weight=1)

        self.excel_path_var = tk.StringVar()
        ttk.Entry(
            excel_box,
            textvariable=self.excel_path_var,
            state="readonly",
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 6),
        )
        ttk.Button(
            excel_box,
            text="Excel 파일 선택",
            command=self.choose_excel_file,
        ).grid(
            row=0,
            column=1,
            padx=3,
        )
        ttk.Button(
            excel_box,
            text="Excel 읽기",
            command=self.parse_selected_excel,
        ).grid(
            row=0,
            column=2,
            padx=3,
        )

        ttk.Label(
            excel_box,
            text=(
                "숫자 Stage와 Rest는 위에서 설정한 시간으로 "
                "그래프에 맞춰 정규화됩니다."
            ),
            style="Muted.TLabel",
        ).grid(
            row=1,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(8, 5),
        )

        columns = (
            "Stage",
            "Duration",
            "HR_min",
            "HR_max",
            "HR_mean",
            "VO2_min",
            "VO2_max",
            "VO2_mean",
        )
        self.summary_tree = ttk.Treeview(
            excel_box,
            columns=columns,
            show="headings",
        )
        for column in columns:
            self.summary_tree.heading(
                column,
                text=column,
            )
            self.summary_tree.column(
                column,
                width=90,
                anchor="center",
                stretch=True,
            )
        self.summary_tree.grid(
            row=2,
            column=0,
            columnspan=3,
            sticky="nsew",
            pady=(8, 0),
        )

    def _field(
        self,
        parent,
        row: int,
        col: int,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        ttk.Label(
            parent,
            text=label,
        ).grid(
            row=row,
            column=col,
            sticky="w",
            padx=5,
            pady=(6, 2),
        )
        ttk.Entry(
            parent,
            textvariable=variable,
        ).grid(
            row=row + 1,
            column=col,
            sticky="ew",
            padx=5,
            pady=(0, 7),
        )

    # ---------- Analysis ----------

    def _build_analysis_tab(self) -> None:
        option_row = ttk.Frame(self.analysis_tab)
        option_row.pack(fill="x", pady=(0, 8))

        self.show_lt1_var = tk.BooleanVar(value=True)
        self.show_lt2_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(
            option_row,
            text="LT1 계산 및 표시",
            variable=self.show_lt1_var,
        ).pack(side="left", padx=(0, 20))
        ttk.Checkbutton(
            option_row,
            text="LT2 계산 및 표시",
            variable=self.show_lt2_var,
        ).pack(side="left")

        lactate_box = ttk.LabelFrame(
            self.analysis_tab,
            text="혈중 젖산염 입력",
            padding=10,
        )
        lactate_box.pack(fill="x")

        self.lactate_frame = ttk.Frame(lactate_box)
        self.lactate_frame.pack(fill="x")

        ttk.Button(
            lactate_box,
            text="분석 실행",
            style="Primary.TButton",
            command=self.run_analysis,
        ).pack(
            anchor="e",
            pady=(8, 0),
        )

        result_row = ttk.Frame(self.analysis_tab)
        result_row.pack(fill="x", pady=8)

        self.lt1_result_var = tk.StringVar(
            value="LT1: 분석 전"
        )
        self.lt2_result_var = tk.StringVar(
            value="LT2: 분석 전"
        )

        ttk.Label(
            result_row,
            textvariable=self.lt1_result_var,
        ).pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 5),
        )
        ttk.Label(
            result_row,
            textvariable=self.lt2_result_var,
        ).pack(
            side="left",
            fill="x",
            expand=True,
            padx=(5, 0),
        )

        graph_notebook = ttk.Notebook(
            self.analysis_tab
        )
        graph_notebook.pack(
            fill="both",
            expand=True,
        )

        frame1 = ttk.Frame(graph_notebook)
        frame2 = ttk.Frame(graph_notebook)
        frame3 = ttk.Frame(graph_notebook)

        graph_notebook.add(
            frame1,
            text="혈중 젖산염",
        )
        graph_notebook.add(
            frame2,
            text="HR 및 VO2",
        )
        graph_notebook.add(
            frame3,
            text="HR, VO2 및 Lactate",
        )

        self.lactate_graph = GraphCanvas(
            frame1,
            height=430,
        )
        self.lactate_graph.pack(
            fill="both",
            expand=True,
        )
        self.basic_graph = GraphCanvas(
            frame2,
            height=430,
        )
        self.basic_graph.pack(
            fill="both",
            expand=True,
        )
        self.combined_graph = GraphCanvas(
            frame3,
            height=430,
        )
        self.combined_graph.pack(
            fill="both",
            expand=True,
        )

    # ---------- Report ----------

    def _build_report_tab(self) -> None:
        toolbar = ttk.Frame(
            self.report_tab,
            padding=(10, 8),
        )
        toolbar.pack(fill="x")

        for text, command in [
            ("굵게", "bold"),
            ("기울임", "italic"),
            ("밑줄", "underline"),
        ]:
            ttk.Button(
                toolbar,
                text=text,
                command=lambda cmd=command: self.apply_text_style(
                    cmd
                ),
            ).pack(side="left", padx=2)

        ttk.Button(
            toolbar,
            text="빨강",
            command=lambda: self.apply_text_color(
                "#D7191C"
            ),
        ).pack(side="left", padx=(10, 2))
        ttk.Button(
            toolbar,
            text="파랑",
            command=lambda: self.apply_text_color(
                "#2679D9"
            ),
        ).pack(side="left", padx=2)
        ttk.Button(
            toolbar,
            text="검정",
            command=lambda: self.apply_text_color(
                "#111111"
            ),
        ).pack(side="left", padx=2)

        ttk.Button(
            toolbar,
            text="서식 지우기",
            command=self.clear_text_style,
        ).pack(side="left", padx=(10, 2))

        ttk.Button(
            toolbar,
            text="PDF 결과지 저장",
            command=self.save_report_pdf,
        ).pack(side="right", padx=2)
        ttk.Button(
            toolbar,
            text="Excel 결과 저장",
            command=self.save_report_excel,
        ).pack(side="right", padx=2)

        self.report_scroll = ScrollableFrame(
            self.report_tab
        )
        self.report_scroll.pack(
            fill="both",
            expand=True,
        )

        self.report_container = self.report_scroll.inner
        self._render_empty_report()

    def _render_empty_report(self) -> None:
        for child in self.report_container.winfo_children():
            child.destroy()

        ttk.Label(
            self.report_container,
            text="분석을 실행하면 결과지가 표시됩니다.",
            style="Muted.TLabel",
        ).pack(pady=40)

    def render_report(self) -> None:
        if (
            self.report_data is None
            or self.analysis is None
        ):
            self._render_empty_report()
            return

        for child in self.report_container.winfo_children():
            child.destroy()

        self.report_texts = {}
        self._current_report_text = None

        page1 = tk.Frame(
            self.report_container,
            bg="white",
            bd=1,
            relief="solid",
            padx=28,
            pady=22,
        )
        page1.pack(
            fill="x",
            padx=70,
            pady=(20, 15),
        )

        tk.Label(
            page1,
            text="차세대스포츠과학지원센터 체력측정 결과",
            bg="white",
            fg="#123A79",
            font=("Malgun Gothic", 18, "bold"),
        ).pack(pady=(0, 14))

        self._report_section_label(
            page1,
            "선수 정보",
        )
        info = ttk.Frame(page1)
        info.pack(fill="x", pady=(4, 10))
        self._report_value(
            info,
            0,
            "이름",
            self.report_data["name"],
        )
        self._report_value(
            info,
            1,
            "성별",
            self.report_data["sex"],
        )
        self._report_value(
            info,
            2,
            "구분",
            self.report_data["category"],
        )

        self._report_section_label(
            page1,
            "선수 체격 및 신체조성",
        )
        body = ttk.Frame(page1)
        body.pack(fill="x", pady=(4, 10))
        self._report_value(
            body,
            0,
            "신장(cm)",
            self.report_data["height"],
        )
        self._report_value(
            body,
            1,
            "체중(kg)",
            self.report_data["weight"],
        )
        self._report_value(
            body,
            2,
            "BMI(kg/m²)",
            self.report_data["bmi"],
        )

        self._report_section_label(
            page1,
            "운동 부하 검사 - KISS Protocol",
        )
        load = ttk.Frame(page1)
        load.pack(fill="x", pady=(4, 10))
        self._report_value(
            load,
            0,
            "최대 산소 섭취량",
            self.report_data["vo2max"],
        )
        self._report_value(
            load,
            1,
            "최대 심박수",
            self.report_data["hrmax"],
        )
        self._report_value(
            load,
            2,
            "최대 부하",
            (
                f"{self.report_data['max_load']} "
                f"{self.report_data['load_unit']}"
            ),
        )

        self._report_section_label(
            page1,
            "심박수(beats/min)",
        )

        stage_tree = ttk.Treeview(
            page1,
            columns=(
                "stage",
                "range",
                "mean",
                "zone",
            ),
            show="headings",
            height=min(
                max(len(self.report_data["stages"]), 3),
                10,
            ),
        )
        for key, label in [
            ("stage", "Stage"),
            ("range", "HR range"),
            ("mean", "HR mean"),
            ("zone", "주요 Zone"),
        ]:
            stage_tree.heading(
                key,
                text=label,
            )
            stage_tree.column(
                key,
                anchor="center",
                width=100,
                stretch=True,
            )
        for stage in self.report_data["stages"]:
            stage_tree.insert(
                "",
                "end",
                values=(
                    stage["stage"],
                    stage["hr_range"],
                    stage["hr_mean"],
                    stage["zone"],
                ),
            )
        stage_tree.pack(
            fill="x",
            pady=(4, 8),
        )

        graph = GraphCanvas(
            page1,
            height=360,
        )
        graph.pack(
            fill="x",
            pady=8,
        )
        graph.set_model(
            self.analysis.get("basic_model")
        )

        self._report_text(
            page1,
            "page1_comment",
            self.report_data.get(
                "page1_comment",
                "",
            ),
            height=4,
        )

        page2 = tk.Frame(
            self.report_container,
            bg="white",
            bd=1,
            relief="solid",
            padx=28,
            pady=22,
        )
        page2.pack(
            fill="x",
            padx=70,
            pady=(0, 30),
        )

        self._report_section_label(
            page2,
            "혈중 젖산염(mmol/L)",
        )

        lactate_tree = ttk.Treeview(
            page2,
            columns=("stage", "value"),
            show="headings",
            height=min(
                max(len(self.report_data["lactates"]), 3),
                8,
            ),
        )
        lactate_tree.heading(
            "stage",
            text="Stage",
        )
        lactate_tree.heading(
            "value",
            text="Lactate",
        )
        lactate_tree.column(
            "stage",
            anchor="center",
            stretch=True,
        )
        lactate_tree.column(
            "value",
            anchor="center",
            stretch=True,
        )
        for point in self.report_data["lactates"]:
            lactate_tree.insert(
                "",
                "end",
                values=(
                    point["label"],
                    f"{float(point['lactate']):.2f}",
                ),
            )
        lactate_tree.pack(
            fill="x",
            pady=(4, 8),
        )

        lac_graph = GraphCanvas(
            page2,
            height=300,
        )
        lac_graph.pack(
            fill="x",
            pady=8,
        )
        lac_graph.set_model(
            self.analysis.get("lactate_model")
        )

        self._report_text(
            page2,
            "lactate_comment",
            self.report_data.get(
                "lactate_comment",
                "",
            ),
            height=4,
        )

        self._report_section_label(
            page2,
            "총평",
        )
        combined = GraphCanvas(
            page2,
            height=360,
        )
        combined.pack(
            fill="x",
            pady=8,
        )
        combined.set_model(
            self.analysis.get(
                "combined_report_model"
            )
        )

        if self.report_data.get("lt1", {}).get("show"):
            self._report_section_label(
                page2,
                "LT1 분석 결과",
            )
            self._report_text(
                page2,
                "lt1_comment",
                self.report_data.get(
                    "lt1_comment",
                    "",
                ),
                height=5,
            )

        if self.report_data.get("lt2", {}).get("show"):
            self._report_section_label(
                page2,
                "LT2 분석 결과",
            )
            self._report_text(
                page2,
                "lt2_comment",
                self.report_data.get(
                    "lt2_comment",
                    "",
                ),
                height=5,
            )

    def _report_section_label(
        self,
        parent,
        text: str,
    ) -> None:
        label = tk.Label(
            parent,
            text=text,
            bg="#EAF6FF",
            fg="#111111",
            font=("Malgun Gothic", 11, "bold"),
            padx=8,
            pady=4,
        )
        label.pack(
            anchor="w",
            pady=(8, 3),
        )

    def _report_value(
        self,
        parent,
        column: int,
        label: str,
        value: Any,
    ) -> None:
        parent.columnconfigure(
            column,
            weight=1,
        )
        box = ttk.Frame(parent)
        box.grid(
            row=0,
            column=column,
            sticky="ew",
            padx=4,
        )
        ttk.Label(
            box,
            text=label,
            style="Muted.TLabel",
        ).pack()
        ttk.Label(
            box,
            text=str(value),
            font=("Malgun Gothic", 9),
        ).pack()

    def _report_text(
        self,
        parent,
        key: str,
        value: str,
        *,
        height: int,
    ) -> None:
        text = tk.Text(
            parent,
            height=height,
            wrap="word",
            font=("Malgun Gothic", 9),
            relief="solid",
            bd=1,
            padx=6,
            pady=5,
        )
        text.insert("1.0", value)
        text.pack(
            fill="x",
            pady=(4, 8),
        )
        text.tag_configure(
            "bold",
            font=("Malgun Gothic", 9, "bold"),
        )
        text.tag_configure(
            "italic",
            font=("Malgun Gothic", 9, "italic"),
        )
        text.tag_configure(
            "underline",
            underline=True,
        )
        text.tag_configure(
            "red",
            foreground="#D7191C",
        )
        text.tag_configure(
            "blue",
            foreground="#2679D9",
        )
        text.tag_configure(
            "black",
            foreground="#111111",
        )
        text.bind(
            "<FocusIn>",
            lambda _event, widget=text: self._set_current_report_text(
                widget
            ),
        )
        self.report_texts[key] = text

    def _set_current_report_text(
        self,
        widget: tk.Text,
    ) -> None:
        self._current_report_text = widget

    # ---------- Data actions ----------

    def refresh_athletes(self) -> None:
        try:
            self.athletes = list_athletes()
            for item in self.athlete_tree.get_children():
                self.athlete_tree.delete(item)

            for athlete in self.athletes:
                self.athlete_tree.insert(
                    "",
                    "end",
                    values=(
                        athlete["name"],
                        athlete["sex"],
                        athlete["category"],
                    ),
                )

            values = [
                (
                    f"{athlete['name']} "
                    f"({athlete['sex']} / {athlete['category']})"
                )
                for athlete in self.athletes
            ]
            self.measurement_athlete_combo[
                "values"
            ] = values

            if values:
                self.measurement_athlete_combo.current(
                    min(
                        self.measurement_athlete_combo.current(),
                        len(values) - 1,
                    )
                    if self.measurement_athlete_combo.current() >= 0
                    else 0
                )
                self.on_measurement_athlete_changed()
            else:
                self.measurement_athlete_var.set("")
                self.saved_measurement_combo["values"] = [
                    "새 측정"
                ]
                self.saved_measurement_combo.current(0)

            self._status("선수 목록을 불러왔습니다.")
        except Exception as exc:
            self._error(
                "선수 목록 오류",
                str(exc),
            )

    def register_athlete(self) -> None:
        try:
            athlete = add_athlete(
                self.athlete_name_var.get(),
                self.athlete_sex_var.get(),
                self.athlete_category_var.get(),
            )
            self.athlete_name_var.set("")
            self.refresh_athletes()

            for index, item in enumerate(
                self.athletes
            ):
                if int(item["id"]) == int(
                    athlete["id"]
                ):
                    self.measurement_athlete_combo.current(
                        index
                    )
                    break

            self._status(
                f"{athlete['name']} 선수를 저장했습니다."
            )
        except Exception as exc:
            self._error(
                "선수 저장 오류",
                str(exc),
            )

    def _selected_athlete(
        self,
    ) -> dict[str, Any] | None:
        index = self.measurement_athlete_combo.current()
        if index < 0 or index >= len(self.athletes):
            return None
        return self.athletes[index]

    def on_measurement_athlete_changed(
        self,
    ) -> None:
        athlete = self._selected_athlete()
        self.measurements = []

        if athlete is None:
            return

        try:
            self.measurements = list_measurements(
                int(athlete["id"])
            )
            values = ["새 측정"] + [
                str(item["test_date"])
                for item in self.measurements
            ]
            self.saved_measurement_combo[
                "values"
            ] = values
            self.saved_measurement_combo.current(0)
            self.fill_measurement(None)
        except Exception as exc:
            self._error(
                "측정 기록 오류",
                str(exc),
            )

    def on_saved_measurement_changed(
        self,
    ) -> None:
        index = self.saved_measurement_combo.current()
        if index <= 0:
            self.fill_measurement(None)
            return
        measurement_index = index - 1
        if measurement_index < len(
            self.measurements
        ):
            self.fill_measurement(
                self.measurements[
                    measurement_index
                ]
            )

    def fill_measurement(
        self,
        measurement: dict[str, Any] | None,
    ) -> None:
        if measurement is None:
            self.test_date_var.set(
                dt.date.today().isoformat()
            )
            self.height_var.set("0")
            self.weight_var.set("0")
            self.bmi_var.set("0")
            self.vo2max_var.set("0")
            self.hrmax_var.set("0")
            self.exercise_time_var.set("")
            self.load_type_var.set("Speed")
            self.max_load_var.set("0")
            self.grade_var.set("0")
            self.stage_duration_var.set("3")
            self.rest_duration_var.set("1")
            self.update_load_label()
            return

        self.test_date_var.set(
            str(measurement["test_date"])
        )
        self.height_var.set(
            str(measurement.get("height") or 0)
        )
        self.weight_var.set(
            str(measurement.get("weight") or 0)
        )
        self.bmi_var.set(
            str(measurement.get("bmi") or 0)
        )
        self.vo2max_var.set(
            str(measurement.get("vo2max") or 0)
        )
        self.hrmax_var.set(
            str(measurement.get("hrmax") or 0)
        )
        self.exercise_time_var.set(
            str(
                measurement.get(
                    "exercise_time"
                )
                or ""
            )
        )
        self.load_type_var.set(
            str(
                measurement.get(
                    "load_type"
                )
                or "Speed"
            )
        )
        self.max_load_var.set(
            str(
                measurement.get(
                    "max_load"
                )
                or 0
            )
        )
        self.grade_var.set(
            str(
                measurement.get(
                    "grade_percent"
                )
                or 0
            )
        )
        self.stage_duration_var.set(
            str(
                max(
                    1,
                    round(
                        float(
                            measurement.get(
                                "stage_duration_min"
                            )
                            or 3
                        )
                    ),
                )
            )
        )
        self.rest_duration_var.set(
            str(
                max(
                    1,
                    round(
                        float(
                            measurement.get(
                                "rest_duration_min"
                            )
                            or 1
                        )
                    ),
                )
            )
        )
        self.update_load_label()

    def update_load_label(self) -> None:
        if self.load_type_var.get() == "Power":
            self.max_load_label.configure(
                text="최대 Power(watt)"
            )
        else:
            self.max_load_label.configure(
                text="최대 Speed(km/h)"
            )

    def _current_meta(
        self,
    ) -> dict[str, Any]:
        athlete = self._selected_athlete()
        if athlete is None:
            raise ValueError(
                "선수를 먼저 선택하세요."
            )

        try:
            test_date = dt.date.fromisoformat(
                self.test_date_var.get().strip()
            )
        except ValueError as exc:
            raise ValueError(
                "측정 날짜는 YYYY-MM-DD 형식으로 입력하세요."
            ) from exc

        load_type = self.load_type_var.get()
        return {
            "athlete": athlete,
            "test_date": test_date,
            "height": self._float(
                self.height_var.get(),
                "신장",
            ),
            "weight": self._float(
                self.weight_var.get(),
                "체중",
            ),
            "bmi": self._float(
                self.bmi_var.get(),
                "BMI",
            ),
            "vo2max": self._float(
                self.vo2max_var.get(),
                "최대 산소 섭취량",
            ),
            "hrmax": self._int(
                self.hrmax_var.get(),
                "최대 심박수",
            ),
            "exercise_time": (
                self.exercise_time_var.get().strip()
            ),
            "load_type": load_type,
            "load_unit": (
                "km/h"
                if load_type == "Speed"
                else "watt"
            ),
            "max_load": self._float(
                self.max_load_var.get(),
                "최대 부하",
            ),
            "grade_percent": self._float(
                self.grade_var.get(),
                "경사도",
            ),
            "stage_duration_min": max(
                1,
                self._int(
                    self.stage_duration_var.get(),
                    "일반 운동 Stage 시간",
                ),
            ),
            "rest_duration_min": max(
                1,
                self._int(
                    self.rest_duration_var.get(),
                    "Rest 시간",
                ),
            ),
            "show_lt1": self.show_lt1_var.get(),
            "show_lt2": self.show_lt2_var.get(),
        }

    def save_current_measurement(
        self,
    ) -> None:
        try:
            meta = self._current_meta()
            saved = save_measurement(
                athlete_id=int(
                    meta["athlete"]["id"]
                ),
                test_date=meta[
                    "test_date"
                ].isoformat(),
                height=meta["height"],
                weight=meta["weight"],
                bmi=meta["bmi"],
                vo2max=meta["vo2max"],
                hrmax=meta["hrmax"],
                exercise_time=meta[
                    "exercise_time"
                ],
                load_type=meta["load_type"],
                max_load=meta["max_load"],
                grade_percent=meta[
                    "grade_percent"
                ],
                stage_duration_min=meta[
                    "stage_duration_min"
                ],
                rest_duration_min=meta[
                    "rest_duration_min"
                ],
            )
            self.on_measurement_athlete_changed()

            for index, item in enumerate(
                self.measurements,
                start=1,
            ):
                if int(item["id"]) == int(
                    saved["id"]
                ):
                    self.saved_measurement_combo.current(
                        index
                    )
                    break

            self._status(
                "측정 정보를 저장했습니다."
            )
        except Exception as exc:
            self._error(
                "측정 정보 저장 오류",
                str(exc),
            )

    def save_input_template(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Excel 입력 양식 저장",
            initialfile="NGC_CPET_입력양식.xlsx",
            defaultextension=".xlsx",
            filetypes=[
                ("Excel Workbook", "*.xlsx")
            ],
        )
        if not path:
            return
        try:
            Path(path).write_bytes(
                build_input_template()
            )
            self._status(
                "Excel 입력 양식을 저장했습니다."
            )
        except Exception as exc:
            self._error(
                "양식 저장 오류",
                str(exc),
            )

    def choose_excel_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Excel 파일 선택",
            filetypes=[
                (
                    "Excel Workbook",
                    "*.xlsx *.xlsm",
                )
            ],
        )
        if path:
            self.excel_path_var.set(path)

    def parse_selected_excel(self) -> None:
        path = self.excel_path_var.get().strip()
        if not path:
            self._error(
                "Excel 입력",
                "Excel 파일을 먼저 선택하세요.",
            )
            return

        try:
            meta = self._current_meta()
            with open(path, "rb") as handle:
                rows, segments, summary = (
                    excel_parser.parse_excel(
                        handle,
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
                )

            with open(path, "rb") as handle:
                imported_lactate = (
                    parse_lactate_sheet(
                        handle
                    )
                )

            self.parsed = {
                "rows": rows,
                "segments": segments,
                "summary": summary,
                "lactate_rows": imported_lactate,
            }
            self.meta = meta
            self.analysis = None
            self.report_data = None

            for item in self.summary_tree.get_children():
                self.summary_tree.delete(item)

            for row in summary_records(summary):
                self.summary_tree.insert(
                    "",
                    "end",
                    values=(
                        row["Stage"],
                        row["Duration"],
                        self._display_number(
                            row["HR_min"]
                        ),
                        self._display_number(
                            row["HR_max"]
                        ),
                        self._display_number(
                            row["HR_mean"]
                        ),
                        self._display_number(
                            row["VO2_min"]
                        ),
                        self._display_number(
                            row["VO2_max"]
                        ),
                        self._display_number(
                            row["VO2_mean"]
                        ),
                    ),
                )

            self.lactate_rows = (
                initial_lactate_rows(
                    segments,
                    imported_lactate,
                    meta["max_load"],
                )
            )
            self.populate_lactate_inputs()

            self.notebook.select(
                self.analysis_tab
            )
            self._status(
                "Excel 자료를 읽었습니다."
            )
        except Exception as exc:
            self._error(
                "Excel 읽기 오류",
                str(exc),
            )

    def populate_lactate_inputs(self) -> None:
        for child in self.lactate_frame.winfo_children():
            child.destroy()

        headers = [
            "Stage",
            "Load",
            "혈중 젖산염(mmol/L)",
        ]
        for col, text in enumerate(headers):
            ttk.Label(
                self.lactate_frame,
                text=text,
                font=(
                    "Malgun Gothic",
                    9,
                    "bold",
                ),
            ).grid(
                row=0,
                column=col,
                sticky="ew",
                padx=4,
                pady=3,
            )
            self.lactate_frame.columnconfigure(
                col,
                weight=1,
            )

        self.lactate_entries = []

        for row_index, item in enumerate(
            self.lactate_rows,
            start=1,
        ):
            ttk.Label(
                self.lactate_frame,
                text=str(item["stage"]),
            ).grid(
                row=row_index,
                column=0,
                sticky="ew",
                padx=4,
                pady=2,
            )
            ttk.Label(
                self.lactate_frame,
                text=(
                    "-"
                    if item["load"] is None
                    else f"{float(item['load']):g}"
                ),
            ).grid(
                row=row_index,
                column=1,
                sticky="ew",
                padx=4,
                pady=2,
            )

            entry = ttk.Entry(
                self.lactate_frame
            )
            if item.get("lactate") is not None:
                entry.insert(
                    0,
                    f"{float(item['lactate']):.2f}",
                )
            entry.grid(
                row=row_index,
                column=2,
                sticky="ew",
                padx=4,
                pady=2,
            )
            self.lactate_entries.append(
                entry
            )

    def collect_lactate_rows(
        self,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []

        for base, entry in zip(
            self.lactate_rows,
            self.lactate_entries,
        ):
            text = entry.get().strip()
            if text:
                try:
                    lactate = float(text)
                except ValueError as exc:
                    raise ValueError(
                        f"{base['stage']} 젖산값을 숫자로 입력하세요."
                    ) from exc
            else:
                lactate = None

            result.append(
                {
                    "stage": base["stage"],
                    "load": base["load"],
                    "lactate": lactate,
                }
            )

        return result

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
            for variable, key in [
                (
                    self.lt1_result_var,
                    "LT1",
                ),
                (
                    self.lt2_result_var,
                    "LT2",
                ),
            ]:
                item = lt_api_item(
                    self.analysis[
                        key.lower()
                    ],
                    key,
                    self.analysis[
                        "threshold_hr"
                    ],
                    self.meta,
                )

                if not item.get("show"):
                    variable.set(
                        f"{key}: 표시하지 않음"
                    )
                elif item.get("valid"):
                    hr_text = (
                        f" | {item['hr']} bpm"
                        if item.get("hr")
                        is not None
                        else ""
                    )
                    variable.set(
                        f"{key} = "
                        f"{item['load']:.2f} "
                        f"{unit}{hr_text}"
                    )
                else:
                    variable.set(
                        f"{key} 산출 불가: "
                        f"{item.get('reason', '')}"
                    )

            self.lactate_graph.set_model(
                self.analysis.get(
                    "lactate_model"
                )
            )
            self.basic_graph.set_model(
                self.analysis.get(
                    "basic_model"
                )
            )
            self.combined_graph.set_model(
                self.analysis.get(
                    "combined_analysis_model"
                )
            )

            self.report_data = build_report_data(
                self.parsed,
                self.meta,
                self.analysis,
            )
            self.render_report()

            self._status(
                "분석이 완료되었습니다."
            )
        except Exception as exc:
            self._error(
                "분석 오류",
                str(exc),
            )

    # ---------- Report editing/export ----------

    def apply_text_style(
        self,
        style_name: str,
    ) -> None:
        text = self._current_report_text
        if text is None:
            return
        try:
            start = text.index("sel.first")
            end = text.index("sel.last")
        except tk.TclError:
            return
        text.tag_add(
            style_name,
            start,
            end,
        )

    def apply_text_color(
        self,
        color: str,
    ) -> None:
        text = self._current_report_text
        if text is None:
            return
        try:
            start = text.index("sel.first")
            end = text.index("sel.last")
        except tk.TclError:
            return

        tag = {
            "#D7191C": "red",
            "#2679D9": "blue",
            "#111111": "black",
        }.get(color, "custom")

        if tag == "custom":
            text.tag_configure(
                tag,
                foreground=color,
            )

        for existing in [
            "red",
            "blue",
            "black",
            "custom",
        ]:
            text.tag_remove(
                existing,
                start,
                end,
            )
        text.tag_add(
            tag,
            start,
            end,
        )

    def clear_text_style(self) -> None:
        text = self._current_report_text
        if text is None:
            return
        try:
            start = text.index("sel.first")
            end = text.index("sel.last")
        except tk.TclError:
            return

        for tag in [
            "bold",
            "italic",
            "underline",
            "red",
            "blue",
            "black",
            "custom",
        ]:
            text.tag_remove(
                tag,
                start,
                end,
            )

    def _report_comments(
        self,
    ) -> dict[str, str]:
        return {
            key: widget.get(
                "1.0",
                "end-1c",
            )
            for key, widget in (
                self.report_texts.items()
            )
        }

    def _refresh_report_data_from_text(
        self,
    ) -> None:
        if (
            self.parsed is None
            or self.meta is None
            or self.analysis is None
        ):
            raise ValueError(
                "분석을 먼저 실행하세요."
            )

        self.report_data = (
            build_report_data(
                self.parsed,
                self.meta,
                self.analysis,
                self._report_comments(),
            )
        )

    def save_report_excel(self) -> None:
        try:
            self._refresh_report_data_from_text()
            data = build_excel_bytes(
                self.report_data,
                self.parsed,
                self.analysis,
            )

            default_name = (
                f"{self.meta['test_date']}_"
                f"{self.meta['athlete']['name']}_결과.xlsx"
            )
            path = filedialog.asksaveasfilename(
                title="Excel 결과 저장",
                initialfile=default_name,
                defaultextension=".xlsx",
                filetypes=[
                    (
                        "Excel Workbook",
                        "*.xlsx",
                    )
                ],
            )
            if not path:
                return

            Path(path).write_bytes(data)
            self._status(
                "Excel 결과를 저장했습니다."
            )
        except Exception as exc:
            self._error(
                "Excel 결과 저장 오류",
                str(exc),
            )

    def save_report_pdf(self) -> None:
        try:
            self._refresh_report_data_from_text()

            default_name = (
                f"{self.meta['test_date']}_"
                f"{self.meta['athlete']['name']}_피드백.pdf"
            )
            path = filedialog.asksaveasfilename(
                title="PDF 결과지 저장",
                initialfile=default_name,
                defaultextension=".pdf",
                filetypes=[
                    ("PDF", "*.pdf")
                ],
            )
            if not path:
                return

            save_report_pdf(
                path,
                self.report_data,
                self.analysis,
            )
            self._status(
                "PDF 결과지를 저장했습니다."
            )
        except Exception as exc:
            self._error(
                "PDF 결과지 저장 오류",
                str(exc),
            )

    # ---------- Helpers ----------

    @staticmethod
    def _float(
        value: str,
        label: str,
    ) -> float:
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(
                f"{label} 값을 숫자로 입력하세요."
            ) from exc

    @staticmethod
    def _int(
        value: str,
        label: str,
    ) -> int:
        try:
            return int(
                round(float(value))
            )
        except ValueError as exc:
            raise ValueError(
                f"{label} 값을 숫자로 입력하세요."
            ) from exc

    @staticmethod
    def _display_number(
        value: Any,
    ) -> str:
        if value is None:
            return "-"
        try:
            number = float(value)
            return f"{number:.2f}"
        except (TypeError, ValueError):
            return str(value)

    def _status(
        self,
        message: str,
    ) -> None:
        self.status_var.set(message)

    def _error(
        self,
        title: str,
        message: str,
    ) -> None:
        messagebox.showerror(
            title,
            message,
            parent=self,
        )
