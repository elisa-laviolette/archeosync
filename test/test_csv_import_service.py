"""
Tests for CSV import service.

This module tests the CSV import functionality including:
- CSV file validation (X, Y, Z columns)
- Column matching across multiple CSV files
- PointZ vector layer creation
- Loading into QGIS project
"""

import pytest
import tempfile
import os
import csv
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any

try:
    from ..services.csv_import_service import CSVImportService
    from ..core.interfaces import ICSVImportService
except ImportError:
    from services.csv_import_service import CSVImportService
    from core.interfaces import ICSVImportService


class TestCSVImportService:
    """Test cases for CSV import service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_iface = Mock()
        self.mock_project = Mock()
        self.mock_iface.mapCanvas.return_value.mapSettings.return_value.destinationCrs.return_value = Mock()
        
        # Create mock services for the new parameters
        self.mock_file_system_service = Mock()
        self.mock_settings_manager = Mock()
        
        self.csv_service = CSVImportService(self.mock_iface, self.mock_file_system_service, self.mock_settings_manager)
        
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.test_csv_files = []
    
    def teardown_method(self):
        """Clean up test fixtures."""
        # Clean up temporary files
        for file_path in self.test_csv_files:
            if os.path.exists(file_path):
                os.remove(file_path)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    def _create_test_csv(self, filename: str, headers: List[str], data: List[List[str]]) -> str:
        """Create a test CSV file with given headers and data."""
        file_path = os.path.join(self.temp_dir, filename)
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            for row in data:
                writer.writerow(row)
        
        self.test_csv_files.append(file_path)
        return file_path
    
    def test_validate_csv_files_with_valid_files(self):
        """Test validation of CSV files with valid X, Y, Z columns."""
        # Create test CSV files with valid columns
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Z", "Description", "Type"],
            [["100.0", "200.0", "10.5", "Point 1", "Feature"]]
        )
        csv2 = self._create_test_csv(
            "test2.csv", 
            ["X", "Y", "Z", "Notes"],
            [["150.0", "250.0", "15.2", "Point 2"]]
        )
        
        csv_files = [csv1, csv2]
        result = self.csv_service.validate_csv_files(csv_files)
        
        assert result.is_valid is True
        assert "All CSV files have required X, Y, Z columns" in result.message
    
    def test_validate_csv_files_missing_required_columns(self):
        """Test validation fails when CSV files are missing required columns."""
        # Create test CSV file missing Z column
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Description"],
            [["100.0", "200.0", "Point 1"]]
        )
        
        csv_files = [csv1]
        result = self.csv_service.validate_csv_files(csv_files)
        
        assert result.is_valid is False
        assert "Missing required column: Z" in result.message
    
    def test_validate_csv_files_missing_x_column(self):
        """Test validation fails when CSV file is missing X column."""
        csv1 = self._create_test_csv(
            "test1.csv",
            ["Y", "Z", "Description"],
            [["200.0", "10.5", "Point 1"]]
        )
        
        csv_files = [csv1]
        result = self.csv_service.validate_csv_files(csv_files)
        
        assert result.is_valid is False
        assert "Missing required column: X" in result.message
    
    def test_validate_csv_files_missing_y_column(self):
        """Test validation fails when CSV file is missing Y column."""
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Z", "Description"],
            [["100.0", "10.5", "Point 1"]]
        )
        
        csv_files = [csv1]
        result = self.csv_service.validate_csv_files(csv_files)
        
        assert result.is_valid is False
        assert "Missing required column: Y" in result.message
    
    def test_validate_csv_files_case_insensitive_columns(self):
        """Test validation works with case-insensitive column names."""
        csv1 = self._create_test_csv(
            "test1.csv",
            ["x", "y", "z", "Description"],
            [["100.0", "200.0", "10.5", "Point 1"]]
        )
        
        csv_files = [csv1]
        result = self.csv_service.validate_csv_files(csv_files)
        
        assert result.is_valid is True
        assert "All CSV files have required X, Y, Z columns" in result.message
    
    def test_validate_csv_files_empty_file(self):
        """Test validation fails with empty CSV file."""
        csv1 = self._create_test_csv("test1.csv", [], [])
        
        csv_files = [csv1]
        result = self.csv_service.validate_csv_files(csv_files)
        
        assert result.is_valid is False
        assert "Empty CSV file" in result.message
    
    def test_validate_csv_files_nonexistent_file(self):
        """Test validation fails with nonexistent file."""
        csv_files = ["/nonexistent/file.csv"]
        result = self.csv_service.validate_csv_files(csv_files)
        
        assert result.is_valid is False
        assert "File not found" in result.message
    
    def test_get_column_mapping_same_columns(self):
        """Test column mapping when all CSV files have same columns."""
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Z", "Description", "Type"],
            [["100.0", "200.0", "10.5", "Point 1", "Feature"]]
        )
        csv2 = self._create_test_csv(
            "test2.csv",
            ["X", "Y", "Z", "Description", "Type"],
            [["150.0", "250.0", "15.2", "Point 2", "Feature"]]
        )
        
        csv_files = [csv1, csv2]
        mapping = self.csv_service.get_column_mapping(csv_files)
        
        assert mapping == {
            "X": ["X", "X"],
            "Y": ["Y", "Y"], 
            "Z": ["Z", "Z"],
            "Description": ["Description", "Description"],
            "Type": ["Type", "Type"]
        }
    
    def test_get_column_mapping_different_columns(self):
        """Test column mapping when CSV files have different columns."""
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Z", "Description", "Type"],
            [["100.0", "200.0", "10.5", "Point 1", "Feature"]]
        )
        csv2 = self._create_test_csv(
            "test2.csv",
            ["X", "Y", "Z", "Notes", "Category"],
            [["150.0", "250.0", "15.2", "Point 2", "Feature"]]
        )
        
        csv_files = [csv1, csv2]
        mapping = self.csv_service.get_column_mapping(csv_files)
        
        assert mapping == {
            "X": ["X", "X"],
            "Y": ["Y", "Y"],
            "Z": ["Z", "Z"],
            "Description": ["Description", None],
            "Type": ["Type", None],
            "Notes": [None, "Notes"],
            "Category": [None, "Category"]
        }
    
    def test_get_column_mapping_case_insensitive(self):
        """Test column mapping handles case-insensitive column names."""
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Z", "Description"],
            [["100.0", "200.0", "10.5", "Point 1"]]
        )
        csv2 = self._create_test_csv(
            "test2.csv",
            ["x", "y", "z", "description"],
            [["150.0", "250.0", "15.2", "Point 2"]]
        )
        
        csv_files = [csv1, csv2]
        mapping = self.csv_service.get_column_mapping(csv_files)
        
        assert mapping == {
            "X": ["X", "x"],
            "Y": ["Y", "y"],
            "Z": ["Z", "z"],
            "Description": ["Description", "description"]
        }
    
    @patch('archeosync.services.csv_import_service.QgsVectorLayer')
    @patch('archeosync.services.csv_import_service.QgsFeature')
    @patch('archeosync.services.csv_import_service.QgsGeometry')
    @patch('archeosync.services.csv_import_service.QgsPointXY')
    @patch('qgis.core.QgsProject')
    def test_import_csv_files_creates_pointz_layer(self, mock_project, mock_point, mock_geometry, mock_feature, mock_layer):
        """Test that importing CSV files creates a PointZ vector layer."""
        # Create test CSV files
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Z", "Description"],
            [["100.0", "200.0", "10.5", "Point 1"]]
        )
        csv2 = self._create_test_csv(
            "test2.csv",
            ["X", "Y", "Z", "Notes"],
            [["150.0", "250.0", "15.2", "Point 2"]]
        )
        
        # Mock QGIS objects
        mock_layer_instance = Mock()
        mock_layer.return_value = mock_layer_instance
        mock_layer_instance.isValid.return_value = True
        # Mock fields() to return iterable of mock fields with name()
        mock_field1 = Mock()
        mock_field1.name.return_value = "X"
        mock_field2 = Mock()
        mock_field2.name.return_value = "Y"
        mock_field3 = Mock()
        mock_field3.name.return_value = "Z"
        mock_field4 = Mock()
        mock_field4.name.return_value = "Description"
        mock_field5 = Mock()
        mock_field5.name.return_value = "Notes"
        mock_layer_instance.fields.return_value = [mock_field1, mock_field2, mock_field3, mock_field4, mock_field5]
        mock_layer_instance.startEditing = Mock()
        mock_layer_instance.addFeature = Mock()
        mock_layer_instance.commitChanges = Mock()
        
        mock_feature_instance = Mock()
        mock_feature.return_value = mock_feature_instance
        mock_feature_instance.setId = Mock()
        mock_feature_instance.setGeometry = Mock()
        mock_feature_instance.setAttribute = Mock()
        
        mock_geometry_instance = Mock()
        mock_geometry.return_value = mock_geometry_instance
        mock_geometry.fromPointXY = Mock(return_value=mock_geometry_instance)
        
        mock_point_instance = Mock()
        mock_point.return_value = mock_point_instance
        
        # Mock QgsProject.instance()
        mock_project_instance = Mock()
        mock_project.instance.return_value = mock_project_instance
        mock_project_instance.addMapLayer = Mock()
        
        csv_files = [csv1, csv2]
        result = self.csv_service.import_csv_files(csv_files)
        
        assert result.is_valid is True
        assert "Successfully imported" in result.message
        
        # Verify layer was created and added to project
        mock_layer.assert_called_once()
        mock_project_instance.addMapLayer.assert_called_once_with(mock_layer_instance)
    
    def test_import_csv_files_invalid_files(self):
        """Test import fails with invalid CSV files."""
        # Create invalid CSV file (missing Z column)
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Description"],
            [["100.0", "200.0", "Point 1"]]
        )
        
        csv_files = [csv1]
        result = self.csv_service.import_csv_files(csv_files)
        
        assert result.is_valid is False
        assert "Missing required column: Z" in result.message
    
    def test_import_csv_files_empty_list(self):
        """Test import fails with empty file list."""
        csv_files = []
        result = self.csv_service.import_csv_files(csv_files)
        
        assert result.is_valid is False
        assert "No CSV files provided" in result.message
    
    @patch('archeosync.services.csv_import_service.QgsVectorLayer')
    def test_import_csv_files_layer_creation_fails(self, mock_layer):
        """Test import fails when layer creation fails."""
        # Create valid CSV file
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Z", "Description"],
            [["100.0", "200.0", "10.5", "Point 1"]]
        )
        
        # Mock layer creation failure
        mock_layer_instance = Mock()
        mock_layer.return_value = mock_layer_instance
        mock_layer_instance.isValid.return_value = False
        
        csv_files = [csv1]
        result = self.csv_service.import_csv_files(csv_files)
        
        assert result.is_valid is False
        assert "Failed to create vector layer" in result.message
    
    def test_import_csv_files_archives_files_when_configured(self):
        """Test that CSV files are tracked for later archiving after successful import when archive folder is configured."""
        # Create valid CSV file
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Z", "Description"],
            [["100.0", "200.0", "10.5", "Point 1"]]
        )
        
        # Mock settings to return archive folder
        self.mock_settings_manager.get_value.return_value = "/archive/path"
        
        # Mock file system service
        self.mock_file_system_service.path_exists.return_value = True
        self.mock_file_system_service.create_directory.return_value = True
        self.mock_file_system_service.move_file.return_value = True
        
        # Mock QGIS objects
        with patch('archeosync.services.csv_import_service.QgsVectorLayer') as mock_layer, \
             patch('archeosync.services.csv_import_service.QgsFeature') as mock_feature, \
             patch('archeosync.services.csv_import_service.QgsGeometry') as mock_geometry, \
             patch('archeosync.services.csv_import_service.QgsPointXY') as mock_point:
            
            mock_layer_instance = Mock()
            mock_layer.return_value = mock_layer_instance
            mock_layer_instance.isValid.return_value = True
            mock_layer_instance.fields.return_value = []
            mock_layer_instance.startEditing = Mock()
            mock_layer_instance.addFeature = Mock()
            mock_layer_instance.commitChanges = Mock()
            
            mock_feature_instance = Mock()
            mock_feature.return_value = mock_feature_instance
            mock_feature_instance.setId = Mock()
            mock_feature_instance.setGeometry = Mock()
            mock_feature_instance.setAttribute = Mock()
            
            mock_geometry_instance = Mock()
            mock_geometry.return_value = mock_geometry_instance
            mock_geometry.fromPointXY = Mock(return_value=mock_geometry_instance)
            
            mock_point_instance = Mock()
            mock_point.return_value = mock_point_instance
            
            with patch('qgis.core.QgsProject') as mock_project:
                mock_project_instance = Mock()
                mock_project.instance.return_value = mock_project_instance
                mock_project_instance.addMapLayer = Mock()
                
                csv_files = [csv1]
                result = self.csv_service.import_csv_files(csv_files)
                
                # Verify import was successful
                assert result.is_valid is True
                
                # Verify files are tracked for later archiving
                tracked_files = self.csv_service.get_last_imported_files()
                assert csv1 in tracked_files
                
                # Verify no archiving happened immediately
                self.mock_file_system_service.move_file.assert_not_called()
                
                # Now test the archiving functionality
                self.csv_service.archive_last_imported_files()
                
                # Verify archive folder was checked and file was moved
                self.mock_settings_manager.get_value.assert_called_with('csv_archive_folder', '')
                self.mock_file_system_service.move_file.assert_called_once()
    
    def test_import_csv_files_does_not_archive_when_not_configured(self):
        """Test that CSV files are tracked for later archiving but not archived when archive folder is not configured."""
        # Create valid CSV file
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Z", "Description"],
            [["100.0", "200.0", "10.5", "Point 1"]]
        )
        
        # Mock settings to return empty archive folder
        self.mock_settings_manager.get_value.return_value = ""
        
        # Mock QGIS objects
        with patch('archeosync.services.csv_import_service.QgsVectorLayer') as mock_layer, \
             patch('archeosync.services.csv_import_service.QgsFeature') as mock_feature, \
             patch('archeosync.services.csv_import_service.QgsGeometry') as mock_geometry, \
             patch('archeosync.services.csv_import_service.QgsPointXY') as mock_point:
            
            mock_layer_instance = Mock()
            mock_layer.return_value = mock_layer_instance
            mock_layer_instance.isValid.return_value = True
            mock_layer_instance.fields.return_value = []
            mock_layer_instance.startEditing = Mock()
            mock_layer_instance.addFeature = Mock()
            mock_layer_instance.commitChanges = Mock()
            
            mock_feature_instance = Mock()
            mock_feature.return_value = mock_feature_instance
            mock_feature_instance.setId = Mock()
            mock_feature_instance.setGeometry = Mock()
            mock_feature_instance.setAttribute = Mock()
            
            mock_geometry_instance = Mock()
            mock_geometry.return_value = mock_geometry_instance
            mock_geometry.fromPointXY = Mock(return_value=mock_geometry_instance)
            
            mock_point_instance = Mock()
            mock_point.return_value = mock_point_instance
            
            with patch('qgis.core.QgsProject') as mock_project:
                mock_project_instance = Mock()
                mock_project.instance.return_value = mock_project_instance
                mock_project_instance.addMapLayer = Mock()
                
                csv_files = [csv1]
                result = self.csv_service.import_csv_files(csv_files)
                
                # Verify import was successful
                assert result.is_valid is True
                
                # Verify files are tracked for later archiving
                tracked_files = self.csv_service.get_last_imported_files()
                assert csv1 in tracked_files
                
                # Verify no archiving happened immediately
                self.mock_file_system_service.move_file.assert_not_called()
                
                # Now test the archiving functionality with no archive folder configured
                self.csv_service.archive_last_imported_files()
                
                # Verify archive folder was checked but no file operations were performed
                self.mock_settings_manager.get_value.assert_called_with('csv_archive_folder', '')
                self.mock_file_system_service.move_file.assert_not_called()
    
    @patch('archeosync.services.csv_import_service.QgsVectorLayer')
    @patch('archeosync.services.csv_import_service.QgsFeature')
    @patch('archeosync.services.csv_import_service.QgsGeometry')
    @patch('archeosync.services.csv_import_service.QgsPointXY')
    @patch('qgis.core.QgsProject')
    def test_import_csv_files_uses_project_crs(self, mock_project, mock_point, mock_geometry, mock_feature, mock_layer):
        """Test that importing CSV files uses the project CRS instead of hardcoded EPSG:4326."""
        # Create test CSV file
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Z", "Description"],
            [["100.0", "200.0", "10.5", "Point 1"]]
        )
        
        # Mock QGIS objects
        mock_layer_instance = Mock()
        mock_layer.return_value = mock_layer_instance
        mock_layer_instance.isValid.return_value = True
        mock_layer_instance.fields.return_value = []
        mock_layer_instance.startEditing = Mock()
        mock_layer_instance.addFeature = Mock()
        mock_layer_instance.commitChanges = Mock()
        
        mock_feature_instance = Mock()
        mock_feature.return_value = mock_feature_instance
        mock_feature_instance.setId = Mock()
        mock_feature_instance.setGeometry = Mock()
        mock_feature_instance.setAttribute = Mock()
        
        mock_geometry_instance = Mock()
        mock_geometry.return_value = mock_geometry_instance
        mock_geometry.fromPointXY = Mock(return_value=mock_geometry_instance)
        
        mock_point_instance = Mock()
        mock_point.return_value = mock_point_instance
        
        # Mock QgsProject.instance() with custom CRS
        mock_project_instance = Mock()
        mock_project.instance.return_value = mock_project_instance
        mock_project_instance.addMapLayer = Mock()
        
        # Mock project CRS to be different from hardcoded EPSG:4326
        mock_crs = Mock()
        mock_crs.authid.return_value = "EPSG:3857"  # Web Mercator
        mock_project_instance.crs.return_value = mock_crs
        
        csv_files = [csv1]
        result = self.csv_service.import_csv_files(csv_files)
        
        assert result.is_valid is True
        assert "Successfully imported" in result.message
        
        # Verify layer was created with project CRS
        mock_layer.assert_called_once()
        call_args = mock_layer.call_args[0]
        layer_uri = call_args[0]
        
        # Check that the URI contains the project CRS, not hardcoded EPSG:4326
        assert "crs=EPSG:3857" in layer_uri
        assert "crs=EPSG:4326" not in layer_uri 

    def test_detect_field_types_integer_fields(self):
        """Test field type detection for integer fields."""
        # Create test CSV with integer data
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Z", "ID", "Count", "Code"],
            [
                ["100.0", "200.0", "10.5", "1", "5", "ABC123"],
                ["150.0", "250.0", "15.2", "2", "10", "DEF456"],
                ["200.0", "300.0", "20.1", "3", "15", "GHI789"]
            ]
        )
        
        column_mapping = {
            "X": ["X"],
            "Y": ["Y"],
            "Z": ["Z"],
            "ID": ["ID"],
            "Count": ["Count"],
            "Code": ["Code"]
        }
        
        field_types = self.csv_service._detect_field_types([csv1], column_mapping)
        
        assert field_types["X"] == "real"
        assert field_types["Y"] == "real"
        assert field_types["Z"] == "real"
        assert field_types["ID"] == "integer"
        assert field_types["Count"] == "integer"
        assert field_types["Code"] == "string"
    
    def test_detect_field_types_real_fields(self):
        """Test field type detection for real (float) fields."""
        # Create test CSV with real data
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Z", "Latitude", "Longitude", "Elevation"],
            [
                ["100.0", "200.0", "10.5", "45.123456", "-73.987654", "100.5"],
                ["150.0", "250.0", "15.2", "45.234567", "-73.876543", "101.2"],
                ["200.0", "300.0", "20.1", "45.345678", "-73.765432", "102.8"]
            ]
        )
        
        column_mapping = {
            "X": ["X"],
            "Y": ["Y"],
            "Z": ["Z"],
            "Latitude": ["Latitude"],
            "Longitude": ["Longitude"],
            "Elevation": ["Elevation"]
        }
        
        field_types = self.csv_service._detect_field_types([csv1], column_mapping)
        
        assert field_types["X"] == "real"
        assert field_types["Y"] == "real"
        assert field_types["Z"] == "real"
        assert field_types["Latitude"] == "real"
        assert field_types["Longitude"] == "real"
        assert field_types["Elevation"] == "real"
    
    def test_detect_field_types_mixed_data(self):
        """Test field type detection with mixed data types."""
        # Create test CSV with mixed data
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Z", "MixedField", "StringField", "NumericField"],
            [
                ["100.0", "200.0", "10.5", "123", "Text", "42"],
                ["150.0", "250.0", "15.2", "456", "More Text", "84"],
                ["200.0", "300.0", "20.1", "ABC", "Even More", "126"]
            ]
        )
        
        column_mapping = {
            "X": ["X"],
            "Y": ["Y"],
            "Z": ["Z"],
            "MixedField": ["MixedField"],
            "StringField": ["StringField"],
            "NumericField": ["NumericField"]
        }
        
        field_types = self.csv_service._detect_field_types([csv1], column_mapping)
        
        assert field_types["X"] == "real"
        assert field_types["Y"] == "real"
        assert field_types["Z"] == "real"
        assert field_types["MixedField"] == "string"  # Mixed data defaults to string
        assert field_types["StringField"] == "string"
        assert field_types["NumericField"] == "integer"
    
    def test_detect_field_types_empty_values(self):
        """Test field type detection with empty values."""
        # Create test CSV with empty values
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Z", "EmptyField", "PartialEmpty"],
            [
                ["100.0", "200.0", "10.5", "", "1"],
                ["150.0", "250.0", "15.2", "", "2"],
                ["200.0", "300.0", "20.1", "", ""]
            ]
        )
        
        column_mapping = {
            "X": ["X"],
            "Y": ["Y"],
            "Z": ["Z"],
            "EmptyField": ["EmptyField"],
            "PartialEmpty": ["PartialEmpty"]
        }
        
        field_types = self.csv_service._detect_field_types([csv1], column_mapping)
        
        assert field_types["X"] == "real"
        assert field_types["Y"] == "real"
        assert field_types["Z"] == "real"
        assert field_types["EmptyField"] == "string"  # Default for empty fields
        assert field_types["PartialEmpty"] == "integer"  # Can be converted to int
    
    def test_detect_field_types_multiple_files(self):
        """Test field type detection across multiple CSV files."""
        # Create test CSV files with different data
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Z", "ID", "Description"],
            [
                ["100.0", "200.0", "10.5", "1", "Point 1"],
                ["150.0", "250.0", "15.2", "2", "Point 2"]
            ]
        )
        
        csv2 = self._create_test_csv(
            "test2.csv",
            ["X", "Y", "Z", "ID", "Notes"],
            [
                ["200.0", "300.0", "20.1", "3", "Point 3"],
                ["250.0", "350.0", "25.8", "4", "Point 4"]
            ]
        )
        
        column_mapping = {
            "X": ["X", "X"],
            "Y": ["Y", "Y"],
            "Z": ["Z", "Z"],
            "ID": ["ID", "ID"],
            "Description": ["Description", None],
            "Notes": [None, "Notes"]
        }
        
        field_types = self.csv_service._detect_field_types([csv1, csv2], column_mapping)
        
        assert field_types["X"] == "real"
        assert field_types["Y"] == "real"
        assert field_types["Z"] == "real"
        assert field_types["ID"] == "integer"
        assert field_types["Description"] == "string"
        assert field_types["Notes"] == "string"
    
    def test_detect_field_types_string_id_field(self):
        """Test field type detection for string ID fields (like PINC150725)."""
        # Create test CSV with string ID values
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Z", "ID", "Code"],
            [
                ["100.0", "200.0", "10.5", "PINC150725", "ABC123"],
                ["150.0", "250.0", "15.2", "PINC150726", "DEF456"],
                ["200.0", "300.0", "20.1", "PINC150727", "GHI789"]
            ]
        )
        
        column_mapping = {
            "X": ["X"],
            "Y": ["Y"],
            "Z": ["Z"],
            "ID": ["ID"],
            "Code": ["Code"]
        }
        
        field_types = self.csv_service._detect_field_types([csv1], column_mapping)
        
        assert field_types["X"] == "real"
        assert field_types["Y"] == "real"
        assert field_types["Z"] == "real"
        assert field_types["ID"] == "string"  # String IDs should be detected as string
        assert field_types["Code"] == "string"
    
    def test_detect_field_types_with_invalid_files(self):
        """Test field type detection handles invalid files gracefully."""
        # Create test CSV with valid data
        csv1 = self._create_test_csv(
            "test1.csv",
            ["X", "Y", "Z", "ID"],
            [
                ["100.0", "200.0", "10.5", "1"],
                ["150.0", "250.0", "15.2", "2"]
            ]
        )
        
        column_mapping = {
            "X": ["X"],
            "Y": ["Y"],
            "Z": ["Z"],
            "ID": ["ID"]
        }
        
        # Test with non-existent file
        field_types = self.csv_service._detect_field_types(["/nonexistent/file.csv"], column_mapping)
        
        # Should default to string for all fields when file can't be read
        assert field_types["X"] == "real"  # Required columns are always real
        assert field_types["Y"] == "real"
        assert field_types["Z"] == "real"
        assert field_types["ID"] == "string" 