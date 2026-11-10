"""Standalone tests for payload and input parsing (no Home Assistant needed).

Run: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "custom_components" / "electromaps"

# Load the package's submodules without running its __init__ (which imports HA).
_pkg = types.ModuleType("electromaps")
_pkg.__path__ = [str(PKG_DIR)]
sys.modules.setdefault("electromaps", _pkg)
models = importlib.import_module("electromaps.models")

FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "location_sample.json").read_text())


class ParseLocationTest(unittest.TestCase):
    def test_fixture_has_four_connectors_keyed_by_id(self) -> None:
        loc = models.parse_location(FIXTURE)
        self.assertEqual(loc.id, 123456)
        self.assertEqual(loc.name, "Sample Station")
        self.assertEqual(sorted(loc.connectors), [1001, 1002, 1003, 1004])
        c = loc.connectors[1001]
        self.assertEqual(c.name, "Charger 1 - Socket 1")
        self.assertEqual(c.status, "occupied")
        self.assertEqual(c.status_since.isoformat(), "2026-01-01T09:30:00+00:00")
        self.assertEqual(c.power_kw, 11.0)
        self.assertEqual(loc.connectors[1002].status, "available")
        self.assertEqual(loc.connectors[1003].status, "out_of_service")
        self.assertEqual(loc.connectors[1004].status, "unknown")
        self.assertIsNone(loc.connectors[1004].status_since)

    def test_unrelated_fields_do_not_change_snapshot(self) -> None:
        changed = dict(FIXTURE, rating=1.0, count_comments=9999, updated_at="2030-01-01")
        self.assertEqual(models.parse_location(FIXTURE), models.parse_location(changed))

    def test_status_change_changes_snapshot(self) -> None:
        changed = json.loads(json.dumps(FIXTURE))
        changed["connectors"][0]["status"] = "AVAILABLE"  # was OCCUPIED
        self.assertNotEqual(models.parse_location(FIXTURE), models.parse_location(changed))

    def test_unexpected_status_becomes_unknown(self) -> None:
        data = {"id": 1, "connectors": [{"id": 5, "status": "CHARGING"}, {"id": 6}]}
        loc = models.parse_location(data)
        self.assertEqual(loc.connectors[5].status, "unknown")
        self.assertEqual(loc.connectors[6].status, "unknown")
        self.assertEqual(loc.connectors[6].name, "Connector 2")

    def test_malformed_payload_raises(self) -> None:
        for bad in (None, [], {"id": 1}, {"connectors": []}, {"id": 1, "connectors": {}}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                models.parse_location(bad)


class ConnectorChangesTest(unittest.TestCase):
    def test_only_changed_connectors_are_reported(self) -> None:
        changed = json.loads(json.dumps(FIXTURE))
        changed["connectors"][0]["status"] = "AVAILABLE"  # 1001: occupied -> available
        changed["connectors"][2]["status"] = "OUT_OF_SERVICE"  # 1003: unchanged
        pairs = models.connector_changes(
            models.parse_location(FIXTURE), models.parse_location(changed)
        )
        self.assertEqual(
            [(b.id, b.status, a.status) for b, a in pairs],
            [(1001, "occupied", "available")],
        )

    def test_unchanged_snapshot_reports_nothing(self) -> None:
        loc = models.parse_location(FIXTURE)
        self.assertEqual(models.connector_changes(loc, loc), [])

    def test_new_or_vanished_connectors_are_not_transitions(self) -> None:
        changed = json.loads(json.dumps(FIXTURE))
        changed["connectors"].pop(0)
        changed["connectors"].append({"id": 2000, "status": "AVAILABLE"})
        pairs = models.connector_changes(
            models.parse_location(FIXTURE), models.parse_location(changed)
        )
        self.assertEqual(pairs, [])


class ParseInputTest(unittest.TestCase):
    def test_accepted(self) -> None:
        for value in (
            "123456",
            " 123456 ",
            "https://map.electromaps.com/en/p/123456",
            "https://map.electromaps.com/es/p/123456/",
            "https://map.electromaps.com/en/p/123456?ref=x",
        ):
            with self.subTest(value=value):
                self.assertEqual(models.parse_location_input(value), 123456)

    def test_rejected(self) -> None:
        for value in ("", "abc", "https://map.electromaps.com/en/", "72 23 48"):
            with self.subTest(value=value):
                self.assertIsNone(models.parse_location_input(value))


if __name__ == "__main__":
    unittest.main()
