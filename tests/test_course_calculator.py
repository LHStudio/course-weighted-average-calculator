import tempfile
import unittest
from pathlib import Path

from course_calculator import (
    CourseRecord,
    DEFAULT_GPA_BANDS,
    build_ranked_rows,
    calculate_student,
    deduplicate_records,
    parse_grade_file,
)

from test_fixture_helpers import write_html_fixture


def record(
    record_id,
    student_id="1001",
    student_name="Test",
    code="C-01",
    name="Course",
    credits=1.0,
    score="90",
    source_index=0,
    grade_year="",
    term="",
):
    return CourseRecord(
        record_id=record_id,
        source_index=source_index,
        student_id=student_id,
        student_name=student_name,
        course_code=code,
        course_name=name,
        credits=credits,
        raw_score=score,
        grade_year=grade_year,
        term=term,
    )


class CourseCalculatorTests(unittest.TestCase):
    def test_parse_html_xls_repairs_two_row_last_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_html_fixture(Path(directory))
            records = parse_grade_file(path)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].course_code, "C-01")
        self.assertEqual(records[0].raw_score, "\u4f18\u79c0")
        self.assertEqual(records[0].student_id, "1001")

    def test_duplicate_modes_select_first_last_or_all(self):
        records = [
            record("r1", score="60", source_index=1),
            record("r2", score="88", source_index=2),
        ]

        first = deduplicate_records(records, "code", "first")
        last = deduplicate_records(records, "code", "last")
        all_records = deduplicate_records(records, "code", "all")

        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].raw_score, "60")
        self.assertEqual(len(last), 1)
        self.assertEqual(last[0].raw_score, "88")
        self.assertEqual([item.record_id for item in all_records], ["r1", "r2"])

    def test_duplicate_by_course_name_is_a_separate_shortcut(self):
        records = [
            record("code-a", code="A", name="\u540c\u540d\u8bfe\u7a0b", source_index=1),
            record("code-b", code="B", name="\u540c\u540d\u8bfe\u7a0b", source_index=2),
        ]

        self.assertEqual(len(deduplicate_records(records, "code", "last")), 2)
        self.assertEqual(len(deduplicate_records(records, "name", "last")), 1)

    def test_text_grade_mapping_and_weighted_metrics(self):
        records = [
            record("numeric", credits=1.0, score="90"),
            record("text", credits=2.0, score="\u4f18\u79c0", source_index=1),
        ]

        result = calculate_student(records, {"numeric", "text"}, {"\u4f18\u79c0": 90.0})

        self.assertEqual(result["course_count"], 2)
        self.assertEqual(result["total_credits"], 3.0)
        self.assertEqual(result["total_score"], 180.0)
        self.assertEqual(result["average_score"], 90.0)
        self.assertEqual(result["weighted_average"], 90.0)
        self.assertEqual(result["credit_gpa"], 12.0)
        self.assertEqual(result["average_gpa"], 4.0)

    def test_unmapped_text_grade_leaves_student_uncomputable(self):
        result = calculate_student([record("text", score="\u5408\u683c")], {"text"}, {})

        self.assertEqual(result["course_count"], 0)
        self.assertIsNone(result["total_credits"])
        self.assertIsNone(result["weighted_average"])
        self.assertIsNone(result["average_gpa"])

    def test_selected_ids_exclude_unchecked_courses(self):
        records = [
            record("keep", credits=2.0, score="80"),
            record("skip", credits=4.0, score="100", source_index=1),
        ]

        result = calculate_student(records, {"keep"}, {})

        self.assertEqual(result["course_count"], 1)
        self.assertEqual(result["total_credits"], 2.0)
        self.assertEqual(result["weighted_average"], 80.0)

    def test_ranked_rows_use_competition_rank_and_blank_uncomputable(self):
        student_records = {
            "s1": [record("s1-r", student_id="s1", student_name="A", score="90")],
            "s2": [record("s2-r", student_id="s2", student_name="B", score="90")],
            "s3": [record("s3-r", student_id="s3", student_name="C", score="80")],
            "s4": [record("s4-r", student_id="s4", student_name="D", score="\u5408\u683c")],
        }

        rows = build_ranked_rows(student_records, selections={}, text_mapping={})

        self.assertEqual([row["rank"] for row in rows], [1, 1, 3, None])
        self.assertEqual(rows[0]["weighted_average"], 90.0)
        self.assertIsNone(rows[-1]["weighted_average"])

    def test_export_grade_label_combines_academic_year_and_class_year(self):
        student_records = {
            "1001": [
                record(
                    "r1",
                    grade_year="2024",
                    term="2025-2026\u5b66\u5e74\u7b2c\u4e00\u5b66\u671f",
                )
            ]
        }

        rows = build_ranked_rows(student_records, selections={}, text_mapping={})

        self.assertEqual(rows[0]["grade_year"], "2025-2026\u5927\u4e8c")

    def test_default_gpa_bands_are_descending_and_cover_zero(self):
        thresholds = [threshold for threshold, _ in DEFAULT_GPA_BANDS]

        self.assertEqual(thresholds, sorted(thresholds, reverse=True))
        self.assertEqual(thresholds[-1], 0)


if __name__ == "__main__":
    unittest.main()
