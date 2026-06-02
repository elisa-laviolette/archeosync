"""Tests for asynchronous warning-detection step dispatch."""

import unittest
from unittest.mock import Mock, patch, MagicMock


try:
    from core.warning_detection_runner import dispatch_warning_detection_step
except ImportError:
    from ..core.warning_detection_runner import dispatch_warning_detection_step


class TestWarningDetectionRunner(unittest.TestCase):
    """Test cases for dispatch_warning_detection_step."""

    def test_runs_synchronously_when_task_manager_unavailable(self):
        results = []

        def runner():
            return ["warning"]

        def on_success(warnings):
            results.append(("success", warnings))

        def on_error(error):
            results.append(("error", error))

        with patch(
            "core.warning_detection_runner._get_qgs_task_manager",
            side_effect=RuntimeError("no qgis"),
        ):
            task = dispatch_warning_detection_step(
                "Checking duplicates",
                runner,
                on_success,
                on_error,
            )

        self.assertIsNone(task)
        self.assertEqual(results, [("success", ["warning"])])

    def test_runner_exception_invokes_error_callback_on_sync_fallback(self):
        errors = []

        def runner():
            raise ValueError("boom")

        with patch(
            "core.warning_detection_runner._get_qgs_task_manager",
            side_effect=RuntimeError("no qgis"),
        ):
            dispatch_warning_detection_step(
                "Checking duplicates",
                runner,
                on_success=Mock(),
                on_error=lambda exc: errors.append(exc),
            )

        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ValueError)

    def test_delegates_to_qgs_task_when_available(self):
        mock_task = MagicMock()
        mock_task_manager = MagicMock()

        with patch(
            "core.warning_detection_runner._build_warning_detection_task",
            return_value=mock_task,
        ), patch(
            "core.warning_detection_runner._get_qgs_task_manager",
            return_value=mock_task_manager,
        ):
            task = dispatch_warning_detection_step(
                "Checking distances",
                lambda: [],
                on_success=Mock(),
                on_error=Mock(),
            )

        self.assertIs(task, mock_task)
        mock_task_manager.addTask.assert_called_once_with(mock_task)


if __name__ == "__main__":
    unittest.main()
