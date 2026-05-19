from __future__ import annotations

import unittest
from datetime import datetime

from workday_clock import workday_progress


class WorkdayProgressTests(unittest.TestCase):
    def test_clamps_before_and_after_workday(self) -> None:
        self.assertEqual(workday_progress(datetime(2026, 5, 19, 7, 59)), 0)
        self.assertEqual(workday_progress(datetime(2026, 5, 19, 20, 1)), 1)

    def test_maps_workday_linearly(self) -> None:
        self.assertEqual(workday_progress(datetime(2026, 5, 19, 8, 0)), 0)
        self.assertEqual(workday_progress(datetime(2026, 5, 19, 14, 0)), 0.5)
        self.assertEqual(workday_progress(datetime(2026, 5, 19, 20, 0)), 1)

    def test_rejects_invalid_hour_range(self) -> None:
        with self.assertRaises(ValueError):
            workday_progress(datetime(2026, 5, 19, 12, 0), start_hour=20, end_hour=8)


if __name__ == "__main__":
    unittest.main()
