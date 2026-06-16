import importlib.util
import os
import unittest
from datetime import datetime

# Load the script as a module (it lives in a non-package scripts/ dir).
_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "package", "contents", "scripts", "schoolapp_status.py")
_spec = importlib.util.spec_from_file_location("schoolapp_status", _SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


class TestRelativeTime(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 6, 16, 12, 0, 0)

    def test_just_now(self):
        self.assertEqual(mod.relative_time("2026-06-16T11:59:40", self.now), "just now")

    def test_minutes(self):
        self.assertEqual(mod.relative_time("2026-06-16T11:30:00", self.now), "30m ago")

    def test_hours(self):
        self.assertEqual(mod.relative_time("2026-06-16T09:00:00", self.now), "3h ago")

    def test_days(self):
        self.assertEqual(mod.relative_time("2026-06-14T12:00:00", self.now), "2d ago")

    def test_exactly_60_minutes(self):
        # Boundary between the "Nm ago" and "Nh ago" branches.
        self.assertEqual(mod.relative_time("2026-06-16T11:00:00", self.now), "1h ago")

    def test_bad_input(self):
        self.assertEqual(mod.relative_time("not-a-date", self.now), "")


class TestNextCheckSeconds(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 6, 16, 12, 0, 0)

    def test_future(self):
        s = mod.next_check_seconds({"next_check": "2026-06-16T12:01:30"}, self.now)
        self.assertEqual(s, 90)

    def test_past_clamps_to_zero(self):
        s = mod.next_check_seconds({"next_check": "2026-06-16T11:59:00"}, self.now)
        self.assertEqual(s, 0)

    def test_missing(self):
        self.assertEqual(mod.next_check_seconds({}, self.now), 0)


class TestAnnotateHistory(unittest.TestCase):
    HIST = [
        {"ts": "2026-06-15T23:40:24", "type": "grades", "summary": "Notes mises à jour — S4"},
        {"ts": "2026-06-15T16:41:31", "type": "modules", "summary": "Résultat module: Algèbre 2 — RAT (9.08)"},
    ]

    def test_new_entries_flagged(self):
        annotated, new_summaries = mod.annotate_history(self.HIST, "2026-06-15T20:00:00")
        self.assertTrue(annotated[0]["new"])
        self.assertFalse(annotated[1]["new"])
        self.assertEqual(new_summaries, ["Notes mises à jour — S4"])

    def test_first_run_baselines_silently(self):
        annotated, new_summaries = mod.annotate_history(self.HIST, "")
        self.assertFalse(any(a["new"] for a in annotated))
        self.assertEqual(new_summaries, [])

    def test_exact_boundary_not_flagged(self):
        # last_seen equal to the newest ts: strict '>' means nothing is new.
        annotated, new_summaries = mod.annotate_history(self.HIST, "2026-06-15T23:40:24")
        self.assertFalse(any(a["new"] for a in annotated))
        self.assertEqual(new_summaries, [])


class TestBuildOutput(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 6, 16, 12, 0, 0)
        self.status = {
            "watcher": "active",
            "last_check": "2026-06-16T11:59:00",
            "next_check": "2026-06-16T12:01:30",
            "poll_interval": 120,
        }
        self.history = [
            {"ts": "2026-06-16T11:58:00", "type": "grades", "summary": "Notes mises à jour — S4"},
            {"ts": "2026-06-15T16:41:31", "type": "modules", "summary": "Résultat module: Algèbre 2 — RAT (9.08)"},
        ]
        self.grades = {"semester": "S4", "modules": [
            {"code": "API45", "title": "Analyse", "moy": "12.5", "validated": True,
             "elements": [{"code": "API451", "cc": "14.5", "ex": "--", "tp": "--", "moy": "14.5*"}]},
        ]}

    def test_shape_and_new_change(self):
        out = mod.build_output(self.status, self.history, self.grades,
                               last_seen_ts="2026-06-16T11:00:00", now=self.now)
        self.assertTrue(out["ok"])
        self.assertEqual(out["watcher"], "active")
        self.assertEqual(out["next_check_s"], 90)
        self.assertEqual(out["poll_interval"], 120)
        self.assertEqual(out["latest_change_type"], "grades")
        self.assertEqual(out["latest_change_summary"], "Notes mises à jour — S4")
        self.assertTrue(out["new_change"])
        self.assertEqual(out["new_summaries"], ["Notes mises à jour — S4"])
        self.assertEqual(out["history"][0]["new"], True)
        self.assertEqual(out["history"][1]["new"], False)
        self.assertEqual(out["grades"]["modules"][0]["code"], "API45")
        self.assertEqual(out["error"], "")

    def test_empty_history(self):
        out = mod.build_output(self.status, [], self.grades,
                               last_seen_ts="2026-06-16T11:00:00", now=self.now)
        self.assertFalse(out["new_change"])
        self.assertEqual(out["latest_change_summary"], "")
        self.assertEqual(out["latest_change_type"], "")
        self.assertEqual(out["history"], [])


if __name__ == "__main__":
    unittest.main()
