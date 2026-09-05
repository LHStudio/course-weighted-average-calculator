from __future__ import annotations

import math
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk
from typing import Callable, Sequence

from course_calculator import (
    DEFAULT_GPA_BANDS,
    CourseRecord,
    build_ranked_rows,
    collect_text_grades,
    deduplicate_records,
    group_by_student,
    parse_grade_file,
    parse_score,
)
from excel_io import EXPORT_HEADERS, export_summary


APP_TITLE = "课程加权平均分计算器"
BG = "#F5F7FA"
SURFACE = "#FFFFFF"
TEXT = "#172033"
MUTED = "#667085"
ACCENT = "#176B87"
ACCENT_HOVER = "#12566D"
BORDER = "#D7DCE3"
WARNING = "#A15C00"
SUCCESS = "#287A4D"

KEY_MODE_LABELS = {"按课程代码": "code", "按课程名称": "name"}
KEEP_MODE_LABELS = {"最后一条": "last", "第一条": "first", "全部保留": "all"}


def _display_number(value: object, digits: int = 1) -> str:
    if value is None:
        return ""
    number = float(value)
    text = f"{number:.{digits}f}"
    return text.rstrip("0").rstrip(".") if digits else text


def resource_path(relative_path: str | Path) -> Path:
    """Resolve an asset from the source tree or PyInstaller's temp folder."""
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return bundle_root / relative_path


