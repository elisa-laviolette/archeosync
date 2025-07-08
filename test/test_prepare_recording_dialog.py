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

# Try to import QGIS modules, skip tests if not available
try:
    from qgis.PyQt.QtWidgets import QDialog
    from ui.prepare_recording_dialog import PrepareRecordingDialog
    from core.interfaces import ILayerService, ISettingsManager
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False


@unittest.skipIf(not QGIS_AVAILABLE, "QGIS not available")
class TestPrepareRecordingDialog(unittest.TestCase):
    """Test cases for PrepareRecordingDialog."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock services
        self.mock_layer_service = Mock(spec=ILayerService)
        self.mock_settings_manager = Mock(spec=ISettingsManager)
        
        # Create dialog instance
        self.dialog = PrepareRecordingDialog(
            layer_service=self.mock_layer_service,
            settings_manager=self.mock_settings_manager
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
        
        # Verify OK button is disabled
        ok_button = self.dialog._button_box.button(self.dialog._button_box.Ok)
        self.assertFalse(ok_button.isEnabled())
    
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
        
        # Verify OK button is disabled
        ok_button = self.dialog._button_box.button(self.dialog._button_box.Ok)
        self.assertFalse(ok_button.isEnabled())
    
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
        
        # Verify OK button is disabled and text is updated
        ok_button = self.dialog._button_box.button(self.dialog._button_box.Ok)
        self.assertFalse(ok_button.isEnabled())
        self.assertEqual(ok_button.text(), "No Selection")
        
        # Verify table is empty
        self.assertEqual(self.dialog._entities_table.rowCount(), 0)
    
    def test_update_selected_count_with_selection(self):
        """Test update when layer exists and features are selected."""
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
        mock_feature1 = Mock()
        mock_feature1.id.return_value = 1
        mock_feature2 = Mock()
        mock_feature2.id.return_value = 2
        mock_feature3 = Mock()
        mock_feature3.id.return_value = 3
        
        mock_layer = Mock()
        mock_layer.selectedFeatures.return_value = [mock_feature1, mock_feature2, mock_feature3]
        mock_layer.displayExpression.return_value = ''  # Empty display expression
        mock_fields = Mock()
        mock_fields.indexOf.return_value = -1  # No name fields found
        mock_layer.fields.return_value = mock_fields
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Call the method
        self.dialog._update_selected_count()
        
        # Verify labels are updated correctly
        self.assertEqual(self.dialog._recording_areas_label.text(), "Recording Areas Layer: Test Recording Areas")
        self.assertEqual(self.dialog._selected_count_label.text(), "Selected Entities: 3")
        
        # Verify OK button is enabled and text is updated
        ok_button = self.dialog._button_box.button(self.dialog._button_box.Ok)
        self.assertTrue(ok_button.isEnabled())
        self.assertEqual(ok_button.text(), "Prepare Recording")
        
        # Verify table has the correct number of rows
        self.assertEqual(self.dialog._entities_table.rowCount(), 3)
    
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
        
        # Verify OK button is disabled
        ok_button = self.dialog._button_box.button(self.dialog._button_box.Ok)
        self.assertFalse(ok_button.isEnabled())
    
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
        mock_layer.displayExpression.return_value = 'name'
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
        
        # Mock QGIS expression evaluation
        with patch('qgis.core.QgsExpression') as mock_expr_class:
            with patch('qgis.core.QgsExpressionContext') as mock_context_class:
                with patch('qgis.core.QgsExpressionContextUtils.layerScope') as mock_scope:
                    mock_expr = Mock()
                    mock_expr.evaluate.side_effect = ['Zone A', 'Zone B', 'Zone C']
                    mock_expr_class.return_value = mock_expr
                    
                    mock_context = Mock()
                    mock_context_class.return_value = mock_context
                    
                    # Call the method
                    self.dialog._populate_entities_table(features)
                    
                    # Verify table has correct number of rows
                    self.assertEqual(self.dialog._entities_table.rowCount(), 3)
                    
                    # Verify table content
                    self.assertEqual(self.dialog._entities_table.item(0, 0).text(), 'Zone A')
                    self.assertEqual(self.dialog._entities_table.item(1, 0).text(), 'Zone B')
                    self.assertEqual(self.dialog._entities_table.item(2, 0).text(), 'Zone C')

    def test_populate_entities_table_empty(self):
        """Test populating the entities table with empty data."""
        # Call the method with empty list
        self.dialog._populate_entities_table([])
        
        # Verify table has no rows
        self.assertEqual(self.dialog._entities_table.rowCount(), 0)

    def test_create_entities_table_with_number_field_only(self):
        """Test table creation when only number field is configured."""
        # Mock settings to return objects layer and number field only
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: {
            'objects_layer': 'objects_layer_id',
            'objects_number_field': 'number_field',
            'objects_level_field': ''
        }.get(key, default)
        
        # Recreate the table
        self.dialog._create_entities_table(self.dialog._entities_table.parent().layout())
        
        # Verify table has correct columns
        self.assertEqual(self.dialog._entities_table.columnCount(), 2)
        self.assertEqual(self.dialog._entities_table.horizontalHeaderItem(0).text(), "Name")
        self.assertEqual(self.dialog._entities_table.horizontalHeaderItem(1).text(), "Last object number")

    def test_create_entities_table_with_level_field_only(self):
        """Test table creation when only level field is configured."""
        # Mock settings to return objects layer and level field only
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: {
            'objects_layer': 'objects_layer_id',
            'objects_number_field': '',
            'objects_level_field': 'level_field'
        }.get(key, default)
        
        # Recreate the table
        self.dialog._create_entities_table(self.dialog._entities_table.parent().layout())
        
        # Verify table has correct columns
        self.assertEqual(self.dialog._entities_table.columnCount(), 2)
        self.assertEqual(self.dialog._entities_table.horizontalHeaderItem(0).text(), "Name")
        self.assertEqual(self.dialog._entities_table.horizontalHeaderItem(1).text(), "Last level")

    def test_create_entities_table_with_both_fields(self):
        """Test table creation when both number and level fields are configured."""
        # Mock settings to return objects layer and both fields
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: {
            'objects_layer': 'objects_layer_id',
            'objects_number_field': 'number_field',
            'objects_level_field': 'level_field'
        }.get(key, default)
        
        # Recreate the table
        self.dialog._create_entities_table(self.dialog._entities_table.parent().layout())
        
        # Verify table has correct columns
        self.assertEqual(self.dialog._entities_table.columnCount(), 3)
        self.assertEqual(self.dialog._entities_table.horizontalHeaderItem(0).text(), "Name")
        self.assertEqual(self.dialog._entities_table.horizontalHeaderItem(1).text(), "Last object number")
        self.assertEqual(self.dialog._entities_table.horizontalHeaderItem(2).text(), "Last level")

    def test_populate_entities_table_with_related_objects(self):
        """Test populating table with related objects information."""
        # Mock settings
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: {
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': 'objects_layer_id',
            'objects_number_field': 'number_field',
            'objects_level_field': 'level_field'
        }.get(key, default)
        
        # Mock layer service
        mock_layer = Mock()
        mock_layer.displayExpression.return_value = 'name'
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
        
        # Mock QGIS expression evaluation
        with patch('qgis.core.QgsExpression') as mock_expr_class:
            with patch('qgis.core.QgsExpressionContext') as mock_context_class:
                with patch('qgis.core.QgsExpressionContextUtils.layerScope') as mock_scope:
                    mock_expr = Mock()
                    mock_expr.evaluate.return_value = 'Test Area'
                    mock_expr_class.return_value = mock_expr
                    
                    mock_context = Mock()
                    mock_context_class.return_value = mock_context
                    
                    # Populate table
                    self.dialog._populate_entities_table([mock_feature])
                    
                    # Verify table has one row
                    self.assertEqual(self.dialog._entities_table.rowCount(), 1)
                    
                    # Verify related objects info was called
                    self.mock_layer_service.get_related_objects_info.assert_called_once_with(
                        mock_feature, 'objects_layer_id', 'number_field', 'level_field', 'recording_layer_id'
                    )
                    
                    # Verify table items (basic check - actual values depend on table recreation)
                    self.assertIsNotNone(self.dialog._entities_table.item(0, 0))

    def test_populate_entities_table_no_related_objects(self):
        """Test populating table when no related objects exist."""
        # Mock settings
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: {
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': 'objects_layer_id',
            'objects_number_field': 'number_field',
            'objects_level_field': 'level_field'
        }.get(key, default)
        
        # Mock layer service
        mock_layer = Mock()
        mock_layer.displayExpression.return_value = 'name'
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
        
        # Mock QGIS expression evaluation
        with patch('qgis.core.QgsExpression') as mock_expr_class:
            with patch('qgis.core.QgsExpressionContext') as mock_context_class:
                with patch('qgis.core.QgsExpressionContextUtils.layerScope') as mock_scope:
                    mock_expr = Mock()
                    mock_expr.evaluate.return_value = 'Test Area'
                    mock_expr_class.return_value = mock_expr
                    
                    mock_context = Mock()
                    mock_context_class.return_value = mock_context
                    
                    # Populate table
                    self.dialog._populate_entities_table([mock_feature])
                    
                    # Verify table has one row
                    self.assertEqual(self.dialog._entities_table.rowCount(), 1)
                    
                    # Verify related objects info was called
                    self.mock_layer_service.get_related_objects_info.assert_called_once_with(
                        mock_feature, 'objects_layer_id', 'number_field', 'level_field', 'recording_layer_id'
                    )


if __name__ == '__main__':
    unittest.main() 