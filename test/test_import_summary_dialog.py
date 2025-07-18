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


if __name__ == '__main__':
    unittest.main() 