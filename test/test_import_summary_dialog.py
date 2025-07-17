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
    from ..services.translation_service import QGISTranslationService
except ImportError:
    from ui.import_summary_dialog import ImportSummaryDialog, ImportSummaryData
    from services.translation_service import QGISTranslationService


class TestImportSummaryDialog(unittest.TestCase):
    """Test cases for the ImportSummaryDialog class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock QApplication if one doesn't exist
        if not QApplication.instance():
            self.app = QApplication([])
        else:
            self.app = QApplication.instance()
        
        # Create mock translation service
        self.mock_translation_service = Mock(spec=QGISTranslationService)
        self.mock_translation_service.translate.return_value = "Translated"
    
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
        
        dialog = ImportSummaryDialog(
            summary_data=summary_data,
            translation_service=self.mock_translation_service
        )
        
        # Check that the dialog was created
        self.assertIsNotNone(dialog)
        # The window title should be translated, so it should be "Translated"
        self.assertEqual(dialog.windowTitle(), "Translated")
        self.assertTrue(dialog.isModal())
    
    def test_csv_section_display(self):
        """Test that CSV section is displayed correctly when CSV data is present."""
        summary_data = ImportSummaryData(csv_points_count=150, csv_duplicates=3)
        
        dialog = ImportSummaryDialog(
            summary_data=summary_data,
            translation_service=self.mock_translation_service
        )
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_features_section_display(self):
        """Test that features section is displayed correctly when features data is present."""
        summary_data = ImportSummaryData(features_count=25, features_duplicates=1)
        
        dialog = ImportSummaryDialog(
            summary_data=summary_data,
            translation_service=self.mock_translation_service
        )
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_objects_section_display(self):
        """Test that objects section is displayed correctly when objects data is present."""
        summary_data = ImportSummaryData(objects_count=10, objects_duplicates=0)
        
        dialog = ImportSummaryDialog(
            summary_data=summary_data,
            translation_service=self.mock_translation_service
        )
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_small_finds_section_display(self):
        """Test that small finds section is displayed correctly when small finds data is present."""
        summary_data = ImportSummaryData(small_finds_count=5, small_finds_duplicates=2)
        
        dialog = ImportSummaryDialog(
            summary_data=summary_data,
            translation_service=self.mock_translation_service
        )
        
        # The dialog should have been created successfully
        self.assertIsNotNone(dialog)
    
    def test_empty_summary_data(self):
        """Test that dialog handles empty summary data gracefully."""
        summary_data = ImportSummaryData()
        
        dialog = ImportSummaryDialog(
            summary_data=summary_data,
            translation_service=self.mock_translation_service
        )
        
        # The dialog should have been created successfully even with no data
        self.assertIsNotNone(dialog)
    
    def test_translation_service_usage(self):
        """Test that the dialog uses the translation service correctly."""
        summary_data = ImportSummaryData(csv_points_count=100)
        
        dialog = ImportSummaryDialog(
            summary_data=summary_data,
            translation_service=self.mock_translation_service
        )
        
        # Test that tr method uses translation service
        translated = dialog.tr("Test message")
        self.assertEqual(translated, "Translated")
        self.mock_translation_service.translate.assert_called_with("Test message")
    
    def test_no_translation_service(self):
        """Test that the dialog works without a translation service."""
        summary_data = ImportSummaryData(csv_points_count=100)
        
        dialog = ImportSummaryDialog(
            summary_data=summary_data,
            translation_service=None
        )
        
        # Test that tr method returns original message when no translation service
        message = "Test message"
        translated = dialog.tr(message)
        self.assertEqual(translated, message)
    
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


if __name__ == '__main__':
    unittest.main() 