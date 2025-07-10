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
        
        self.csv_service = CSVImportService(self.mock_iface)
        
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