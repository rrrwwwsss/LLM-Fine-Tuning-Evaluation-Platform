import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from database import Base
import models  # noqa: F401 - registers all tables on Base metadata
import services.dataset_service as dataset_service_module
from services.dataset_service import DatasetService


class DatasetServiceLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.engine = create_engine(f"sqlite:///{root / 'test.db'}")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.datasets_dir = root / "datasets"
        self.server_root = root / "server_files"
        self.server_root.mkdir()
        self.session_patch = patch.object(dataset_service_module, "SessionLocal", self.session_factory)
        self.directory_patch = patch.object(dataset_service_module, "DATASETS_DIR", self.datasets_dir)
        self.server_roots_patch = patch.object(dataset_service_module, "SERVER_BROWSE_ROOTS", [self.server_root])
        self.session_patch.start()
        self.directory_patch.start()
        self.server_roots_patch.start()

    def tearDown(self):
        self.server_roots_patch.stop()
        self.directory_patch.stop()
        self.session_patch.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def test_create_edit_split_convert_and_invalidate(self):
        columns = [
            {"name": "prompt_text", "type": "long_text", "role": "prompt", "required": True},
            {"name": "answer", "type": "long_text", "role": "answer", "required": True},
            {"name": "image_path", "type": "image", "role": "image"},
            {"name": "score", "type": "number", "role": "other"},
        ]
        dataset = DatasetService.create_dataset("demo", "portable dataset", columns, 0.67)
        DatasetService.append_source_rows(dataset.id, [
            {"prompt_text": "question 1", "answer": "yes", "image_path": "images/one.png", "score": 1},
            {"prompt_text": "question 2", "answer": "no", "image_path": "", "score": 2},
            {"prompt_text": "question 3", "answer": "yes", "image_path": "images/three.png", "score": 3},
        ])

        converted = DatasetService.split_dataset(dataset.id, 0.67)
        self.assertEqual(converted.status, "converted")
        self.assertEqual(converted.train_rows, 2)
        data = json.loads(Path(converted.train_json).read_text(encoding="utf-8"))
        self.assertEqual(len(data), 2)
        for item in data:
            if item.get("images"):
                self.assertTrue(Path(item["images"][0]).is_absolute())
            else:
                self.assertFalse(item["messages"][0]["content"].startswith("<image>"))

        DatasetService.update_source_row(dataset.id, 0, {"answer": "updated"})
        updated = DatasetService.get_dataset(dataset.id)
        self.assertEqual(updated.status, "uploaded")
        self.assertFalse(updated.train_json)
        self.assertFalse((self.datasets_dir / f"dataset_{dataset.id}" / "data.json").exists())

    def test_schema_can_rename_and_reorder_columns(self):
        dataset = DatasetService.create_dataset("rename", "", [
            {"name": "prompt", "role": "prompt", "type": "text"},
            {"name": "answer", "role": "answer", "type": "text"},
        ])
        DatasetService.append_source_rows(dataset.id, [{"prompt": "hello", "answer": "world"}])
        DatasetService.update_schema(dataset.id, "renamed", [
            {"name": "response", "source_name": "answer", "role": "answer", "type": "long_text"},
            {"name": "instruction", "source_name": "prompt", "role": "prompt", "type": "long_text"},
        ])
        source = DatasetService.preview_source(dataset.id)
        self.assertEqual(source["columns"], ["response", "instruction"])
        self.assertEqual(source["rows"][0]["response"], "world")
        self.assertEqual(source["rows"][0]["instruction"], "hello")

    def test_filter_and_batch_assign_or_delete_source_rows(self):
        dataset = DatasetService.create_dataset("batch", "", [
            {"name": "prompt", "role": "prompt", "type": "text"},
            {"name": "answer", "role": "answer", "type": "text"},
            {"name": "group", "role": "other", "type": "label"},
        ])
        DatasetService.append_source_rows(dataset.id, [
            {"prompt": "red apple", "answer": "a", "group": ""},
            {"prompt": "green apple", "answer": "b", "group": ""},
            {"prompt": "pear", "answer": "c", "group": ""},
            {"prompt": "", "answer": "d", "group": ""},
        ])

        filtered = DatasetService.preview_source(dataset.id, 1, 50, "prompt", "contains", "apple")
        self.assertEqual(filtered["total"], 2)
        self.assertEqual(filtered["dataset_total"], 4)
        self.assertEqual([row["_row_index"] for row in filtered["rows"]], [0, 1])

        assigned = DatasetService.batch_source_rows(dataset.id, {
            "action": "assign", "scope": "filtered",
            "filter_column": "prompt", "filter_mode": "contains", "filter_value": "apple",
            "assignment_column": "group", "assignment_value": "fruit",
        })
        self.assertEqual(assigned["affected"], 2)
        fruit_rows = DatasetService.preview_source(dataset.id, 1, 50, "group", "equals", "fruit")
        self.assertEqual(fruit_rows["total"], 2)

        deleted = DatasetService.batch_source_rows(dataset.id, {
            "action": "delete", "scope": "selected", "row_indices": [0, 2],
        })
        self.assertEqual(deleted["affected"], 2)
        self.assertEqual(DatasetService.preview_source(dataset.id)["dataset_total"], 2)

        empty_rows = DatasetService.preview_source(dataset.id, 1, 50, "prompt", "empty", "")
        self.assertEqual(empty_rows["total"], 1)

    def test_dpo_dataset_generates_ranked_preference_data(self):
        dataset = DatasetService.create_dataset("dpo-demo", "", [
            {"name": "prompt", "role": "prompt", "type": "long_text", "required": True},
            {"name": "chosen", "role": "chosen", "type": "long_text", "required": True},
            {"name": "rejected", "role": "rejected", "type": "long_text", "required": True},
            {"name": "image", "role": "image", "type": "image"},
        ], training_stage="dpo")
        DatasetService.append_source_rows(dataset.id, [
            {"prompt": "p1", "chosen": "good1", "rejected": "bad1", "image": "images/a.png"},
            {"prompt": "p2", "chosen": "good2", "rejected": "bad2", "image": ""},
            {"prompt": "p3", "chosen": "good3", "rejected": "bad3", "image": ""},
        ])
        converted = DatasetService.split_dataset(dataset.id, 0.67)
        info = json.loads(Path(converted.dataset_info_json).read_text(encoding="utf-8"))[f"dataset_{dataset.id}"]
        self.assertTrue(info["ranking"])
        self.assertEqual(info["columns"]["chosen"], "chosen")
        data = json.loads(Path(converted.train_json).read_text(encoding="utf-8"))
        self.assertEqual(len(data[0]["messages"]), 1)
        self.assertEqual(data[0]["chosen"]["role"], "assistant")
        self.assertEqual(data[0]["rejected"]["role"], "assistant")

    def test_folder_import_creates_image_rows_and_requires_annotation(self):
        dataset = DatasetService.create_dataset("folder", "", [
            {"name": "prompt", "role": "prompt", "type": "long_text", "required": True},
            {"name": "answer", "role": "answer", "type": "long_text", "required": True},
            {"name": "image", "role": "image", "type": "image"},
        ])
        result = DatasetService.import_image_folder(dataset.id, [
            ("folder/a.jpg", b"fake-jpg"),
            ("folder/sub/b.png", b"fake-png"),
        ], {"prompt": "describe this image"})
        self.assertEqual(result["imported"], 2)
        source = DatasetService.preview_source(dataset.id)
        self.assertEqual(source["total"], 2)
        self.assertEqual(source["rows"][0]["image"], "a.jpg")
        self.assertEqual(source["rows"][1]["image"], "sub/b.png")
        self.assertEqual(result["paths"], ["a.jpg", "sub/b.png"])
        self.assertEqual(source["rows"][0]["prompt"], "describe this image")
        resolved = DatasetService.resolve_asset(dataset.id, source["rows"][0]["image"])
        self.assertTrue(resolved.is_file())
        original_content = resolved.read_bytes()
        duplicate_result = DatasetService.import_image_folder(dataset.id, [
            ("folder/a.jpg", b"replacement"),
            ("folder/sub/b.png", b"replacement"),
            ("folder/a.jpg", b"duplicate-in-the-same-batch"),
        ], {"prompt": "new prompt"})
        self.assertEqual(duplicate_result["imported"], 0)
        self.assertEqual(duplicate_result["skipped"], 3)
        self.assertEqual(DatasetService.preview_source(dataset.id)["total"], 2)
        self.assertEqual(resolved.read_bytes(), original_content)
        keep_root_result = DatasetService.import_image_folder(dataset.id, [
            ("another_root/nested/c.jpg", b"third-image"),
        ], {"prompt": "root kept"}, path_strip_levels=0)
        self.assertEqual(keep_root_result["paths"], ["another_root/nested/c.jpg"])
        self.assertTrue(DatasetService.resolve_asset(dataset.id, "another_root/nested/c.jpg").is_file())
        with self.assertRaisesRegex(Exception, "Invalid asset path"):
            DatasetService.resolve_asset(dataset.id, "../outside.png")
        with self.assertRaisesRegex(Exception, "required column answer"):
            DatasetService.split_dataset(dataset.id, 0.5)
        DatasetService.update_source_row(dataset.id, 0, {"answer": "a1"})
        DatasetService.update_source_row(dataset.id, 1, {"answer": "a2"})
        DatasetService.update_source_row(dataset.id, 2, {"answer": "a3"})
        converted = DatasetService.split_dataset(dataset.id, 0.5)
        self.assertEqual(converted.status, "converted")

    def test_browse_and_import_existing_server_image_folder(self):
        image_folder = self.server_root / "pic"
        (image_folder / "baitan").mkdir(parents=True)
        (image_folder / "root.jpg").write_bytes(b"root-image")
        (image_folder / "baitan" / "nested.png").write_bytes(b"nested-image")
        dataset = DatasetService.create_dataset("server-folder", "", [
            {"name": "prompt", "role": "prompt", "type": "long_text", "required": True},
            {"name": "answer", "role": "answer", "type": "long_text", "required": True},
            {"name": "image", "role": "image", "type": "image"},
        ])

        roots = DatasetService.list_server_directory()
        self.assertEqual(roots["entries"][0]["path"], self.server_root.as_posix())
        listing = DatasetService.list_server_directory(self.server_root)
        self.assertEqual(listing["entries"][0]["name"], "pic")
        inspected = DatasetService.inspect_server_image_folder(image_folder)
        self.assertEqual(inspected["count"], 2)
        self.assertEqual(inspected["base_options"][-1]["base"], image_folder.as_posix())

        result = DatasetService.import_server_image_folder(
            dataset.id, image_folder.as_posix(), image_folder.as_posix(),
            {"prompt": "describe"},
        )
        self.assertEqual(result["imported"], 2)
        self.assertEqual(result["image_prefix"], image_folder.as_posix())
        source = DatasetService.preview_source(dataset.id)
        self.assertEqual({row["image"] for row in source["rows"]}, {"root.jpg", "baitan/nested.png"})
        nested = DatasetService.resolve_asset(dataset.id, "baitan/nested.png")
        self.assertEqual(nested.read_bytes(), b"nested-image")
        duplicate = DatasetService.import_server_image_folder(
            dataset.id, image_folder.as_posix(), image_folder.as_posix(),
        )
        self.assertEqual(duplicate["imported"], 0)
        self.assertEqual(duplicate["skipped"], 2)
        DatasetService.update_source_row(dataset.id, 0, {"answer": "first"})
        DatasetService.update_source_row(dataset.id, 1, {"answer": "second"})
        converted = DatasetService.split_dataset(dataset.id, 0.5)
        train_data = json.loads(Path(converted.train_json).read_text(encoding="utf-8"))
        self.assertTrue(train_data[0]["images"][0].startswith(image_folder.as_posix() + "/"))
        server_csv = self.server_root / "existing.csv"
        server_csv.write_text("prompt,answer\nhello,world\n", encoding="utf-8")
        csv_dataset = DatasetService.upload_server_csv("server-csv", server_csv.as_posix())
        self.assertEqual(csv_dataset.total_rows, 1)
        self.assertTrue(Path(csv_dataset.original_csv).is_file())
        with self.assertRaisesRegex(Exception, "outside the configured browse roots"):
            DatasetService.list_server_directory(self.server_root.parent)

    def test_missing_server_browse_root_returns_clear_error(self):
        missing = self.server_root / "does-not-exist"
        with patch.object(dataset_service_module, "SERVER_BROWSE_ROOTS", [missing]):
            with self.assertRaisesRegex(Exception, "目录不存在"):
                DatasetService.list_server_directory()


if __name__ == "__main__":
    unittest.main()
