# -*- coding: utf-8 -*-
"""
Tests for service implementations.

This module contains tests for the service implementations to ensure they
follow SOLID principles and work correctly.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
import tempfile
import os
from pathlib import Path

# Add the parent directory to the path to allow importing the plugin
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import (
    QGISSettingsManager,
    QGISFileSystemService,
    QGISTranslationService,
    ArcheoSyncConfigurationValidator
)
from core.interfaces import (
    ISettingsManager,
    IFileSystemService,
    ITranslationService,
    IConfigurationValidator
)


class TestQGISSettingsManager(unittest.TestCase):
    """Test cases for QGISSettingsManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.settings_patcher = patch('services.settings_service.QSettings')
        self.mock_qsettings_class = self.settings_patcher.start()
        self.mock_qsettings = Mock()
        self.mock_qsettings_class.return_value = self.mock_qsettings
        
        self.settings_manager = QGISSettingsManager()
    
    def tearDown(self):
        """Clean up after tests."""
        self.settings_patcher.stop()
    
    def test_implements_interface(self):
        """Test that QGISSettingsManager implements ISettingsManager."""
        self.assertIsInstance(self.settings_manager, ISettingsManager)
    
    def test_init(self):
        """Test settings manager initialization."""
        self.mock_qsettings_class.assert_called_once()
        self.assertEqual(self.settings_manager.plugin_group, 'ArcheoSync')
    
    def test_set_value(self):
        """Test setting a value."""
        key = 'test_key'
        value = 'test_value'
        
        self.settings_manager.set_value(key, value)
        
        self.mock_qsettings.beginGroup.assert_called_with('ArcheoSync')
        self.mock_qsettings.setValue.assert_called_with(key, value)
        self.mock_qsettings.endGroup.assert_called()
    
    def test_get_value_with_default(self):
        """Test getting a value with default."""
        key = 'test_key'
        default = 'default_value'
        
        self.mock_qsettings.value.return_value = default
        
        result = self.settings_manager.get_value(key, default)
        
        self.assertEqual(result, default)
        self.mock_qsettings.beginGroup.assert_called_with('ArcheoSync')
        self.mock_qsettings.value.assert_called_with(key, default)
        self.mock_qsettings.endGroup.assert_called()
    
    def test_get_value_existing(self):
        """Test getting an existing value."""
        key = 'test_key'
        stored_value = 'stored_value'
        default = 'default_value'
        
        self.mock_qsettings.value.return_value = stored_value
        
        result = self.settings_manager.get_value(key, default)
        
        self.assertEqual(result, stored_value)
    
    def test_remove_value(self):
        """Test removing a value."""
        key = 'test_key'
        
        self.settings_manager.remove_value(key)
        
        self.mock_qsettings.beginGroup.assert_called_with('ArcheoSync')
        self.mock_qsettings.remove.assert_called_with(key)
        self.mock_qsettings.endGroup.assert_called()
    
    def test_clear_all(self):
        """Test clearing all settings."""
        self.settings_manager.clear_all()
        
        self.mock_qsettings.beginGroup.assert_called_with('ArcheoSync')
        self.mock_qsettings.clear.assert_called()
        self.mock_qsettings.endGroup.assert_called()
    
    def test_custom_plugin_group(self):
        """Test using a custom plugin group."""
        custom_group = 'CustomPlugin'
        settings_manager = QGISSettingsManager(custom_group)
        
        self.assertEqual(settings_manager.plugin_group, custom_group)
        
        # Test that it uses the custom group
        settings_manager.set_value('test', 'value')
        self.mock_qsettings.beginGroup.assert_called_with(custom_group)


