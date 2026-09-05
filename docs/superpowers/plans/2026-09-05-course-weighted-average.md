# 课程加权平均分计算系统实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个读取实例 `.xls`、支持课程去重和勾选、计算加权平均分并导出 Excel 的可双击 Windows EXE。

**Architecture:** 用纯 Python 计算核心隔离数据解析、去重、成绩映射和汇总计算；Tkinter 只负责交互状态；openpyxl 负责 Excel 读写和格式化；PyInstaller 将入口打包为单文件 GUI 程序。

**Tech Stack:** Python 3.10+, Tkinter/ttk, standard-library `html.parser`, openpyxl, pytest, PyInstaller.

**Spec:** `docs/superpowers/specs/2026-09-05-course-weighted-average-design.md`

## Global Constraints

- 去重快捷逻辑必须同时支持课程代码和课程名称。
- 重复处理必须支持第一条、最后一条、全部保留，默认最后一条。
- 非数字成绩默认跳过，文字成绩等效分数可编辑。
- 导出无法计算的字段必须为空，不写解释性备注。
- EXE 使用 `--onefile --windowed`，运行时不要求用户安装依赖。
- 生产代码严格遵循 TDD：每个核心行为先写一个会失败的测试，再写最小实现。

---

### Task 1: 建立计算核心的失败测试

**Files:**
- Create: `tests/test_course_calculator.py`
- Create: `tests/test_fixture_helpers.py`

**Interfaces:**
- Tests import `CourseRecord`, `parse_grade_file`, `deduplicate_records`, `calculate_student`, `build_ranked_rows`, and `DEFAULT_GPA_BANDS` from `course_calculator`.

- [ ] **Step 1: Write failing tests for HTML parsing, header repair, duplicate modes, text mapping, selections, and ranking.**

```python
def test_parse_html_xls_repairs_two_row_last_header(tmp_path):
    path = write_html_fixture(tmp_path)
    records = parse_grade_file(path)
    assert records[0].course_code == "C-01"
    assert records[0].raw_score == "优秀"

def test_duplicate_modes_select_first_last_or_all():
    records = sample_duplicate_records()
    assert len(deduplicate_records(records, "code", "first")) == 1
    assert deduplicate_records(records, "code", "last")[0].raw_score == "88"
    assert len(deduplicate_records(records, "code", "all")) == 2

def test_text_grade_mapping_and_weighted_metrics():
    result = calculate_student(sample_records(), {"r1", "r2"}, {"优秀": 95.0})
    assert result["total_credits"] == 3.0
    assert result["weighted_average"] == 90.0
    assert result["credit_gpa"] == 11.1

def test_unmapped_text_grade_leaves_student_uncomputable():
    result = calculate_student(sample_records(), {"text"}, {})
    assert result["weighted_average"] is None

def test_ranked_rows_use_competition_rank_and_blank_uncomputable():
    rows = build_ranked_rows(sample_student_records(), selections={}, text_mapping={})
    assert [row["rank"] for row in rows] == [1, 1, 3, None]
```

- [ ] **Step 2: Run the focused tests and verify they fail because `course_calculator` is absent.**

Run: `python -m pytest tests/test_course_calculator.py -q`

Expected: collection failure with `ModuleNotFoundError: No module named 'course_calculator'`.

### Task 2: Implement the pure-Python parsing and calculation core

**Files:**
- Create: `course_calculator.py`
- Modify: `tests/test_course_calculator.py` only if a test assertion needs exact fixture normalization.

**Interfaces:**
- `CourseRecord` is an immutable dataclass with `record_id`, source metadata, credits, and `raw_score`.
- `parse_grade_file(path: str | Path) -> list[CourseRecord]` reads HTML `.xls`, `.xlsx`, or delimited text.
- `deduplicate_records(records, key_mode: str = "code", keep: str = "last") -> list[CourseRecord]`.
- `calculate_student(records, selected_ids, text_mapping, gpa_bands=DEFAULT_GPA_BANDS) -> dict[str, float | None]`.
- `build_ranked_rows(student_records, selections, text_mapping, ...) -> list[dict]`.

