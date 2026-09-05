from __future__ import annotations

import csv
import math
import re
from collections import OrderedDict
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Mapping, Sequence


DEFAULT_GPA_BANDS: tuple[tuple[float, float], ...] = (
    (90, 4.0),
    (85, 3.7),
    (82, 3.3),
    (78, 3.0),
    (75, 2.7),
    (72, 2.3),
    (68, 2.0),
    (64, 1.5),
    (60, 1.0),
    (0, 0.0),
)

REQUIRED_HEADERS = ("学号", "姓名", "课程名称", "学分", "成绩")
HEADER_ALIASES = {
    "学号": ("学号",),
    "姓名": ("姓名",),
    "年级": ("年级",),
    "班级": ("班级",),
    "学期": ("取得学年学期", "学年学期", "学期"),
    "课程代码": ("课程代码", "课程编号"),
    "课程名称": ("课程名称", "课程名"),
    "学分": ("学分",),
    "成绩": ("成绩", "总评成绩"),
    "课程类别": ("课程类别",),
    "取得方式": ("取得方式",),
    "是否辅修课程": ("是否辅修课程", "是否辅"),
}


@dataclass(frozen=True)
class CourseRecord:
    record_id: str
    source_index: int
    student_id: str
    student_name: str
    course_code: str
    course_name: str
    credits: float
    raw_score: str
    grade_year: str = ""
    class_name: str = ""
    term: str = ""
    category: str = ""
    acquisition: str = ""
    is_minor: str = ""


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table_depth = 0
        self._rows: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._rows = []
        elif self._table_depth == 1 and tag == "tr":
            self._row = []
        elif self._table_depth == 1 and tag in {"td", "th"}:
            self._cell_parts = []
        elif self._cell_parts is not None and tag == "br":
            self._cell_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._table_depth == 1 and tag in {"td", "th"} and self._cell_parts is not None:
            value = "".join(self._cell_parts).replace("\xa0", " ").strip()
            if self._row is not None:
                self._row.append(value)
            self._cell_parts = None
        elif self._table_depth == 1 and tag == "tr":
            if self._rows is not None and self._row and any(cell.strip() for cell in self._row):
                self._rows.append(self._row)
            self._row = None
        elif tag == "table" and self._table_depth:
            if self._table_depth == 1 and self._rows is not None:
                self.tables.append(self._rows)
                self._rows = None
            self._table_depth -= 1


def _clean_header(value: object) -> str:
    return "".join(str(value or "").replace("\n", "").split())


def _find_header_row(rows: Sequence[Sequence[object]]) -> tuple[int, list[str]]:
    for index, row in enumerate(rows):
        headers = [_clean_header(value) for value in row]
        if all(required in headers for required in REQUIRED_HEADERS):
            return index, ["是否辅修课程" if value == "是否辅" else value for value in headers]
    raise ValueError("未找到成绩表头，请确认文件包含学号、姓名、课程名称、学分和成绩列。")


def _column_index(headers: Sequence[str], logical_name: str) -> int | None:
    aliases = HEADER_ALIASES[logical_name]
    for alias in aliases:
        if alias in headers:
            return headers.index(alias)
    return None