class TestQGISFileSystemService(unittest.TestCase):
    """Test cases for QGISFileSystemService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parent_widget = Mock()
        self.file_system_service = QGISFileSystemService(self.parent_widget)
        
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = os.path.join(self.temp_dir, 'test.txt')
        with open(self.temp_file, 'w') as f:
            f.write('test content')
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_implements_interface(self):
        """Test that QGISFileSystemService implements IFileSystemService."""
        self.assertIsInstance(self.file_system_service, IFileSystemService)
    
    @patch('services.file_system_service.QFileDialog')
    def test_select_directory(self, mock_file_dialog):
        """Test directory selection."""
        mock_file_dialog.getExistingDirectory.return_value = self.temp_dir
        
        result = self.file_system_service.select_directory("Test Title", "/initial/path")
        
        self.assertEqual(result, self.temp_dir)
        mock_file_dialog.getExistingDirectory.assert_called_with(
            self.parent_widget, "Test Title", "/initial/path"
        )
    
    @patch('services.file_system_service.QFileDialog')
    def test_select_directory_cancelled(self, mock_file_dialog):
        """Test directory selection when cancelled."""
        mock_file_dialog.getExistingDirectory.return_value = ""
        
        result = self.file_system_service.select_directory("Test Title")
        
        self.assertIsNone(result)
    
    def test_path_exists(self):
        """Test path existence check."""
        self.assertTrue(self.file_system_service.path_exists(self.temp_dir))
        self.assertTrue(self.file_system_service.path_exists(self.temp_file))
        self.assertFalse(self.file_system_service.path_exists('/nonexistent/path'))
    
    def test_create_directory(self):
        """Test directory creation."""
        new_dir = os.path.join(self.temp_dir, 'new_dir')
        
        # Test creating new directory
        result = self.file_system_service.create_directory(new_dir)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(new_dir))
        
        # Test creating existing directory
        result = self.file_system_service.create_directory(new_dir)
        self.assertTrue(result)
    
    def test_is_directory(self):
        """Test directory check."""
        self.assertTrue(self.file_system_service.is_directory(self.temp_dir))
        self.assertFalse(self.file_system_service.is_directory(self.temp_file))
    
    def test_is_file(self):
        """Test file check."""
        self.assertTrue(self.file_system_service.is_file(self.temp_file))
        self.assertFalse(self.file_system_service.is_file(self.temp_dir))
    
    def test_get_file_extension(self):
        """Test file extension extraction."""
        self.assertEqual(self.file_system_service.get_file_extension('test.txt'), '.txt')
        self.assertEqual(self.file_system_service.get_file_extension('test.TXT'), '.TXT')
        self.assertEqual(self.file_system_service.get_file_extension('test'), '')
        self.assertEqual(self.file_system_service.get_file_extension('test.file.txt'), '.txt')
    
    def test_list_files(self):
        """Test file listing."""
        # Create test files
        test_files = ['test1.txt', 'test2.csv', 'test3.txt']
        for filename in test_files:
            with open(os.path.join(self.temp_dir, filename), 'w') as f:
                f.write('content')
        
        # Test listing all files
        all_files = self.file_system_service.list_files(self.temp_dir)
        self.assertEqual(len(all_files), 4)  # 3 test files + 1 from setUp
        
        # Test listing with extension filter
        txt_files = self.file_system_service.list_files(self.temp_dir, '.txt')
        self.assertEqual(len(txt_files), 3)
        
        # Test listing with non-existent directory
        result = self.file_system_service.list_files('/nonexistent')
        self.assertEqual(result, [])
        
        # Test listing with file instead of directory
        result = self.file_system_service.list_files(self.temp_file)
        self.assertEqual(result, [])


class TestQGISTranslationService(unittest.TestCase):
    """Test cases for QGISTranslationService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.plugin_dir = tempfile.mkdtemp()
        self.translation_service = QGISTranslationService(self.plugin_dir, 'TestPlugin')
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.plugin_dir, ignore_errors=True)
    
    def test_implements_interface(self):
        """Test that QGISTranslationService implements ITranslationService."""
        self.assertIsInstance(self.translation_service, ITranslationService)
    
    @patch('services.translation_service.QSettings')
    @patch('services.translation_service.QTranslator')
    @patch('services.translation_service.QCoreApplication')
    def test_init_with_translation_file(self, mock_core_app, mock_translator_class, mock_settings_class):
        """Test initialization with translation file."""
        # Mock QSettings
        mock_settings = Mock()
        mock_settings.value.return_value = 'en'
        mock_settings_class.return_value = mock_settings
        
        # Mock QTranslator
        mock_translator = Mock()
        mock_translator.load.return_value = True
        mock_translator_class.return_value = mock_translator
        
        # Create translation file
        i18n_dir = os.path.join(self.plugin_dir, 'i18n')
        os.makedirs(i18n_dir)
        translation_file = os.path.join(i18n_dir, 'TestPlugin_en.qm')
        with open(translation_file, 'w') as f:
            f.write('dummy content')
        
        service = QGISTranslationService(self.plugin_dir, 'TestPlugin')
        
        self.assertEqual(service.get_current_locale(), 'en')
        self.assertTrue(service.is_translation_loaded())
    
    @patch('services.translation_service.QCoreApplication')
    def test_translate(self, mock_core_app):
        """Test translation functionality."""
        mock_core_app.translate.return_value = 'Translated Message'
        
        result = self.translation_service.translate('Test Message')
        
        self.assertEqual(result, 'Translated Message')
        # The service uses the plugin name passed to constructor, which is 'TestPlugin' in setUp
        mock_core_app.translate.assert_called_with('TestPlugin', 'Test Message')
    
    def test_get_current_locale(self):
        """Test getting current locale."""
        locale = self.translation_service.get_current_locale()
        self.assertIsInstance(locale, str)
        self.assertGreater(len(locale), 0)
    
    def test_is_translation_loaded(self):
        """Test translation loaded status."""
        # Should be False when no translation file exists
        self.assertFalse(self.translation_service.is_translation_loaded())
    
    def test_get_translation_file_path(self):
        """Test getting translation file path."""
        # Should return None when no translation file exists
        self.assertIsNone(self.translation_service.get_translation_file_path())
        
        # Create translation file
        i18n_dir = os.path.join(self.plugin_dir, 'i18n')
        os.makedirs(i18n_dir)
        # Use the plugin name from setUp ('TestPlugin')
        translation_file = os.path.join(i18n_dir, 'TestPlugin_en.qm')
        with open(translation_file, 'w') as f:
            f.write('dummy content')
        
        path = self.translation_service.get_translation_file_path()
        self.assertEqual(path, translation_file)