- [ ] **Step 1: Run the failing tests from Task 1 and capture the expected missing-module failure.**
- [ ] **Step 2: Implement `CourseRecord`, the HTML table parser, header row repair, and normalized record construction.**
- [ ] **Step 3: Run parser tests and verify the parser assertions pass.**
- [ ] **Step 4: Implement code/name duplicate grouping with first/last/all behavior and stable source order.**
- [ ] **Step 5: Run duplicate tests and verify all three modes pass.**
- [ ] **Step 6: Implement numeric/text grade resolution, default GPA bands, selected-course metrics, and blank results for zero computable courses.**
- [ ] **Step 7: Implement competition ranking while preserving first-seen student order.**
- [ ] **Step 8: Run the full core test module and verify it passes with no warnings.**

### Task 3: Add Excel import/export and formatting tests

**Files:**
- Create: `tests/test_excel_io.py`
- Create: `excel_io.py`

**Interfaces:**
- `export_summary(path, rows, title="加权平均分排名") -> Path` creates an `.xlsx` with the ten requested columns.
- `read_xlsx_records(path) -> list[CourseRecord]` delegates normalized rows to the same core model.

- [ ] **Step 1: Write failing tests that inspect header order, blank uncomputable cells, numeric formats, freeze panes, and rank ordering in the exported workbook.**
- [ ] **Step 2: Run `python -m pytest tests/test_excel_io.py -q` and verify it fails because the module is absent.**
- [ ] **Step 3: Implement openpyxl import for `.xlsx` and styled summary export with a frozen first row, autofilter, widths, borders, and blank `None` cells.**
- [ ] **Step 4: Run the export tests and verify they pass.**

### Task 4: Build the Tkinter desktop interface

**Files:**
- Create: `app.py`
- Modify: `course_calculator.py` only for UI-facing helper types if tests remain green.

**Interfaces:**
- `CourseCalculatorApp` owns raw records, deduped records, per-student selections, text mappings, GPA bands, and preview rows.
- Toolbar actions call `load_file`, `apply_deduplication`, `open_text_mapping_dialog`, `open_gpa_dialog`, `recalculate`, and `export_file`.

- [ ] **Step 1: Add a smoke test that imports `app` and verifies the main class exists without creating a Tk root at import time.**
- [ ] **Step 2: Implement the main window, toolbar, split student/course selection area, scrollable course rows with checkbuttons, and result preview.**
- [ ] **Step 3: Implement per-student selection persistence, select-all/select-none, apply-to-all, duplicate controls, and live status text.**
- [ ] **Step 4: Implement text mapping and editable GPA dialogs with validation and cancel behavior.**
- [ ] **Step 5: Implement file dialogs, auto-discovery of the example file, messagebox error handling, and export action.**
- [ ] **Step 6: Run all tests and perform a manual launch smoke check with the provided `.xls`.**

### Task 5: Package and verify the EXE

**Files:**
- Create: `build_exe.ps1`
- Create: `README.md`

**Interfaces:**
- `build_exe.ps1` cleans only the project-local `build/` and `dist/` directories, then runs PyInstaller against `app.py`.
- Output: `dist/课程加权平均分计算器.exe`.

- [ ] **Step 1: Write the build script and README usage/build notes.**
- [ ] **Step 2: Run the full test suite: `python -m pytest -q`.**
- [ ] **Step 3: Build the EXE with `powershell -ExecutionPolicy Bypass -File .\build_exe.ps1` and verify exit code 0 and the output file exists.**
- [ ] **Step 4: Launch the EXE in a separate process with the provided `.xls`, verify it reaches the main window, then close it cleanly.**
- [ ] **Step 5: Run an end-to-end export through the core/export path and inspect the resulting workbook headers, 51 student rows, blank text-grade behavior, and rank values.**
