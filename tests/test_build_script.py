import unittest
from pathlib import Path


class BuildScriptTests(unittest.TestCase):
    def test_windows_powershell_build_script_is_ascii_safe(self):
        script = Path(__file__).parents[1] / "build_exe.ps1"

        script.read_text(encoding="ascii")

    def test_build_script_embeds_custom_icon(self):
        script = (Path(__file__).parents[1] / "build_exe.ps1").read_text(encoding="ascii")

        self.assertIn("--icon", script)
        self.assertIn("--add-data", script)

    def test_icon_source_has_distinct_score_sheet_colors(self):
        icon = (Path(__file__).parents[1] / "assets" / "icon.svg").read_text(encoding="utf-8")

        self.assertIn("#F4B942", icon)
        self.assertIn("#287A4D", icon)
        self.assertIn("#FFFFFF", icon)


if __name__ == "__main__":
    unittest.main()
