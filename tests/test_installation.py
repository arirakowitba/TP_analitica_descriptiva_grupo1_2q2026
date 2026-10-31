"""Pruebas de regresión: requieren instalar primero requirements.txt."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class EditableInstallationTests(unittest.TestCase):
    def check_imports(self, cwd):
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "-I", "-c",
             "from pathlib import Path; "
             "from src import config, eda, externas, features, geo, pe3_visuals, usig; "
             f"assert config.REPO_ROOT == Path({str(ROOT)!r}); "
             "assert config.PROCESSED_DIR.is_dir()"],
            cwd=cwd, env=env, capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_import_from_notebooks(self):
        self.check_imports(ROOT / "notebooks")

    def test_import_outside_repository(self):
        with tempfile.TemporaryDirectory() as folder:
            self.check_imports(folder)


if __name__ == "__main__":
    unittest.main()
