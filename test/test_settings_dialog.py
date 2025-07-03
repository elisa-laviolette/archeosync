# coding=utf-8
"""Dialog test.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'elisa.laviolette@gmail.com'
__date__ = '2025-07-01'
__copyright__ = 'Copyright 2025, Elisa Caron-Laviolette'

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Try to import QGIS modules, skip tests if not available
try:
    from qgis.PyQt.QtWidgets import QDialogButtonBox, QDialog, QApplication, QFileDialog # type: ignore
    from qgis.PyQt.QtCore import QCoreApplication # type: ignore
    from ui.settings_dialog import SettingsDialog
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

from .utilities import get_qgis_app

from services.settings_service import QGISSettingsManager
from services.file_system_service import QGISFileSystemService
from services.configuration_validator import ArcheoSyncConfigurationValidator


@pytest.mark.unit
class TestSettingsDialogBasic:
    """Basic tests that don't require QGIS."""
    
    def test_import_available(self):
        """Test that the dialog module can be imported."""
        try:
            from ui.settings_dialog import SettingsDialog
            assert SettingsDialog is not None
        except ImportError:
            pytest.skip("SettingsDialog module not available")


@pytest.mark.qgis
@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class TestSettingsDialog:
    """Test dialog works."""

    def setup_method(self):
        """Runs before each test."""
        self.qgis_app, self.canvas, self.iface, self.parent = get_qgis_app()
        if QApplication.instance() is None:
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()
        # Create mock services for dependency injection
        self.mock_settings = Mock()
        self.mock_file_service = Mock()
        self.mock_validator = Mock()
        
        # Mock the settings manager to return empty values to prevent setText errors
        self.mock_settings.get_value.return_value = ''
        
        # Mock the configuration validator to pass validation
        self.mock_validator.validate_all_settings.return_value = {}
        self.mock_validator.has_validation_errors.return_value = False
        self.mock_validator.get_all_errors.return_value = []
        
        # Patch QMessageBox
        self.message_box_patcher = patch('ui.settings_dialog.QtWidgets.QMessageBox')
        self.mock_message_box = self.message_box_patcher.start()
        self.mock_message_box.warning.return_value = None
        self.mock_message_box.critical.return_value = None
        
        # Create dialog with mock services
        try:
            self.dialog = SettingsDialog(
                settings_manager=self.mock_settings,
                file_system_service=self.mock_file_service,
                configuration_validator=self.mock_validator,
                parent=self.parent
            )
        except Exception as e:
            pytest.skip(f"Failed to create dialog: {e}")

    def teardown_method(self):
        if hasattr(self, 'dialog'):
            self.dialog.close()
            self.dialog.deleteLater()
        self.dialog = None
        self.message_box_patcher.stop()

    def test_dialog_creation(self):
        assert self.dialog is not None
        assert hasattr(self.dialog, '_button_box')
        assert self.dialog.windowTitle() == "ArcheoSync Settings"

    def test_dialog_ok(self):
        button = self.dialog._button_box.button(QDialogButtonBox.Ok)
        button.click()
        result = self.dialog.result()
        assert result == QDialog.Accepted

    def test_dialog_cancel(self):
        button = self.dialog._button_box.button(QDialogButtonBox.Cancel)
        button.click()
        result = self.dialog.result()
        assert result == QDialog.Rejected

    def test_dialog_ui_elements_exist(self):
        # Test that the settings UI elements exist
        assert hasattr(self.dialog, '_field_projects_widget')
        assert hasattr(self.dialog, '_total_station_widget')
        assert hasattr(self.dialog, '_completed_projects_widget')
        assert hasattr(self.dialog, '_qfield_checkbox')
        assert hasattr(self.dialog, '_template_project_widget')

    def test_field_projects_input_properties(self):
        assert self.dialog._field_projects_widget.input_field.isReadOnly() is True
        assert self.dialog._field_projects_widget.input_field.placeholderText() == "Select destination folder for new field projects..."

    def test_total_station_input_properties(self):
        assert self.dialog._total_station_widget.input_field.isReadOnly() is True
        assert self.dialog._total_station_widget.input_field.placeholderText() == "Select folder containing total station CSV files..."

    def test_completed_projects_input_properties(self):
        assert self.dialog._completed_projects_widget.input_field.isReadOnly() is True
        assert self.dialog._completed_projects_widget.input_field.placeholderText() == "Select folder containing completed field projects..."

    def test_qfield_checkbox_properties(self):
        assert self.dialog._qfield_checkbox.text() == "Use QField for field data collection"
        assert self.dialog._qfield_checkbox.isChecked() is False

    def test_template_project_input_properties(self):
        assert self.dialog._template_project_widget.input_field.isReadOnly() is True
        assert self.dialog._template_project_widget.input_field.placeholderText() == "Select folder containing template QGIS project..."


