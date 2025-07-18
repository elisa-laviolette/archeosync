"""
Tests for ImportSummaryDialog.

This module tests the import summary dialog functionality.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

try:
    from qgis.PyQt import QtWidgets
    from ui.import_summary_dialog import ImportSummaryDialog, ImportSummaryDockWidget
    from core.data_structures import ImportSummaryData, WarningData
except ImportError:
    from qgis.PyQt import QtWidgets
    from ..ui.import_summary_dialog import ImportSummaryDialog, ImportSummaryDockWidget
    from ..core.data_structures import ImportSummaryData, WarningData


class TestImportSummaryDialog(unittest.TestCase):
    """Test cases for ImportSummaryDialog."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_iface = Mock()
        self.mock_settings_manager = Mock()
        self.mock_csv_import_service = Mock()
        self.mock_field_project_import_service = Mock()
        self.mock_layer_service = Mock()
        self.mock_translation_service = Mock()
        # Configure the translation service to return the input string
        self.mock_translation_service.translate.side_effect = lambda x: x
        
        # Create parent widget for testing
        self.parent = QtWidgets.QWidget()
        
        # Create sample summary data
        self.summary_data = ImportSummaryData(
            csv_points_count=10,
            features_count=5,
            objects_count=3,
            small_finds_count=2,
            csv_duplicates=1,
            features_duplicates=0,
            objects_duplicates=1,
            small_finds_duplicates=0,
            duplicate_objects_warnings=[
                WarningData(
                    message="Test duplicate warning",
                    recording_area_name="Test Area",
                    layer_name="Test Layer",
                    filter_expression="test_filter"
                )
            ],
            skipped_numbers_warnings=[
                WarningData(
                    message="Test skipped numbers warning",
                    recording_area_name="Test Area",
                    layer_name="Test Layer",
                    filter_expression="test_filter",
                    skipped_numbers=[2, 4]
                )
            ]
        )
        
        self.dialog = ImportSummaryDialog(
            summary_data=self.summary_data,
            iface=self.mock_iface,
            settings_manager=self.mock_settings_manager,
            csv_import_service=self.mock_csv_import_service,
            field_project_import_service=self.mock_field_project_import_service,
            layer_service=self.mock_layer_service,
            translation_service=self.mock_translation_service,
            parent=self.parent
        )
    
    def test_init_with_services(self):
        """Test that the dialog initializes correctly with all services."""
        self.assertEqual(self.dialog._summary_data, self.summary_data)
        self.assertEqual(self.dialog._iface, self.mock_iface)
        self.assertEqual(self.dialog._settings_manager, self.mock_settings_manager)
        self.assertEqual(self.dialog._csv_import_service, self.mock_csv_import_service)
        self.assertEqual(self.dialog._field_project_import_service, self.mock_field_project_import_service)
        self.assertEqual(self.dialog._layer_service, self.mock_layer_service)
        self.assertEqual(self.dialog._translation_service, self.mock_translation_service)
    
    def test_refresh_warnings_button_exists(self):
        """Test that the refresh warnings button is created."""
        self.assertIsNotNone(self.dialog._refresh_button)
        self.assertEqual(self.dialog._refresh_button.text(), "Refresh Warnings")
    
    def test_refresh_warnings_success(self):
        """Test that refresh warnings works correctly."""
        # Mock the detection services
        mock_duplicate_detector = Mock()
        mock_duplicate_detector.detect_duplicate_objects.return_value = [
            WarningData(
                message="Updated duplicate warning",
                recording_area_name="Updated Area",
                layer_name="Updated Layer",
                filter_expression="updated_filter"
            )
        ]
        
        mock_skipped_detector = Mock()
        mock_skipped_detector.detect_skipped_numbers.return_value = [
            WarningData(
                message="Updated skipped numbers warning",
                recording_area_name="Updated Area",
                layer_name="Updated Layer",
                filter_expression="updated_filter"
            )
        ]
        
        # Mock the service classes
        with patch('ui.import_summary_dialog.DuplicateObjectsDetectorService', return_value=mock_duplicate_detector), \
             patch('ui.import_summary_dialog.SkippedNumbersDetectorService', return_value=mock_skipped_detector), \
             patch.object(self.dialog, '_recreate_summary_content') as mock_recreate:
            
            # Set up summary data with objects
            self.dialog._summary_data.objects_count = 5
            
            # Call the method
            self.dialog._handle_refresh_warnings()
            
            # Verify the services were called
            mock_duplicate_detector.detect_duplicate_objects.assert_called_once()
            mock_skipped_detector.detect_skipped_numbers.assert_called_once()
            
            # Verify the summary data was updated
            self.assertEqual(len(self.dialog._summary_data.duplicate_objects_warnings), 1)
            self.assertEqual(len(self.dialog._summary_data.skipped_numbers_warnings), 1)
            
            # Verify the UI was recreated
            mock_recreate.assert_called_once()
    
    def test_refresh_warnings_error_handling(self):
        """Test that refresh warnings handles errors gracefully."""
        # Mock the detection services to raise an exception
        with patch('ui.import_summary_dialog.DuplicateObjectsDetectorService', side_effect=Exception("Test error")), \
             patch('qgis.PyQt.QtWidgets.QMessageBox') as mock_message_box:
            
            # Call the refresh method
            self.dialog._handle_refresh_warnings()
            
            # Verify that error message was shown
            mock_message_box.critical.assert_called_once()
    
    def test_refresh_warnings_no_objects(self):
        """Test that refresh warnings works when no objects are imported."""
        # Create summary data with no objects
        no_objects_data = ImportSummaryData(
            csv_points_count=10,
            features_count=5,
            objects_count=0,  # No objects
            small_finds_count=2
        )
        
        dialog = ImportSummaryDialog(
            summary_data=no_objects_data,
            iface=self.mock_iface,
            settings_manager=self.mock_settings_manager,
            csv_import_service=self.mock_csv_import_service,
            field_project_import_service=self.mock_field_project_import_service,
            layer_service=self.mock_layer_service,
            translation_service=self.mock_translation_service,
            parent=self.parent
        )
        
        with patch('qgis.PyQt.QtWidgets.QMessageBox') as mock_qmessagebox, \
             patch.object(dialog, '_recreate_summary_content') as mock_recreate:
            
            # Configure the mock QMessageBox
            mock_qmessagebox.information = Mock()
            
            # Call the refresh method
            dialog._handle_refresh_warnings()
            
            # Verify that UI was recreated (even with no warnings)
            mock_recreate.assert_called_once()
            
            # Verify that success message was shown
            mock_qmessagebox.information.assert_called_once()
    
    def test_recreate_summary_content(self):
        """Test that the summary content recreation works correctly."""
        # Mock the widget and layout structure
        mock_widget = Mock()
        mock_layout = Mock()
        mock_scroll_area = Mock()
        
        # Set up the mock structure
        mock_widget.layout.return_value = mock_layout
        mock_layout.count.return_value = 1
        mock_layout.itemAt.return_value.widget.return_value = mock_scroll_area
        mock_scroll_area.__class__ = type(QtWidgets.QScrollArea())
        
        with patch.object(self.dialog, 'widget', return_value=mock_widget), \
             patch.object(self.dialog, '_create_summary_content') as mock_create:
            
            # Call the recreate method
            self.dialog._recreate_summary_content()
            
            # Verify that the scroll area was removed and recreated
            mock_layout.removeItem.assert_called_once()
            mock_scroll_area.deleteLater.assert_called_once()
            mock_create.assert_called_once()
    
    def test_recreate_summary_content_error_handling(self):
        """Test that recreate summary content handles errors gracefully."""
        # Mock the layout to raise an exception
        with patch.object(self.dialog, 'layout', side_effect=Exception("Test error")):
            
            # Call the recreate method - should not raise an exception
            try:
                self.dialog._recreate_summary_content()
            except Exception:
                self.fail("_recreate_summary_content should handle exceptions gracefully")
    
    def test_dock_widget_creation(self):
        """Test that dock widget can be created successfully."""
        # Create a dock widget
        dock_widget = ImportSummaryDockWidget(
            summary_data=self.summary_data,
            iface=self.mock_iface,
            settings_manager=self.mock_settings_manager,
            csv_import_service=self.mock_csv_import_service,
            field_project_import_service=self.mock_field_project_import_service,
            layer_service=self.mock_layer_service,
            translation_service=self.mock_translation_service,
            parent=self.parent
        )
        
        # Check that it's a dock widget
        from qgis.PyQt.QtWidgets import QDockWidget
        self.assertIsInstance(dock_widget, QDockWidget)
        
        # Check that it has the correct title
        self.assertEqual(dock_widget.windowTitle(), "Import Summary")
    
    def test_dock_widget_allowed_areas(self):
        """Test that dock widget has correct allowed areas."""
        # Create a dock widget
        dock_widget = ImportSummaryDockWidget(
            summary_data=self.summary_data,
            iface=self.mock_iface,
            settings_manager=self.mock_settings_manager,
            csv_import_service=self.mock_csv_import_service,
            field_project_import_service=self.mock_field_project_import_service,
            layer_service=self.mock_layer_service,
            translation_service=self.mock_translation_service,
            parent=self.parent
        )
        
        # Check that it allows all dock areas
        from qgis.PyQt.QtCore import Qt
        expected_areas = (Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | 
                         Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        self.assertEqual(dock_widget.allowedAreas(), expected_areas)
    
    def test_cancel_button_exists(self):
        """Test that the cancel button is created."""
        self.assertIsNotNone(self.dialog._cancel_button)
        self.assertEqual(self.dialog._cancel_button.text(), "Cancel Import")
    
    def test_cancel_button_confirmation_yes(self):
        """Test that cancel button shows confirmation dialog and proceeds when user clicks Yes."""
        with patch('qgis.PyQt.QtWidgets.QMessageBox.question') as mock_question, \
             patch.object(self.dialog, '_delete_temporary_layers') as mock_delete, \
             patch.object(self.dialog, 'deleteLater') as mock_delete_later:
            
            # Configure the mock to return Yes
            mock_question.return_value = QtWidgets.QMessageBox.Yes
            
            # Call the cancel method
            self.dialog._handle_cancel()
            
            # Verify confirmation dialog was shown
            mock_question.assert_called_once_with(
                self.dialog,
                "Cancel Import",
                "Are you sure you want to cancel the import? This will delete all temporary import layers and cannot be undone.",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            
            # Verify temporary layers were deleted
            mock_delete.assert_called_once()
            
            # Verify widget was deleted
            mock_delete_later.assert_called_once()
    
    def test_cancel_button_confirmation_no(self):
        """Test that cancel button shows confirmation dialog and does nothing when user clicks No."""
        with patch('qgis.PyQt.QtWidgets.QMessageBox.question') as mock_question, \
             patch.object(self.dialog, '_delete_temporary_layers') as mock_delete, \
             patch.object(self.dialog, 'deleteLater') as mock_delete_later:
            
            # Configure the mock to return No
            mock_question.return_value = QtWidgets.QMessageBox.No
            
            # Call the cancel method
            self.dialog._handle_cancel()
            
            # Verify confirmation dialog was shown
            mock_question.assert_called_once()
            
            # Verify temporary layers were NOT deleted
            mock_delete.assert_not_called()
            
            # Verify widget was NOT deleted
            mock_delete_later.assert_not_called()
    
    def test_cancel_button_error_handling(self):
        """Test that cancel button handles errors gracefully."""
        with patch('qgis.PyQt.QtWidgets.QMessageBox.question', side_effect=Exception("Test error")), \
             patch('qgis.PyQt.QtWidgets.QMessageBox.critical') as mock_critical:
            
            # Call the cancel method
            self.dialog._handle_cancel()
            
            # Verify error message was shown
            mock_critical.assert_called_once_with(
                self.dialog,
                "Cancel Error",
                "An error occurred while canceling the import: Test error"
            )
    
    def test_delete_temporary_layers_includes_csv_layer(self):
        """Test that the delete temporary layers method includes the CSV temporary layer."""
        with patch('qgis.core.QgsProject') as mock_project_class:
            
            # Create mock project and layers
            mock_project = Mock()
            mock_project_class.instance.return_value = mock_project
            
            # Create mock layers
            mock_objects_layer = Mock()
            mock_objects_layer.name.return_value = "New Objects"
            mock_objects_layer.id.return_value = "objects_layer_id"
            
            mock_features_layer = Mock()
            mock_features_layer.name.return_value = "New Features"
            mock_features_layer.id.return_value = "features_layer_id"
            
            mock_csv_layer = Mock()
            mock_csv_layer.name.return_value = "Imported_CSV_Points"
            mock_csv_layer.id.return_value = "csv_layer_id"
            
            # Set up the project to return our mock layers
            mock_project.mapLayers.return_value = {
                "objects_layer_id": mock_objects_layer,
                "features_layer_id": mock_features_layer,
                "csv_layer_id": mock_csv_layer
            }
            
            # Call the delete method
            self.dialog._delete_temporary_layers()
            
            # Check that removeMapLayer was called for each temporary layer
            self.assertEqual(mock_project.removeMapLayer.call_count, 3)
            
            # Verify the specific layer IDs were called
            mock_project.removeMapLayer.assert_any_call("objects_layer_id")
            mock_project.removeMapLayer.assert_any_call("features_layer_id")
            mock_project.removeMapLayer.assert_any_call("csv_layer_id")
    
    def test_copy_temporary_to_definitive_layers_includes_csv_points(self):
        """Test that the copy temporary to definitive layers method includes the CSV points layer."""
        with patch('qgis.core.QgsProject') as mock_project_class:
            
            # Create mock project and layers
            mock_project = Mock()
            mock_project_class.instance.return_value = mock_project
            
            # Create mock temporary CSV layer
            mock_csv_layer = Mock()
            mock_csv_layer.name.return_value = "Imported_CSV_Points"
            mock_csv_layer.getFeatures.return_value = [Mock(), Mock()]  # 2 features
            
            # Create mock definitive total station points layer
            mock_definitive_layer = Mock()
            mock_definitive_layer.name.return_value = "Total Station Points"
            mock_definitive_layer.id.return_value = "definitive_layer_id"
            mock_definitive_layer.isEditable.return_value = False
            mock_definitive_layer.startEditing = Mock()
            mock_definitive_layer.addFeature = Mock(return_value=True)
            mock_definitive_layer.removeSelection = Mock()
            mock_definitive_layer.select = Mock()
            
            # Set up the project to return our mock layers
            # The method iterates through project.mapLayers().values() and looks for layers by name
            mock_project.mapLayers.return_value = {
                "csv_layer_id": mock_csv_layer,
                "definitive_layer_id": mock_definitive_layer
            }
            
            # Mock settings manager to return the definitive layer ID for total_station_points_layer
            def mock_get_value(key, default=None):
                if key == 'total_station_points_layer':
                    return "definitive_layer_id"
                return default
            
            self.dialog._settings_manager.get_value = mock_get_value
            
            # Call the copy method
            self.dialog._copy_temporary_to_definitive_layers()
            
            # Verify that the CSV layer was processed
            mock_csv_layer.getFeatures.assert_called_once()
            
            # Verify that the definitive layer was put in edit mode
            mock_definitive_layer.startEditing.assert_called_once()
            
            # Verify that features were added to the definitive layer
            self.assertEqual(mock_definitive_layer.addFeature.call_count, 2)
    
    def test_validate_button_exists(self):
        """Test that the validate button is created."""
        self.assertIsNotNone(self.dialog._validate_button)
        self.assertEqual(self.dialog._validate_button.text(), "Validate")
    
    def test_validate_button_success(self):
        """Test that validate button properly deletes the dock widget on success."""
        with patch.object(self.dialog, '_copy_temporary_to_definitive_layers') as mock_copy, \
             patch.object(self.dialog, '_delete_temporary_layers') as mock_delete, \
             patch.object(self.dialog, '_archive_imported_data') as mock_archive, \
             patch.object(self.dialog, 'deleteLater') as mock_delete_later:
            
            # Call the validate method
            self.dialog._handle_validate()
            
            # Verify all the validation steps were called
            mock_copy.assert_called_once()
            mock_delete.assert_called_once()
            mock_archive.assert_called_once()
            
            # Verify the dock widget was removed from the interface
            self.mock_iface.removeDockWidget.assert_called_once_with(self.dialog)
            
            # Verify the widget was deleted
            mock_delete_later.assert_called_once()
    
    def test_validate_button_error_handling(self):
        """Test that validate button handles errors gracefully."""
        with patch.object(self.dialog, '_copy_temporary_to_definitive_layers', side_effect=Exception("Test error")), \
             patch('qgis.PyQt.QtWidgets.QMessageBox.critical') as mock_critical:
            
            # Call the validate method
            self.dialog._handle_validate()
            
            # Verify error message was shown
            mock_critical.assert_called_once_with(
                self.dialog,
                "Validation Error",
                "An error occurred during validation: Test error"
            )
            
            # Verify the dock widget was NOT removed from the interface on error
            self.mock_iface.removeDockWidget.assert_not_called()
    
    def test_has_warnings_with_duplicates(self):
        """Test that _has_warnings returns True when duplicate warnings exist."""
        # Set up summary data with duplicate warnings
        self.dialog._summary_data.duplicate_objects_warnings = [WarningData("test", "area", "layer", "filter")]
        self.dialog._summary_data.skipped_numbers_warnings = []
        
        self.assertTrue(self.dialog._has_warnings())
    
    def test_has_warnings_with_skipped_numbers(self):
        """Test that _has_warnings returns True when skipped numbers warnings exist."""
        # Set up summary data with skipped numbers warnings
        self.dialog._summary_data.duplicate_objects_warnings = []
        self.dialog._summary_data.skipped_numbers_warnings = [WarningData("test", "area", "layer", "filter")]
        
        self.assertTrue(self.dialog._has_warnings())
    
    def test_has_warnings_with_both_types(self):
        """Test that _has_warnings returns True when both types of warnings exist."""
        # Set up summary data with both types of warnings
        self.dialog._summary_data.duplicate_objects_warnings = [WarningData("test1", "area1", "layer1", "filter1")]
        self.dialog._summary_data.skipped_numbers_warnings = [WarningData("test2", "area2", "layer2", "filter2")]
        
        self.assertTrue(self.dialog._has_warnings())
    
    def test_has_warnings_without_warnings(self):
        """Test that _has_warnings returns False when no warnings exist."""
        # Set up summary data with no warnings
        self.dialog._summary_data.duplicate_objects_warnings = []
        self.dialog._summary_data.skipped_numbers_warnings = []
        
        self.assertFalse(self.dialog._has_warnings())
    
    def test_confirm_validation_with_warnings_duplicates_only(self):
        """Test confirmation dialog when only duplicate warnings exist."""
        # Set up summary data with only duplicate warnings
        self.dialog._summary_data.duplicate_objects_warnings = [
            WarningData("test1", "area1", "layer1", "filter1"),
            WarningData("test2", "area2", "layer2", "filter2")
        ]
        self.dialog._summary_data.skipped_numbers_warnings = []
        
        with patch('qgis.PyQt.QtWidgets.QMessageBox.question') as mock_question:
            mock_question.return_value = QtWidgets.QMessageBox.Yes
            
            result = self.dialog._confirm_validation_with_warnings()
            
            # Verify the confirmation dialog was shown
            mock_question.assert_called_once()
            self.assertTrue(result)
    
    def test_confirm_validation_with_warnings_skipped_only(self):
        """Test confirmation dialog when only skipped numbers warnings exist."""
        # Set up summary data with only skipped numbers warnings
        self.dialog._summary_data.duplicate_objects_warnings = []
        self.dialog._summary_data.skipped_numbers_warnings = [
            WarningData("test1", "area1", "layer1", "filter1"),
            WarningData("test2", "area2", "layer2", "filter2"),
            WarningData("test3", "area3", "layer3", "filter3")
        ]
        
        with patch('qgis.PyQt.QtWidgets.QMessageBox.question') as mock_question:
            mock_question.return_value = QtWidgets.QMessageBox.No
            
            result = self.dialog._confirm_validation_with_warnings()
            
            # Verify the confirmation dialog was shown
            mock_question.assert_called_once()
            self.assertFalse(result)
    
    def test_confirm_validation_with_warnings_both_types(self):
        """Test confirmation dialog when both types of warnings exist."""
        # Set up summary data with both types of warnings
        self.dialog._summary_data.duplicate_objects_warnings = [
            WarningData("test1", "area1", "layer1", "filter1")
        ]
        self.dialog._summary_data.skipped_numbers_warnings = [
            WarningData("test2", "area2", "layer2", "filter2"),
            WarningData("test3", "area3", "layer3", "filter3")
        ]
        
        with patch('qgis.PyQt.QtWidgets.QMessageBox.question') as mock_question:
            mock_question.return_value = QtWidgets.QMessageBox.Yes
            
            result = self.dialog._confirm_validation_with_warnings()
            
            # Verify the confirmation dialog was shown
            mock_question.assert_called_once()
            self.assertTrue(result)
    
    def test_validate_with_warnings_user_confirms(self):
        """Test validation when warnings exist and user confirms."""
        # Set up summary data with warnings
        self.dialog._summary_data.duplicate_objects_warnings = [WarningData("test", "area", "layer", "filter")]
        self.dialog._summary_data.skipped_numbers_warnings = []
        
        with patch.object(self.dialog, '_has_warnings', return_value=True), \
             patch.object(self.dialog, '_confirm_validation_with_warnings', return_value=True), \
             patch.object(self.dialog, '_copy_temporary_to_definitive_layers') as mock_copy, \
             patch.object(self.dialog, '_delete_temporary_layers') as mock_delete, \
             patch.object(self.dialog, '_archive_imported_data') as mock_archive, \
             patch.object(self.dialog, 'deleteLater') as mock_delete_later:
            
            # Call the validate method
            self.dialog._handle_validate()
            
            # Verify that all validation steps were executed
            mock_copy.assert_called_once()
            mock_delete.assert_called_once()
            mock_archive.assert_called_once()
            mock_delete_later.assert_called_once()
    
    def test_validate_with_warnings_user_cancels(self):
        """Test validation when warnings exist and user cancels."""
        # Set up summary data with warnings
        self.dialog._summary_data.duplicate_objects_warnings = [WarningData("test", "area", "layer", "filter")]
        self.dialog._summary_data.skipped_numbers_warnings = []
        
        with patch.object(self.dialog, '_has_warnings', return_value=True), \
             patch.object(self.dialog, '_confirm_validation_with_warnings', return_value=False), \
             patch.object(self.dialog, '_copy_temporary_to_definitive_layers') as mock_copy, \
             patch.object(self.dialog, '_delete_temporary_layers') as mock_delete, \
             patch.object(self.dialog, '_archive_imported_data') as mock_archive, \
             patch.object(self.dialog, 'deleteLater') as mock_delete_later:
            
            # Call the validate method
            self.dialog._handle_validate()
            
            # Verify that no validation steps were executed
            mock_copy.assert_not_called()
            mock_delete.assert_not_called()
            mock_archive.assert_not_called()
            mock_delete_later.assert_not_called()
    
    def test_validate_without_warnings(self):
        """Test validation when no warnings exist."""
        # Set up summary data with no warnings
        self.dialog._summary_data.duplicate_objects_warnings = []
        self.dialog._summary_data.skipped_numbers_warnings = []
        
        with patch.object(self.dialog, '_has_warnings', return_value=False), \
             patch.object(self.dialog, '_confirm_validation_with_warnings') as mock_confirm, \
             patch.object(self.dialog, '_copy_temporary_to_definitive_layers') as mock_copy, \
             patch.object(self.dialog, '_delete_temporary_layers') as mock_delete, \
             patch.object(self.dialog, '_archive_imported_data') as mock_archive, \
             patch.object(self.dialog, 'deleteLater') as mock_delete_later:
            
            # Call the validate method
            self.dialog._handle_validate()
            
            # Verify that confirmation was not called
            mock_confirm.assert_not_called()
            
            # Verify that all validation steps were executed
            mock_copy.assert_called_once()
            mock_delete.assert_called_once()
            mock_archive.assert_called_once()
            mock_delete_later.assert_called_once()


if __name__ == '__main__':
    unittest.main() 