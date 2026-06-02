"""
Cooperative UI yielding during long synchronous work on the Qt main thread.

When a warning-detection step must run synchronously (tests or QgsTask unavailable),
call ``maybe_yield_to_ui`` inside tight loops so Qt can still process events.
"""

_yield_counter = 0


def reset_yield_counter() -> None:
    """Reset the iteration counter (e.g. at the start of each warning-detection step)."""
    global _yield_counter
    _yield_counter = 0


def maybe_yield_to_ui(*, every: int = 1, force: bool = False) -> None:
    """
    Process pending Qt events periodically during tight loops.

    Args:
        every: Invoke ``processEvents`` every N calls (ignored when ``force`` is True).
        force: When True, always process events immediately.
    """
    global _yield_counter
    if force:
        _process_events()
        return

    _yield_counter += 1
    if _yield_counter % every == 0:
        _process_events()


def _process_events() -> None:
    try:
        from qgis.PyQt.QtCore import QCoreApplication, QEventLoop

        flags = QEventLoop.AllEvents
        process_events_flag = getattr(QEventLoop, "ProcessEventsFlag", None)
        if process_events_flag is not None and hasattr(process_events_flag, "AllEvents"):
            flags = process_events_flag.AllEvents

        # Cap each yield so one tight loop cannot monopolize the event loop.
        QCoreApplication.processEvents(flags, 50)
    except ImportError:
        pass
    except TypeError:
        try:
            from qgis.PyQt.QtCore import QCoreApplication

            QCoreApplication.processEvents()
        except ImportError:
            pass
