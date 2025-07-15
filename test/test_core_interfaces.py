# -*- coding: utf-8 -*-
"""
Tests for core interfaces.

This module contains tests for the core interfaces to ensure they follow
SOLID principles and are properly defined.
"""

import unittest
from unittest.mock import Mock, MagicMock
from abc import ABC

# Add the parent directory to the path to allow importing the plugin
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.interfaces import (
    ISettingsManager,
    IFileSystemService,
    ITranslationService,
    IPluginActionManager,
    IUserInterface,
    IProjectManager,
    IConfigurationValidator
)


class TestCoreInterfaces(unittest.TestCase):
    """Test cases for core interfaces."""
    
    def test_interfaces_are_abstract_base_classes(self):
        """Test that all interfaces are abstract base classes."""
        interfaces = [
            ISettingsManager,
            IFileSystemService,
            ITranslationService,
            IPluginActionManager,
            IUserInterface,
            IProjectManager,
            IConfigurationValidator
        ]
        
        for interface in interfaces:
            with self.subTest(interface=interface.__name__):
                self.assertTrue(issubclass(interface, ABC))
    
    def test_interfaces_have_required_methods(self):
        """Test that interfaces have the required abstract methods."""
        # Test ISettingsManager
        self.assertTrue(hasattr(ISettingsManager, 'set_value'))
        self.assertTrue(hasattr(ISettingsManager, 'get_value'))
        self.assertTrue(hasattr(ISettingsManager, 'remove_value'))
        self.assertTrue(hasattr(ISettingsManager, 'clear_all'))
        
        # Test IFileSystemService
        self.assertTrue(hasattr(IFileSystemService, 'select_directory'))
        self.assertTrue(hasattr(IFileSystemService, 'path_exists'))
        self.assertTrue(hasattr(IFileSystemService, 'create_directory'))
        
        # Test ITranslationService
        self.assertTrue(hasattr(ITranslationService, 'translate'))
        self.assertTrue(hasattr(ITranslationService, 'get_current_locale'))
        
        # Test IPluginActionManager
        self.assertTrue(hasattr(IPluginActionManager, 'add_action'))
        self.assertTrue(hasattr(IPluginActionManager, 'remove_action'))
        
        # Test IUserInterface
        self.assertTrue(hasattr(IUserInterface, 'show_dialog'))
        self.assertTrue(hasattr(IUserInterface, 'show_message'))
        
        # Test IProjectManager
        self.assertTrue(hasattr(IProjectManager, 'create_field_project'))
        self.assertTrue(hasattr(IProjectManager, 'import_total_station_data'))
        self.assertTrue(hasattr(IProjectManager, 'import_completed_project'))
        
        # Test IConfigurationValidator
        self.assertTrue(hasattr(IConfigurationValidator, 'validate_field_projects_folder'))
        self.assertTrue(hasattr(IConfigurationValidator, 'validate_total_station_folder'))
        self.assertTrue(hasattr(IConfigurationValidator, 'validate_completed_projects_folder'))
        self.assertTrue(hasattr(IConfigurationValidator, 'validate_csv_archive_folder'))


    
    def test_interfaces_cannot_be_instantiated(self):
        """Test that interfaces cannot be instantiated directly."""
        interfaces = [
            ISettingsManager,
            IFileSystemService,
            ITranslationService,
            IPluginActionManager,
            IUserInterface,
            IProjectManager,
            IConfigurationValidator
        ]
        
        for interface in interfaces:
            with self.subTest(interface=interface.__name__):
                with self.assertRaises(TypeError):
                    interface()
    
    def test_interface_methods_are_abstract(self):
        """Test that interface methods are abstract."""
        # Create a mock implementation that doesn't implement abstract methods
        class MockSettingsManager(ISettingsManager):
            pass
        
        with self.assertRaises(TypeError):
            MockSettingsManager()


class TestInterfaceSegregation(unittest.TestCase):
    """Test cases for Interface Segregation Principle."""
    
    def test_settings_manager_interface_is_focused(self):
        """Test that ISettingsManager interface is focused on settings only."""
        # The interface should only contain settings-related methods
        settings_methods = ['set_value', 'get_value', 'remove_value', 'clear_all']
        
        for method in settings_methods:
            self.assertTrue(hasattr(ISettingsManager, method))
        
        # Should not contain unrelated methods
        unrelated_methods = ['translate', 'select_directory', 'show_dialog']
        for method in unrelated_methods:
            self.assertFalse(hasattr(ISettingsManager, method))
    
    def test_file_system_interface_is_focused(self):
        """Test that IFileSystemService interface is focused on file operations only."""
        # The interface should only contain file system-related methods
        file_methods = ['select_directory', 'path_exists', 'create_directory']
        
        for method in file_methods:
            self.assertTrue(hasattr(IFileSystemService, method))
        
        # Should not contain unrelated methods
        unrelated_methods = ['translate', 'set_value', 'show_dialog']
        for method in unrelated_methods:
            self.assertFalse(hasattr(IFileSystemService, method))
    
    def test_translation_interface_is_focused(self):
        """Test that ITranslationService interface is focused on translation only."""
        # The interface should only contain translation-related methods
        translation_methods = ['translate', 'get_current_locale']
        
        for method in translation_methods:
            self.assertTrue(hasattr(ITranslationService, method))
        
        # Should not contain unrelated methods
        unrelated_methods = ['set_value', 'select_directory', 'show_dialog']
        for method in unrelated_methods:
            self.assertFalse(hasattr(ITranslationService, method))


class TestInterfaceDocumentation(unittest.TestCase):
    """Test cases for interface documentation."""
    
    def test_interfaces_have_docstrings(self):
        """Test that all interfaces have proper docstrings."""
        interfaces = [
            ISettingsManager,
            IFileSystemService,
            ITranslationService,
            IPluginActionManager,
            IUserInterface,
            IProjectManager,
            IConfigurationValidator
        ]
        
        for interface in interfaces:
            with self.subTest(interface=interface.__name__):
                self.assertIsNotNone(interface.__doc__)
                self.assertGreater(len(interface.__doc__.strip()), 0)
    
    def test_interface_methods_have_docstrings(self):
        """Test that interface methods have proper docstrings."""
        # Test a few key methods
        test_cases = [
            (ISettingsManager.set_value, 'set_value'),
            (ISettingsManager.get_value, 'get_value'),
            (IFileSystemService.select_directory, 'select_directory'),
            (ITranslationService.translate, 'translate'),
        ]
        
        for method, method_name in test_cases:
            with self.subTest(method=method_name):
                self.assertIsNotNone(method.__doc__)
                self.assertGreater(len(method.__doc__.strip()), 0)


if __name__ == '__main__':
    unittest.main() 