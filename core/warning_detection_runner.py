"""
Run warning-detection steps off the Qt main thread via QgsTask.

Long-running read-only detector scans block the Qt event loop when executed
synchronously on the main thread. Scheduling each step as a QgsTask keeps the
map and the rest of QGIS interactive while analysis runs.
"""

from __future__ import annotations

import traceback
from typing import Any, Callable, Optional


def _qgs_task_can_cancel_flag() -> int:
    """Return a QgsTask cancel flag compatible with QGIS 3 and QGIS 4."""
    from qgis.core import QgsTask

    if hasattr(QgsTask, "CanCancel"):
        return QgsTask.CanCancel
    return QgsTask.Flag.CanCancel


def _get_qgs_task_manager():
    from qgis.core import QgsApplication

    task_manager = QgsApplication.taskManager()
    if task_manager is None:
        raise RuntimeError("QgsApplication.taskManager() is not available")
    return task_manager


def _build_warning_detection_task(description: str, runner: Callable[[], Any]):
    from qgis.core import QgsTask

    class WarningDetectionStepTask(QgsTask):
        def __init__(self) -> None:
            super().__init__(description, _qgs_task_can_cancel_flag())
            self._runner = runner
            self._result: Any = None
            self._exception: Optional[Exception] = None
            self.on_success: Optional[Callable[[Any], None]] = None
            self.on_error: Optional[Callable[[Exception], None]] = None

        def run(self) -> bool:
            try:
                self._result = self._runner()
                return True
            except Exception as exc:
                self._exception = exc
                traceback.print_exc()
                return False

        def finished(self, result: bool) -> None:
            if self._exception is not None:
                if self.on_error is not None:
                    self.on_error(self._exception)
                return
            if result and self.on_success is not None:
                self.on_success(self._result)
                return
            if self.on_error is not None:
                self.on_error(RuntimeError("Warning detection step failed"))

    return WarningDetectionStepTask()


def dispatch_warning_detection_step(
    description: str,
    runner: Callable[[], Any],
    on_success: Callable[[Any], None],
    on_error: Callable[[Exception], None],
) -> Optional[Any]:
    """
    Execute ``runner`` asynchronously when the QGIS task manager is available.

    Falls back to synchronous execution on the main thread when QgsTask cannot be
    used, for example in unit tests outside QGIS.

    Returns:
        The QgsTask instance when scheduled asynchronously, otherwise ``None``.
    """
    try:
        task = _build_warning_detection_task(description, runner)
        task.on_success = on_success
        task.on_error = on_error
        _get_qgs_task_manager().addTask(task)
        return task
    except Exception:
        try:
            on_success(runner())
        except Exception as exc:
            on_error(exc)
        return None