def _cell(row: Sequence[object], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    value = row[index]
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _parse_credits(value: str) -> float | None:
    try:
        credits = float(value.strip())
    except (TypeError, ValueError):
        return None
    return credits if math.isfinite(credits) and credits > 0 else None


def records_from_rows(rows: Sequence[Sequence[object]]) -> list[CourseRecord]:
    header_index, headers = _find_header_row(rows)
    indexes = {name: _column_index(headers, name) for name in HEADER_ALIASES}
    records: list[CourseRecord] = []

    for row_index, row in enumerate(rows[header_index + 1 :], start=header_index + 1):
        student_id = _cell(row, indexes["学号"])
        student_name = _cell(row, indexes["姓名"])
        course_name = _cell(row, indexes["课程名称"])
        credits = _parse_credits(_cell(row, indexes["学分"]))
        raw_score = _cell(row, indexes["成绩"])
        if not student_id or not student_name or not course_name or credits is None:
            continue
        course_code = _cell(row, indexes["课程代码"])
        record_id = f"{row_index}:{student_id}:{course_code or course_name}"
        records.append(
            CourseRecord(
                record_id=record_id,
                source_index=row_index,
                student_id=student_id,
                student_name=student_name,
                course_code=course_code,
                course_name=course_name,
                credits=credits,
                raw_score=raw_score,
                grade_year=_cell(row, indexes["年级"]),
                class_name=_cell(row, indexes["班级"]),
                term=_cell(row, indexes["学期"]),
                category=_cell(row, indexes["课程类别"]),
                acquisition=_cell(row, indexes["取得方式"]),
                is_minor=_cell(row, indexes["是否辅修课程"]),
            )
        )
    if not records:
        raise ValueError("成绩表中没有识别到有效课程记录。")
    return records


def _read_html_rows(path: Path) -> list[list[str]]:
    raw = path.read_bytes()
    text = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("无法识别文件字符编码。")
    parser = _TableParser()
    parser.feed(text)
    if not parser.tables:
        raise ValueError("文件中未找到成绩表格。")
    return max(parser.tables, key=len)


def _read_delimited_rows(path: Path) -> list[list[str]]:
    raw = path.read_bytes()
    text = None
    for encoding in ("utf-8-sig", "gb18030", "utf-8"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("无法识别文件字符编码。")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
    except csv.Error:
        dialect = csv.excel_tab if path.suffix.lower() == ".tsv" else csv.excel
    return [list(row) for row in csv.reader(text.splitlines(), dialect)]


def parse_grade_file(path: str | Path) -> list[CourseRecord]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"找不到成绩文件：{source}")
    suffix = source.suffix.lower()
    if suffix == ".xlsx":
        from excel_io import read_xlsx_records

        return read_xlsx_records(source)
    if suffix in {".csv", ".tsv"}:
        return records_from_rows(_read_delimited_rows(source))

    signature = source.read_bytes()[:16].lstrip().lower()
    if suffix in {".xls", ".html", ".htm"} and signature.startswith((b"<html", b"<!doctype")):
        return records_from_rows(_read_html_rows(source))
    if suffix == ".xls":
        raise ValueError("暂不支持二进制旧版 XLS，请先在 Excel/WPS 中另存为 XLSX。")
    raise ValueError("仅支持 .xls（HTML 格式）、.xlsx、.csv 和 .tsv 成绩文件。")


def deduplicate_records(
    records: Iterable[CourseRecord], key_mode: str = "code", keep: str = "last"
) -> list[CourseRecord]:
    ordered = sorted(records, key=lambda item: item.source_index)
    if keep == "all":
        return ordered
    if key_mode not in {"code", "name"}:
        raise ValueError("去重依据必须是 code 或 name。")
    if keep not in {"first", "last"}:
        raise ValueError("重复处理方式必须是 first、last 或 all。")

    selected: OrderedDict[tuple[str, str], CourseRecord] = OrderedDict()
    for item in ordered:
        course_key = item.course_code if key_mode == "code" else item.course_name
        if not course_key:
            course_key = item.course_name if key_mode == "code" else item.course_code
        key = (item.student_id, course_key.strip().casefold())
        if keep == "first":
            selected.setdefault(key, item)
        else:
            selected[key] = item
    return sorted(selected.values(), key=lambda item: item.source_index)


def group_by_student(records: Iterable[CourseRecord]) -> OrderedDict[str, list[CourseRecord]]:
    groups: OrderedDict[str, list[CourseRecord]] = OrderedDict()
    for item in sorted(records, key=lambda record: record.source_index):
        groups.setdefault(item.student_id, []).append(item)
    return groups


def parse_score(raw_score: object, text_mapping: Mapping[str, float | None]) -> float | None:
    text = str(raw_score or "").strip()
    if not text:
        return None
    try:
        score = float(text.replace(",", ""))
    except ValueError:
        mapped = text_mapping.get(text)
        if mapped is None:
            return None
        try:
            score = float(mapped)
        except (TypeError, ValueError):
            return None
    if not math.isfinite(score):
        return None
    return score


def collect_text_grades(records: Iterable[CourseRecord]) -> list[str]:
    values: OrderedDict[str, None] = OrderedDict()
    for item in records:
        if parse_score(item.raw_score, {}) is None and str(item.raw_score).strip():
            values.setdefault(str(item.raw_score).strip(), None)
    return list(values)


def score_to_gpa(score: float, gpa_bands: Sequence[tuple[float, float]] = DEFAULT_GPA_BANDS) -> float:
    bands = sorted(((float(threshold), float(gpa)) for threshold, gpa in gpa_bands), reverse=True)
    for threshold, gpa in bands:
        if score >= threshold:
            return gpa
    return 0.0


def _rounded(value: float) -> float:
    return round(value, 6)


def format_grade_label(grade_year: str, term: str) -> str:
    match = re.search(r"(\d{4})\s*[-—]\s*(\d{4})", term or "")
    try:
        enrollment_year = int(str(grade_year).strip())
    except ValueError:
        return grade_year
    if not match:
        return grade_year
    academic_start = int(match.group(1))
    class_year = academic_start - enrollment_year + 1
    chinese_years = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八"}
    if class_year not in chinese_years:
        return grade_year
    return f"{match.group(1)}-{match.group(2)}大{chinese_years[class_year]}"


def calculate_student(
    records: Iterable[CourseRecord],
    selected_ids: set[str] | None,
    text_mapping: Mapping[str, float | None],
    gpa_bands: Sequence[tuple[float, float]] = DEFAULT_GPA_BANDS,
) -> dict[str, int | float | None]:
    computable: list[tuple[CourseRecord, float]] = []
    for item in records:
        if selected_ids is not None and item.record_id not in selected_ids:
            continue
        score = parse_score(item.raw_score, text_mapping)
        if score is not None and item.credits > 0:
            computable.append((item, score))

    if not computable:
        return {
            "course_count": 0,
            "total_credits": None,
            "total_score": None,
            "average_score": None,
            "weighted_average": None,
            "credit_gpa": None,
            "average_gpa": None,
        }

    total_credits = sum(item.credits for item, _ in computable)
    total_score = sum(score for _, score in computable)
    weighted_score = sum(item.credits * score for item, score in computable)
    credit_gpa = sum(item.credits * score_to_gpa(score, gpa_bands) for item, score in computable)
    return {
        "course_count": len(computable),
        "total_credits": _rounded(total_credits),
        "total_score": _rounded(total_score),
        "average_score": _rounded(total_score / len(computable)),
        "weighted_average": _rounded(weighted_score / total_credits),
        "credit_gpa": _rounded(credit_gpa),
        "average_gpa": _rounded(credit_gpa / total_credits),
    }


def build_ranked_rows(
    student_records: Mapping[str, Sequence[CourseRecord]],
    selections: Mapping[str, set[str]],
    text_mapping: Mapping[str, float | None],
    gpa_bands: Sequence[tuple[float, float]] = DEFAULT_GPA_BANDS,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for student_id, records in student_records.items():
        if not records:
            continue
        first = records[0]
        selected = selections.get(student_id)
        metrics = calculate_student(records, selected, text_mapping, gpa_bands)
        rows.append(
            {
                "grade_year": format_grade_label(first.grade_year, first.term),
                "student_id": student_id,
                "student_name": first.student_name,
                **metrics,
                "rank": None,
            }
        )

    scores = sorted(
        (float(row["weighted_average"]) for row in rows if row["weighted_average"] is not None),
        reverse=True,
    )
    first_rank: dict[float, int] = {}
    for position, score in enumerate(scores, start=1):
        first_rank.setdefault(round(score, 6), position)
    for row in rows:
        value = row["weighted_average"]
        if value is not None:
            row["rank"] = first_rank[round(float(value), 6)]
    return rows
