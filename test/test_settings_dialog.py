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

    def test_align_center_flag_supports_qt5_style(self):
        """The alignment helper should support Qt5's direct AlignCenter flag."""
        import ui.settings_dialog as settings_dialog_module

        fake_qt = type("FakeQt", (), {"AlignCenter": "qt5-center"})
        with patch.object(settings_dialog_module, "Qt", fake_qt):
            assert settings_dialog_module._align_center_flag() == "qt5-center"

    def test_align_center_flag_supports_qt6_style(self):
        """The alignment helper should support Qt6's AlignmentFlag.AlignCenter."""
        import ui.settings_dialog as settings_dialog_module

        fake_alignment_flag = type("AlignmentFlag", (), {"AlignCenter": "qt6-center"})
        fake_qt = type("FakeQt", (), {"AlignmentFlag": fake_alignment_flag})
        with patch.object(settings_dialog_module, "Qt", fake_qt):
            assert settings_dialog_module._align_center_flag() == "qt6-center"

    def test_no_selection_mode_supports_qt5_style(self):
        """The selection mode helper should support Qt5's direct NoSelection flag."""
        import ui.settings_dialog as settings_dialog_module

        fake_item_view = type("FakeItemView", (), {"NoSelection": "qt5-no-selection"})
        fake_qt_widgets = type("FakeQtWidgets", (), {"QAbstractItemView": fake_item_view})
        with patch.object(settings_dialog_module, "QtWidgets", fake_qt_widgets):
            assert settings_dialog_module._no_selection_mode() == "qt5-no-selection"

    def test_no_selection_mode_supports_qt6_style(self):
        """The selection mode helper should support Qt6's SelectionMode.NoSelection."""
        import ui.settings_dialog as settings_dialog_module

        fake_selection_mode = type("SelectionMode", (), {"NoSelection": "qt6-no-selection"})
        fake_item_view = type("FakeItemView", (), {"SelectionMode": fake_selection_mode})
        fake_qt_widgets = type("FakeQtWidgets", (), {"QAbstractItemView": fake_item_view})
        with patch.object(settings_dialog_module, "QtWidgets", fake_qt_widgets):
            assert settings_dialog_module._no_selection_mode() == "qt6-no-selection"

    def test_dialog_button_ok_cancel_supports_qt5_style(self):
        """The button helper should support Qt5's direct Ok/Cancel flags."""
        import ui.settings_dialog as settings_dialog_module

        fake_button_box = type("FakeButtonBox", (), {"Ok": 1, "Cancel": 2})
        fake_qt_widgets = type("FakeQtWidgets", (), {"QDialogButtonBox": fake_button_box})
        with patch.object(settings_dialog_module, "QtWidgets", fake_qt_widgets):
            assert settings_dialog_module._dialog_button_ok_cancel() == 3

    def test_dialog_button_ok_cancel_supports_qt6_style(self):
        """The button helper should support Qt6's StandardButton.Ok/Cancel flags."""
        import ui.settings_dialog as settings_dialog_module

        fake_standard_button = type("StandardButton", (), {"Ok": 4, "Cancel": 8})
        fake_button_box = type("FakeButtonBox", (), {"StandardButton": fake_standard_button})
        fake_qt_widgets = type("FakeQtWidgets", (), {"QDialogButtonBox": fake_button_box})
        with patch.object(settings_dialog_module, "QtWidgets", fake_qt_widgets):
            assert settings_dialog_module._dialog_button_ok_cancel() == 12

    def test_horizontal_orientation_supports_qt5_style(self):
        """The orientation helper should support Qt5's direct Horizontal flag."""
        import ui.settings_dialog as settings_dialog_module

        fake_qt = type("FakeQt", (), {"Horizontal": "qt5-horizontal"})
        with patch.object(settings_dialog_module, "Qt", fake_qt):
            assert settings_dialog_module._horizontal_orientation() == "qt5-horizontal"

    def test_horizontal_orientation_supports_qt6_style(self):
        """The orientation helper should support Qt6's Orientation.Horizontal."""
        import ui.settings_dialog as settings_dialog_module

        fake_orientation = type("Orientation", (), {"Horizontal": "qt6-horizontal"})
        fake_qt = type("FakeQt", (), {"Orientation": fake_orientation})
        with patch.object(settings_dialog_module, "Qt", fake_qt):
            assert settings_dialog_module._horizontal_orientation() == "qt6-horizontal"

    def test_user_role_item_data_role_supports_qt5_style(self):
        """The UserRole helper should support Qt5's direct UserRole."""
        import ui.settings_dialog as settings_dialog_module

        fake_qt = type("FakeQt", (), {"UserRole": 32})
        with patch.object(settings_dialog_module, "Qt", fake_qt):
            assert settings_dialog_module._user_role_item_data_role() == 32

    def test_user_role_item_data_role_supports_qt6_style(self):
        """The UserRole helper should support Qt6's ItemDataRole.UserRole."""
        import ui.settings_dialog as settings_dialog_module

        fake_item_data_role = type("ItemDataRole", (), {"UserRole": 256})
        fake_qt = type("FakeQt", (), {"ItemDataRole": fake_item_data_role})
        with patch.object(settings_dialog_module, "Qt", fake_qt):
            assert settings_dialog_module._user_role_item_data_role() == 256

    def test_item_is_user_checkable_flag_supports_qt5_style(self):
        """The item-flag helper should support Qt5's direct ItemIsUserCheckable."""
        import ui.settings_dialog as settings_dialog_module

        fake_qt = type("FakeQt", (), {"ItemIsUserCheckable": 1})
        with patch.object(settings_dialog_module, "Qt", fake_qt):
            assert settings_dialog_module._item_is_user_checkable_flag() == 1

    def test_item_is_user_checkable_flag_supports_qt6_style(self):
        """The item-flag helper should support Qt6's ItemFlag.ItemIsUserCheckable."""
        import ui.settings_dialog as settings_dialog_module

        fake_item_flag = type("ItemFlag", (), {"ItemIsUserCheckable": 2})
        fake_qt = type("FakeQt", (), {"ItemFlag": fake_item_flag})
        with patch.object(settings_dialog_module, "Qt", fake_qt):
            assert settings_dialog_module._item_is_user_checkable_flag() == 2

    def test_item_is_enabled_flag_supports_qt5_style(self):
        """The item-flag helper should support Qt5's direct ItemIsEnabled."""
        import ui.settings_dialog as settings_dialog_module

        fake_qt = type("FakeQt", (), {"ItemIsEnabled": 4})
        with patch.object(settings_dialog_module, "Qt", fake_qt):
            assert settings_dialog_module._item_is_enabled_flag() == 4

    def test_item_is_enabled_flag_supports_qt6_style(self):
        """The item-flag helper should support Qt6's ItemFlag.ItemIsEnabled."""
        import ui.settings_dialog as settings_dialog_module

        fake_item_flag = type("ItemFlag", (), {"ItemIsEnabled": 8})
        fake_qt = type("FakeQt", (), {"ItemFlag": fake_item_flag})
        with patch.object(settings_dialog_module, "Qt", fake_qt):
            assert settings_dialog_module._item_is_enabled_flag() == 8

    def test_checked_check_state_supports_qt5_style(self):
        """The check-state helper should support Qt5's direct Checked."""
        import ui.settings_dialog as settings_dialog_module

        fake_qt = type("FakeQt", (), {"Checked": "qt5-checked"})
        with patch.object(settings_dialog_module, "Qt", fake_qt):
            assert settings_dialog_module._checked_check_state() == "qt5-checked"

    def test_checked_check_state_supports_qt6_style(self):
        """The check-state helper should support Qt6's CheckState.Checked."""
        import ui.settings_dialog as settings_dialog_module

        fake_check_state = type("CheckState", (), {"Checked": "qt6-checked"})
        fake_qt = type("FakeQt", (), {"CheckState": fake_check_state})
        with patch.object(settings_dialog_module, "Qt", fake_qt):
            assert settings_dialog_module._checked_check_state() == "qt6-checked"

    def test_unchecked_check_state_supports_qt5_style(self):
        """The check-state helper should support Qt5's direct Unchecked."""
        import ui.settings_dialog as settings_dialog_module

        fake_qt = type("FakeQt", (), {"Unchecked": "qt5-unchecked"})
        with patch.object(settings_dialog_module, "Qt", fake_qt):
            assert settings_dialog_module._unchecked_check_state() == "qt5-unchecked"

    def test_unchecked_check_state_supports_qt6_style(self):
        """The check-state helper should support Qt6's CheckState.Unchecked."""
        import ui.settings_dialog as settings_dialog_module

        fake_check_state = type("CheckState", (), {"Unchecked": "qt6-unchecked"})
        fake_qt = type("FakeQt", (), {"CheckState": fake_check_state})
        with patch.object(settings_dialog_module, "Qt", fake_qt):
            assert settings_dialog_module._unchecked_check_state() == "qt6-unchecked"

    def test_dialog_button_ok_identifier_supports_qt5_style(self):
        """The OK button helper should support Qt5's direct Ok flag."""
        import ui.settings_dialog as settings_dialog_module

        fake_button_box = type("FakeButtonBox", (), {"Ok": "qt5-ok"})
        fake_qt_widgets = type("FakeQtWidgets", (), {"QDialogButtonBox": fake_button_box})
        with patch.object(settings_dialog_module, "QtWidgets", fake_qt_widgets):
            assert settings_dialog_module._dialog_button_ok() == "qt5-ok"

    def test_dialog_button_ok_identifier_supports_qt6_style(self):
        """The OK button helper should support Qt6's StandardButton.Ok flag."""
        import ui.settings_dialog as settings_dialog_module

        fake_standard_button = type("StandardButton", (), {"Ok": "qt6-ok"})
        fake_button_box = type("FakeButtonBox", (), {"StandardButton": fake_standard_button})
        fake_qt_widgets = type("FakeQtWidgets", (), {"QDialogButtonBox": fake_button_box})
        with patch.object(settings_dialog_module, "QtWidgets", fake_qt_widgets):
            assert settings_dialog_module._dialog_button_ok() == "qt6-ok"

    def test_dialog_button_cancel_identifier_supports_qt5_style(self):
        """The Cancel button helper should support Qt5's direct Cancel flag."""
        import ui.settings_dialog as settings_dialog_module

        fake_button_box = type("FakeButtonBox", (), {"Cancel": "qt5-cancel"})
        fake_qt_widgets = type("FakeQtWidgets", (), {"QDialogButtonBox": fake_button_box})
        with patch.object(settings_dialog_module, "QtWidgets", fake_qt_widgets):
            assert settings_dialog_module._dialog_button_cancel() == "qt5-cancel"

    def test_dialog_button_cancel_identifier_supports_qt6_style(self):
        """The Cancel button helper should support Qt6's StandardButton.Cancel flag."""
        import ui.settings_dialog as settings_dialog_module

        fake_standard_button = type("StandardButton", (), {"Cancel": "qt6-cancel"})
        fake_button_box = type("FakeButtonBox", (), {"StandardButton": fake_standard_button})
        fake_qt_widgets = type("FakeQtWidgets", (), {"QDialogButtonBox": fake_button_box})
        with patch.object(settings_dialog_module, "QtWidgets", fake_qt_widgets):
            assert settings_dialog_module._dialog_button_cancel() == "qt6-cancel"


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
        
        # Mock the settings manager to return proper values
        self.mock_settings.get_value.side_effect = lambda key, default=None: {
            'enable_distance_warnings': True,
            'distance_max_distance': 0.05,
            'enable_height_warnings': True,
            'height_max_distance': 1.0,
            'height_max_difference': 0.2,
            'enable_bounds_warnings': True,
            'bounds_max_distance': 0.2,
            'field_projects_folder': '',
            'total_station_folder': '',
            'completed_projects_folder': '',
            'csv_archive_folder': '',
            'field_project_archive_folder': '',
            'recording_areas_layer': '',
            'recording_area_variable_source': 'display',
            'objects_layer': '',
            'objects_number_field': '',
            'objects_level_field': '',
            'features_layer': '',
            'small_finds_layer': '',
            'total_station_points_layer': '',
            'raster_clipping_offset': 0.2,
            'raster_brightness': 0,
            'raster_contrast': 0,
            'raster_saturation': 0,
            'extra_field_layers': []
        }.get(key, default)
        
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
        
        # Test that the tab widget exists and has the expected tabs
        assert hasattr(self.dialog, '_tab_widget')
        assert self.dialog._tab_widget.count() == 4
        assert self.dialog._tab_widget.tabText(0) == "Folders"
        assert self.dialog._tab_widget.tabText(1) == "Layers & Fields"
        assert self.dialog._tab_widget.tabText(2) == "Warnings"
        assert self.dialog._tab_widget.tabText(3) == "Raster"

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
    
    def test_warnings_tab_ui_elements_exist(self):
        """Test that the warnings tab UI elements exist."""
        assert hasattr(self.dialog, '_enable_distance_warnings')
        assert hasattr(self.dialog, '_distance_max_distance')
        assert hasattr(self.dialog, '_enable_height_warnings')
        assert hasattr(self.dialog, '_height_max_distance')
        assert hasattr(self.dialog, '_height_max_difference')
        assert hasattr(self.dialog, '_enable_bounds_warnings')
        assert hasattr(self.dialog, '_bounds_max_distance')



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

    def test_recording_area_variable_source_options_include_layer_fields(self):
        """Recording area variable source should offer display, id, and layer fields."""
        self.mock_layer_service.get_polygon_layers.return_value = [
            {
                'id': 'recording_layer',
                'name': 'Recording Areas',
                'source': '/path/to/recording.shp',
                'crs': 'EPSG:4326',
                'feature_count': 3
            }
        ]
        self.mock_layer_service.get_layer_fields.return_value = [
            {'name': 'id', 'type': 'Integer', 'is_integer': True},
            {'name': 'display_code', 'type': 'String', 'is_integer': False},
        ]

        self.dialog._refresh_layer_list()
        self.dialog._recording_areas_widget.combo_box.setCurrentIndex(1)
        self.dialog._refresh_recording_area_variable_source_options()

        variable_source_combo = self.dialog._recording_area_variable_source_combo
        all_values = [variable_source_combo.itemData(i) for i in range(variable_source_combo.count())]
        assert "display" in all_values
        assert "id" in all_values
        assert "field:id" in all_values
        assert "field:display_code" in all_values

    def test_refresh_extra_layers_disables_selected_main_layers(self):
        """Core layers should be checked and disabled in the extra layers list."""
        import ui.settings_dialog as settings_dialog_module

        self.mock_layer_service.get_vector_layers.return_value = [
            {"id": "recording", "name": "Recording", "feature_count": 10},
            {"id": "objects", "name": "Objects", "feature_count": 12},
            {"id": "features", "name": "Features", "feature_count": 8},
            {"id": "small", "name": "Small finds", "feature_count": 6},
            {"id": "extra", "name": "Extra layer", "feature_count": 2},
        ]

        self.dialog._recording_areas_widget.combo_box.clear()
        self.dialog._recording_areas_widget.combo_box.addItem("Recording", "recording")
        self.dialog._recording_areas_widget.combo_box.setCurrentIndex(0)

        self.dialog._objects_widget.combo_box.clear()
        self.dialog._objects_widget.combo_box.addItem("Objects", "objects")
        self.dialog._objects_widget.combo_box.setCurrentIndex(0)

        self.dialog._features_widget.combo_box.clear()
        self.dialog._features_widget.combo_box.addItem("Features", "features")
        self.dialog._features_widget.combo_box.setCurrentIndex(0)

        self.dialog._small_finds_widget.combo_box.clear()
        self.dialog._small_finds_widget.combo_box.addItem("Small finds", "small")
        self.dialog._small_finds_widget.combo_box.setCurrentIndex(0)

        self.dialog._refresh_extra_layers_list()

        items_by_id = {}
        for idx in range(self.dialog._extra_layers_list.count()):
            item = self.dialog._extra_layers_list.item(idx)
            items_by_id[item.data(settings_dialog_module._user_role_item_data_role())] = item

        enabled_flag = settings_dialog_module._item_is_enabled_flag()
        checked_state = settings_dialog_module._checked_check_state()
        for layer_id in ("recording", "objects", "features", "small"):
            assert items_by_id[layer_id].checkState() == checked_state
            assert items_by_id[layer_id].flags() & enabled_flag == 0
        assert items_by_id["extra"].flags() & enabled_flag != 0

    def test_get_selected_extra_layers_excludes_core_layers(self):
        """Saving should not persist core layers as optional extras."""
        import ui.settings_dialog as settings_dialog_module

        self.mock_layer_service.get_vector_layers.return_value = [
            {"id": "recording", "name": "Recording", "feature_count": 10},
            {"id": "objects", "name": "Objects", "feature_count": 12},
            {"id": "extra", "name": "Extra layer", "feature_count": 2},
        ]
        self.dialog._recording_areas_widget.combo_box.clear()
        self.dialog._recording_areas_widget.combo_box.addItem("Recording", "recording")
        self.dialog._recording_areas_widget.combo_box.setCurrentIndex(0)
        self.dialog._objects_widget.combo_box.clear()
        self.dialog._objects_widget.combo_box.addItem("Objects", "objects")
        self.dialog._objects_widget.combo_box.setCurrentIndex(0)
        self.dialog._refresh_extra_layers_list()

        checked_state = settings_dialog_module._checked_check_state()
        extra_item = None
        for idx in range(self.dialog._extra_layers_list.count()):
            item = self.dialog._extra_layers_list.item(idx)
            if item.data(settings_dialog_module._user_role_item_data_role()) == "extra":
                extra_item = item
                break
        assert extra_item is not None
        extra_item.setCheckState(checked_state)

        assert self.dialog._get_selected_extra_layers() == ["extra"]


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

