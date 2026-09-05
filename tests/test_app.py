import unittest
import tkinter as tk


class AppImportTests(unittest.TestCase):
    def test_app_exposes_main_window_without_creating_root_on_import(self):
        import app

        self.assertTrue(hasattr(app, "CourseCalculatorApp"))
        self.assertTrue(callable(app.main))

    def test_high_dpi_layout_has_separate_settings_row_and_horizontal_course_scroll(self):
        import app

        root = tk.Tk()
        root.withdraw()
        try:
            window = app.CourseCalculatorApp(root)
            self.assertTrue(hasattr(window, "settings_toolbar"))
            self.assertTrue(hasattr(window.course_list, "horizontal_scrollbar"))
        finally:
            root.destroy()

    def test_course_list_exposes_frozen_header_and_larger_checkbutton_style(self):
        import app

        root = tk.Tk()
        root.withdraw()
        try:
            window = app.CourseCalculatorApp(root)
            self.assertTrue(hasattr(window.course_list, "header_canvas"))
            self.assertGreaterEqual(window.course_list.checkbox_font.cget("size"), 12)
        finally:
            root.destroy()

    def test_course_toggle_refreshes_result_without_rebuilding_course_rows(self):
        import app

        root = tk.Tk()
        root.withdraw()
        try:
            window = app.CourseCalculatorApp(root)
            calls = []
            original = window._refresh_course_list
            window._refresh_course_list = lambda: calls.append(True)
            item = app.CourseRecord(
                record_id="r1",
                source_index=0,
                student_id="s1",
                student_name="A",
                course_code="C1",
                course_name="Course",
                credits=1,
                raw_score="90",
            )
            window._on_course_toggled(item, False)
            self.assertEqual(calls, [])
            window._refresh_course_list = original
        finally:
            root.destroy()

    def test_gpa_dialog_has_dynamic_row_controls(self):
        import app

        root = tk.Tk()
        root.withdraw()
        try:
            editor = app.GpaBandsEditor(root, [(60, 1.0), (0, 0.0)])
            editor.add_row(90, 4.0)
            self.assertEqual(editor.get_bands(), [(90.0, 4.0), (60.0, 1.0), (0.0, 0.0)])
            editor.remove_row()
            self.assertEqual(len(editor.variables), 2)
        finally:
            root.destroy()

    def test_recalculate_reports_completion_in_status_bar(self):
        import app

        root = tk.Tk()
        root.withdraw()
        try:
            window = app.CourseCalculatorApp(root)
            item = app.CourseRecord(
                record_id="r1",
                source_index=0,
                student_id="s1",
                student_name="A",
                course_code="C1",
                course_name="Course",
                credits=1,
                raw_score="90",
            )
            window.student_records = {"s1": [item]}
            window.selection_state = {"r1": True}
            window.recalculate()
            self.assertIn("重新计算完成", window.summary_var.get())
            self.assertIn("1/1 名学生可计算", window.summary_var.get())
        finally:
            root.destroy()

    def test_course_toggle_updates_only_current_student_status(self):
        import app

        root = tk.Tk()
        root.withdraw()
        try:
            window = app.CourseCalculatorApp(root)
            item = app.CourseRecord(
                record_id="r1",
                source_index=0,
                student_id="s1",
                student_name="A",
                course_code="C1",
                course_name="Course",
                credits=1,
                raw_score="90",
            )
            window.student_records = {"s1": [item]}
            window.current_student_id = "s1"
            window.selection_state = {"r1": True}
            window.student_tree.insert("", "end", iid="s1", values=("s1", "A", "可计算"))
            window._on_course_toggled(item, False)
            self.assertEqual(window.student_tree.set("s1", "state"), "无有效成绩")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
