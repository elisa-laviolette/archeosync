"""Tests for cooperative UI yielding during long main-thread work."""

import unittest
from unittest.mock import patch

try:
    import core.ui_responsiveness as ui_responsiveness
except ImportError:
    from ..core import ui_responsiveness


class TestUIResponsiveness(unittest.TestCase):
    """Test cases for maybe_yield_to_ui."""

    def setUp(self):
        ui_responsiveness.reset_yield_counter()

    def test_maybe_yield_calls_process_events_every_n_iterations(self):
        with patch.object(ui_responsiveness, "_process_events") as mock_process:
            for _ in range(24):
                ui_responsiveness.maybe_yield_to_ui(every=25)
            mock_process.assert_not_called()

            ui_responsiveness.maybe_yield_to_ui(every=25)
            mock_process.assert_called_once()

    def test_force_always_processes_events(self):
        with patch.object(ui_responsiveness, "_process_events") as mock_process:
            ui_responsiveness.maybe_yield_to_ui(force=True)
            mock_process.assert_called_once()

    def test_reset_yield_counter_restarts_interval(self):
        with patch.object(ui_responsiveness, "_process_events") as mock_process:
            for _ in range(25):
                ui_responsiveness.maybe_yield_to_ui(every=25)
            self.assertEqual(mock_process.call_count, 1)

            ui_responsiveness.reset_yield_counter()
            for _ in range(24):
                ui_responsiveness.maybe_yield_to_ui(every=25)
            self.assertEqual(mock_process.call_count, 1)

            ui_responsiveness.maybe_yield_to_ui(every=25)
            self.assertEqual(mock_process.call_count, 2)


if __name__ == "__main__":
    unittest.main()
