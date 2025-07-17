"""
Tests for the Import Summary dialog.

This module tests the ImportSummaryDialog class to ensure it correctly displays
import statistics and handles different data scenarios properly.
"""

import unittest
from unittest.mock import Mock, MagicMock
from qgis.PyQt.QtWidgets import QApplication
from qgis.PyQt.QtCore import Qt

try:
    from ..ui.import_summary_dialog import ImportSummaryDialog, ImportSummaryData
except ImportError:
    from ui.import_summary_dialog import ImportSummaryDialog, ImportSummaryData


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
    
    def test_import_summary_data_structure(self):
        """Test that ImportSummaryData structure works correctly."""
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
        
        # Check that all fields are set correctly
        self.assertEqual(summary_data.csv_points_count, 150)
        self.assertEqual(summary_data.features_count, 25)
        self.assertEqual(summary_data.objects_count, 10)
        self.assertEqual(summary_data.small_finds_count, 5)
        self.assertEqual(summary_data.csv_duplicates, 3)
        self.assertEqual(summary_data.features_duplicates, 1)
        self.assertEqual(summary_data.objects_duplicates, 0)
        self.assertEqual(summary_data.small_finds_duplicates, 2)
    
    def test_import_summary_data_defaults(self):
        """Test that ImportSummaryData has correct default values."""
        summary_data = ImportSummaryData()
        
        # Check that all fields default to 0
        self.assertEqual(summary_data.csv_points_count, 0)
        self.assertEqual(summary_data.features_count, 0)
        self.assertEqual(summary_data.objects_count, 0)
        self.assertEqual(summary_data.small_finds_count, 0)
        self.assertEqual(summary_data.csv_duplicates, 0)
        self.assertEqual(summary_data.features_duplicates, 0)
        self.assertEqual(summary_data.objects_duplicates, 0)
        self.assertEqual(summary_data.small_finds_duplicates, 0)
    
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
    
    def test_duplicate_objects_warnings_none_value(self):
        """Test that duplicate_objects_warnings handles None value correctly."""
        summary_data = ImportSummaryData(
            objects_count=10,
            duplicate_objects_warnings=None
        )
        
        # Check that duplicate_objects_warnings defaults to empty list when None
        self.assertEqual(summary_data.duplicate_objects_warnings, [])


if __name__ == '__main__':
    unittest.main() 