class TestArcheoSyncConfigurationValidator(unittest.TestCase):
    """Test cases for ArcheoSyncConfigurationValidator."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a more complete mock that includes all methods
        self.file_system_service = Mock()
        # Add the methods that the validator uses
        self.file_system_service.path_exists = Mock()
        self.file_system_service.is_directory = Mock()
        self.file_system_service.is_file = Mock()
        self.file_system_service.list_files = Mock()
        self.file_system_service.create_directory = Mock()
        self.file_system_service.select_directory = Mock()
        
        self.validator = ArcheoSyncConfigurationValidator(self.file_system_service)
        
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = os.path.join(self.temp_dir, 'test.txt')
        with open(self.temp_file, 'w') as f:
            f.write('test content')
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_implements_interface(self):
        """Test that ArcheoSyncConfigurationValidator implements IConfigurationValidator."""
        self.assertIsInstance(self.validator, IConfigurationValidator)
    
    def test_validate_field_projects_folder_empty_path(self):
        """Test validation of empty field projects folder path."""
        errors = self.validator.validate_field_projects_folder("")
        self.assertEqual(len(errors), 1)
        self.assertIn("required", errors[0])
    
    def test_validate_field_projects_folder_nonexistent(self):
        """Test validation of nonexistent field projects folder."""
        self.file_system_service.path_exists.return_value = False
        
        errors = self.validator.validate_field_projects_folder("/nonexistent/path")
        
        self.assertEqual(len(errors), 1)
        self.assertIn("does not exist", errors[0])
    
    def test_validate_field_projects_folder_not_directory(self):
        """Test validation of field projects folder that is not a directory."""
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.is_directory.return_value = False
        
        errors = self.validator.validate_field_projects_folder("/path/to/file")
        
        self.assertEqual(len(errors), 1)
        self.assertIn("not a directory", errors[0])
    
    def test_validate_field_projects_folder_not_writable(self):
        """Test validation of field projects folder that is not writable."""
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.is_directory.return_value = True
        
        # Mock Path to raise PermissionError on touch()
        with patch('services.configuration_validator.Path') as mock_path_class:
            # Create a mock instance that behaves like Path
            mock_path_instance = Mock()
            mock_path_instance.__truediv__ = Mock(return_value=mock_path_instance)
            mock_path_instance.touch = Mock(side_effect=PermissionError())
            mock_path_instance.unlink = Mock()
            mock_path_class.return_value = mock_path_instance
            
            # Use a real path string
            test_path = "/test/path"
            errors = self.validator.validate_field_projects_folder(test_path)
            
            self.assertEqual(len(errors), 1)
            self.assertIn("not writable", errors[0])
    
    def test_validate_total_station_folder_no_csv_files(self):
        """Test validation of total station folder with no CSV files."""
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.is_directory.return_value = True
        self.file_system_service.list_files.return_value = []
        
        errors = self.validator.validate_total_station_folder(self.temp_dir)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("No CSV files found", errors[0])
    
    def test_validate_template_project_folder_no_qgis_files(self):
        """Test validation of template project folder with no QGIS files."""
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.is_directory.return_value = True
        self.file_system_service.list_files.return_value = []
        
        errors = self.validator.validate_template_project_folder(self.temp_dir)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("No QGIS project files", errors[0])
    
    def test_validate_all_settings(self):
        """Test validation of all settings at once."""
        settings = {
            'field_projects_folder': '/path/to/field',
            'total_station_folder': '/path/to/total',
            'completed_projects_folder': '/path/to/completed',
            'template_project_folder': '/path/to/template'
        }
        
        # Mock all validation methods to return errors
        with patch.object(self.validator, 'validate_field_projects_folder') as mock_field:
            with patch.object(self.validator, 'validate_total_station_folder') as mock_total:
                with patch.object(self.validator, 'validate_completed_projects_folder') as mock_completed:
                    with patch.object(self.validator, 'validate_template_project_folder') as mock_template:
                        mock_field.return_value = ['Field error']
                        mock_total.return_value = ['Total error']
                        mock_completed.return_value = []
                        mock_template.return_value = ['Template error']
                        
                        results = self.validator.validate_all_settings(settings)
                        
                        self.assertIn('field_projects_folder', results)
                        self.assertIn('total_station_folder', results)
                        self.assertIn('completed_projects_folder', results)
                        self.assertIn('template_project_folder', results)
                        
                        self.assertEqual(len(results['field_projects_folder']), 1)
                        self.assertEqual(len(results['total_station_folder']), 1)
                        self.assertEqual(len(results['completed_projects_folder']), 0)
                        self.assertEqual(len(results['template_project_folder']), 1)
    
    def test_has_validation_errors(self):
        """Test checking for validation errors."""
        # Test with errors
        validation_results = {
            'field_projects_folder': ['Error 1'],
            'total_station_folder': []
        }
        self.assertTrue(self.validator.has_validation_errors(validation_results))
        
        # Test without errors
        validation_results = {
            'field_projects_folder': [],
            'total_station_folder': []
        }
        self.assertFalse(self.validator.has_validation_errors(validation_results))
    
    def test_get_all_errors(self):
        """Test getting all errors as a flat list."""
        validation_results = {
            'field_projects_folder': ['Field error 1', 'Field error 2'],
            'total_station_folder': ['Total error 1']
        }
        
        all_errors = self.validator.get_all_errors(validation_results)
        
        self.assertEqual(len(all_errors), 3)
        self.assertIn('field_projects_folder: Field error 1', all_errors)
        self.assertIn('field_projects_folder: Field error 2', all_errors)
        self.assertIn('total_station_folder: Total error 1', all_errors)


if __name__ == '__main__':
    unittest.main() 