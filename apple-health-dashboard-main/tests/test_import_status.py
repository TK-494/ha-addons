from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import data


class ImportStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = data.DATA_DIR
        data.DATA_DIR = Path(self.tmp.name)

    def tearDown(self) -> None:
        data.DATA_DIR = self.old_data_dir
        self.tmp.cleanup()

    def write_json(self, name: str, obj: dict) -> None:
        (data.DATA_DIR / name).write_text(json.dumps(obj), encoding="utf-8")

    def test_unknown_without_import_files(self) -> None:
        status = data.import_status()

        self.assertEqual(status["status"], "onbekend")
        self.assertEqual(status["scope"], "volledige_export")
        self.assertFalse(status["has_import"])
        self.assertEqual(status["processed_days"], 0)
        self.assertEqual(status["clean_workouts"], 0)
        self.assertEqual(status["suspicious_workouts"], 0)

    def test_success_status_from_summary_without_private_records(self) -> None:
        self.write_json("health-summary.json", {
            "schema_version": 1,
            "generated_at": "2026-05-14T12:00:00",
            "totals": {"days_recorded": 42, "workouts": 7},
            "workout_quality": {
                "clean_workouts_count": 7,
                "suspicious_workouts_count": 2,
            },
        })

        status = data.import_status()

        self.assertEqual(status["status"], "succesvol")
        self.assertEqual(status["scope"], "volledige_export")
        self.assertTrue(status["has_import"])
        self.assertEqual(status["last_import_at"], "2026-05-14T12:00:00")
        self.assertEqual(status["processed_days"], 42)
        self.assertEqual(status["clean_workouts"], 7)
        self.assertEqual(status["suspicious_workouts"], 2)

    def test_failed_latest_import_keeps_failure_status(self) -> None:
        data.write_import_status({
            "status": "fout",
            "last_import_at": "2026-05-14T13:00:00",
            "processed_days": 0,
            "clean_workouts": 0,
            "suspicious_workouts": 0,
        })
        self.write_json("health-summary.json", {
            "schema_version": 1,
            "generated_at": "2026-05-14T12:00:00",
            "totals": {"days_recorded": 42, "workouts": 7},
            "workout_quality": {
                "clean_workouts_count": 7,
                "suspicious_workouts_count": 2,
            },
        })

        status = data.import_status()

        self.assertEqual(status["status"], "fout")
        self.assertEqual(status["scope"], "volledige_export")
        self.assertTrue(status["has_import"])
        self.assertEqual(status["last_import_at"], "2026-05-14T13:00:00")
        self.assertEqual(status["processed_days"], 0)
        self.assertEqual(status["clean_workouts"], 0)
        self.assertEqual(status["suspicious_workouts"], 0)

    def test_failed_status_overrides_summary_success(self) -> None:
        data.write_import_status({
            "status": "fout",
            "last_import_at": "2099-01-01T10:00:00",
            "processed_days": 0,
            "clean_workouts": 0,
            "suspicious_workouts": 0,
        })
        self.write_json("health-summary.json", {
            "schema_version": 1,
            "generated_at": "2099-01-02T12:00:00",
            "totals": {"days_recorded": 100, "workouts": 50},
            "workout_quality": {
                "clean_workouts_count": 50,
                "suspicious_workouts_count": 5,
            },
        })

        status = data.import_status()

        self.assertEqual(status["status"], "fout")
        self.assertEqual(status["scope"], "volledige_export")
        self.assertTrue(status["has_import"])
        self.assertEqual(status["source"], "import-status.json")
        self.assertEqual(status["last_import_at"], "2099-01-01T10:00:00")
        self.assertEqual(status["processed_days"], 0)
        self.assertEqual(status["clean_workouts"], 0)
        self.assertEqual(status["suspicious_workouts"], 0)


if __name__ == "__main__":
    unittest.main()
