"""
UI package for ArcheoSync plugin.

This package contains user interface components that follow SOLID principles
and use dependency injection for better testability and maintainability.
"""

from .settings_dialog import SettingsDialog
from .prepare_recording_dialog import PrepareRecordingDialog

__all__ = [
    'SettingsDialog',
    'PrepareRecordingDialog'
] 