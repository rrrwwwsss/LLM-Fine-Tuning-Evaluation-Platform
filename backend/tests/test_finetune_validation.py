import json
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from services.finetune_runner import FinetuneRunner


class FinetuneDatasetValidationTest(unittest.TestCase):
    def test_dpo_requires_ranked_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "dataset_info.json").write_text(json.dumps({
                "preference": {"file_name": "data.json", "ranking": True},
                "supervised": {"file_name": "data.json"},
            }), encoding="utf-8")
            FinetuneRunner.validate_training_dataset(
                f"stage: dpo\ndataset: preference\ndataset_dir: {path.as_posix()}"
            )
            with self.assertRaisesRegex(Exception, "ranking=true"):
                FinetuneRunner.validate_training_dataset(
                    f"stage: dpo\ndataset: supervised\ndataset_dir: {path.as_posix()}"
                )

    def test_sft_rejects_preference_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "dataset_info.json").write_text(json.dumps({
                "preference": {"file_name": "data.json", "ranking": True},
            }), encoding="utf-8")
            with self.assertRaisesRegex(Exception, "select DPO"):
                FinetuneRunner.validate_training_dataset(
                    f"stage: sft\ndataset: preference\ndataset_dir: {path.as_posix()}"
                )


if __name__ == "__main__":
    unittest.main()
