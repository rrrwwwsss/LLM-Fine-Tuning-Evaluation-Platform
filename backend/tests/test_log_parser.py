import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from services.log_parser import parse_train_log_line


class TrainLogParserTest(unittest.TestCase):
    def test_parses_quoted_llamafactory_metrics(self):
        parsed = parse_train_log_line(
            "{'loss': '0.6408', 'grad_norm': '0.351', 'epoch': '0.03781'}"
        )
        self.assertEqual(parsed['current_loss'], 0.6408)
        self.assertEqual(parsed['epoch'], 0.03781)

    def test_parses_json_and_scientific_notation(self):
        parsed = parse_train_log_line('{"loss": 1.2e-3, "epoch": 1.5}')
        self.assertEqual(parsed['current_loss'], 0.0012)
        self.assertEqual(parsed['epoch'], 1.5)

    def test_keeps_legacy_epoch_fraction_support(self):
        parsed = parse_train_log_line("{'loss': 0.5, 'epoch': 1.0/3.0}")
        self.assertEqual(parsed['total_epochs'], 3)

    def test_sample_log_contains_parsed_loss_records(self):
        sample = BACKEND_DIR.parent / '示例代码' / '日志.log'
        if not sample.exists():
            self.skipTest('sample log is not present')
        losses = [
            parsed['current_loss']
            for line in sample.read_text(encoding='utf-8', errors='replace').splitlines()
            if (parsed := parse_train_log_line(line)) and 'current_loss' in parsed
        ]
        self.assertGreater(len(losses), 0)
        self.assertAlmostEqual(losses[0], 0.6408)


if __name__ == '__main__':
    unittest.main()
