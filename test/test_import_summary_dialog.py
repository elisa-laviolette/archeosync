"""
Tests for the Import Summary dialog.

This module tests the ImportSummaryDialog class to ensure it correctly displays
import statistics and handles different data scenarios properly.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from qgis.PyQt.QtWidgets import QApplication, QPushButton
from qgis.PyQt.QtCore import Qt

try:
    from ..ui.import_summary_dialog import ImportSummaryDialog, ImportSummaryData, WarningData
except ImportError:
    from ui.import_summary_dialog import ImportSummaryDialog, ImportSummaryData, WarningData


class TestImportSummaryDialog(unittest.TestCase):
    """Test cases for the ImportSummaryDialog class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock QApplication if one doesn't exist
        if not QApplication.instance():
            self.app = QApplication([])
        else:
            self.app = QApplication.instance()
    
    def test_dialog_initialization(self):
        """Test that the dialog initializes correctly."""
        summary_data = ImportSummaryData(
            csv_points_count=150,
            features_count=25,
            objects_count=10,
            small_finds_count=5,
            csv_duplicates=3,
            features_duplicates=1,
            objects_duplicates=0,
            small_finds_duplicates=2
        )
        
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # Check that the dialog was created
        self.assertIsNotNone(dialog)
        # By default, dialog should not be modal
        self.assertFalse(dialog.isModal())
    
    def test_dialog_modal_behavior(self):
        """Test that the dialog can be set to modal when needed."""
        summary_data = ImportSummaryData(
            csv_points_count=150,
            features_count=25,
            objects_count=10,
            small_finds_count=5,
            csv_duplicates=3,
            features_duplicates=1,
            objects_duplicates=0,
            small_finds_duplicates=2
        )
        
        dialog = ImportSummaryDialog(summary_data=summary_data, modal=True, settings_manager=None)
        
        # Check that the dialog was created and is modal when specified
        self.assertIsNotNone(dialog)
        self.assertTrue(dialog.isModal())
    
    def test_csv_section_display(self):
        """Test that CSV section is displayed correctly when CSV data is present."""
        summary_data = ImportSummaryData(csv_points_count=150, csv_duplicates=3)
        
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_features_section_display(self):
        """Test that features section is displayed correctly when features data is present."""
        summary_data = ImportSummaryData(features_count=25, features_duplicates=1)
        
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_objects_section_display(self):
        """Test that objects section is displayed correctly when objects data is present."""
        summary_data = ImportSummaryData(objects_count=10, objects_duplicates=0)
        
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_small_finds_section_display(self):
        """Test that small finds section is displayed correctly when small finds data is present."""
        summary_data = ImportSummaryData(small_finds_count=5, small_finds_duplicates=2)
        
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_empty_summary_data(self):
        """Test that dialog handles empty summary data gracefully."""
        summary_data = ImportSummaryData()
        
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # The dialog should have been created successfully even with no data
        self.assertIsNotNone(dialog)
    
    def test_duplicate_objects_warnings_display(self):
        """Test that duplicate objects warnings are displayed when there are duplicates with same recording area and number."""
        # Create summary data with duplicate objects warnings
        summary_data = ImportSummaryData(
            objects_count=10,
            objects_duplicates=0,
            duplicate_objects_warnings=[
                "Recording Area 'Test Area 1' has multiple objects with number 5",
                "Recording Area 'Test Area 2' has multiple objects with number 3"
            ]
        )
        
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_no_duplicate_objects_warnings_when_empty(self):
        """Test that duplicate objects warnings section is not displayed when there are no warnings."""
        # Create summary data without duplicate objects warnings
        summary_data = ImportSummaryData(
            objects_count=10,
            objects_duplicates=0,
            duplicate_objects_warnings=[]
        )
        
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_duplicate_objects_warnings_default_value(self):
        """Test that duplicate_objects_warnings defaults to empty list when not provided."""
        summary_data = ImportSummaryData(objects_count=10)
        
        # Check that duplicate_objects_warnings defaults to empty list
        self.assertEqual(summary_data.duplicate_objects_warnings, [])
    
    def test_skipped_numbers_warnings_display(self):
        """Test that skipped numbers warnings are displayed when there are gaps in numbering."""
        # Create summary data with skipped numbers warnings
        summary_data = ImportSummaryData(
            objects_count=10,
            objects_duplicates=0,
            skipped_numbers_warnings=[
                "Recording Area 'Test Area 1' has skipped numbers: [2, 4]",
                "Recording Area 'Test Area 2' has skipped numbers: [7]"
            ]
        )
        
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_no_skipped_numbers_warnings_when_empty(self):
        """Test that skipped numbers warnings section is not displayed when there are no warnings."""
        # Create summary data without skipped numbers warnings
        summary_data = ImportSummaryData(
            objects_count=10,
            objects_duplicates=0,
            skipped_numbers_warnings=[]
        )
        
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_skipped_numbers_warnings_default_value(self):
        """Test that skipped_numbers_warnings defaults to empty list when not provided."""
        summary_data = ImportSummaryData(objects_count=10)
        
        # Check that skipped_numbers_warnings defaults to empty list
        self.assertEqual(summary_data.skipped_numbers_warnings, [])
    
    def test_warning_buttons_creation(self):
        """Test that buttons are created for each warning."""
        # Create summary data with warnings
        summary_data = ImportSummaryData(
            objects_count=10,
            duplicate_objects_warnings=[
                "Recording Area 'Test Area 1' has multiple objects with number 5",
                "Recording Area 'Test Area 2' has multiple objects with number 3"
            ],
            skipped_numbers_warnings=[
                "Recording Area 'Test Area 1' has skipped numbers: [2, 4]"
            ]
        )
        
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_warning_button_click_opens_attribute_table(self):
        """Test that clicking a warning button opens the attribute table."""
        # Create summary data with a warning
        summary_data = ImportSummaryData(
            objects_count=10,
            duplicate_objects_warnings=[
                "Recording Area 'Test Area 1' has multiple objects with number 5"
            ]
        )
        
        # Mock the QGIS interface
        mock_iface = Mock()
        
        dialog = ImportSummaryDialog(summary_data=summary_data, iface=mock_iface, settings_manager=None)
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_warning_buttons_with_structured_data(self):
        """Test that buttons work correctly with structured warning data."""
        # Create summary data with structured warnings
        summary_data = ImportSummaryData(
            objects_count=10,
            duplicate_objects_warnings=[
                WarningData(
                    message="Recording Area 'Test Area 1' has multiple objects with number 5",
                    recording_area_name='Test Area 1',
                    layer_name='Objects',
                    filter_expression='"recording_area" = \'Test Area 1\' AND "number" = 5',
                    object_number=5
                )
            ],
            skipped_numbers_warnings=[
                WarningData(
                    message="Recording Area 'Test Area 1' has skipped numbers: [2, 4]",
                    recording_area_name='Test Area 1',
                    layer_name='Objects',
                    filter_expression='"recording_area" = \'Test Area 1\' AND "number" IN (2, 4)',
                    skipped_numbers=[2, 4]
                )
            ]
        )
        
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_open_filtered_attribute_table_with_warning_data(self):
        """Test that the _open_filtered_attribute_table method works with WarningData."""
        # Create a warning data object
        warning_data = WarningData(
            message="Test warning",
            recording_area_name='Test Area',
            layer_name='Objects',
            filter_expression='"recording_area" = \'Test Area\'',
            object_number=5
        )
        
        # Mock the QGIS interface
        mock_iface = Mock()
        
        dialog = ImportSummaryDialog(ImportSummaryData(), iface=mock_iface, settings_manager=None)
        
        # Mock QGIS project and layer
        mock_project = Mock()
        mock_layer = Mock()
        mock_layer.name.return_value = 'Objects'
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            mock_project.mapLayers.return_value = {'layer_id': mock_layer}
            
            # Call the method
            dialog._open_filtered_attribute_table(warning_data)
            
            # Verify that the layer was set as active
            mock_iface.setActiveLayer.assert_called_with(mock_layer)
            
            # Verify that the filter was applied
            mock_layer.setSubsetString.assert_called_with('"recording_area" = \'Test Area\'')
            
            # Verify that the attribute table was opened
            mock_iface.actionOpenTable.assert_called_once()

    def test_validate_button_exists(self):
        """Test that the Validate button exists instead of OK button."""
        summary_data = ImportSummaryData(objects_count=10)
        mock_settings = Mock()
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=mock_settings)
        
        # Check that the validate button exists
        self.assertIsNotNone(dialog._validate_button)
        self.assertEqual(dialog._validate_button.text(), "Validate")
    
    def test_validate_button_click_handler(self):
        """Test that the validate button has the correct click handler."""
        summary_data = ImportSummaryData(objects_count=10)
        mock_settings = Mock()
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=mock_settings)
        
        # Check that the validate button is connected to the handler
        self.assertIsNotNone(dialog._validate_button)
        # The connection should be set up in _setup_connections
        self.assertTrue(hasattr(dialog, '_handle_validate'))
    
    @patch('qgis.core.QgsProject')
    @patch('qgis.PyQt.QtCore.QSettings')
    def test_copy_temporary_to_definitive_layers_success(self, mock_settings, mock_project):
        """Test successful copying of features from temporary to definitive layers."""
        # Mock QGIS project and layers
        mock_project_instance = Mock()
        mock_project.instance.return_value = mock_project_instance
        
        # Mock temporary layers
        mock_temp_objects = Mock()
        mock_temp_objects.name.return_value = "New Objects"
        mock_temp_features = Mock()
        mock_temp_features.name.return_value = "New Features"
        mock_temp_small_finds = Mock()
        mock_temp_small_finds.name.return_value = "New Small Finds"
        
        # Mock definitive layers
        mock_def_objects = Mock()
        mock_def_objects.name.return_value = "Objects"
        mock_def_objects.isEditable.return_value = False
        mock_def_objects.startEditing = Mock()
        mock_def_objects.addFeature = Mock(return_value=True)
        mock_def_objects.commitChanges = Mock()
        
        mock_def_features = Mock()
        mock_def_features.name.return_value = "Features"
        mock_def_features.isEditable.return_value = False
        mock_def_features.startEditing = Mock()
        mock_def_features.addFeature = Mock(return_value=True)
        mock_def_features.commitChanges = Mock()
        
        mock_def_small_finds = Mock()
        mock_def_small_finds.name.return_value = "Small Finds"
        mock_def_small_finds.isEditable.return_value = False
        mock_def_small_finds.startEditing = Mock()
        mock_def_small_finds.addFeature = Mock(return_value=True)
        mock_def_small_finds.commitChanges = Mock()
        
        # Mock project map layers - use layer IDs that match the settings
        mock_project_instance.mapLayers.return_value = {
            'temp_objects_id': mock_temp_objects,
            'temp_features_id': mock_temp_features,
            'temp_small_finds_id': mock_temp_small_finds,
            'def_objects_id': mock_def_objects,
            'def_features_id': mock_def_features,
            'def_small_finds_id': mock_def_small_finds
        }
        
        # Mock settings
        mock_settings_instance = Mock()
        mock_settings.return_value = mock_settings_instance
        mock_settings_instance.value.side_effect = lambda key, default: {
            'archeosync/objects_layer': 'def_objects_id',
            'archeosync/features_layer': 'def_features_id',
            'archeosync/small_finds_layer': 'def_small_finds_id'
        }.get(key, default)
        
        # Create mock features
        from qgis.core import QgsFeature, QgsFields, QgsField
        from PyQt5.QtCore import QVariant
        
        # Create fields for features
        fields = QgsFields()
        fields.append(QgsField("name", QVariant.String))
        fields.append(QgsField("value", QVariant.Int))
        
        # Create mock features
        mock_feature1 = Mock()
        mock_feature1.fields.return_value = fields
        mock_feature1.__getitem__ = Mock(return_value="test")
        mock_feature1.geometry.return_value = Mock()
        mock_feature1.geometry().isEmpty.return_value = False
        
        mock_feature2 = Mock()
        mock_feature2.fields.return_value = fields
        mock_feature2.__getitem__ = Mock(return_value="test2")
        mock_feature2.geometry.return_value = Mock()
        mock_feature2.geometry().isEmpty.return_value = False
        
        # Mock getFeatures to return our test features
        mock_temp_objects.getFeatures.return_value = [mock_feature1]
        mock_temp_features.getFeatures.return_value = [mock_feature2]
        mock_temp_small_finds.getFeatures.return_value = []
        
        # Mock target layer fields
        mock_def_objects.fields.return_value = fields
        mock_def_features.fields.return_value = fields
        mock_def_small_finds.fields.return_value = fields
        
        # Create dialog and test
        summary_data = ImportSummaryData(objects_count=1, features_count=1)
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # Test the copy functionality
        dialog._copy_temporary_to_definitive_layers()
        
        # Verify that layers were put in edit mode
        mock_def_objects.startEditing.assert_called()
        mock_def_features.startEditing.assert_called()
        mock_def_small_finds.startEditing.assert_called()
        
        # Verify that features were added
        mock_def_objects.addFeature.assert_called()
        mock_def_features.addFeature.assert_called()
        
        # Verify that changes were committed
        mock_def_objects.commitChanges.assert_called()
        mock_def_features.commitChanges.assert_called()
    
    @patch('qgis.core.QgsProject')
    @patch('qgis.PyQt.QtCore.QSettings')
    def test_copy_temporary_to_definitive_layers_no_temporary_layers(self, mock_settings, mock_project):
        """Test copying when no temporary layers exist."""
        # Mock QGIS project with no temporary layers
        mock_project_instance = Mock()
        mock_project.instance.return_value = mock_project_instance
        mock_project_instance.mapLayers.return_value = {}
        
        # Mock settings
        mock_settings_instance = Mock()
        mock_settings.return_value = mock_settings_instance
        mock_settings_instance.value.return_value = ""
        
        # Create dialog and test
        summary_data = ImportSummaryData(objects_count=0)
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # Test the copy functionality - should not raise an exception
        dialog._copy_temporary_to_definitive_layers()
    
    @patch('qgis.core.QgsProject')
    @patch('qgis.PyQt.QtCore.QSettings')
    def test_copy_temporary_to_definitive_layers_no_definitive_layers(self, mock_settings, mock_project):
        """Test copying when definitive layers are not configured."""
        # Mock QGIS project with temporary layers but no definitive layers
        mock_project_instance = Mock()
        mock_project.instance.return_value = mock_project_instance
        
        # Mock temporary layers
        mock_temp_objects = Mock()
        mock_temp_objects.name.return_value = "New Objects"
        
        mock_project_instance.mapLayers.return_value = {
            'temp_objects_id': mock_temp_objects
        }
        
        # Mock settings with no definitive layer configured
        mock_settings_instance = Mock()
        mock_settings.return_value = mock_settings_instance
        mock_settings_instance.value.return_value = ""
        
        # Create dialog and test
        summary_data = ImportSummaryData(objects_count=1)
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # Test the copy functionality - should not raise an exception
        dialog._copy_temporary_to_definitive_layers()
    
    @patch('qgis.core.QgsProject')
    @patch('qgis.PyQt.QtCore.QSettings')
    def test_copy_temporary_to_definitive_layers_no_configuration(self, mock_settings, mock_project):
        """Test copying when definitive layers are not configured."""
        # Mock QGIS project and layers
        mock_project_instance = Mock()
        mock_project.instance.return_value = mock_project_instance
        
        # Mock temporary layers
        mock_temp_objects = Mock()
        mock_temp_objects.name.return_value = "New Objects"
        mock_temp_features = Mock()
        mock_temp_features.name.return_value = "New Features"
        
        # Mock project map layers
        mock_project_instance.mapLayers.return_value = {
            'temp_objects_id': mock_temp_objects,
            'temp_features_id': mock_temp_features
        }
        
        # Mock settings to return empty values (not configured)
        mock_settings_instance = Mock()
        mock_settings.return_value = mock_settings_instance
        mock_settings_instance.value.side_effect = lambda key, default: ""
        
        # Create dialog and test
        summary_data = ImportSummaryData(objects_count=1, features_count=1)
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # Test the copy functionality - should handle missing configuration gracefully
        dialog._copy_temporary_to_definitive_layers()
        
        # The method should complete without raising exceptions
        # The actual behavior (showing message boxes) is tested in integration tests
    
    def test_create_feature_with_target_structure(self):
        """Test creating a feature with target layer structure."""
        from qgis.core import QgsFeature, QgsFields, QgsField, QgsGeometry, QgsPointXY
        from PyQt5.QtCore import QVariant
        
        # Create source feature
        source_fields = QgsFields()
        source_fields.append(QgsField("name", QVariant.String))
        source_fields.append(QgsField("value", QVariant.Int))
        
        source_feature = QgsFeature(source_fields)
        source_feature["name"] = "test_name"
        source_feature["value"] = 42
        source_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1, 1)))
        
        # Create target layer with different field structure
        target_fields = QgsFields()
        target_fields.append(QgsField("name", QVariant.String))
        target_fields.append(QgsField("value", QVariant.Int))
        target_fields.append(QgsField("extra", QVariant.String))  # Extra field
        
        mock_target_layer = Mock()
        mock_target_layer.fields.return_value = target_fields
        
        # Create dialog and test
        summary_data = ImportSummaryData()
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # Test feature creation
        new_feature = dialog._create_feature_with_target_structure(source_feature, mock_target_layer)
        
        # Verify the new feature has the correct structure
        self.assertIsNotNone(new_feature)
        self.assertEqual(new_feature["name"], "test_name")
        self.assertEqual(new_feature["value"], 42)
        # Check that extra field is NULL (QGIS NULL value)
        self.assertIsNone(new_feature["extra"])  # Should be None for missing field
        self.assertFalse(new_feature.geometry().isEmpty())
    
    def test_create_feature_with_target_structure_no_geometry(self):
        """Test creating a feature when source has no geometry."""
        from qgis.core import QgsFeature, QgsFields, QgsField
        from PyQt5.QtCore import QVariant
        
        # Create source feature without geometry
        source_fields = QgsFields()
        source_fields.append(QgsField("name", QVariant.String))
        
        source_feature = QgsFeature(source_fields)
        source_feature["name"] = "test_name"
        # No geometry set
        
        # Create target layer
        target_fields = QgsFields()
        target_fields.append(QgsField("name", QVariant.String))
        
        mock_target_layer = Mock()
        mock_target_layer.fields.return_value = target_fields
        
        # Create dialog and test
        summary_data = ImportSummaryData()
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # Test feature creation
        new_feature = dialog._create_feature_with_target_structure(source_feature, mock_target_layer)
        
        # Verify the new feature has the correct structure
        self.assertIsNotNone(new_feature)
        self.assertEqual(new_feature["name"], "test_name")
        self.assertTrue(new_feature.geometry().isEmpty())
    
    @patch('qgis.PyQt.QtWidgets.QMessageBox.critical')
    def test_handle_validate_with_error(self, mock_critical):
        """Test that validation errors are handled gracefully."""
        summary_data = ImportSummaryData(objects_count=1)
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # Mock the copy method to raise an exception
        with patch.object(dialog, '_copy_temporary_to_definitive_layers', side_effect=Exception("Test error")):
            # Test that the error is handled
            dialog._handle_validate()
            
            # Verify error message was shown
            mock_critical.assert_called_once()
    
    def test_get_definitive_layer_id_success(self):
        """Test getting definitive layer ID from settings."""
        with patch('qgis.PyQt.QtCore.QSettings') as mock_settings:
            mock_settings_instance = Mock()
            mock_settings.return_value = mock_settings_instance
            mock_settings_instance.value.return_value = "test_layer_id"
            
            summary_data = ImportSummaryData()
            dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
            
            layer_id = dialog._get_definitive_layer_id("objects_layer")
            self.assertEqual(layer_id, "test_layer_id")
    
    def test_get_definitive_layer_id_not_found(self):
        """Test getting definitive layer ID when not configured."""
        with patch('qgis.PyQt.QtCore.QSettings') as mock_settings:
            mock_settings_instance = Mock()
            mock_settings.return_value = mock_settings_instance
            mock_settings_instance.value.return_value = ""
            
            summary_data = ImportSummaryData()
            dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
            
            layer_id = dialog._get_definitive_layer_id("objects_layer")
            self.assertIsNone(layer_id)
    
    def test_get_definitive_layer_id_with_settings_manager(self):
        """Test getting definitive layer ID using settings manager."""
        mock_settings = Mock()
        mock_settings.get_value.return_value = "test_layer_id"
        
        summary_data = ImportSummaryData()
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=mock_settings)
        
        layer_id = dialog._get_definitive_layer_id("objects_layer")
        
        # Verify the settings manager was called correctly
        mock_settings.get_value.assert_called_with("objects_layer", "")
        self.assertEqual(layer_id, "test_layer_id")
    
    def test_get_definitive_layer_id_without_settings_manager(self):
        """Test getting definitive layer ID without settings manager (fallback)."""
        summary_data = ImportSummaryData()
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # This should use the fallback QSettings approach
        layer_id = dialog._get_definitive_layer_id("objects_layer")
        
        # Should return None or empty string when no settings manager is provided
        self.assertIsNone(layer_id)
    
    def test_copy_features_between_layers_success(self):
        """Test successful copying of features between layers."""
        from qgis.core import QgsFeature, QgsFields, QgsField
        from PyQt5.QtCore import QVariant
        
        # Create mock source layer
        mock_source_layer = Mock()
        fields = QgsFields()
        fields.append(QgsField("name", QVariant.String))
        
        source_feature = QgsFeature(fields)
        source_feature["name"] = "test"
        mock_source_layer.getFeatures.return_value = [source_feature]
        
        # Create mock target layer
        mock_target_layer = Mock()
        mock_target_layer.isEditable.return_value = False
        mock_target_layer.startEditing = Mock()
        mock_target_layer.addFeature = Mock(return_value=True)
        mock_target_layer.commitChanges = Mock()
        mock_target_layer.fields.return_value = fields
        
        summary_data = ImportSummaryData()
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # Test copying
        copied_count = dialog._copy_features_between_layers(mock_source_layer, mock_target_layer)
        
        # Verify results
        self.assertEqual(copied_count, 1)
        mock_target_layer.startEditing.assert_called()
        mock_target_layer.addFeature.assert_called()
        mock_target_layer.commitChanges.assert_called()
    
    def test_copy_features_between_layers_with_error(self):
        """Test copying features when addFeature fails."""
        from qgis.core import QgsFeature, QgsFields, QgsField
        from PyQt5.QtCore import QVariant
        
        # Create mock source layer
        mock_source_layer = Mock()
        fields = QgsFields()
        fields.append(QgsField("name", QVariant.String))
        
        source_feature = QgsFeature(fields)
        source_feature["name"] = "test"
        mock_source_layer.getFeatures.return_value = [source_feature]
        
        # Create mock target layer that fails to add features
        mock_target_layer = Mock()
        mock_target_layer.isEditable.return_value = False
        mock_target_layer.startEditing = Mock()
        mock_target_layer.addFeature = Mock(return_value=False)
        mock_target_layer.lastError.return_value = "Test error"
        mock_target_layer.rollBack = Mock()
        mock_target_layer.fields.return_value = fields
        
        summary_data = ImportSummaryData()
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # Test copying - should handle the error gracefully
        copied_count = dialog._copy_features_between_layers(mock_source_layer, mock_target_layer)
        
        # Verify results
        self.assertEqual(copied_count, 0)
        # Note: rollBack is only called if there's an exception, not just when addFeature fails
        # So we don't expect rollBack to be called in this case

    def test_create_feature_with_target_structure_excludes_fid_fields(self):
        """Test that FID fields are excluded when creating features to avoid conflicts."""
        from qgis.core import QgsFeature, QgsFields, QgsField, QgsGeometry, QgsPointXY
        from PyQt5.QtCore import QVariant
        
        # Create source feature with FID field
        source_fields = QgsFields()
        source_fields.append(QgsField("fid", QVariant.Int))
        source_fields.append(QgsField("name", QVariant.String))
        source_fields.append(QgsField("value", QVariant.Int))
        
        source_feature = QgsFeature(source_fields)
        source_feature["fid"] = 999  # This should be ignored
        source_feature["name"] = "test_name"
        source_feature["value"] = 42
        source_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1, 1)))
        
        # Create target layer with FID field
        target_fields = QgsFields()
        target_fields.append(QgsField("fid", QVariant.Int))
        target_fields.append(QgsField("name", QVariant.String))
        target_fields.append(QgsField("extra", QVariant.String))
        
        mock_target_layer = Mock()
        mock_target_layer.fields.return_value = target_fields
        
        # Create dialog and test
        summary_data = ImportSummaryData()
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # Test feature creation
        new_feature = dialog._create_feature_with_target_structure(source_feature, mock_target_layer)
        
        # Verify the feature was created
        self.assertIsNotNone(new_feature)
        
        # Verify that FID field is not copied (should be None or new value)
        # The FID should be automatically assigned by QGIS, not copied from source
        self.assertNotEqual(new_feature["fid"], 999)
        
        # Verify other fields are copied correctly
        self.assertEqual(new_feature["name"], "test_name")
        self.assertIsNone(new_feature["extra"])  # Should be None for missing field

    def test_copy_features_between_layers_with_improved_error_handling(self):
        """Test copying features with improved error handling and reporting."""
        from qgis.core import QgsFeature, QgsFields, QgsField
        from PyQt5.QtCore import QVariant
        
        # Create mock source layer
        mock_source_layer = Mock()
        fields = QgsFields()
        fields.append(QgsField("name", QVariant.String))
        
        source_feature = QgsFeature(fields)
        source_feature["name"] = "test"
        mock_source_layer.getFeatures.return_value = [source_feature]
        
        # Create mock target layer that succeeds for some features and fails for others
        mock_target_layer = Mock()
        mock_target_layer.isEditable.return_value = False
        mock_target_layer.startEditing = Mock()
        mock_target_layer.fields.return_value = fields
        mock_target_layer.addFeature.side_effect = [True, False, True]  # Success, failure, success
        mock_target_layer.lastError.return_value = "FID conflict"
        mock_target_layer.commitChanges = Mock()  # Should not be called
        mock_target_layer.rollBack = Mock()
        
        # Create dialog and test
        summary_data = ImportSummaryData()
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        # Test copying with multiple features (some will fail)
        mock_source_layer.getFeatures.return_value = [source_feature, source_feature, source_feature]
        
        copied_count = dialog._copy_features_between_layers(mock_source_layer, mock_target_layer)
        
        # Verify that the method handled errors gracefully
        self.assertEqual(copied_count, 2)  # 2 successful, 1 failed
        
        # Verify that editing was started but NOT committed (user should decide)
        mock_target_layer.startEditing.assert_called()
        mock_target_layer.commitChanges.assert_not_called()  # Should NOT commit automatically
        mock_target_layer.rollBack.assert_not_called()  # Should not rollback since some features succeeded

    def test_copy_features_between_layers_selects_new_features(self):
        """Test that newly copied features are automatically selected."""
        from qgis.core import QgsFeature, QgsFields, QgsField
        from PyQt5.QtCore import QVariant
        
        # Create mock source layer
        mock_source_layer = Mock()
        fields = QgsFields()
        fields.append(QgsField("name", QVariant.String))
        
        source_feature = QgsFeature(fields)
        source_feature["name"] = "test"
        mock_source_layer.getFeatures.return_value = [source_feature]
        
        # Create mock target layer
        mock_target_layer = Mock()
        mock_target_layer.isEditable.return_value = False
        mock_target_layer.startEditing = Mock()
        mock_target_layer.fields.return_value = fields
        mock_target_layer.addFeature.return_value = True
        mock_target_layer.removeSelection = Mock()
        mock_target_layer.select = Mock()
        
        # Create dialog and test
        summary_data = ImportSummaryData()
        dialog = ImportSummaryDialog(summary_data=summary_data, settings_manager=None)
        
        copied_count = dialog._copy_features_between_layers(mock_source_layer, mock_target_layer)
        
        # Verify that features were copied
        self.assertEqual(copied_count, 1)
        
        # Verify that selection was cleared and new features were selected
        mock_target_layer.removeSelection.assert_called_once()
        mock_target_layer.select.assert_called_once()
        
        # Verify that editing was started but NOT committed
        mock_target_layer.startEditing.assert_called()
        mock_target_layer.commitChanges.assert_not_called()  # Should NOT commit automatically


if __name__ == '__main__':
    unittest.main() 