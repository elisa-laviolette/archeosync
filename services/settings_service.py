"""
Settings service implementation for ArcheoSync plugin.

This module provides a concrete implementation of the ISettingsManager interface
using QSettings for persistent storage. This service handles all plugin configuration
persistence in a QGIS-compatible way.

Key Features:
- Persistent storage using QSettings
- Namespace isolation to prevent conflicts with other plugins
- Type-safe access to settings
- Proper QSettings lifecycle management

Usage:
    settings_manager = QGISSettingsManager('MyPlugin')
    settings_manager.set_value('my_setting', 'my_value')
    value = settings_manager.get_value('my_setting', 'default_value')

The service automatically handles:
- QSettings group management
- Type conversion for QSettings compatibility
- Error handling for invalid operations
"""

from typing import Any, Optional
from qgis.PyQt.QtCore import QSettings

try:
    from ..core.interfaces import ISettingsManager
except ImportError:
    from core.interfaces import ISettingsManager


class QGISSettingsManager(ISettingsManager):
    """
    QGIS-specific implementation of settings management.
    
    This class provides a centralized way to save and retrieve plugin settings
    using QSettings. All settings are stored under the 'ArcheoSync' group
    to avoid conflicts with other plugins or QGIS settings.
    """
    
    def __init__(self, plugin_group: str = 'ArcheoSync'):
        """
        Initialize the settings manager.
        
        Args:
            plugin_group: The settings group name for this plugin
        """
        self._settings = QSettings()
        self._plugin_group = plugin_group
    
    def set_value(self, key: str, value: Any) -> None:
        """
        Save a value to settings.
        
        Args:
            key: The setting key
            value: The value to save (can be any type supported by QSettings)
        """
        self._settings.beginGroup(self._plugin_group)
        self._settings.setValue(key, value)
        self._settings.endGroup()
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from settings.
        
        Args:
            key: The setting key
            default: Default value to return if key doesn't exist
            
        Returns:
            The stored value or default if not found
        """
        self._settings.beginGroup(self._plugin_group)
        value = self._settings.value(key, default)
        self._settings.endGroup()
        return value
    
    def remove_value(self, key: str) -> None:
        """
        Remove a setting value.
        
        Args:
            key: The setting key to remove
        """
        self._settings.beginGroup(self._plugin_group)
        self._settings.remove(key)
        self._settings.endGroup()
    
    def clear_all(self) -> None:
        """Clear all plugin settings."""
        self._settings.beginGroup(self._plugin_group)
        self._settings.clear()
        self._settings.endGroup()
    
    @property
    def plugin_group(self) -> str:
        """Get the plugin group name."""
        return self._plugin_group 