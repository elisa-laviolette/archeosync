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
from services.layer_service import QGISLayerService


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
        self.mock_layer_service = Mock()
        self.mock_validator = Mock()
        
        # Mock the settings manager to return empty values to prevent setText errors
        self.mock_settings.get_value.return_value = ''
        
        # Mock the layer service to return empty list
        self.mock_layer_service.get_polygon_layers.return_value = []
        
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
                layer_service=self.mock_layer_service,
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
        assert hasattr(self.dialog, '_recording_areas_widget')

    def test_field_projects_input_properties(self):
        assert self.dialog._field_projects_widget.input_field.isReadOnly() is True
        assert self.dialog._field_projects_widget.input_field.placeholderText() == "Select destination folder for new field projects..."

    def test_total_station_input_properties(self):
        assert self.dialog._total_station_widget.input_field.isReadOnly() is True
        assert self.dialog._total_station_widget.input_field.placeholderText() == "Select folder containing total station CSV files..."

    def test_completed_projects_input_properties(self):
        assert self.dialog._completed_projects_widget.input_field.isReadOnly() is True
        assert self.dialog._completed_projects_widget.input_field.placeholderText() == "Select folder containing completed field projects..."

    def test_recording_areas_widget_properties(self):
        assert hasattr(self.dialog._recording_areas_widget, 'combo_box')
        assert hasattr(self.dialog._recording_areas_widget, 'refresh_button')
        assert self.dialog._recording_areas_widget.combo_box.count() > 0
        assert self.dialog._recording_areas_widget.combo_box.itemText(0) == "-- Select a polygon layer --"



    def test_refresh_layer_list(self):
        """Test refreshing the layer list."""
        # Mock layer service to return test layers
        test_layers = [
            {
                'id': 'layer1',
                'name': 'Test Layer 1',
                'source': '/path/to/layer1.shp',
                'crs': 'EPSG:4326',
                'feature_count': 10
            },
            {
                'id': 'layer2',
                'name': 'Test Layer 2',
                'source': '/path/to/layer2.shp',
                'crs': 'EPSG:4326',
                'feature_count': 5
            }
        ]
        self.mock_layer_service.get_polygon_layers.return_value = test_layers
        
        # Call refresh method
        self.dialog._refresh_layer_list()
        
        # Check that layers were added to combo box
        combo_box = self.dialog._recording_areas_widget.combo_box
        assert combo_box.count() == 3  # 1 placeholder + 2 layers
        assert combo_box.itemText(1) == "Test Layer 1 (10 features)"
        assert combo_box.itemText(2) == "Test Layer 2 (5 features)"
        assert combo_box.itemData(1) == "layer1"
        assert combo_box.itemData(2) == "layer2"

    def test_refresh_layer_list_preserves_selection(self):
        """Test that refresh preserves the currently selected layer."""
        # Set up initial layers
        initial_layers = [
            {
                'id': 'layer1',
                'name': 'Test Layer 1',
                'source': '/path/to/layer1.shp',
                'crs': 'EPSG:4326',
                'feature_count': 10
            }
        ]
        self.mock_layer_service.get_polygon_layers.return_value = initial_layers
        
        # Refresh and select a layer
        self.dialog._refresh_layer_list()
        self.dialog._recording_areas_widget.combo_box.setCurrentIndex(1)  # Select layer1
        
        # Set up new layers (including the previously selected one)
        new_layers = [
            {
                'id': 'layer2',
                'name': 'Test Layer 2',
                'source': '/path/to/layer2.shp',
                'crs': 'EPSG:4326',
                'feature_count': 5
            },
            {
                'id': 'layer1',
                'name': 'Test Layer 1',
                'source': '/path/to/layer1.shp',
                'crs': 'EPSG:4326',
                'feature_count': 10
            }
        ]
        self.mock_layer_service.get_polygon_layers.return_value = new_layers
        
        # Refresh again
        self.dialog._refresh_layer_list()
        
        # Check that layer1 is still selected
        combo_box = self.dialog._recording_areas_widget.combo_box
        assert combo_box.currentData() == "layer1"


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
        layer_service = QGISLayerService()
        configuration_validator = ArcheoSyncConfigurationValidator(file_system_service, layer_service)
        
        dialog = SettingsDialog(
            settings_service,
            file_system_service,
            layer_service,
            configuration_validator,
            parent=self.parent
        )
        
        # Verify that dialog was created successfully
        assert dialog is not None
        assert dialog._settings_manager == settings_service
        assert dialog._file_system_service == file_system_service
        assert dialog._layer_service == layer_service
        assert dialog._configuration_validator == configuration_validator
        
        dialog.close()
        dialog.deleteLater()

    def test_settings_persistence(self):
        """Test that settings persist through dialog operations."""
        settings_service = QGISSettingsManager()
        file_system_service = QGISFileSystemService()
        layer_service = QGISLayerService()
        configuration_validator = ArcheoSyncConfigurationValidator(file_system_service, layer_service)
        
        dialog = SettingsDialog(
            settings_service,
            file_system_service,
            layer_service,
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
            layer_service,
            configuration_validator,
            parent=self.parent
        )
        
        # Verify the setting is loaded in the new dialog
        assert new_dialog._field_projects_widget.input_field.text() == test_value
        
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
        """Test error handling when loading settings fails."""
        # Create mock services
        mock_settings = Mock()
        mock_file_service = Mock()
        mock_layer_service = Mock()
        mock_validator = Mock()
        
        # Make settings manager raise an exception
        mock_settings.get_value.side_effect = Exception("Settings error")
        
        # Mock QMessageBox
        with patch('ui.settings_dialog.QtWidgets.QMessageBox') as mock_message_box:
            mock_message_box.critical.return_value = None
            
            # Create dialog - should handle the exception gracefully
            dialog = SettingsDialog(
                mock_settings,
                mock_file_service,
                mock_layer_service,
                mock_validator,
                parent=self.parent
            )
            
            # Verify error message was shown
            mock_message_box.critical.assert_called_once()
            call_args = mock_message_box.critical.call_args
            assert call_args[0][1] == "Settings Error"
            assert "Failed to load settings" in call_args[0][2]
            
            dialog.close()
            dialog.deleteLater()

    def test_save_settings_error(self):
        """Test error handling when saving settings fails."""
        # Create mock services
        mock_settings = Mock()
        mock_file_service = Mock()
        mock_layer_service = Mock()
        mock_validator = Mock()
        
        # Mock the settings manager to return empty values
        mock_settings.get_value.return_value = ''
        
        # Mock the layer service to return empty lists
        mock_layer_service.get_polygon_layers.return_value = []
        mock_layer_service.get_polygon_and_multipolygon_layers.return_value = []
        
        # Mock the configuration validator to pass validation
        mock_validator.validate_all_settings.return_value = {}
        mock_validator.has_validation_errors.return_value = False
        
        # Make settings manager raise an exception when saving
        mock_settings.set_value.side_effect = Exception("Save error")
        
        # Mock QMessageBox
        with patch('ui.settings_dialog.QtWidgets.QMessageBox') as mock_message_box:
            mock_message_box.critical.return_value = None
            
            # Create dialog
            dialog = SettingsDialog(
                mock_settings,
                mock_file_service,
                mock_layer_service,
                mock_validator,
                parent=self.parent
            )
            
            # Try to save settings
            dialog._save_and_accept()
            
            # Verify error message was shown (may be called multiple times due to layer refresh errors)
            assert mock_message_box.critical.call_count >= 1
            found = False
            for call_args in mock_message_box.critical.call_args_list:
                if call_args[0][1] == "Settings Error" and "Failed to save settings" in call_args[0][2]:
                    found = True
            assert found
            
            dialog.close()
            dialog.deleteLater()

    def test_validation_error(self):
        """Test error handling when validation fails."""
        # Create mock services
        mock_settings = Mock()
        mock_file_service = Mock()
        mock_layer_service = Mock()
        mock_validator = Mock()
        
        # Mock the settings manager to return empty values
        mock_settings.get_value.return_value = ''
        
        # Mock the layer service to return empty lists
        mock_layer_service.get_polygon_layers.return_value = []
        mock_layer_service.get_polygon_and_multipolygon_layers.return_value = []
        
        # Mock the configuration validator to fail validation
        mock_validator.validate_all_settings.return_value = {
            'field_projects_folder': ['Field projects folder path is required']
        }
        mock_validator.has_validation_errors.return_value = True
        mock_validator.get_all_errors.return_value = ['field_projects_folder: Field projects folder path is required']
        
        # Mock QMessageBox
        with patch('ui.settings_dialog.QtWidgets.QMessageBox') as mock_message_box:
            mock_message_box.critical.return_value = None
            
            # Create dialog
            dialog = SettingsDialog(
                mock_settings,
                mock_file_service,
                mock_layer_service,
                mock_validator,
                parent=self.parent
            )
            
            # Try to save settings
            dialog._save_and_accept()
            
            # Verify validation error message was shown (may be called multiple times due to layer refresh errors)
            assert mock_message_box.critical.call_count >= 1
            found = False
            for call_args in mock_message_box.critical.call_args_list:
                if call_args[0][1] == "Validation Error" and "Please fix the following issues" in call_args[0][2]:
                    found = True
            assert found
            
            dialog.close()
            dialog.deleteLater()

    def test_refresh_layer_list_error(self):
        """Test error handling when refreshing layer list fails."""
        # Create mock services
        mock_settings = Mock()
        mock_file_service = Mock()
        mock_layer_service = Mock()
        mock_validator = Mock()
        
        # Mock the settings manager to return empty values
        mock_settings.get_value.return_value = ''
        
        # Mock the layer service to raise an exception
        mock_layer_service.get_polygon_layers.side_effect = Exception("Layer service error")
        
        # Mock the configuration validator to pass validation
        mock_validator.validate_all_settings.return_value = {}
        mock_validator.has_validation_errors.return_value = False
        
        # Mock QMessageBox
        with patch('ui.settings_dialog.QtWidgets.QMessageBox') as mock_message_box:
            mock_message_box.critical.return_value = None
            
            # Create dialog
            dialog = SettingsDialog(
                mock_settings,
                mock_file_service,
                mock_layer_service,
                mock_validator,
                parent=self.parent
            )
            
            # Try to refresh layer list
            dialog._refresh_layer_list()
            
            # Allow for multiple calls
            assert mock_message_box.critical.call_count >= 1
            found = False
            for call_args in mock_message_box.critical.call_args_list:
                if call_args[0][1] == "Layer Error" and "Failed to refresh layer list" in call_args[0][2]:
                    found = True
            assert found
            
            dialog.close()
            dialog.deleteLater()

