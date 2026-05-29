from __future__ import annotations

import unittest
from datetime import datetime

from workday_clock import (
    MonitorWorkArea,
    display_number_from_device_name,
    format_window_geometry,
    select_monitor_work_area,
    workday_progress,
)


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


class MonitorSelectionTests(unittest.TestCase):
    def test_parses_windows_display_number(self) -> None:
        self.assertEqual(display_number_from_device_name(r"\\.\DISPLAY2"), 2)
        self.assertIsNone(display_number_from_device_name("unknown"))

    def test_selects_requested_display_number(self) -> None:
        primary = MonitorWorkArea(0, 0, 1920, 1040, number=1, device_name=r"\\.\DISPLAY1", is_primary=True)
        secondary = MonitorWorkArea(1920, 0, 3840, 1040, number=2, device_name=r"\\.\DISPLAY2")

        self.assertIs(select_monitor_work_area([primary, secondary], 2), secondary)

    def test_defaults_to_secondary_monitor(self) -> None:
        secondary = MonitorWorkArea(-1280, 0, 0, 1040, number=1, device_name=r"\\.\DISPLAY1")
        primary = MonitorWorkArea(0, 0, 1920, 1040, number=2, device_name=r"\\.\DISPLAY2", is_primary=True)

        self.assertIs(select_monitor_work_area([secondary, primary], None), secondary)

    def test_falls_back_to_ordinal_monitor_when_display_number_is_missing(self) -> None:
        primary = MonitorWorkArea(0, 0, 1920, 1040, is_primary=True)
        secondary = MonitorWorkArea(-1280, 0, 0, 1040)

        self.assertIs(select_monitor_work_area([primary, secondary], 2), secondary)

    def test_falls_back_to_primary_when_target_is_unavailable(self) -> None:
        primary = MonitorWorkArea(0, 0, 1920, 1040, number=1, is_primary=True)

        self.assertIs(select_monitor_work_area([primary], 2), primary)

    def test_formats_tk_geometry_with_negative_coordinates(self) -> None:
        self.assertEqual(format_window_geometry(68, 1040, -68, 0), "68x1040-68+0")
        self.assertEqual(format_window_geometry(68, 1040, 1920, -40), "68x1040+1920-40")


if __name__ == "__main__":
    unittest.main()
