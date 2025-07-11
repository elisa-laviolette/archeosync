"""
CSV Import Service for ArcheoSync plugin.

This module provides functionality for importing CSV files containing point data
into QGIS as PointZ vector layers. It handles validation of required columns (X, Y, Z),
column mapping across multiple files, and layer creation.

Key Features:
- Validates CSV files have required X, Y, Z columns (case-insensitive)
- Maps columns across multiple CSV files
- Creates PointZ vector layers from CSV data
- Loads layers into QGIS project as temporary layers
- Handles different column names and data types

Architecture Benefits:
- Single Responsibility: Focuses only on CSV import operations
- Dependency Inversion: Implements ICSVImportService interface
- Testability: All QGIS dependencies can be mocked
- Extensibility: Easy to add new import formats or validation rules

Usage:
    csv_service = CSVImportService(qgis_iface)
    
    # Validate CSV files
    result = csv_service.validate_csv_files(['file1.csv', 'file2.csv'])
    if result.is_valid:
        # Import files
        import_result = csv_service.import_csv_files(['file1.csv', 'file2.csv'])
"""

import csv
import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

try:
    from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY, QgsField
    from qgis.PyQt.QtCore import QVariant
    from ..core.interfaces import ICSVImportService, ValidationResult
except ImportError:
    # For testing without QGIS
    QgsVectorLayer = None
    QgsFeature = None
    QgsGeometry = None
    QgsPointXY = None
    QgsField = None
    QVariant = None
    from core.interfaces import ICSVImportService, ValidationResult


