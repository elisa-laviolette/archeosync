"""
Translation service implementation for ArcheoSync plugin.

This module provides a concrete implementation of the ITranslationService interface
for handling internationalization in a clean, testable way.
"""

import os
from typing import Optional
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication

try:
    from ..core.interfaces import ITranslationService
except ImportError:
    from core.interfaces import ITranslationService


class QGISTranslationService(ITranslationService):
    """
    QGIS-specific implementation of translation operations.
    
    This class provides translation functionality using QGIS/Qt translation
    mechanisms while maintaining a clean interface.
    """
    
    def __init__(self, plugin_directory: str, plugin_name: str = 'ArcheoSync'):
        """
        Initialize the translation service.
        
        Args:
            plugin_directory: Directory containing translation files
            plugin_name: Name of the plugin for translation context
        """
        self._plugin_directory = plugin_directory
        self._plugin_name = plugin_name
        self._translator: Optional[QTranslator] = None
        self._current_locale: Optional[str] = None
        
        # Initialize translation
        self._setup_translation()
    
    def _setup_translation(self) -> None:
        """Set up the translation system."""
        # Get current locale
        locale = QSettings().value('locale/userLocale', 'en')[0:2]
        self._current_locale = locale
        
        # Build translation file path
        locale_path = os.path.join(
            self._plugin_directory,
            'i18n',
            f'{self._plugin_name}_{locale}.qm'
        )
        
        # Debug: Print translation setup info
        print(f"[ArcheoSync] Translation setup:")
        print(f"  - Current locale: {locale}")
        print(f"  - Plugin name: {self._plugin_name}")
        print(f"  - Translation file path: {locale_path}")
        print(f"  - File exists: {os.path.exists(locale_path)}")
        
        # Load translation if file exists
        if os.path.exists(locale_path):
            self._translator = QTranslator()
            if self._translator.load(locale_path):
                QCoreApplication.installTranslator(self._translator)
                print(f"  - Translation loaded successfully")
            else:
                print(f"  - Failed to load translation file")
        else:
            print(f"  - Translation file not found")
    
    def translate(self, message: str) -> str:
        """
        Translate a message.
        
        Args:
            message: Message to translate
            
        Returns:
            Translated message
        """
        # Use Qt translation API
        return QCoreApplication.translate(self._plugin_name, message)
    
    def get_current_locale(self) -> str:
        """
        Get the current locale.
        
        Returns:
            Current locale code (e.g., 'en', 'fr')
        """
        return self._current_locale or 'en'
    
    def is_translation_loaded(self) -> bool:
        """
        Check if translation is loaded.
        
        Returns:
            True if translation is loaded, False otherwise
        """
        return self._translator is not None
    
    def get_translation_file_path(self) -> Optional[str]:
        """
        Get the path to the current translation file.
        
        Returns:
            Path to translation file or None if not found
        """
        if not self._current_locale:
            return None
        
        locale_path = os.path.join(
            self._plugin_directory,
            'i18n',
            f'{self._plugin_name}_{self._current_locale}.qm'
        )
        
        return locale_path if os.path.exists(locale_path) else None
    
    def reload_translation(self) -> bool:
        """
        Reload the translation system.
        
        Returns:
            True if translation was reloaded successfully, False otherwise
        """
        # Remove existing translator
        if self._translator:
            QCoreApplication.removeTranslator(self._translator)
            self._translator = None
        
        # Set up translation again
        self._setup_translation()
        
        return self._translator is not None 