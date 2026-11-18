"""Tests for telemetry-collector/check_schema.py, the pre-deploy column check."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

_DIR = Path(__file__).resolve().parents[2] / "telemetry-collector"
sys.path.insert(0, str(_DIR))   # check_schema imports dashboard from its own folder
try:
    _spec = importlib.util.spec_from_file_location("check_schema", _DIR / "check_schema.py")
    cs = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(cs)
finally:
    sys.path.remove(str(_DIR))

_WORKER = (_DIR / "src" / "index.js").read_text(encoding="utf-8")


def _pragma(names):
    return json.dumps([{"results": [{"cid": i, "name": n} for i, n in enumerate(names)],
                        "success": True, "meta": {}}])


class CheckSchemaTest(unittest.TestCase):
    def test_the_worker_columns_are_read_from_the_insert(self):
        cols = cs.insert_columns(_WORKER)
        self.assertIn("hw_id_a", cols)
        self.assertIn("hw_id_b", cols)
        self.assertEqual(cols[-1], "raw")

    def test_a_migrated_table_passes(self):
        out = _pragma(["id"] + cs.insert_columns(_WORKER))
        self.assertEqual(cs.missing_columns(_WORKER, out), [])

    def test_an_unmigrated_table_names_the_missing_columns(self):
        cols = [c for c in cs.insert_columns(_WORKER) if not c.startswith("hw_id_")]
        self.assertEqual(cs.missing_columns(_WORKER, _pragma(cols)), ["hw_id_a", "hw_id_b"])

    def test_an_empty_result_never_passes(self):
        with self.assertRaises(ValueError):
            cs.missing_columns(_WORKER, _pragma([]))

    def test_main_exit_codes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            worker, cols = Path(d) / "w.js", Path(d) / "c.json"
            worker.write_text(_WORKER, encoding="utf-8")
            cols.write_text(_pragma(cs.insert_columns(_WORKER)), encoding="utf-8")
            self.assertEqual(cs.main([str(worker), str(cols)]), 0)
            cols.write_text(_pragma(["id", "raw"]), encoding="utf-8")
            self.assertEqual(cs.main([str(worker), str(cols)]), 1)


if __name__ == "__main__":
    unittest.main()
