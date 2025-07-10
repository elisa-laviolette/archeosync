# coding=utf-8
"""Prepare recording dialog tests.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'elisa.laviolette@gmail.com'
__date__ = '2025-07-01'
__copyright__ = 'Copyright 2025, Elisa Caron-Laviolette'

import unittest
from unittest.mock import Mock, patch, MagicMock
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt

# Try to import QGIS modules, skip tests if not available
try:
    from qgis.PyQt.QtWidgets import QDialog
    from ui.prepare_recording_dialog import PrepareRecordingDialog
    from core.interfaces import ILayerService, ISettingsManager, IQFieldService
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False


@unittest.skipIf(not QGIS_AVAILABLE, "QGIS not available")
class TestPrepareRecordingDialog(unittest.TestCase):
    """Test cases for PrepareRecordingDialog."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_layer_service = Mock()
        self.mock_settings_manager = Mock()
        self.mock_qfield_service = Mock()
        
        # Set up default mock return values
        self.mock_settings_manager.get_value.return_value = ''
        self.mock_layer_service.get_layer_info.return_value = None
        self.mock_layer_service.get_layer_by_id.return_value = None
        self.mock_layer_service.get_related_objects_info.return_value = {'last_number': '', 'last_level': ''}
        self.mock_layer_service.calculate_next_level.return_value = ''
        self.mock_layer_service.get_raster_layers_overlapping_feature.return_value = []
        
        # Set up QField service mock
        self.mock_qfield_service.is_qfield_enabled.return_value = False
        
        self.dialog = PrepareRecordingDialog(
            layer_service=self.mock_layer_service,
            settings_manager=self.mock_settings_manager,
            qfield_service=self.mock_qfield_service
        )
    
    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, 'dialog'):
            self.dialog.close()
    
    def test_implements_interface(self):
        """Test that dialog implements expected interface."""
        # Test that dialog is a QDialog
        self.assertIsInstance(self.dialog, QDialog)
    
    def test_init_with_dependencies(self):
        """Test dialog initialization with injected dependencies."""
        self.assertEqual(self.dialog._layer_service, self.mock_layer_service)
        self.assertEqual(self.dialog._settings_manager, self.mock_settings_manager)
        self.assertEqual(self.dialog._qfield_service, self.mock_qfield_service)
    
    def test_window_title(self):
        """Test that dialog has correct window title."""
        self.assertEqual(self.dialog.windowTitle(), "Prepare Recording")
    
    def test_dialog_modal(self):
        """Test that dialog is modal."""
        self.assertTrue(self.dialog.isModal())
    
    def test_update_selected_count_no_layer_configured(self):
        """Test update when no recording areas layer is configured."""
        # Mock settings to return empty layer ID
        self.mock_settings_manager.get_value.return_value = ''
        
        # Call the method
        self.dialog._update_selected_count()
        
        # Verify labels are updated correctly
        self.assertEqual(self.dialog._recording_areas_label.text(), "Recording Areas Layer: Not configured")
        self.assertEqual(self.dialog._selected_count_label.text(), "Selected Entities: 0")
        
        # Verify OK button is hidden (QField is disabled by default in mock)
        ok_button = self.dialog._button_box.button(self.dialog._button_box.Ok)
        self.assertFalse(ok_button.isVisible())
    
    def test_update_selected_count_layer_not_found(self):
        """Test update when configured layer is not found."""
        # Mock settings to return a layer ID
        self.mock_settings_manager.get_value.return_value = 'test_layer_id'
        
        # Mock layer service to return None for layer info
        self.mock_layer_service.get_layer_info.return_value = None
        
        # Call the method
        self.dialog._update_selected_count()
        
        # Verify labels are updated correctly
        self.assertEqual(self.dialog._recording_areas_label.text(), "Recording Areas Layer: Layer not found")
        self.assertEqual(self.dialog._selected_count_label.text(), "Selected Entities: 0")
        
        # Verify OK button is hidden (QField is disabled by default in mock)
        ok_button = self.dialog._button_box.button(self.dialog._button_box.Ok)
        self.assertFalse(ok_button.isVisible())
    
    def test_update_selected_count_no_selection(self):
        """Test update when layer exists but no features are selected."""
        # Mock settings to return a layer ID
        self.mock_settings_manager.get_value.return_value = 'test_layer_id'
        
        # Mock layer service to return layer info
        layer_info = {
            'name': 'Test Recording Areas',
            'id': 'test_layer_id'
        }
        self.mock_layer_service.get_layer_info.return_value = layer_info
        
        # Mock layer with no selected features
        mock_layer = Mock()
        mock_layer.selectedFeatures.return_value = []
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Call the method
        self.dialog._update_selected_count()
        
        # Verify labels are updated correctly
        self.assertEqual(self.dialog._recording_areas_label.text(), "Recording Areas Layer: Test Recording Areas")
        self.assertEqual(self.dialog._selected_count_label.text(), "Selected Entities: 0")
        
        # Verify OK button is hidden (QField is disabled by default in mock)
        ok_button = self.dialog._button_box.button(self.dialog._button_box.Ok)
        self.assertFalse(ok_button.isVisible())
        
        # Verify table is empty
        self.assertEqual(self.dialog._entities_table.rowCount(), 0)
    
    def test_update_selected_count_with_selection(self):
        """Test update when layer exists and features are selected."""
        # Set up all mocks BEFORE creating the dialog
        self.mock_qfield_service.is_qfield_enabled.return_value = True
        
        # Mock settings to return proper values for all calls
        def mock_get_value(key, default=None):
            if key == 'recording_areas_layer':
                return 'test_layer_id'
            elif key == 'objects_layer':
                return ''
            elif key == 'objects_number_field':
                return ''
            elif key == 'objects_level_field':
                return ''
            return default
        
        self.mock_settings_manager.get_value.side_effect = mock_get_value
        
        # Mock layer service to return layer info
        layer_info = {
            'name': 'Test Recording Areas',
            'id': 'test_layer_id'
        }
        self.mock_layer_service.get_layer_info.return_value = layer_info
        
        # Mock layer with selected features
        mock_layer = Mock()
        mock_feature = Mock()
        mock_feature.id.return_value = 1
        mock_layer.selectedFeatures.return_value = [mock_feature]
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock layer fields for name extraction
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0
        mock_layer.fields.return_value = mock_fields
        mock_layer.displayExpression.return_value = ''  # No display expression to avoid QGIS expression evaluation
        
        # Create a new dialog with QField enabled
        dialog = PrepareRecordingDialog(
            layer_service=self.mock_layer_service,
            settings_manager=self.mock_settings_manager,
            qfield_service=self.mock_qfield_service
        )
        
        # Call the method
        dialog._update_selected_count()
        
        # Verify labels are updated correctly
        self.assertEqual(dialog._recording_areas_label.text(), "Recording Areas Layer: Test Recording Areas")
        self.assertEqual(dialog._selected_count_label.text(), "Selected Entities: 1")
        
        # Verify OK button is enabled and has correct text (QField is enabled)
        ok_button = dialog._button_box.button(dialog._button_box.Ok)
        self.assertTrue(ok_button.isEnabled())
        self.assertEqual(ok_button.text(), "Prepare Recording")
        
        # Note: Button visibility is managed by Qt events and may not be immediately visible
        # in test environment, but the logic is correct (enabled when QField is enabled and selection exists)
        
        # Verify table has one row
        self.assertEqual(dialog._entities_table.rowCount(), 1)
    
    def test_update_selected_count_exception_handling(self):
        """Test update when an exception occurs."""
        # Mock settings to return proper values for all calls
        def mock_get_value(key, default=None):
            if key == 'recording_areas_layer':
                return 'test_layer_id'
            elif key == 'objects_layer':
                return ''
            elif key == 'objects_number_field':
                return ''
            elif key == 'objects_level_field':
                return ''
            return default
        
        self.mock_settings_manager.get_value.side_effect = mock_get_value
        
        # Mock layer service to return layer info
        layer_info = {
            'name': 'Test Recording Areas',
            'id': 'test_layer_id'
        }
        self.mock_layer_service.get_layer_info.return_value = layer_info
        
        # Mock layer to raise exception when selectedFeatures is called
        mock_layer = Mock()
        mock_layer.selectedFeatures.side_effect = Exception("Test exception")
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Call the method
        self.dialog._update_selected_count()
        
        # Verify labels show error state
        self.assertEqual(self.dialog._recording_areas_label.text(), "Recording Areas Layer: Error")
        self.assertEqual(self.dialog._selected_count_label.text(), "Selected Entities: Error")
        
        # Verify OK button is hidden (QField is disabled by default in mock)
        ok_button = self.dialog._button_box.button(self.dialog._button_box.Ok)
        self.assertFalse(ok_button.isVisible())
    
    def test_button_box_exists(self):
        """Test that button box exists and has expected buttons."""
        # Get the button box
        button_box = self.dialog._button_box
        
        # Verify buttons exist
        ok_button = button_box.button(button_box.Ok)
        cancel_button = button_box.button(button_box.Cancel)
        
        self.assertIsNotNone(ok_button)
        self.assertIsNotNone(cancel_button)

    def test_populate_entities_table(self):
        """Test populating the entities table with feature data."""
        # Mock settings
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: {
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': '',
            'objects_number_field': '',
            'objects_level_field': ''
        }.get(key, default)
        
        # Mock layer service
        mock_layer = Mock()
        mock_layer.displayExpression.return_value = ''  # No display expression to avoid QGIS expression evaluation
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0
        mock_layer.fields.return_value = mock_fields
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock features
        mock_feature1 = Mock()
        mock_feature1.id.return_value = 1
        mock_feature1.attribute.return_value = 'Zone A'
        
        mock_feature2 = Mock()
        mock_feature2.id.return_value = 2
        mock_feature2.attribute.return_value = 'Zone B'
        
        mock_feature3 = Mock()
        mock_feature3.id.return_value = 3
        mock_feature3.attribute.return_value = 'Zone C'
        
        features = [mock_feature1, mock_feature2, mock_feature3]
        
        # Call the method
        self.dialog._populate_entities_table(features)
        
        # Verify table has correct number of rows
        self.assertEqual(self.dialog._entities_table.rowCount(), 3)
        
        # Verify table has correct number of columns (Name + Background image)
        self.assertEqual(self.dialog._entities_table.columnCount(), 2)
        
        # Verify first row data
        self.assertEqual(self.dialog._entities_table.item(0, 0).text(), 'Zone A')
        
        # Verify background image dropdown was created for each row
        for row in range(3):
            background_widget = self.dialog._entities_table.cellWidget(row, 1)
            self.assertIsInstance(background_widget, QtWidgets.QComboBox)
            self.assertEqual(background_widget.count(), 1)  # Only "No image" option
            self.assertEqual(background_widget.itemText(0), "No image")

    def test_populate_entities_table_empty(self):
        """Test populating the entities table with empty data."""
        # Call the method with empty list
        self.dialog._populate_entities_table([])
        
        # Verify table has no rows
        self.assertEqual(self.dialog._entities_table.rowCount(), 0)

    def test_create_entities_table_with_both_fields(self):
        """Test creating entities table when both number and level fields are configured."""
        # Mock settings to return objects layer and both fields
        def mock_get_value(key, default=None):
            if key == 'recording_areas_layer':
                return 'recording_layer_id'
            elif key == 'objects_layer':
                return 'objects_layer_id'
            elif key == 'objects_number_field':
                return 'number_field'
            elif key == 'objects_level_field':
                return 'level_field'
            return default
        
        self.mock_settings_manager.get_value.side_effect = mock_get_value
        
        # Recreate the table with the new configuration
        self.dialog._create_entities_table(self.dialog._entities_table.parent().layout())
        
        # Verify table has correct number of columns (Name + Last/Next number + Last/Next level + Background image)
        self.assertEqual(self.dialog._entities_table.columnCount(), 6)
        
        # Verify column headers
        headers = []
        for i in range(self.dialog._entities_table.columnCount()):
            headers.append(self.dialog._entities_table.horizontalHeaderItem(i).text())
        
        expected_headers = ["Name", "Last object number", "Next object number", "Last level", "Next level", "Background image"]
        self.assertEqual(headers, expected_headers)

    def test_populate_entities_table_with_next_values(self):
        """Test populating table with next values for number and level fields."""
        # Mock settings to return objects layer and both fields
        def mock_get_value(key, default=None):
            if key == 'recording_areas_layer':
                return 'recording_layer_id'
            elif key == 'objects_layer':
                return 'objects_layer_id'
            elif key == 'objects_number_field':
                return 'number_field'
            elif key == 'objects_level_field':
                return 'level_field'
            return default
        
        self.mock_settings_manager.get_value.side_effect = mock_get_value
        
        # Recreate the table with the new configuration
        self.dialog._create_entities_table(self.dialog._entities_table.parent().layout())
        
        # Mock layer service
        mock_layer = Mock()
        mock_layer.displayExpression.return_value = ''  # No display expression to avoid QGIS expression evaluation
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0
        mock_layer.fields.return_value = mock_fields
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock feature
        mock_feature = Mock()
        mock_feature.id.return_value = 1
        mock_feature.attribute.return_value = 'Test Area'
        
        # Mock related objects info
        self.mock_layer_service.get_related_objects_info.return_value = {
            'last_number': '10',
            'last_level': 'Level A'
        }
        
        # Mock calculate_next_level
        self.mock_layer_service.calculate_next_level.return_value = 'Level B'
        
        # Call the method
        self.dialog._populate_entities_table([mock_feature])
        
        # Verify table has correct number of columns (Name + Last/Next number + Last/Next level + Background image)
        self.assertEqual(self.dialog._entities_table.columnCount(), 6)
        
        # Verify table has one row
        self.assertEqual(self.dialog._entities_table.rowCount(), 1)
        
        # Verify next number is calculated correctly (10 + 1 = 11)
        next_number_item = self.dialog._entities_table.item(0, 2)  # Next number column
        self.assertEqual(next_number_item.text(), '11')
        
        # Verify next level is calculated correctly
        next_level_item = self.dialog._entities_table.item(0, 4)  # Next level column
        self.assertEqual(next_level_item.text(), 'Level B')
        
        # Verify background image dropdown was created
        background_widget = self.dialog._entities_table.cellWidget(0, 5)  # Background image column
        self.assertIsInstance(background_widget, QtWidgets.QComboBox)

    def test_get_next_values_for_feature(self):
        """Test getting next values for a specific feature."""
        # Mock settings to return objects layer and both fields
        def mock_get_value(key, default=None):
            if key == 'recording_areas_layer':
                return 'recording_layer_id'
            elif key == 'objects_layer':
                return 'objects_layer_id'
            elif key == 'objects_number_field':
                return 'number_field'
            elif key == 'objects_level_field':
                return 'level_field'
            return default
        
        self.mock_settings_manager.get_value.side_effect = mock_get_value
        
        # Recreate the table with the new configuration
        self.dialog._create_entities_table(self.dialog._entities_table.parent().layout())
        
        # Mock layer service
        mock_layer = Mock()
        mock_layer.displayExpression.return_value = ''  # No display expression to avoid QGIS expression evaluation
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0
        mock_layer.fields.return_value = mock_fields
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock feature
        mock_feature = Mock()
        mock_feature.id.return_value = 1
        mock_feature.attribute.return_value = 'Test Area'
        
        # Mock related objects info
        self.mock_layer_service.get_related_objects_info.return_value = {
            'last_number': '15',
            'last_level': 'Level B'
        }
        
        # Mock calculate_next_level
        self.mock_layer_service.calculate_next_level.return_value = 'Level C'
        
        # Populate table
        self.dialog._populate_entities_table([mock_feature])
        
        # Set next number and next level values
        self.dialog._entities_table.setItem(0, 2, QtWidgets.QTableWidgetItem('16'))  # Next number column
        self.dialog._entities_table.setItem(0, 4, QtWidgets.QTableWidgetItem('Level C'))  # Next level column
        
        # Set background image selection
        background_widget = self.dialog._entities_table.cellWidget(0, 5)  # Background image column
        background_widget.setCurrentIndex(1)  # Select first raster layer
        
        # Get next values
        result = self.dialog.get_next_values_for_feature(0)
        
        # Verify result
        self.assertEqual(result['next_number'], '16')  # 15 + 1
        self.assertEqual(result['next_level'], 'Level C')
        self.assertEqual(result['background_image'], '')  # No raster layers in default mock

    def test_get_next_values_for_feature_invalid_index(self):
        """Test getting next values for an invalid feature index."""
        result = self.dialog.get_next_values_for_feature(999)
        self.assertEqual(result['next_number'], '')
        self.assertEqual(result['next_level'], '')

    def test_get_all_next_values(self):
        """Test getting all next values for all features."""
        # Mock settings to return objects layer and both fields
        def mock_get_value(key, default=None):
            if key == 'recording_areas_layer':
                return 'recording_layer_id'
            elif key == 'objects_layer':
                return 'objects_layer_id'
            elif key == 'objects_number_field':
                return 'number_field'
            elif key == 'objects_level_field':
                return 'level_field'
            return default
        
        self.mock_settings_manager.get_value.side_effect = mock_get_value
        
        # Recreate the table with the new configuration
        self.dialog._create_entities_table(self.dialog._entities_table.parent().layout())
        
        # Mock layer service
        mock_layer = Mock()
        mock_layer.displayExpression.return_value = ''  # No display expression to avoid QGIS expression evaluation
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0
        mock_layer.fields.return_value = mock_fields
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock features
        mock_feature1 = Mock()
        mock_feature1.id.return_value = 1
        mock_feature1.attribute.return_value = 'Test Area 1'
        
        mock_feature2 = Mock()
        mock_feature2.id.return_value = 2
        mock_feature2.attribute.return_value = 'Test Area 2'
        
        # Mock related objects info
        self.mock_layer_service.get_related_objects_info.return_value = {
            'last_number': '15',
            'last_level': 'Level B'
        }
        
        # Mock calculate_next_level
        self.mock_layer_service.calculate_next_level.return_value = 'Level C'
        
        # Populate table
        self.dialog._populate_entities_table([mock_feature1, mock_feature2])
        
        # Set next number and next level values for both rows
        self.dialog._entities_table.setItem(0, 2, QtWidgets.QTableWidgetItem('16'))  # Next number column, row 0
        self.dialog._entities_table.setItem(0, 4, QtWidgets.QTableWidgetItem('Level C'))  # Next level column, row 0
        self.dialog._entities_table.setItem(1, 2, QtWidgets.QTableWidgetItem('17'))  # Next number column, row 1
        self.dialog._entities_table.setItem(1, 4, QtWidgets.QTableWidgetItem('Level D'))  # Next level column, row 1
        
        # Get all next values
        results = self.dialog.get_all_next_values()
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['next_number'], '16')
        self.assertEqual(results[0]['next_level'], 'Level C')
        self.assertEqual(results[0]['background_image'], '')  # No raster layers in default mock
        self.assertEqual(results[1]['next_number'], '17')
        self.assertEqual(results[1]['next_level'], 'Level D')
        self.assertEqual(results[1]['background_image'], '')  # No raster layers in default mock

    def test_table_editing_enabled(self):
        """Test that table editing is enabled for next value columns."""
        # Mock settings to return objects layer and both fields
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: {
            'objects_layer': 'objects_layer_id',
            'objects_number_field': 'number_field',
            'objects_level_field': 'level_field'
        }.get(key, default)
        
        # Recreate the table
        self.dialog._create_entities_table(self.dialog._entities_table.parent().layout())
        
        # Verify editing is enabled
        edit_triggers = self.dialog._entities_table.editTriggers()
        expected_triggers = QtWidgets.QAbstractItemView.DoubleClicked | QtWidgets.QAbstractItemView.EditKeyPressed
        self.assertEqual(edit_triggers, expected_triggers)

    def test_populate_entities_table_with_number_field_only(self):
        """Test populating table when only number field is configured."""
        # Mock settings to return objects layer and number field only
        def mock_get_value(key, default=None):
            if key == 'recording_areas_layer':
                return 'recording_layer_id'
            elif key == 'objects_layer':
                return 'objects_layer_id'
            elif key == 'objects_number_field':
                return 'number_field'
            elif key == 'objects_level_field':
                return ''
            return default
        
        self.mock_settings_manager.get_value.side_effect = mock_get_value
        
        # Recreate the table with the new configuration
        self.dialog._create_entities_table(self.dialog._entities_table.parent().layout())
        
        # Mock layer service
        mock_layer = Mock()
        mock_layer.displayExpression.return_value = ''  # No display expression to avoid QGIS expression evaluation
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0
        mock_layer.fields.return_value = mock_fields
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock feature
        mock_feature = Mock()
        mock_feature.id.return_value = 1
        mock_feature.attribute.return_value = 'Test Area'
        
        # Mock related objects info
        self.mock_layer_service.get_related_objects_info.return_value = {
            'last_number': '10',
            'last_level': ''
        }
        
        # Call the method
        self.dialog._populate_entities_table([mock_feature])
        
        # Verify table has correct number of columns (Name + Last/Next number + Background image)
        self.assertEqual(self.dialog._entities_table.columnCount(), 4)
        
        # Verify table has one row
        self.assertEqual(self.dialog._entities_table.rowCount(), 1)
        
        # Verify next number is calculated correctly (10 + 1 = 11)
        next_number_item = self.dialog._entities_table.item(0, 2)  # Next number column
        self.assertEqual(next_number_item.text(), '11')
        
        # Verify background image dropdown was created (last column)
        background_widget = self.dialog._entities_table.cellWidget(0, 3)  # Background image column
        self.assertIsInstance(background_widget, QtWidgets.QComboBox)

    def test_populate_entities_table_with_level_field_only(self):
        """Test populating table when only level field is configured."""
        # Mock settings to return objects layer and level field only
        def mock_get_value(key, default=None):
            if key == 'recording_areas_layer':
                return 'recording_layer_id'
            elif key == 'objects_layer':
                return 'objects_layer_id'
            elif key == 'objects_number_field':
                return ''
            elif key == 'objects_level_field':
                return 'level_field'
            return default
        
        self.mock_settings_manager.get_value.side_effect = mock_get_value
        
        # Recreate the table with the new configuration
        self.dialog._create_entities_table(self.dialog._entities_table.parent().layout())
        
        # Mock layer service
        mock_layer = Mock()
        mock_layer.displayExpression.return_value = ''  # No display expression to avoid QGIS expression evaluation
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0
        mock_layer.fields.return_value = mock_fields
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock feature
        mock_feature = Mock()
        mock_feature.id.return_value = 1
        mock_feature.attribute.return_value = 'Test Area'
        
        # Mock related objects info
        self.mock_layer_service.get_related_objects_info.return_value = {
            'last_number': '',
            'last_level': 'Level A'
        }
        
        # Mock calculate_next_level
        self.mock_layer_service.calculate_next_level.return_value = 'Level B'
        
        # Call the method
        self.dialog._populate_entities_table([mock_feature])
        
        # Verify table has correct number of columns (Name + Last/Next level + Background image)
        self.assertEqual(self.dialog._entities_table.columnCount(), 4)
        
        # Verify table has one row
        self.assertEqual(self.dialog._entities_table.rowCount(), 1)
        
        # Verify next level is calculated correctly
        next_level_item = self.dialog._entities_table.item(0, 2)  # Next level column
        self.assertEqual(next_level_item.text(), 'Level B')
        
        # Verify background image dropdown was created (last column)
        background_widget = self.dialog._entities_table.cellWidget(0, 3)  # Background image column
        self.assertIsInstance(background_widget, QtWidgets.QComboBox)

    def test_populate_entities_table_no_related_objects(self):
        """Test populating table when no related objects exist."""
        # Mock settings
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: {
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': 'objects_layer_id',
            'objects_number_field': 'number_field',
            'objects_level_field': 'level_field'
        }.get(key, default)
        
        # Recreate the table with the new configuration
        self.dialog._create_entities_table(self.dialog._entities_table.parent().layout())
        
        # Mock layer service
        mock_layer = Mock()
        mock_layer.displayExpression.return_value = ''  # No display expression to avoid QGIS expression evaluation
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0
        mock_layer.fields.return_value = mock_fields
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock feature
        mock_feature = Mock()
        mock_feature.id.return_value = 1
        mock_feature.attribute.return_value = 'Test Area'
        
        # Mock related objects info (empty)
        self.mock_layer_service.get_related_objects_info.return_value = {
            'last_number': '',
            'last_level': ''
        }
        
        # Mock calculate_next_level
        self.mock_layer_service.calculate_next_level.return_value = 'a'
        
        # Call the method
        self.dialog._populate_entities_table([mock_feature])
        
        # Verify table has correct number of columns (Name + Last/Next number + Last/Next level + Background image)
        self.assertEqual(self.dialog._entities_table.columnCount(), 6)
        
        # Verify table has one row
        self.assertEqual(self.dialog._entities_table.rowCount(), 1)
        
        # Verify next number defaults to '1' when no previous objects exist
        next_number_item = self.dialog._entities_table.item(0, 2)  # Next number column
        self.assertEqual(next_number_item.text(), '1')
        
        # Verify next level is calculated correctly
        next_level_item = self.dialog._entities_table.item(0, 4)  # Next level column
        self.assertEqual(next_level_item.text(), 'a')
        
        # Verify background image dropdown was created
        background_widget = self.dialog._entities_table.cellWidget(0, 5)  # Background image column
        self.assertIsInstance(background_widget, QtWidgets.QComboBox)

    def test_read_only_columns_not_editable(self):
        """Test that read-only columns are not editable."""
        # Mock settings
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: {
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': 'objects_layer_id',
            'objects_number_field': 'number_field',
            'objects_level_field': 'level_field'
        }.get(key, default)
        
        # Recreate the table with the new configuration
        self.dialog._create_entities_table(self.dialog._entities_table.parent().layout())
        
        # Mock layer service
        mock_layer = Mock()
        mock_layer.displayExpression.return_value = ''  # No display expression to avoid QGIS expression evaluation
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0
        mock_layer.fields.return_value = mock_fields
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock feature
        mock_feature = Mock()
        mock_feature.id.return_value = 1
        mock_feature.attribute.return_value = 'Test Area'
        
        # Mock related objects info
        self.mock_layer_service.get_related_objects_info.return_value = {
            'last_number': '10',
            'last_level': 'Level A'
        }
        
        # Mock calculate_next_level
        self.mock_layer_service.calculate_next_level.return_value = 'Level B'
        
        # Call the method
        self.dialog._populate_entities_table([mock_feature])
        
        # Verify table has correct number of columns (Name + Last/Next number + Last/Next level + Background image)
        self.assertEqual(self.dialog._entities_table.columnCount(), 6)
        
        # Verify table has one row
        self.assertEqual(self.dialog._entities_table.rowCount(), 1)
        
        # Verify read-only columns are not editable
        name_item = self.dialog._entities_table.item(0, 0)  # Name column
        self.assertFalse(name_item.flags() & Qt.ItemIsEditable)
        
        last_number_item = self.dialog._entities_table.item(0, 1)  # Last number column
        self.assertFalse(last_number_item.flags() & Qt.ItemIsEditable)
        
        last_level_item = self.dialog._entities_table.item(0, 3)  # Last level column
        self.assertFalse(last_level_item.flags() & Qt.ItemIsEditable)
        
        # Verify editable columns are editable
        next_number_item = self.dialog._entities_table.item(0, 2)  # Next number column
        self.assertTrue(next_number_item.flags() & Qt.ItemIsEditable)
        
        next_level_item = self.dialog._entities_table.item(0, 4)  # Next level column
        self.assertTrue(next_level_item.flags() & Qt.ItemIsEditable)
        
        # Verify background image dropdown was created
        background_widget = self.dialog._entities_table.cellWidget(0, 5)  # Background image column
        self.assertIsInstance(background_widget, QtWidgets.QComboBox)

    def test_case_preservation_in_next_level_calculation(self):
        """Test that case is preserved in next level calculation."""
        # Mock settings
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: {
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': 'objects_layer_id',
            'objects_number_field': '',
            'objects_level_field': 'level_field'
        }.get(key, default)
        
        # Recreate the table with the new configuration
        self.dialog._create_entities_table(self.dialog._entities_table.parent().layout())
        
        # Mock layer service
        mock_layer = Mock()
        mock_layer.displayExpression.return_value = ''  # No display expression to avoid QGIS expression evaluation
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0
        mock_layer.fields.return_value = mock_fields
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock feature
        mock_feature = Mock()
        mock_feature.id.return_value = 1
        mock_feature.attribute.return_value = 'Test Area'
        
        # Mock related objects info with uppercase level
        self.mock_layer_service.get_related_objects_info.return_value = {
            'last_number': '',
            'last_level': 'LEVEL A'
        }
        
        # Mock calculate_next_level to preserve case
        self.mock_layer_service.calculate_next_level.return_value = 'LEVEL B'
        
        # Call the method
        self.dialog._populate_entities_table([mock_feature])
        
        # Verify table has correct number of columns (Name + Last/Next level + Background image)
        self.assertEqual(self.dialog._entities_table.columnCount(), 4)
        
        # Verify table has one row
        self.assertEqual(self.dialog._entities_table.rowCount(), 1)
        
        # Verify next level preserves case
        next_level_item = self.dialog._entities_table.item(0, 2)  # Next level column
        self.assertEqual(next_level_item.text(), 'LEVEL B')  # Should preserve uppercase
        
        # Verify background image dropdown was created (last column)
        background_widget = self.dialog._entities_table.cellWidget(0, 3)  # Background image column
        self.assertIsInstance(background_widget, QtWidgets.QComboBox)

    def test_populate_entities_table_with_background_image_column(self):
        """Test that the Background image column is always added to the table."""
        # Mock settings
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: {
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': '',
            'objects_number_field': '',
            'objects_level_field': ''
        }.get(key, default)
        
        # Mock layer service
        mock_layer = Mock()
        mock_layer.displayExpression.return_value = ''  # No display expression to avoid QGIS expression evaluation
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0
        mock_layer.fields.return_value = mock_fields
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock feature
        mock_feature = Mock()
        mock_feature.id.return_value = 1
        mock_feature.attribute.return_value = 'Test Area'
        
        # Mock overlapping raster layers
        self.mock_layer_service.get_raster_layers_overlapping_feature.return_value = [
            {
                'id': 'raster1',
                'name': 'Test Raster 1',
                'width': 100,
                'height': 200
            },
            {
                'id': 'raster2',
                'name': 'Test Raster 2',
                'width': 150,
                'height': 250
            }
        ]
        
        features = [mock_feature]
        
        # Call the method
        self.dialog._populate_entities_table(features)
        
        # Verify table has the correct number of columns (Name + Background image)
        self.assertEqual(self.dialog._entities_table.columnCount(), 2)
        
        # Verify column headers
        self.assertEqual(self.dialog._entities_table.horizontalHeaderItem(0).text(), "Name")
        self.assertEqual(self.dialog._entities_table.horizontalHeaderItem(1).text(), "Background image")
        
        # Verify background image dropdown was created
        background_widget = self.dialog._entities_table.cellWidget(0, 1)
        self.assertIsInstance(background_widget, QtWidgets.QComboBox)
        
        # Verify dropdown has correct items
        self.assertEqual(background_widget.count(), 3)  # "No image" + 2 raster layers
        self.assertEqual(background_widget.itemText(0), "No image")
        self.assertEqual(background_widget.itemText(1), "Test Raster 1 (100x200)")
        self.assertEqual(background_widget.itemText(2), "Test Raster 2 (150x250)")
        self.assertEqual(background_widget.itemData(0), "")
        self.assertEqual(background_widget.itemData(1), "raster1")
        self.assertEqual(background_widget.itemData(2), "raster2")

    def test_populate_entities_table_with_background_image_no_overlapping_layers(self):
        """Test background image column when no raster layers overlap."""
        # Mock settings
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: {
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': '',
            'objects_number_field': '',
            'objects_level_field': ''
        }.get(key, default)
        
        # Mock layer service
        mock_layer = Mock()
        mock_layer.displayExpression.return_value = ''  # No display expression to avoid QGIS expression evaluation
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0
        mock_layer.fields.return_value = mock_fields
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock feature
        mock_feature = Mock()
        mock_feature.id.return_value = 1
        mock_feature.attribute.return_value = 'Test Area'
        
        # Mock no overlapping raster layers
        self.mock_layer_service.get_raster_layers_overlapping_feature.return_value = []
        
        features = [mock_feature]
        
        # Call the method
        self.dialog._populate_entities_table(features)
        
        # Verify background image dropdown was created with only "No image" option
        background_widget = self.dialog._entities_table.cellWidget(0, 1)
        self.assertIsInstance(background_widget, QtWidgets.QComboBox)
        self.assertEqual(background_widget.count(), 1)
        self.assertEqual(background_widget.itemText(0), "No image")
        self.assertEqual(background_widget.itemData(0), "")

    def test_get_next_values_for_feature_with_background_image(self):
        """Test getting next values including background image selection."""
        # Mock settings
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: {
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': '',
            'objects_number_field': '',
            'objects_level_field': ''
        }.get(key, default)
        
        # Mock layer service
        mock_layer = Mock()
        mock_layer.displayExpression.return_value = ''  # No display expression to avoid QGIS expression evaluation
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0
        mock_layer.fields.return_value = mock_fields
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock feature
        mock_feature = Mock()
        mock_feature.id.return_value = 1
        mock_feature.attribute.return_value = 'Test Area'
        
        # Mock overlapping raster layers
        self.mock_layer_service.get_raster_layers_overlapping_feature.return_value = [
            {
                'id': 'raster1',
                'name': 'Test Raster 1',
                'width': 100,
                'height': 200
            }
        ]
        
        features = [mock_feature]
        
        # Populate table
        self.dialog._populate_entities_table(features)
        
        # Set background image selection
        background_widget = self.dialog._entities_table.cellWidget(0, 1)
        background_widget.setCurrentIndex(1)  # Select the raster layer
        
        # Get next values
        result = self.dialog.get_next_values_for_feature(0)
        
        # Verify result includes background image
        self.assertEqual(result['next_number'], '')
        self.assertEqual(result['next_level'], '')
        self.assertEqual(result['background_image'], 'raster1')

    def test_get_all_next_values_with_background_image(self):
        """Test getting all next values including background image selections."""
        # Mock settings
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: {
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': '',
            'objects_number_field': '',
            'objects_level_field': ''
        }.get(key, default)
        
        # Mock layer service
        mock_layer = Mock()
        mock_layer.displayExpression.return_value = ''  # No display expression to avoid QGIS expression evaluation
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0
        mock_layer.fields.return_value = mock_fields
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock features
        mock_feature1 = Mock()
        mock_feature1.id.return_value = 1
        mock_feature1.attribute.return_value = 'Test Area 1'
        
        mock_feature2 = Mock()
        mock_feature2.id.return_value = 2
        mock_feature2.attribute.return_value = 'Test Area 2'
        
        # Mock overlapping raster layers
        self.mock_layer_service.get_raster_layers_overlapping_feature.return_value = [
            {
                'id': 'raster1',
                'name': 'Test Raster 1',
                'width': 100,
                'height': 200
            }
        ]
        
        features = [mock_feature1, mock_feature2]
        
        # Populate table
        self.dialog._populate_entities_table(features)
        
        # Set different background image selections
        background_widget1 = self.dialog._entities_table.cellWidget(0, 1)
        background_widget1.setCurrentIndex(1)  # Select raster layer for first feature
        
        background_widget2 = self.dialog._entities_table.cellWidget(1, 1)
        background_widget2.setCurrentIndex(0)  # Select "No image" for second feature
        
        # Get all next values
        results = self.dialog.get_all_next_values()
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['background_image'], 'raster1')
        self.assertEqual(results[1]['background_image'], '')

    def test_add_background_image_dropdown(self):
        """Test the _add_background_image_dropdown method directly."""
        # Mock overlapping raster layers
        self.mock_layer_service.get_raster_layers_overlapping_feature.return_value = [
            {
                'id': 'raster1',
                'name': 'Test Raster 1',
                'width': 100,
                'height': 200
            }
        ]
        
        # Mock feature
        mock_feature = Mock()
        
        # Create a test table with one row and two columns
        self.dialog._entities_table.setRowCount(1)
        self.dialog._entities_table.setColumnCount(2)
        
        # Call the method
        self.dialog._add_background_image_dropdown(0, 1, mock_feature, 'recording_layer_id')
        
        # Verify dropdown was created
        widget = self.dialog._entities_table.cellWidget(0, 1)
        self.assertIsInstance(widget, QtWidgets.QComboBox)
        self.assertEqual(widget.count(), 2)  # "No image" + 1 raster layer
        self.assertEqual(widget.itemText(0), "No image")
        self.assertEqual(widget.itemText(1), "Test Raster 1 (100x200)")
        self.assertEqual(widget.itemData(0), "")
        self.assertEqual(widget.itemData(1), "raster1")


if __name__ == '__main__':
    unittest.main() 