class ScrollableCourseList(ttk.Frame):
    COLUMNS = (
        ("", 42, "center"),
        ("课程代码", 112, "w"),
        ("课程名称", 210, "w"),
        ("学分", 62, "center"),
        ("成绩", 70, "center"),
        ("取得学期", 180, "w"),
        ("课程类别", 140, "w"),
        ("取得方式", 90, "center"),
    )

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, style="Surface.TFrame")
        self.checkbox_font = tkfont.Font(family="Microsoft YaHei UI", size=13)
        self._variables: list[tk.BooleanVar] = []
        self._checkbuttons: dict[str, tk.Checkbutton] = {}

        self.header_canvas = tk.Canvas(self, background="#E9EEF3", height=34, highlightthickness=0)
        self.header_frame = ttk.Frame(self.header_canvas, style="Surface.TFrame")
        self.header_window = self.header_canvas.create_window((0, 0), window=self.header_frame, anchor="nw")
        self.header_canvas.grid(row=0, column=0, sticky="ew")

        self.canvas = tk.Canvas(self, background=SURFACE, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.horizontal_scrollbar = ttk.Scrollbar(self, orient="horizontal", command=self._xview)
        self.canvas.configure(
            yscrollcommand=self.scrollbar.set,
            xscrollcommand=self._sync_horizontal_scrollbar,
        )
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.scrollbar.grid(row=1, column=1, sticky="ns")
        self.horizontal_scrollbar.grid(row=2, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.inner = ttk.Frame(self.canvas, style="Surface.TFrame")
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_inner)
        self.header_canvas.bind("<Configure>", self._resize_header)
        self.canvas.bind("<Enter>", lambda _event: self.canvas.bind_all("<MouseWheel>", self._on_wheel))
        self.canvas.bind("<Leave>", lambda _event: self.canvas.unbind_all("<MouseWheel>"))

    def _update_scroll_region(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_inner(self, event) -> None:
        required = sum(width for _, width, _ in self.COLUMNS)
        self.canvas.itemconfigure(self.window, width=max(event.width, required))
        self.header_canvas.itemconfigure(self.header_window, width=max(event.width, required))
        self.header_canvas.configure(scrollregion=(0, 0, max(event.width, required), 34))

    def _resize_header(self, event) -> None:
        required = sum(width for _, width, _ in self.COLUMNS)
        self.header_canvas.itemconfigure(self.header_window, width=max(event.width, required))

    def _sync_horizontal_scrollbar(self, first: str, last: str) -> None:
        self.horizontal_scrollbar.set(first, last)
        self.header_canvas.xview_moveto(first)

    def _xview(self, *args) -> None:
        self.canvas.xview(*args)
        self.header_canvas.xview(*args)

    def _configure_columns(self, frame: tk.Misc) -> None:
        for column, (_, width, _) in enumerate(self.COLUMNS):
            frame.grid_columnconfigure(column, minsize=width, weight=1 if column == 2 else 0)

    def _on_wheel(self, event) -> None:
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def set_records(
        self,
        records: Sequence[CourseRecord],
        selection_state: dict[str, bool],
        text_mapping: dict[str, float],
        on_change: Callable[[CourseRecord, bool], None],
    ) -> None:
        for child in self.inner.winfo_children():
            child.destroy()
        for child in self.header_frame.winfo_children():
            child.destroy()
        self._variables.clear()
        self._checkbuttons.clear()

        self._configure_columns(self.header_frame)
        for column, (label, width, anchor) in enumerate(self.COLUMNS):
            header = ttk.Label(
                self.header_frame,
                text=label,
                anchor=anchor,
                padding=(8, 8),
                style="CourseHeader.TLabel",
            )
            header.grid(row=0, column=column, sticky="nsew")

        if not records:
            ttk.Label(
                self.inner,
                text="请先选择一名学生",
                style="Empty.TLabel",
                anchor="center",
                padding=30,
            ).grid(row=0, column=0, columnspan=len(self.COLUMNS), sticky="ew")
            self._update_scroll_region()
            return

        self._configure_columns(self.inner)
        for row_index, record in enumerate(records):
            variable = tk.BooleanVar(value=selection_state.get(record.record_id, True))
            self._variables.append(variable)
            check = tk.Checkbutton(
                self.inner,
                variable=variable,
                font=self.checkbox_font,
                background=SURFACE,
                activebackground=SURFACE,
                selectcolor="#CFE8EF",
                relief="flat",
                bd=0,
                highlightthickness=0,
                padx=5,
                pady=0,
                command=lambda item=record, var=variable: on_change(item, var.get()),
            )
            check.grid(row=row_index, column=0, sticky="nsew", padx=(12, 4), pady=1)
            self._checkbuttons[record.record_id] = check

            values = (
                record.course_code,
                record.course_name,
                _display_number(record.credits, 2),
                record.raw_score,
                record.term,
                record.category,
                record.acquisition,
            )
            score_is_text = parse_score(record.raw_score, {}) is None
            for column, value in enumerate(values, start=1):
                style = "Warning.TLabel" if column == 4 and score_is_text else "CourseCell.TLabel"
                label = ttk.Label(
                    self.inner,
                    text=value,
                    anchor=self.COLUMNS[column][2],
                    padding=(8, 7),
                    style=style,
                )
                label.grid(row=row_index, column=column, sticky="nsew", pady=1)
            self.inner.grid_rowconfigure(row_index, minsize=34)
        self.canvas.yview_moveto(0)
        self._update_scroll_region()


class GpaBandsEditor(ttk.Frame):
    """Editable list of score thresholds and their corresponding GPA values."""

    def __init__(self, master: tk.Misc, bands: Sequence[tuple[float, float]]) -> None:
        super().__init__(master, style="Surface.TFrame")
        self.variables: list[tuple[tk.StringVar, tk.StringVar]] = []
        self._rows: list[tuple[ttk.Entry, ttk.Entry]] = []

        ttk.Label(self, text="最低分", style="CourseHeader.TLabel", padding=(20, 6)).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Label(self, text="绩点", style="CourseHeader.TLabel", padding=(20, 6)).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )
        self.rows_frame = ttk.Frame(self, style="Surface.TFrame")
        self.rows_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        controls = ttk.Frame(self, style="Surface.TFrame")
        controls.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(controls, text="添加分段", command=self.add_row).pack(side="left")
        ttk.Button(controls, text="删除末行", command=self.remove_row).pack(side="left", padx=(6, 0))

        for threshold, points in bands:
            self.add_row(threshold, points)
        if not self.variables:
            self.add_row()

    def add_row(self, threshold: object = "", points: object = "") -> None:
        threshold_var = tk.StringVar(value=_display_number(threshold, 2) if threshold != "" else "")
        points_var = tk.StringVar(value=_display_number(points, 2) if points != "" else "")
        threshold_entry = ttk.Entry(self.rows_frame, textvariable=threshold_var, width=12, justify="center")
        points_entry = ttk.Entry(self.rows_frame, textvariable=points_var, width=12, justify="center")
        self.variables.append((threshold_var, points_var))
        self._rows.append((threshold_entry, points_entry))
        self._regrid_rows()

    def remove_row(self) -> None:
        if len(self.variables) <= 1:
            return
        threshold_entry, points_entry = self._rows.pop()
        threshold_entry.destroy()
        points_entry.destroy()
        self.variables.pop()
        self._regrid_rows()

    def _regrid_rows(self) -> None:
        for row_index, (threshold_entry, points_entry) in enumerate(self._rows):
            threshold_entry.grid(row=row_index, column=0, padx=(0, 6), pady=3)
            points_entry.grid(row=row_index, column=1, padx=(6, 0), pady=3)

    def set_bands(self, bands: Sequence[tuple[float, float]]) -> None:
        for threshold_entry, points_entry in self._rows:
            threshold_entry.destroy()
            points_entry.destroy()
        self.variables.clear()
        self._rows.clear()
        for threshold, points in bands:
            self.add_row(threshold, points)
        if not self.variables:
            self.add_row()

    def get_bands(self) -> list[tuple[float, float]]:
        try:
            bands = [(float(threshold.get().strip()), float(points.get().strip())) for threshold, points in self.variables]
        except ValueError as exc:
            raise ValueError("最低分和绩点必须填写数字。") from exc
        return sorted(bands, reverse=True)


class CourseCalculatorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1240x820")
        self.root.minsize(1020, 680)
        self.root.configure(background=BG)
        icon_path = resource_path(Path("assets") / "icon.ico")
        if icon_path.is_file():
            try:
                self.root.iconbitmap(default=str(icon_path))
            except tk.TclError:
                pass

        self.source_path: Path | None = None
        self.raw_records: list[CourseRecord] = []
        self.active_records: list[CourseRecord] = []
        self.student_records: dict[str, list[CourseRecord]] = {}
        self.selection_state: dict[str, bool] = {}
        self.text_mapping: dict[str, float] = {}
        self.gpa_bands: list[tuple[float, float]] = list(DEFAULT_GPA_BANDS)
        self.result_rows: list[dict[str, object]] = []
        self.current_student_id: str | None = None

        self.key_mode_var = tk.StringVar(value="按课程代码")
        self.keep_mode_var = tk.StringVar(value="最后一条")
        self.file_var = tk.StringVar(value="尚未打开成绩文件")
        self.summary_var = tk.StringVar(value="打开成绩文件后即可开始计算")
        self.student_title_var = tk.StringVar(value="学生")
        self.course_title_var = tk.StringVar(value="课程明细")

        self._configure_style()
        self._build_layout()
        self._set_data_controls_enabled(False)
        self.root.after(160, self._load_initial_file)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        default_font = ("Microsoft YaHei UI", 10)
        self.root.option_add("*Font", default_font)
        style.configure("TFrame", background=BG)
        style.configure("Surface.TFrame", background=SURFACE)
        style.configure("Toolbar.TFrame", background=SURFACE)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Toolbar.TLabel", background=SURFACE, foreground=TEXT)
        style.configure("Muted.TLabel", background=SURFACE, foreground=MUTED)
        style.configure("SectionTitle.TLabel", background=SURFACE, foreground=TEXT, font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("CourseHeader.TLabel", background="#E9EEF3", foreground=TEXT, font=("Microsoft YaHei UI", 9, "bold"))
        style.configure("CourseCell.TLabel", background=SURFACE, foreground=TEXT, font=("Microsoft YaHei UI", 9))
        style.configure("Warning.TLabel", background="#FFF5E6", foreground=WARNING, font=("Microsoft YaHei UI", 9, "bold"))
        style.configure("Empty.TLabel", background=SURFACE, foreground=MUTED)
        style.configure("Status.TLabel", background="#EAF3F6", foreground=ACCENT, padding=(12, 7))
        style.configure("TButton", padding=(12, 7), background="#EEF1F4", foreground=TEXT, borderwidth=1)
        style.map("TButton", background=[("active", "#E1E7EC"), ("disabled", "#F4F5F6")])
        style.configure("Primary.TButton", padding=(14, 8), background=ACCENT, foreground="#FFFFFF", font=("Microsoft YaHei UI", 10, "bold"))
        style.map("Primary.TButton", background=[("active", ACCENT_HOVER), ("disabled", "#A6BBC4")])
        style.configure("Treeview", rowheight=30, background=SURFACE, fieldbackground=SURFACE, foreground=TEXT, bordercolor=BORDER)
        style.configure("Treeview.Heading", background="#E9EEF3", foreground=TEXT, font=("Microsoft YaHei UI", 9, "bold"), padding=(6, 7))
        style.map("Treeview", background=[("selected", "#DCECF2")], foreground=[("selected", TEXT)])
        style.configure("TLabelframe", background=SURFACE, bordercolor=BORDER, relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background=SURFACE, foreground=TEXT, font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("TCombobox", padding=5)

    def _build_layout(self) -> None:
        toolbar = ttk.Frame(self.root, style="Toolbar.TFrame", padding=(18, 14))
        toolbar.pack(fill="x")
        self.open_button = ttk.Button(toolbar, text="打开成绩文件", style="Primary.TButton", command=self.choose_file)
        self.open_button.grid(row=0, column=0, padx=(0, 14), sticky="w")
        ttk.Label(toolbar, textvariable=self.file_var, style="Toolbar.TLabel", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=1, sticky="w")
        self.export_button = ttk.Button(toolbar, text="导出 Excel", style="Primary.TButton", command=self.export_file)
        self.export_button.grid(row=0, column=2, padx=(16, 0), sticky="e")
        toolbar.columnconfigure(1, weight=1)

        self.settings_toolbar = ttk.Frame(toolbar, style="Toolbar.TFrame")
        self.settings_toolbar.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Label(self.settings_toolbar, text="去重依据", style="Muted.TLabel").grid(row=0, column=0, padx=(0, 6), sticky="w")
        self.key_combo = ttk.Combobox(self.settings_toolbar, textvariable=self.key_mode_var, values=list(KEY_MODE_LABELS), width=12, state="readonly")
        self.key_combo.grid(row=0, column=1, padx=(0, 14), sticky="w")
        ttk.Label(self.settings_toolbar, text="重复记录", style="Muted.TLabel").grid(row=0, column=2, padx=(0, 6), sticky="w")
        self.keep_combo = ttk.Combobox(self.settings_toolbar, textvariable=self.keep_mode_var, values=list(KEEP_MODE_LABELS), width=10, state="readonly")
        self.keep_combo.grid(row=0, column=3, padx=(0, 14), sticky="w")
        self.mapping_button = ttk.Button(self.settings_toolbar, text="文字成绩换算", command=self.open_text_mapping_dialog)
        self.mapping_button.grid(row=0, column=4, padx=(0, 8), sticky="w")
        self.gpa_button = ttk.Button(self.settings_toolbar, text="绩点规则", command=self.open_gpa_dialog)
        self.gpa_button.grid(row=0, column=5, padx=(0, 8), sticky="w")
        self.calculate_button = ttk.Button(self.settings_toolbar, text="重新计算", command=self.recalculate)
        self.calculate_button.grid(row=0, column=6, sticky="w")
        self.key_combo.bind("<<ComboboxSelected>>", lambda _event: self.apply_deduplication())
        self.keep_combo.bind("<<ComboboxSelected>>", lambda _event: self.apply_deduplication())

        main = ttk.Panedwindow(self.root, orient="vertical")
        main.pack(fill="both", expand=True, padx=14, pady=(12, 10))
        selection_panel = ttk.Panedwindow(main, orient="horizontal")
        result_panel = ttk.Frame(main, style="Surface.TFrame", padding=(12, 10))
        main.add(selection_panel, weight=3)
        main.add(result_panel, weight=2)

        student_panel = ttk.Frame(selection_panel, style="Surface.TFrame", padding=(12, 10))
        course_panel = ttk.Frame(selection_panel, style="Surface.TFrame", padding=(12, 10))
        selection_panel.add(student_panel, weight=1)
        selection_panel.add(course_panel, weight=3)

        ttk.Label(student_panel, textvariable=self.student_title_var, style="SectionTitle.TLabel").pack(fill="x", pady=(0, 8))
        student_tree_frame = ttk.Frame(student_panel, style="Surface.TFrame")
        student_tree_frame.pack(fill="both", expand=True)
        self.student_tree = ttk.Treeview(student_tree_frame, columns=("id", "name", "state"), show="headings", selectmode="browse")
        self.student_tree.heading("id", text="学号")
        self.student_tree.heading("name", text="姓名")
        self.student_tree.heading("state", text="状态")
        self.student_tree.column("id", width=125, minwidth=105, anchor="center")
        self.student_tree.column("name", width=80, minwidth=70, anchor="center")
        self.student_tree.column("state", width=82, minwidth=72, anchor="center")
        student_scroll = ttk.Scrollbar(student_tree_frame, orient="vertical", command=self.student_tree.yview)
        self.student_tree.configure(yscrollcommand=student_scroll.set)
        self.student_tree.pack(side="left", fill="both", expand=True)
        student_scroll.pack(side="right", fill="y")
        self.student_tree.bind("<<TreeviewSelect>>", self._on_student_selected)

        course_header = ttk.Frame(course_panel, style="Surface.TFrame")
        course_header.pack(fill="x", pady=(0, 6))
        ttk.Label(course_header, textvariable=self.course_title_var, style="SectionTitle.TLabel").pack(anchor="w")
        course_actions = ttk.Frame(course_panel, style="Surface.TFrame")
        course_actions.pack(fill="x", pady=(0, 8))
        self.select_all_button = ttk.Button(course_actions, text="全选", command=lambda: self.set_current_selection(True))
        self.select_all_button.pack(side="left")
        self.select_none_button = ttk.Button(course_actions, text="全不选", command=lambda: self.set_current_selection(False))
        self.select_none_button.pack(side="left", padx=(6, 0))
        self.apply_all_button = ttk.Button(course_actions, text="应用当前科目方案到全部学生", command=self.apply_selection_to_all)
        self.apply_all_button.pack(side="left", padx=(6, 0))
        self.course_list = ScrollableCourseList(course_panel)
        self.course_list.pack(fill="both", expand=True)

        ttk.Label(result_panel, text="计算结果预览", style="SectionTitle.TLabel").pack(anchor="w", pady=(0, 8))
        result_tree_frame = ttk.Frame(result_panel, style="Surface.TFrame")
        result_tree_frame.pack(fill="both", expand=True)
        result_columns = tuple(f"c{index}" for index in range(len(EXPORT_HEADERS)))
        self.result_tree = ttk.Treeview(result_tree_frame, columns=result_columns, show="headings")
        result_widths = (145, 120, 80, 70, 80, 80, 95, 82, 110, 58)
        for column, label, width in zip(result_columns, EXPORT_HEADERS, result_widths):
            self.result_tree.heading(column, text=label)
            self.result_tree.column(column, width=width, minwidth=55, anchor="center")
        result_y = ttk.Scrollbar(result_tree_frame, orient="vertical", command=self.result_tree.yview)
        result_x = ttk.Scrollbar(result_tree_frame, orient="horizontal", command=self.result_tree.xview)
        self.result_tree.configure(yscrollcommand=result_y.set, xscrollcommand=result_x.set)
        self.result_tree.grid(row=0, column=0, sticky="nsew")
        result_y.grid(row=0, column=1, sticky="ns")
        result_x.grid(row=1, column=0, sticky="ew")
        result_tree_frame.columnconfigure(0, weight=1)
        result_tree_frame.rowconfigure(0, weight=1)

        status = ttk.Label(self.root, textvariable=self.summary_var, style="Status.TLabel", anchor="w")
        status.pack(fill="x")

    def _set_data_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        combo_state = "readonly" if enabled else "disabled"
        for button in (
            self.mapping_button,
            self.gpa_button,
            self.calculate_button,
            self.export_button,
            self.apply_all_button,
            self.select_none_button,
            self.select_all_button,
        ):
            button.configure(state=state)
        self.key_combo.configure(state=combo_state)
        self.keep_combo.configure(state=combo_state)

    def _load_initial_file(self) -> None:
        if len(sys.argv) > 1:
            argument = Path(sys.argv[1])
            if argument.is_file():
                self.load_file(argument)
                return
        candidates: list[Path] = []
        roots = [Path.cwd(), Path(sys.executable).resolve().parent, Path(__file__).resolve().parent]
        for root in roots:
            preferred = root / "2402成绩-25-26学年.xls"
            if preferred.is_file():
                candidates.append(preferred)
            candidates.extend(sorted(root.glob("*.xls")))
            candidates.extend(sorted(root.glob("*.xlsx")))
        seen: set[Path] = set()
        unique = [item for item in candidates if not (item.resolve() in seen or seen.add(item.resolve()))]
        if unique:
            self.load_file(unique[0], show_error=False)

    def choose_file(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="打开成绩文件",
            filetypes=(
                ("成绩表", "*.xls *.xlsx *.csv *.tsv"),
                ("Excel 文件", "*.xls *.xlsx"),
                ("所有文件", "*.*"),
            ),
        )
        if filename:
            self.load_file(Path(filename))

    def load_file(self, path: Path, show_error: bool = True) -> bool:
        try:
            records = parse_grade_file(path)
        except Exception as exc:
            self.summary_var.set(f"读取失败：{exc}")
            if show_error:
                messagebox.showerror("无法读取成绩文件", str(exc), parent=self.root)
            return False
        self.source_path = path
        self.raw_records = records
        self.selection_state = {record.record_id: True for record in records}
        detected = collect_text_grades(records)
        self.text_mapping = {key: value for key, value in self.text_mapping.items() if key in detected}
        self.file_var.set(path.name)
        self._set_data_controls_enabled(True)
        self.apply_deduplication()
        self.summary_var.set(
            f"已读取 {len(records)} 条成绩，{len(group_by_student(records))} 名学生，"
            f"{len(detected)} 种文字成绩"
        )
        return True

    def apply_deduplication(self) -> None:
        if not self.raw_records:
            return
        key_mode = KEY_MODE_LABELS[self.key_mode_var.get()]
        keep_mode = KEEP_MODE_LABELS[self.keep_mode_var.get()]
        previous_student = self.current_student_id
        self.active_records = deduplicate_records(self.raw_records, key_mode, keep_mode)
        self.student_records = group_by_student(self.active_records)
        for record in self.active_records:
            self.selection_state.setdefault(record.record_id, True)
        if previous_student not in self.student_records:
            previous_student = next(iter(self.student_records), None)
        self.current_student_id = previous_student
        self.student_title_var.set(f"学生  {len(self.student_records)} 人")
        self.recalculate(refresh_students=True)

    def _refresh_student_tree(self) -> None:
        selected_id = self.current_student_id
        self.student_tree.delete(*self.student_tree.get_children())
        result_by_id = {str(row["student_id"]): row for row in self.result_rows}
        for student_id, records in self.student_records.items():
            row = result_by_id.get(student_id, {})
            status = "可计算" if row.get("weighted_average") is not None else "无有效成绩"
            self.student_tree.insert("", "end", iid=student_id, values=(student_id, records[0].student_name, status))
        if selected_id and self.student_tree.exists(selected_id):
            self.student_tree.selection_set(selected_id)
            self.student_tree.focus(selected_id)
            self.student_tree.see(selected_id)
        elif self.student_tree.get_children():
            first = self.student_tree.get_children()[0]
            self.student_tree.selection_set(first)
            self.student_tree.focus(first)
            self.current_student_id = first
        self._refresh_course_list()

    def _on_student_selected(self, _event=None) -> None:
        selection = self.student_tree.selection()
        if selection:
            self.current_student_id = selection[0]
            self._refresh_course_list()

    def _refresh_course_list(self) -> None:
        records = self.student_records.get(self.current_student_id or "", [])
        self._update_course_title(records)
        self.course_list.set_records(records, self.selection_state, self.text_mapping, self._on_course_toggled)

    def _update_course_title(self, records: Sequence[CourseRecord] | None = None) -> None:
        if records is None:
            records = self.student_records.get(self.current_student_id or "", [])
        if records:
            first = records[0]
            selected_count = sum(self.selection_state.get(item.record_id, True) for item in records)
            self.course_title_var.set(
                f"{first.student_name}  {first.student_id}    已选 {selected_count}/{len(records)} 门"
            )
        else:
            self.course_title_var.set("课程明细")

    def _on_course_toggled(self, record: CourseRecord, selected: bool) -> None:
        self.selection_state[record.record_id] = selected
        self.recalculate(refresh_students=False)
        self._update_course_title()
        self._update_student_status(record.student_id)

    def _update_student_status(self, student_id: str) -> None:
        if not self.student_tree.exists(student_id):
            return
        result = next((row for row in self.result_rows if row["student_id"] == student_id), None)
        status = "可计算" if result and result.get("weighted_average") is not None else "无有效成绩"
        values = list(self.student_tree.item(student_id, "values"))
        if len(values) >= 3:
            values[2] = status
            self.student_tree.item(student_id, values=values)

    def set_current_selection(self, selected: bool) -> None:
        for record in self.student_records.get(self.current_student_id or "", []):
            self.selection_state[record.record_id] = selected
        self.recalculate(refresh_students=True)

    def apply_selection_to_all(self) -> None:
        records = self.student_records.get(self.current_student_id or "", [])
        if not records:
            return
        key_mode = KEY_MODE_LABELS[self.key_mode_var.get()]

        def key(item: CourseRecord) -> str:
            if key_mode == "code":
                return (item.course_code or item.course_name).strip().casefold()
            return (item.course_name or item.course_code).strip().casefold()

        selected_keys = {key(item) for item in records if self.selection_state.get(item.record_id, True)}
        for item in self.active_records:
            self.selection_state[item.record_id] = key(item) in selected_keys
        self.recalculate(refresh_students=True)
        self.summary_var.set("已将当前学生的科目勾选方案应用到全部学生")

    def recalculate(self, refresh_students: bool = False) -> None:
        if not self.student_records:
            return
        selections = {
            student_id: {
                record.record_id
                for record in records
                if self.selection_state.get(record.record_id, True)
            }
            for student_id, records in self.student_records.items()
        }
        self.result_rows = build_ranked_rows(
            self.student_records,
            selections,
            self.text_mapping,
            self.gpa_bands,
        )
        self._refresh_result_tree()
        if refresh_students:
            self._refresh_student_tree()
        computable = sum(row["weighted_average"] is not None for row in self.result_rows)
        self.summary_var.set(
            f"重新计算完成：{computable}/{len(self.result_rows)} 名学生可计算；"
            f"当前规则：{self.key_mode_var.get()}，重复课程取{self.keep_mode_var.get()}"
        )

    def _refresh_result_tree(self) -> None:
        self.result_tree.delete(*self.result_tree.get_children())
        for row in self.result_rows:
            values = (
                row["grade_year"],
                row["student_id"],
                row["student_name"],
                _display_number(row["total_credits"], 2),
                _display_number(row["total_score"], 2),
                _display_number(row["average_score"], 1),
                _display_number(row["weighted_average"], 1),
                _display_number(row["credit_gpa"], 2),
                _display_number(row["average_gpa"], 4),
                "" if row["rank"] is None else row["rank"],
            )
            self.result_tree.insert("", "end", values=values)

    def open_text_mapping_dialog(self) -> None:
        grades = collect_text_grades(self.raw_records)
        if not grades:
            messagebox.showinfo("文字成绩换算", "当前文件中没有文字成绩。", parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("文字成绩换算")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, style="Surface.TFrame", padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="启用后，文字成绩将按填写的等效分数参与计算。", style="Muted.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        ttk.Label(frame, text="启用", style="CourseHeader.TLabel", padding=(8, 6)).grid(row=1, column=0, sticky="ew")
        ttk.Label(frame, text="文字成绩", style="CourseHeader.TLabel", padding=(8, 6)).grid(row=1, column=1, sticky="ew")
        ttk.Label(frame, text="等效分数", style="CourseHeader.TLabel", padding=(8, 6)).grid(row=1, column=2, sticky="ew")
        suggestions = {"优秀": 95, "良好": 85, "中等": 75, "及格": 60, "合格": 60, "不及格": 0, "不合格": 0}
        controls: dict[str, tuple[tk.BooleanVar, tk.StringVar]] = {}
        for row_index, grade in enumerate(grades, start=2):
            current = self.text_mapping.get(grade)
            enabled = tk.BooleanVar(value=current is not None)
            value = tk.StringVar(value=_display_number(current if current is not None else suggestions.get(grade, 60), 2))
            ttk.Checkbutton(frame, variable=enabled).grid(row=row_index, column=0, padx=10, pady=6)
            ttk.Label(frame, text=grade, style="Toolbar.TLabel", padding=(8, 6)).grid(row=row_index, column=1, sticky="ew")
            ttk.Entry(frame, textvariable=value, width=12, justify="center").grid(row=row_index, column=2, padx=(8, 0), pady=6)
            controls[grade] = (enabled, value)

        button_row = ttk.Frame(frame, style="Surface.TFrame")
        button_row.grid(row=2 + len(grades), column=0, columnspan=3, sticky="e", pady=(14, 0))
        ttk.Button(button_row, text="取消", command=dialog.destroy).pack(side="right")

        def save() -> None:
            mapping: dict[str, float] = {}
            try:
                for grade, (enabled, value) in controls.items():
                    if enabled.get():
                        number = float(value.get().strip())
                        if not 0 <= number <= 100:
                            raise ValueError(f"{grade} 的等效分数必须在 0 到 100 之间。")
                        mapping[grade] = number
            except ValueError as exc:
                messagebox.showerror("换算设置无效", str(exc), parent=dialog)
                return
            self.text_mapping = mapping
            dialog.destroy()
            self.recalculate(refresh_students=True)
            self._refresh_course_list()
            self.summary_var.set(f"已启用 {len(mapping)} 种文字成绩换算")

        ttk.Button(button_row, text="保存并计算", style="Primary.TButton", command=save).pack(side="right", padx=(0, 8))
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.grab_set()
        dialog.wait_visibility()
        dialog.focus_set()

    def open_gpa_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("绩点换算规则")
        dialog.transient(self.root)
        dialog.resizable(False, True)
        frame = ttk.Frame(dialog, style="Surface.TFrame", padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="成绩达到最低分时使用对应绩点。可添加任意数量的分段。", style="Muted.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 12)
        )
        editor = GpaBandsEditor(frame, self.gpa_bands)
        editor.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        def restore_defaults() -> None:
            editor.set_bands(DEFAULT_GPA_BANDS)

        def save() -> None:
            try:
                bands = editor.get_bands()
                thresholds = [threshold for threshold, _ in bands]
                if any(not math.isfinite(threshold) or not 0 <= threshold <= 100 for threshold in thresholds):
                    raise ValueError("最低分必须在 0 到 100 之间。")
                if any(not math.isfinite(points) or points < 0 for _, points in bands):
                    raise ValueError("绩点不能为负数。")
                if len(set(thresholds)) != len(thresholds):
                    raise ValueError("最低分不能重复。")
                if 0 not in thresholds:
                    raise ValueError("规则中必须包含最低分 0。")
            except ValueError as exc:
                messagebox.showerror("绩点规则无效", str(exc), parent=dialog)
                return
            self.gpa_bands = sorted(bands, reverse=True)
            dialog.destroy()
            self.recalculate(refresh_students=True)
            self.summary_var.set(f"重新计算完成：已更新 {len(bands)} 段绩点换算规则")

        button_row = ttk.Frame(frame, style="Surface.TFrame")
        button_row.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        ttk.Button(button_row, text="恢复默认", command=restore_defaults).pack(side="left")
        ttk.Button(button_row, text="取消", command=dialog.destroy).pack(side="right")
        ttk.Button(button_row, text="保存并计算", style="Primary.TButton", command=save).pack(side="right", padx=(0, 8))
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.grab_set()
        dialog.wait_visibility()
        dialog.focus_set()

    def export_file(self) -> None:
        if not self.result_rows:
            return
        initial_dir = self.source_path.parent if self.source_path else Path.cwd()
        filename = filedialog.asksaveasfilename(
            parent=self.root,
            title="导出排名表",
            initialdir=initial_dir,
            initialfile="加权平均分排名.xlsx",
            defaultextension=".xlsx",
            filetypes=(("Excel 工作簿", "*.xlsx"),),
        )
        if not filename:
            return
        try:
            destination = export_summary(filename, self.result_rows)
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc), parent=self.root)
            self.summary_var.set(f"导出失败：{exc}")
            return
        self.summary_var.set(f"已导出：{destination}")
        messagebox.showinfo("导出完成", f"排名表已保存到：\n{destination}", parent=self.root)


def main() -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    CourseCalculatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
