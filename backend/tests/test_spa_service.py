import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from services.spa_service import resolve_spa_file


class SPAServiceTest(unittest.TestCase):
    def test_vue_history_routes_fall_back_to_index(self):
        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory)
            index = dist / "index.html"
            index.write_text("app", encoding="utf-8")
            self.assertEqual(resolve_spa_file(dist, "dataset"), index)
            self.assertEqual(resolve_spa_file(dist, "dataset/create"), index)
            self.assertEqual(resolve_spa_file(dist, "finetune/12"), index)

    def test_api_and_missing_assets_do_not_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory)
            (dist / "index.html").write_text("app", encoding="utf-8")
            self.assertIsNone(resolve_spa_file(dist, "api/v1/dataset"))
            self.assertIsNone(resolve_spa_file(dist, "assets/missing.js"))

    def test_existing_root_static_file_is_served(self):
        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory)
            icon = dist / "favicon.ico"
            icon.write_bytes(b"icon")
            self.assertEqual(resolve_spa_file(dist, "favicon.ico"), icon)


if __name__ == "__main__":
    unittest.main()
