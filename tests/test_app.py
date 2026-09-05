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


if __name__ == "__main__":
    unittest.main()
