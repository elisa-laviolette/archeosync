# -*- coding: utf-8 -*-
"""
Tests for ArcheoSync dialog settings functionality.

This module contains tests for the dialog's integration with the settings manager.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from qgis.PyQt.QtWidgets import QApplication
from qgis.PyQt.QtCore import Qt

# Add the parent directory to the path to allow importing the plugin
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.settings_service import QGISSettingsManager
from ui.settings_dialog import SettingsDialog


class TestArcheoSyncDialogSettings(unittest.TestCase):
    """Test cases for SettingsDialog settings integration."""

    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        # Create QApplication instance for widget tests
        cls.app = QApplication([])

    @classmethod
    def tearDownClass(cls):
        """Clean up test class."""
        cls.app.quit()

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock settings manager
        self.mock_settings = Mock(spec=QGISSettingsManager)
        
        # Configure mock to return appropriate default values
        def mock_get_value(key, default):
            if key == 'field_projects_folder':
                return '/default/field/projects'  # Return default folder path
            else:
                return default  # Return default for other settings
        
        self.mock_settings.get_value.side_effect = mock_get_value
        self.mock_settings.set_value.return_value = None
        self.mock_settings.clear_all.return_value = None
        
        # Create mock services
        self.mock_file_service = Mock()
        self.mock_layer_service = Mock()
        self.mock_layer_service.get_polygon_layers = Mock(return_value=[])
        self.mock_validator = Mock()
        
        # Mock QMessageBox globally to prevent GUI dialogs during tests
        self.message_box_patcher = patch('ui.settings_dialog.QtWidgets.QMessageBox')
        self.mock_message_box = self.message_box_patcher.start()
        self.mock_message_box.information.return_value = None
        self.mock_message_box.warning.return_value = None
        self.mock_message_box.critical.return_value = None
        self.mock_message_box.question.return_value = self.mock_message_box.Yes
        
        # Create dialog with mock services
        self.dialog = SettingsDialog(
            settings_manager=self.mock_settings,
            file_system_service=self.mock_file_service,
            layer_service=self.mock_layer_service,
            configuration_validator=self.mock_validator
        )

    def tearDown(self):
        """Clean up after tests."""
        self.dialog.close()
        # Stop the QMessageBox mock
        self.message_box_patcher.stop()

    def test_dialog_initialization_with_settings(self):
        """Test dialog initializes with settings manager and field_projects_widget."""
        self.assertIsNotNone(self.dialog._field_projects_widget)

    def test_folder_input_properties(self):
        """Test that field_projects_widget has correct properties."""
        self.assertTrue(self.dialog._field_projects_widget.input_field.isReadOnly())
        self.assertEqual(self.dialog._field_projects_widget.input_field.placeholderText(), "Select destination folder for new field projects...")

    def test_browse_folder_success(self):
        """Test successful folder browsing for field projects."""
        test_path = "/test/selected/folder"
        self.mock_file_service.select_directory.return_value = test_path
        initial_path = "/initial/path"
        self.dialog._field_projects_widget.input_field.setText(initial_path)
        
        # Call the browse method directly
        self.dialog._browse_folder(self.dialog._field_projects_widget.input_field, "Test Title")
        
        self.mock_file_service.select_directory.assert_called_once_with(
            "Test Title",
            initial_path
        )
        self.assertEqual(self.dialog._field_projects_widget.input_field.text(), test_path)

    def test_browse_folder_cancelled(self):
        """Test folder browsing cancelled for field projects."""
        self.mock_file_service.select_directory.return_value = None
        initial_path = "/initial/path"
        self.dialog._field_projects_widget.input_field.setText(initial_path)
        
        # Call the browse method directly
        self.dialog._browse_folder(self.dialog._field_projects_widget.input_field, "Test Title")
        
        self.mock_file_service.select_directory.assert_called_once()
        self.assertEqual(self.dialog._field_projects_widget.input_field.text(), initial_path)

    def test_browse_folder_empty_initial_path(self):
        """Test folder browsing with empty initial path for field projects."""
        test_path = "/test/selected/folder"
        self.mock_file_service.select_directory.return_value = test_path
        self.dialog._field_projects_widget.input_field.clear()
        
        # Call the browse method directly
        self.dialog._browse_folder(self.dialog._field_projects_widget.input_field, "Test Title")
        
        # When input field is empty, it should pass None, not empty string
        self.mock_file_service.select_directory.assert_called_once_with(
            "Test Title",
            None
        )
        self.assertEqual(self.dialog._field_projects_widget.input_field.text(), test_path)

    def test_load_settings_success(self):
        """Test successful settings load operation for field projects."""
        test_folder_path = "/test/field/projects"
        self.mock_settings.get_value.side_effect = [
            test_folder_path,  # field_projects_folder
            '',                # total_station_folder (not tested here)
            '',                # completed_projects_folder (not tested here)
            '',                # recording_areas_layer (not tested here)
            '',                # objects_layer (not tested here)
            '',                # features_layer (not tested here)
        ]
        
        # Call the load settings method directly
        self.dialog._load_settings()
        
        self.mock_settings.get_value.assert_any_call('field_projects_folder', '')
        self.assertEqual(self.dialog._field_projects_widget.input_field.text(), test_folder_path)

    def test_save_and_accept_success(self):
        """Test successful save and accept for field projects."""
        test_folder_path = "/test/field/projects"
        self.dialog._field_projects_widget.input_field.setText(test_folder_path)
        
        # Mock validation to return no errors
        self.mock_validator.validate_all_settings.return_value = {}
        self.mock_validator.has_validation_errors.return_value = False
        
        # Call the save and accept method directly
        self.dialog._save_and_accept()
        
        self.mock_settings.set_value.assert_any_call('field_projects_folder', test_folder_path)

    def test_save_and_accept_validation_errors(self):
        """Test save_and_accept when validation fails."""
        test_folder_path = "/test/field/projects"
        self.dialog._field_projects_widget.input_field.setText(test_folder_path)
        
        # Mock validation to return errors
        self.mock_validator.validate_all_settings.return_value = {
            'field_projects_folder': ['Path does not exist']
        }
        self.mock_validator.has_validation_errors.return_value = True
        self.mock_validator.get_all_errors.return_value = ['Path does not exist']
        
        # Call the save and accept method directly
        self.dialog._save_and_accept()
        
        # Should not call set_value when validation fails
        self.mock_settings.set_value.assert_not_called()



    def test_cancel_reverts_settings(self):
        """Test cancel reverts field projects folder."""
        original_folder = "/original/folder"
        self.dialog._original_values = {
            'field_projects_folder': original_folder,
            'total_station_folder': '',
            'completed_projects_folder': ''
        }
        self.dialog._field_projects_widget.input_field.setText("/changed/folder")
        
        # Call the reject method directly
        self.dialog._reject()
        
        self.assertEqual(self.dialog._field_projects_widget.input_field.text(), original_folder)


if __name__ == '__main__':
    unittest.main() 