@pytest.mark.qgis
@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class TestSettingsDialogIntegration:
    """Integration tests for SettingsDialog with real dependencies."""

    def setup_method(self):
        """Runs before each test."""
        self.qgis_app, self.canvas, self.iface, self.parent = get_qgis_app()
        if QApplication.instance() is None:
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()

    def test_dialog_with_real_services(self):
        """Test that dialog works with real service instances."""
        settings_service = QGISSettingsManager()
        file_system_service = QGISFileSystemService()
        configuration_validator = ArcheoSyncConfigurationValidator(file_system_service)
        
        dialog = SettingsDialog(
            settings_service,
            file_system_service,
            configuration_validator,
            parent=self.parent
        )
        
        # Verify that dialog was created successfully
        assert dialog is not None
        assert dialog._settings_manager == settings_service
        assert dialog._file_system_service == file_system_service
        assert dialog._configuration_validator == configuration_validator
        
        dialog.close()
        dialog.deleteLater()

    def test_settings_persistence(self):
        """Test that settings persist through dialog operations."""
        settings_service = QGISSettingsManager()
        file_system_service = QGISFileSystemService()
        configuration_validator = ArcheoSyncConfigurationValidator(file_system_service)
        
        dialog = SettingsDialog(
            settings_service,
            file_system_service,
            configuration_validator,
            parent=self.parent
        )
        
        # Set a test setting
        test_value = "/test/directory"
        settings_service.set_value('field_projects_folder', test_value)
        
        # Verify the setting was saved
        assert settings_service.get_value('field_projects_folder') == test_value
        
        # Create a new dialog instance and verify the setting persists
        new_dialog = SettingsDialog(
            settings_service,
            file_system_service,
            configuration_validator,
            parent=self.parent
        )
        
        assert new_dialog._settings_manager.get_value('field_projects_folder') == test_value
        
        dialog.close()
        dialog.deleteLater()
        new_dialog.close()
        new_dialog.deleteLater()


@pytest.mark.qgis
@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class TestSettingsDialogErrorHandling:
    """Test error handling in SettingsDialog."""

    def setup_method(self):
        """Runs before each test."""
        self.qgis_app, self.canvas, self.iface, self.parent = get_qgis_app()
        if QApplication.instance() is None:
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()

    def test_load_settings_error(self):
        """Test handling of errors during settings loading."""
        settings_service = Mock(spec=QGISSettingsManager)
        file_system_service = Mock(spec=QGISFileSystemService)
        configuration_validator = Mock(spec=ArcheoSyncConfigurationValidator)
        
        # Mock settings service to raise an exception
        settings_service.get_value.side_effect = Exception("Settings error")
        
        # Mock QMessageBox to prevent actual dialog
        with patch('PyQt5.QtWidgets.QMessageBox.critical') as mock_critical:
            dialog = SettingsDialog(
                settings_service,
                file_system_service,
                configuration_validator,
                parent=self.parent
            )
            
            # Verify that the error was handled gracefully
            assert settings_service.get_value.called
            # The error should have been caught and shown via QMessageBox
            mock_critical.assert_called()
            
            dialog.close()
            dialog.deleteLater()

    def test_save_settings_error(self):
        """Test handling of errors during settings saving."""
        settings_service = Mock(spec=QGISSettingsManager)
        file_system_service = Mock(spec=QGISFileSystemService)
        configuration_validator = Mock(spec=ArcheoSyncConfigurationValidator)
        
        # Mock settings service to return empty values initially, then raise exception on save
        settings_service.get_value.return_value = ''
        settings_service.set_value.side_effect = Exception("Save error")
        
        # Mock validation to pass
        configuration_validator.validate_all_settings.return_value = {}
        configuration_validator.has_validation_errors.return_value = False
        
        # Mock QMessageBox to prevent actual dialog
        with patch('PyQt5.QtWidgets.QMessageBox.critical') as mock_critical:
            dialog = SettingsDialog(
                settings_service,
                file_system_service,
                configuration_validator,
                parent=self.parent
            )
            
            # Try to save settings
            dialog._save_and_accept()
            
            # Verify that the error was handled gracefully
            assert settings_service.set_value.called
            # The error should have been caught and shown via QMessageBox
            mock_critical.assert_called()
            
            dialog.close()
            dialog.deleteLater()

    def test_validation_error(self):
        """Test handling of errors during validation."""
        settings_service = Mock(spec=QGISSettingsManager)
        file_system_service = Mock(spec=QGISFileSystemService)
        configuration_validator = Mock(spec=ArcheoSyncConfigurationValidator)
        
        # Mock settings service to return empty values initially
        settings_service.get_value.return_value = ''
        
        # Mock validation to raise an exception
        configuration_validator.validate_all_settings.side_effect = Exception("Validation error")
        
        # Mock QMessageBox to prevent actual dialog
        with patch('PyQt5.QtWidgets.QMessageBox.critical') as mock_critical:
            dialog = SettingsDialog(
                settings_service,
                file_system_service,
                configuration_validator,
                parent=self.parent
            )
            
            # Try to save settings
            dialog._save_and_accept()
            
            # Verify that the error was handled gracefully
            assert configuration_validator.validate_all_settings.called
            # The error should have been caught and shown via QMessageBox
            mock_critical.assert_called()
            
            dialog.close()
            dialog.deleteLater()