class CSVImportService(ICSVImportService):
    """
    Service for importing CSV files into QGIS as PointZ vector layers.
    
    This service handles the complete workflow of importing CSV files containing
    point data, including validation, column mapping, and layer creation.
    """
    
    def __init__(self, qgis_iface: Any, file_system_service: Optional[Any] = None, settings_manager: Optional[Any] = None):
        """
        Initialize the CSV import service.
        
        Args:
            qgis_iface: QGIS interface object for accessing project and canvas
            file_system_service: Service for file system operations (optional)
            settings_manager: Service for managing settings (optional)
        """
        self._iface = qgis_iface
        self._file_system_service = file_system_service
        self._settings_manager = settings_manager
        self._required_columns = ['X', 'Y', 'Z']
    
    def validate_csv_files(self, csv_files: List[str]) -> ValidationResult:
        """
        Validate that all CSV files have required X, Y, Z columns.
        
        Args:
            csv_files: List of CSV file paths to validate
            
        Returns:
            ValidationResult indicating if files are valid and any error messages
        """
        if not csv_files:
            return ValidationResult(False, "No CSV files provided")
        
        for csv_file in csv_files:
            # Check if file exists
            if not os.path.exists(csv_file):
                return ValidationResult(False, f"File not found: {csv_file}")
            
            # Check if file is readable
            if not os.access(csv_file, os.R_OK):
                return ValidationResult(False, f"File not readable: {csv_file}")
            
            # Read CSV headers
            try:
                with open(csv_file, 'r', newline='', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    headers = next(reader, None)
                    
                    if not headers:
                        return ValidationResult(False, f"Empty CSV file: {csv_file}")
                    
                    # Convert headers to uppercase for case-insensitive comparison
                    header_upper = [h.upper() for h in headers]
                    
                    # Check for required columns
                    for required_col in self._required_columns:
                        if required_col.upper() not in header_upper:
                            return ValidationResult(False, f"Missing required column: {required_col}")
                            
            except Exception as e:
                return ValidationResult(False, f"Error reading CSV file {csv_file}: {str(e)}")
        
        return ValidationResult(True, "All CSV files have required X, Y, Z columns")
    
    def get_column_mapping(self, csv_files: List[str]) -> Dict[str, List[Optional[str]]]:
        """
        Get column mapping across multiple CSV files.
        
        Args:
            csv_files: List of CSV file paths to analyze
            
        Returns:
            Dictionary mapping unified column names to lists of column names from each file
        """
        if not csv_files:
            return {}
        
        # Read headers from all files
        all_headers = []
        for csv_file in csv_files:
            try:
                with open(csv_file, 'r', newline='', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    headers = next(reader, None)
                    if headers:
                        all_headers.append(headers)
            except Exception:
                # Skip files that can't be read
                all_headers.append([])
        
        if not all_headers:
            return {}
        
        # Create mapping based on column names (case-insensitive)
        column_mapping = {}
        
        # Start with required columns
        for required_col in self._required_columns:
            column_mapping[required_col] = []
            for headers in all_headers:
                # Find matching column (case-insensitive)
                matching_col = None
                for header in headers:
                    if header.upper() == required_col.upper():
                        matching_col = header
                        break
                column_mapping[required_col].append(matching_col)
        
        # Add all other columns (case-insensitive)
        all_unique_columns = set()
        for headers in all_headers:
            for header in headers:
                if header.upper() not in [col.upper() for col in self._required_columns]:
                    all_unique_columns.add(header.upper())
        
        for column_upper in sorted(all_unique_columns):
            # Find the first occurrence of this column (case-insensitive) to use as the key
            column_key = None
            for headers in all_headers:
                for header in headers:
                    if header.upper() == column_upper:
                        column_key = header
                        break
                if column_key:
                    break
            
            if column_key:
                column_mapping[column_key] = []
                for headers in all_headers:
                    # Find matching column (case-insensitive)
                    matching_col = None
                    for header in headers:
                        if header.upper() == column_upper:
                            matching_col = header
                            break
                    column_mapping[column_key].append(matching_col)
        
        return column_mapping
    
    def get_column_mapping_and_headers(self, csv_files: List[str]):
        """
        Get column mapping and all headers across multiple CSV files.
        Returns (column_mapping, all_headers)
        """
        if not csv_files:
            return {}, []
        all_headers = []
        for csv_file in csv_files:
            try:
                with open(csv_file, 'r', newline='', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    headers = next(reader, None)
                    if headers:
                        all_headers.append(headers)
            except Exception:
                all_headers.append([])
        if not all_headers:
            return {}, all_headers
        column_mapping = {}
        for required_col in self._required_columns:
            column_mapping[required_col] = []
            for headers in all_headers:
                matching_col = None
                for header in headers:
                    if header.upper() == required_col.upper():
                        matching_col = header
                        break
                column_mapping[required_col].append(matching_col)
        all_unique_columns = set()
        for headers in all_headers:
            for header in headers:
                if header.upper() not in [col.upper() for col in self._required_columns]:
                    all_unique_columns.add(header.upper())
        for column_upper in sorted(all_unique_columns):
            column_key = None
            for headers in all_headers:
                for header in headers:
                    if header.upper() == column_upper:
                        column_key = header
                        break
                if column_key:
                    break
            if column_key:
                column_mapping[column_key] = []
                for headers in all_headers:
                    matching_col = None
                    for header in headers:
                        if header.upper() == column_upper:
                            matching_col = header
                            break
                    column_mapping[column_key].append(matching_col)
        return column_mapping, all_headers
    
    def import_csv_files(self, csv_files: List[str], column_mapping: Optional[Dict[str, List[Optional[str]]]] = None) -> ValidationResult:
        """
        Import CSV files into a PointZ vector layer and add to QGIS project.
        
        Args:
            csv_files: List of CSV file paths to import
            column_mapping: Optional column mapping (if None, will be generated automatically)
            
        Returns:
            ValidationResult indicating if import was successful and any error messages
        """
        # Validate CSV files first
        validation_result = self.validate_csv_files(csv_files)
        if not validation_result.is_valid:
            return validation_result
        
        # Generate column mapping if not provided
        if column_mapping is None:
            column_mapping = self.get_column_mapping(csv_files)
        
        try:
            # Create temporary layer
            layer_name = "Imported_CSV_Points"
            
            # Get project CRS instead of using hardcoded EPSG:4326
            from qgis.core import QgsProject
            project_crs = QgsProject.instance().crs().authid()
            layer_uri = f"PointZ?crs={project_crs}&field=id:integer"
            
            # Add fields for all columns in mapping (excluding required X, Y, Z columns)
            for column_name in column_mapping.keys():
                if column_name not in self._required_columns:
                    layer_uri += f"&field={column_name.lower()}:string"
            
            layer = QgsVectorLayer(layer_uri, layer_name, "memory")
            
            if not layer.isValid():
                return ValidationResult(False, "Failed to create vector layer")
            
            # Start editing
            layer.startEditing()
            
            # Process each CSV file
            feature_id = 1
            for file_index, csv_file in enumerate(csv_files):
                try:
                    with open(csv_file, 'r', newline='', encoding='utf-8') as file:
                        reader = csv.DictReader(file)
                        
                        for row in reader:
                            # Create feature
                            feature = QgsFeature(layer.fields())
                            feature.setId(feature_id)
                            
                            # Set geometry (X, Y, Z coordinates)
                            x_col = column_mapping['X'][file_index]
                            y_col = column_mapping['Y'][file_index]
                            z_col = column_mapping['Z'][file_index]
                            
                            try:
                                x = float(row[x_col])
                                y = float(row[y_col])
                                z = float(row[z_col])
                                
                                # Create PointZ geometry
                                point = QgsPointXY(x, y)
                                geometry = QgsGeometry.fromPointXY(point)
                                feature.setGeometry(geometry)
                                
                                # Set attributes
                                feature.setAttribute('id', feature_id)
                                
                                # Set all attributes from column mapping (excluding X, Y, Z)
                                for column_name, column_list in column_mapping.items():
                                    if column_name not in self._required_columns:
                                        col_name = column_list[file_index]
                                        if col_name and col_name in row:
                                            field_name = column_name.lower()
                                            if field_name in [field.name() for field in layer.fields()]:
                                                feature.setAttribute(field_name, row[col_name])
                                
                                # Add feature to layer
                                layer.addFeature(feature)
                                feature_id += 1
                                
                            except (ValueError, KeyError) as e:
                                # Skip invalid rows but continue processing
                                continue
                                
                except Exception as e:
                    return ValidationResult(False, f"Error processing CSV file {csv_file}: {str(e)}")
            
            # Commit changes
            layer.commitChanges()
            
            # Add layer to project
            from qgis.core import QgsProject
            QgsProject.instance().addMapLayer(layer)
            
            # Archive CSV files if archive folder is configured
            if self._file_system_service and self._settings_manager:
                self._archive_csv_files(csv_files)
            
            return ValidationResult(True, f"Successfully imported {feature_id - 1} points from {len(csv_files)} CSV file(s)")
            
        except Exception as e:
            return ValidationResult(False, f"Error during import: {str(e)}")
    
    def _archive_csv_files(self, csv_files: List[str]) -> None:
        """
        Move imported CSV files to the archive folder.
        
        Args:
            csv_files: List of CSV file paths to archive
        """
        try:
            # Get archive folder from settings
            archive_folder = self._settings_manager.get_value('csv_archive_folder', '')
            if not archive_folder:
                return  # No archive folder configured
            
            # Create archive folder if it doesn't exist
            if not self._file_system_service.path_exists(archive_folder):
                if not self._file_system_service.create_directory(archive_folder):
                    print(f"Warning: Could not create CSV archive folder: {archive_folder}")
                    return
            
            # Move each CSV file to archive
            for csv_file in csv_files:
                if self._file_system_service.path_exists(csv_file):
                    filename = os.path.basename(csv_file)
                    archive_path = os.path.join(archive_folder, filename)
                    
                    if self._file_system_service.move_file(csv_file, archive_path):
                        print(f"Archived CSV file: {filename}")
                    else:
                        print(f"Warning: Could not archive CSV file: {filename}")
                        
        except Exception as e:
            print(f"Error archiving CSV files: {str(e)}") 