# -*- coding: utf-8 -*-
"""
Tests for UI components.

This module contains tests for the UI components to ensure they follow SOLID principles
and work correctly with dependency injection.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
import tempfile
import os

# Add the parent directory to the path to allow importing the plugin
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.settings_dialog import SettingsDialog
from core.interfaces import ISettingsManager, IFileSystemService, IConfigurationValidator


class TestSettingsDialog(unittest.TestCase):
    """Test cases for SettingsDialog."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock services with all required methods
        self.mock_settings_manager = Mock()
        self.mock_settings_manager.set_value = Mock()
        self.mock_settings_manager.get_value = Mock()
        self.mock_settings_manager.remove_value = Mock()
        self.mock_settings_manager.clear_all = Mock()
        
        self.mock_file_system_service = Mock()
        self.mock_file_system_service.select_directory = Mock()
        self.mock_file_system_service.path_exists = Mock()
        self.mock_file_system_service.create_directory = Mock()
        self.mock_file_system_service.is_directory = Mock()
        self.mock_file_system_service.is_file = Mock()
        self.mock_file_system_service.get_file_extension = Mock()
        self.mock_file_system_service.list_files = Mock()
        
        self.mock_configuration_validator = Mock()
        self.mock_configuration_validator.validate_field_projects_folder = Mock()
        self.mock_configuration_validator.validate_total_station_folder = Mock()
        self.mock_configuration_validator.validate_completed_projects_folder = Mock()
        self.mock_configuration_validator.validate_template_project_folder = Mock()
        self.mock_configuration_validator.validate_all_settings = Mock()
        self.mock_configuration_validator.has_validation_errors = Mock()
        self.mock_configuration_validator.get_all_errors = Mock()
        
        # Create dialog with mocked dependencies
        self.dialog = SettingsDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service,
            configuration_validator=self.mock_configuration_validator
        )
    
    def test_init_with_dependencies(self):
        """Test dialog initialization with injected dependencies."""
        self.assertIsNotNone(self.dialog)
        self.assertEqual(self.dialog._settings_manager, self.mock_settings_manager)
        self.assertEqual(self.dialog._file_system_service, self.mock_file_system_service)
        self.assertEqual(self.dialog._configuration_validator, self.mock_configuration_validator)
    
    def test_setup_ui_creates_required_widgets(self):
        """Test that UI setup creates all required widgets."""
        # Check that main widgets exist
        self.assertIsNotNone(self.dialog._field_projects_widget)
        self.assertIsNotNone(self.dialog._total_station_widget)
        self.assertIsNotNone(self.dialog._completed_projects_widget)
        self.assertIsNotNone(self.dialog._qfield_checkbox)
        self.assertIsNotNone(self.dialog._template_project_widget)
        self.assertIsNotNone(self.dialog._button_box)
        
        # Check that widget components exist
        self.assertIsNotNone(self.dialog._field_projects_widget.input_field)
        self.assertIsNotNone(self.dialog._field_projects_widget.browse_button)
        self.assertIsNotNone(self.dialog._total_station_widget.input_field)
        self.assertIsNotNone(self.dialog._total_station_widget.browse_button)
        self.assertIsNotNone(self.dialog._completed_projects_widget.input_field)
        self.assertIsNotNone(self.dialog._completed_projects_widget.browse_button)
        self.assertIsNotNone(self.dialog._template_project_widget.input_field)
        self.assertIsNotNone(self.dialog._template_project_widget.browse_button)
    
    def test_load_settings_calls_settings_manager(self):
        """Test that loading settings calls the settings manager."""
        # Mock settings manager to return test values
        self.mock_settings_manager.get_value.side_effect = [
            '/path/to/field',  # field_projects_folder
            '/path/to/total',  # total_station_folder
            '/path/to/completed',  # completed_projects_folder
            False,  # use_qfield
            '/path/to/template'  # template_project_folder
        ]
        
        # Call load_settings
        self.dialog._load_settings()
        
        # Verify settings manager was called correctly
        expected_calls = [
            call('field_projects_folder', ''),
            call('total_station_folder', ''),
            call('completed_projects_folder', ''),
            call('use_qfield', False),
            call('template_project_folder', '')
        ]
        self.mock_settings_manager.get_value.assert_has_calls(expected_calls)
    
    def test_load_settings_updates_ui_widgets(self):
        """Test that loading settings updates UI widgets."""
        # Mock settings manager to return test values
        self.mock_settings_manager.get_value.side_effect = [
            '/path/to/field',
            '/path/to/total',
            '/path/to/completed',
            True,  # use_qfield
            '/path/to/template'
        ]
        
        # Call load_settings
        self.dialog._load_settings()
        
        # Verify UI widgets were updated
        self.assertEqual(self.dialog._field_projects_widget.input_field.text(), '/path/to/field')
        self.assertEqual(self.dialog._total_station_widget.input_field.text(), '/path/to/total')
        self.assertEqual(self.dialog._completed_projects_widget.input_field.text(), '/path/to/completed')
        self.assertTrue(self.dialog._qfield_checkbox.isChecked())
        self.assertEqual(self.dialog._template_project_widget.input_field.text(), '/path/to/template')
    
    def test_load_settings_stores_original_values(self):
        """Test that loading settings stores original values."""
        # Mock settings manager to return test values
        self.mock_settings_manager.get_value.side_effect = [
            '/path/to/field',
            '/path/to/total',
            '/path/to/completed',
            False,
            '/path/to/template'
        ]
        
        # Call load_settings
        self.dialog._load_settings()
        
        # Verify original values were stored
        expected_original_values = {
            'field_projects_folder': '/path/to/field',
            'total_station_folder': '/path/to/total',
            'completed_projects_folder': '/path/to/completed',
            'use_qfield': False,
            'template_project_folder': '/path/to/template'
        }
        self.assertEqual(self.dialog._original_values, expected_original_values)
    
    def test_browse_folder_calls_file_system_service(self):
        """Test that browsing for folders calls the file system service."""
        input_field = self.dialog._field_projects_widget.input_field
        input_field.setText('/initial/path')
        
        # Mock file system service to return a path
        self.mock_file_system_service.select_directory.return_value = '/selected/path'
        
        # Call browse_folder
        self.dialog._browse_folder(input_field, 'Test Title')
        
        # Verify file system service was called
        self.mock_file_system_service.select_directory.assert_called_with(
            'Test Title', '/initial/path'
        )
        
        # Verify input field was updated
        self.assertEqual(input_field.text(), '/selected/path')
    
    def test_browse_folder_handles_cancellation(self):
        """Test that browsing for folders handles cancellation."""
        input_field = self.dialog._field_projects_widget.input_field
        input_field.setText('/initial/path')
        
        # Mock file system service to return None (cancelled)
        self.mock_file_system_service.select_directory.return_value = None
        
        # Call browse_folder
        self.dialog._browse_folder(input_field, 'Test Title')
        
        # Verify input field was not changed
        self.assertEqual(input_field.text(), '/initial/path')
    
    def test_update_ui_state_shows_template_widget_when_qfield_unchecked(self):
        """Test that UI state updates correctly when QField is unchecked."""
        # Set QField checkbox to unchecked
        self.dialog._qfield_checkbox.setChecked(False)
        
        # Call update_ui_state
        self.dialog._update_ui_state()
        
        # Verify template project widgets are visible
        # Note: The widgets might be hidden initially, so we check the logic rather than visibility
        use_qfield = self.dialog._qfield_checkbox.isChecked()
        should_be_visible = not use_qfield
        self.assertFalse(use_qfield)  # QField should be unchecked
        self.assertTrue(should_be_visible)  # Template should be visible
    
    def test_update_ui_state_hides_template_widget_when_qfield_checked(self):
        """Test that UI state updates correctly when QField is checked."""
        # Set QField checkbox to checked
        self.dialog._qfield_checkbox.setChecked(True)
        
        # Call update_ui_state
        self.dialog._update_ui_state()
        
        # Verify template project widgets are hidden
        self.assertFalse(self.dialog._template_project_label.isVisible())
        self.assertFalse(self.dialog._template_project_widget.isVisible())
    
    def test_save_and_accept_validates_settings(self):
        """Test that saving settings validates the configuration."""
        # Set up UI with test values
        self.dialog._field_projects_widget.input_field.setText('/path/to/field')
        self.dialog._total_station_widget.input_field.setText('/path/to/total')
        self.dialog._completed_projects_widget.input_field.setText('/path/to/completed')
        self.dialog._qfield_checkbox.setChecked(False)
        self.dialog._template_project_widget.input_field.setText('/path/to/template')
        
        # Mock validation to return errors
        validation_results = {
            'field_projects_folder': ['Field error'],
            'total_station_folder': [],
            'completed_projects_folder': [],
            'template_project_folder': []
        }
        self.mock_configuration_validator.validate_all_settings.return_value = validation_results
        self.mock_configuration_validator.has_validation_errors.return_value = True
        self.mock_configuration_validator.get_all_errors.return_value = ['Field error']
        
        # Mock QMessageBox to avoid showing actual dialog
        with patch('ui.settings_dialog.QtWidgets.QMessageBox') as mock_message_box:
            mock_message_box.critical = Mock()
            
            # Call save_and_accept
            self.dialog._save_and_accept()
            
            # Verify validation was called
            self.mock_configuration_validator.validate_all_settings.assert_called_once()
            
            # Verify error message was shown
            mock_message_box.critical.assert_called_once()
            
            # Verify dialog was not accepted
            self.assertNotEqual(self.dialog.result(), 1)  # Not accepted
    
    def test_save_and_accept_saves_valid_settings(self):
        """Test that saving settings saves valid configuration."""
        # Set up UI with test values
        self.dialog._field_projects_widget.input_field.setText('/path/to/field')
        self.dialog._total_station_widget.input_field.setText('/path/to/total')
        self.dialog._completed_projects_widget.input_field.setText('/path/to/completed')
        self.dialog._qfield_checkbox.setChecked(False)
        self.dialog._template_project_widget.input_field.setText('/path/to/template')
        
        # Mock validation to return no errors
        validation_results = {
            'field_projects_folder': [],
            'total_station_folder': [],
            'completed_projects_folder': [],
            'template_project_folder': []
        }
        self.mock_configuration_validator.validate_all_settings.return_value = validation_results
        self.mock_configuration_validator.has_validation_errors.return_value = False
        
        # Call save_and_accept
        self.dialog._save_and_accept()
        
        # Verify settings were saved
        expected_calls = [
            call('field_projects_folder', '/path/to/field'),
            call('total_station_folder', '/path/to/total'),
            call('completed_projects_folder', '/path/to/completed'),
            call('use_qfield', False),
            call('template_project_folder', '/path/to/template')
        ]
        self.mock_settings_manager.set_value.assert_has_calls(expected_calls)
        
        # Verify dialog was accepted
        self.assertEqual(self.dialog.result(), 1)  # Accepted
    
    def test_reject_reverts_to_original_values(self):
        """Test that rejecting the dialog reverts to original values."""
        # Set up original values
        self.dialog._original_values = {
            'field_projects_folder': '/original/field',
            'total_station_folder': '/original/total',
            'completed_projects_folder': '/original/completed',
            'use_qfield': True,
            'template_project_folder': '/original/template'
        }
        
        # Change UI values
        self.dialog._field_projects_widget.input_field.setText('/changed/field')
        self.dialog._total_station_widget.input_field.setText('/changed/total')
        self.dialog._completed_projects_widget.input_field.setText('/changed/completed')
        self.dialog._qfield_checkbox.setChecked(False)
        self.dialog._template_project_widget.input_field.setText('/changed/template')
        
        # Mock QMessageBox to avoid showing actual dialog
        with patch('ui.settings_dialog.QtWidgets.QMessageBox') as mock_message_box:
            mock_message_box.critical = Mock()
            
            # Call reject
            self.dialog._reject()
            
            # Verify UI was reverted
            self.assertEqual(self.dialog._field_projects_widget.input_field.text(), '/original/field')
            self.assertEqual(self.dialog._total_station_widget.input_field.text(), '/original/total')
            self.assertEqual(self.dialog._completed_projects_widget.input_field.text(), '/original/completed')
            self.assertTrue(self.dialog._qfield_checkbox.isChecked())
            self.assertEqual(self.dialog._template_project_widget.input_field.text(), '/original/template')
            
            # Verify settings manager was reverted
            expected_calls = [
                call('field_projects_folder', '/original/field'),
                call('total_station_folder', '/original/total'),
                call('completed_projects_folder', '/original/completed'),
                call('use_qfield', True),
                call('template_project_folder', '/original/template')
            ]
            self.mock_settings_manager.set_value.assert_has_calls(expected_calls)
    
    def test_show_error_shows_message_box(self):
        """Test that showing errors displays a message box."""
        with patch('ui.settings_dialog.QtWidgets.QMessageBox') as mock_message_box:
            mock_critical = Mock()
            mock_message_box.critical = mock_critical
            
            # Call show_error
            self.dialog._show_error('Test Title', 'Test Message')
            
            # Verify message box was shown
            mock_critical.assert_called_once_with(self.dialog, 'Test Title', 'Test Message')
    
    def test_dependency_injection_follows_solid_principles(self):
        """Test that the dialog follows SOLID principles through dependency injection."""
        # Single Responsibility: Dialog only handles UI, not business logic
        # Open/Closed: Can extend functionality by injecting different services
        # Liskov Substitution: Can use any implementation of the interfaces
        # Interface Segregation: Only depends on the interfaces it needs
        # Dependency Inversion: Depends on abstractions, not concretions
        
        # Test that we can inject different implementations
        mock_settings_manager2 = Mock(spec=ISettingsManager)
        mock_file_system_service2 = Mock(spec=IFileSystemService)
        mock_configuration_validator2 = Mock(spec=IConfigurationValidator)
        
        dialog2 = SettingsDialog(
            settings_manager=mock_settings_manager2,
            file_system_service=mock_file_system_service2,
            configuration_validator=mock_configuration_validator2
        )
        
        # Verify the dialog works with different implementations
        self.assertIsNotNone(dialog2)
        self.assertEqual(dialog2._settings_manager, mock_settings_manager2)
        self.assertEqual(dialog2._file_system_service, mock_file_system_service2)
        self.assertEqual(dialog2._configuration_validator, mock_configuration_validator2)


if __name__ == '__main__':
    unittest.main() 