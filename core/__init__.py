"""
Core package for ArcheoSync plugin.

This package contains the core interfaces and abstractions that follow SOLID principles
and enable clean architecture throughout the application.
"""

from .interfaces import (
    ISettingsManager,
    IFileSystemService,
    ITranslationService,
    IPluginActionManager,
    IUserInterface,
    IProjectManager,
    IConfigurationValidator
)

__all__ = [
    'ISettingsManager',
    'IFileSystemService',
    'ITranslationService',
    'IPluginActionManager',
    'IUserInterface',
    'IProjectManager',
    'IConfigurationValidator'
] 