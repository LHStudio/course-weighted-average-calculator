import unittest
from pathlib import Path


class BuildScriptTests(unittest.TestCase):
    def test_windows_powershell_build_script_is_ascii_safe(self):
        script = Path(__file__).parents[1] / "build_exe.ps1"

        script.read_text(encoding="ascii")


if __name__ == "__main__":
    unittest.main()
