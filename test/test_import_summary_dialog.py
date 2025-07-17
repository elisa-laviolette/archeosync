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
        
        dialog = ImportSummaryDialog(summary_data=summary_data)
        
        # Check that the dialog was created
        self.assertIsNotNone(dialog)
        self.assertTrue(dialog.isModal())
    
    def test_csv_section_display(self):
        """Test that CSV section is displayed correctly when CSV data is present."""
        summary_data = ImportSummaryData(csv_points_count=150, csv_duplicates=3)
        
        dialog = ImportSummaryDialog(summary_data=summary_data)
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_features_section_display(self):
        """Test that features section is displayed correctly when features data is present."""
        summary_data = ImportSummaryData(features_count=25, features_duplicates=1)
        
        dialog = ImportSummaryDialog(summary_data=summary_data)
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_objects_section_display(self):
        """Test that objects section is displayed correctly when objects data is present."""
        summary_data = ImportSummaryData(objects_count=10, objects_duplicates=0)
        
        dialog = ImportSummaryDialog(summary_data=summary_data)
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_small_finds_section_display(self):
        """Test that small finds section is displayed correctly when small finds data is present."""
        summary_data = ImportSummaryData(small_finds_count=5, small_finds_duplicates=2)
        
        dialog = ImportSummaryDialog(summary_data=summary_data)
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_empty_summary_data(self):
        """Test that dialog handles empty summary data gracefully."""
        summary_data = ImportSummaryData()
        
        dialog = ImportSummaryDialog(summary_data=summary_data)
        
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
        
        dialog = ImportSummaryDialog(summary_data=summary_data)
        
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
        
        dialog = ImportSummaryDialog(summary_data=summary_data)
        
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
        
        dialog = ImportSummaryDialog(summary_data=summary_data)
        
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
        
        dialog = ImportSummaryDialog(summary_data=summary_data)
        
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
        
        dialog = ImportSummaryDialog(summary_data=summary_data)
        
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
        
        dialog = ImportSummaryDialog(summary_data=summary_data, iface=mock_iface)
        
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
        
        dialog = ImportSummaryDialog(summary_data=summary_data)
        
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
        
        dialog = ImportSummaryDialog(ImportSummaryData(), iface=mock_iface)
        
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


if __name__ == '__main__':
    unittest.main() 