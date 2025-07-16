"""
Field Project Import Service for ArcheoSync plugin.

This module provides functionality for importing completed field projects and merging
their Objects and Features layers. It can process both data.gpkg files and individual
layer files that are not contained within a data.gpkg file.

Key Features:
- Processes data.gpkg files from field projects
- Processes individual layer files (Objects.gpkg, Features.gpkg, etc.)
- Merges Objects and Features layers from multiple projects
- Creates new "New Objects" and "New Features" layers in the project
- Handles layer validation and error recovery
- Automatic archiving of imported projects

Architecture Benefits:
- Single Responsibility: Focuses only on field project import operations
- Dependency Inversion: Implements IFieldProjectImportService interface
- Testability: All QGIS dependencies can be mocked
- Extensibility: Easy to add support for new layer types or formats

Usage:
    field_import_service = FieldProjectImportService(
        settings_manager, layer_service, file_system_service
    )
    
    # Import completed field projects
    result = field_import_service.import_field_projects(['/path/to/project1', '/path/to/project2'])
    if result.is_valid:
        print(f"Import successful: {result.message}")
    else:
        print(f"Import failed: {result.message}")
"""

import os
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

try:
    from qgis.core import QgsVectorLayer, QgsFeature, QgsProject, QgsVectorFileWriter, QgsGeometry
    from qgis.PyQt.QtCore import QVariant
    from ..core.interfaces import IFieldProjectImportService, ISettingsManager, ILayerService, IFileSystemService, ValidationResult, ITranslationService
except ImportError:
    # For testing without QGIS
    QgsVectorLayer = None
    QgsFeature = None
    QgsProject = None
    QgsVectorFileWriter = None
    QgsGeometry = None
    QVariant = None
    from core.interfaces import IFieldProjectImportService, ISettingsManager, ILayerService, IFileSystemService, ValidationResult, ITranslationService


class FieldProjectImportService(IFieldProjectImportService):
    """
    QGIS-specific implementation for importing completed field projects.
    
    This service imports completed field projects by:
    1. Scanning project directories for layer files
    2. Processing data.gpkg files and individual layer files
    3. Extracting Objects and Features layers
    4. Merging layers from multiple projects
    5. Creating new layers in the current QGIS project
    6. Archiving imported projects
    """
    
    def __init__(self, 
                 settings_manager: ISettingsManager,
                 layer_service: ILayerService,
                 file_system_service: IFileSystemService,
                 translation_service: Optional[ITranslationService] = None):
        """
        Initialize the field project import service.
        
        Args:
            settings_manager: Service for managing settings
            layer_service: Service for layer operations
            file_system_service: Service for file system operations
        """
        self._settings_manager = settings_manager
        self._layer_service = layer_service
        self._file_system_service = file_system_service
        self._translation_service = translation_service
    
    def import_field_projects(self, project_paths: List[str]) -> ValidationResult:
        """
        Import completed field projects and merge their Objects and Features layers.
        
        Args:
            project_paths: List of paths to completed field project directories
            
        Returns:
            ValidationResult indicating if import was successful and any error messages
        """
        if not project_paths:
            return ValidationResult(True, "No projects to import")
        
        try:
            # Collect all features from all projects
            all_objects_features = []
            all_features_features = []
            all_small_finds_features = []
            processed_projects = 0
            failed_projects = 0
            
            for project_path in project_paths:
                try:
                    # Scan for layer files in the project
                    layer_files = self._scan_project_layers(project_path)
                    
                    # Track which layers we've already processed from data.gpkg
                    processed_layers = set()
                    
                    # Process data.gpkg if it exists
                    data_gpkg_path = os.path.join(project_path, "data.gpkg")
                    if os.path.exists(data_gpkg_path):
                        print(f"Processing data.gpkg: {data_gpkg_path}")
                        data_features = self._process_data_gpkg(data_gpkg_path)
                        print(f"  Data.gpkg objects: {len(data_features.get('objects', []))}")
                        print(f"  Data.gpkg features: {len(data_features.get('features', []))}")
                        all_objects_features.extend(data_features.get('objects', []))
                        all_features_features.extend(data_features.get('features', []))
                        
                        # Mark that we've processed objects and features layers from data.gpkg
                        if data_features.get('objects'):
                            processed_layers.add('objects')
                        if data_features.get('features'):
                            processed_layers.add('features')
                    
                    # Process individual layer files (skip if already processed from data.gpkg)
                    print(f"Processing individual layer files: {len(layer_files.get('objects', []))} objects, {len(layer_files.get('features', []))} features")
                    
                    # Filter out already processed layer types
                    filtered_layer_files = {
                        'objects': layer_files['objects'] if 'objects' not in processed_layers else [],
                        'features': layer_files['features'] if 'features' not in processed_layers else [],
                        'small_finds': layer_files['small_finds'] if 'small_finds' not in processed_layers else []
                    }
                    
                    individual_features = self._process_individual_layers(filtered_layer_files)
                    print(f"  Individual objects: {len(individual_features.get('objects', []))}")
                    print(f"  Individual features: {len(individual_features.get('features', []))}")
                    print(f"  Individual small finds: {len(individual_features.get('small_finds', []))}")
                    all_objects_features.extend(individual_features.get('objects', []))
                    all_features_features.extend(individual_features.get('features', []))
                    all_small_finds_features.extend(individual_features.get('small_finds', []))
                    
                    processed_projects += 1
                    
                except Exception as e:
                    print(f"Error processing project {project_path}: {str(e)}")
                    failed_projects += 1
                    continue
            
            print(f"Total objects features collected: {len(all_objects_features)}")
            print(f"Total features features collected: {len(all_features_features)}")
            print(f"Total small finds features collected: {len(all_small_finds_features)}")
            
            # Create merged layers
            layers_created = 0
            
            if all_objects_features:
                objects_layer = self._create_merged_layer("New Objects", all_objects_features)
                if objects_layer:
                    QgsProject.instance().addMapLayer(objects_layer)
                    layers_created += 1
            
            if all_features_features:
                features_layer = self._create_merged_layer("New Features", all_features_features)
                if features_layer:
                    QgsProject.instance().addMapLayer(features_layer)
                    layers_created += 1
            
            if all_small_finds_features:
                layer_name = "New Small Finds"
                if self._translation_service:
                    layer_name = self._translation_service.translate("New Small Finds")
                small_finds_layer = self._create_merged_layer(layer_name, all_small_finds_features)
                if small_finds_layer:
                    QgsProject.instance().addMapLayer(small_finds_layer)
                    layers_created += 1
            
            # Archive projects if archive folder is configured
            if self._settings_manager.get_value('field_project_archive_folder', ''):
                self._archive_projects(project_paths)
            
            # Prepare result message
            if layers_created > 0:
                message = f"Successfully imported {layers_created} layer(s) from {processed_projects} project(s)"
                if failed_projects > 0:
                    message += f" ({failed_projects} project(s) failed)"
                return ValidationResult(True, message)
            else:
                return ValidationResult(False, "No Objects or Features layers found in any project")
                
        except Exception as e:
            return ValidationResult(False, f"Error during import: {str(e)}")
    
    def _scan_project_layers(self, project_path: str) -> Dict[str, List[str]]:
        """
        Scan a field project directory for layer files.
        
        Args:
            project_path: Path to the field project directory
            
        Returns:
            Dictionary mapping layer types to lists of file paths
        """
        layer_files = {
            'objects': [],
            'features': [],
            'small_finds': []
        }
        
        if not os.path.exists(project_path):
            return layer_files
        
        print(f"Scanning project directory: {project_path}")
        
        # Look for individual layer files
        for filename in os.listdir(project_path):
            file_path = os.path.join(project_path, filename)
            if not os.path.isfile(file_path):
                continue
            
            print(f"  Found file: {filename}")
            
            # Check for Objects layer files
            if self._is_objects_layer_file(filename):
                print(f"    -> Recognized as Objects layer")
                layer_files['objects'].append(file_path)
            
            # Check for Features layer files
            elif self._is_features_layer_file(filename):
                print(f"    -> Recognized as Features layer")
                layer_files['features'].append(file_path)
            # Check for Small Finds layer files
            elif self._is_small_finds_layer_file(filename):
                print(f"    -> Recognized as Small Finds layer")
                layer_files['small_finds'].append(file_path)
            else:
                print(f"    -> Not recognized as Objects, Features, or Small Finds layer")
        
        return layer_files
    
    def _process_data_gpkg(self, data_gpkg_path: str) -> Dict[str, List[Any]]:
        """
        Process a data.gpkg file to extract Objects and Features layers.
        
        Args:
            data_gpkg_path: Path to the data.gpkg file
            
        Returns:
            Dictionary mapping layer types to lists of features
        """
        features = {
            'objects': [],
            'features': [],
            'small_finds': []
        }
        
        try:
            # Load the data.gpkg as a vector layer
            data_layer = QgsVectorLayer(data_gpkg_path, "temp_data", "ogr")
            if not data_layer.isValid():
                return features
            
            # Get sublayers from the data.gpkg
            sublayers = data_layer.dataProvider().subLayers()
            
            for sublayer in sublayers:
                # Parse sublayer info: "0!!::!!LayerName!!::!!GeometryType!!::!!CRS"
                parts = sublayer.split("!!::!!")
                if len(parts) >= 2:
                    layer_name = parts[1]
                    print(f"Found sublayer: {layer_name}")
                    
                    # Create layer URI for the sublayer
                    layer_uri = f"{data_gpkg_path}|layername={layer_name}"
                    layer = QgsVectorLayer(layer_uri, layer_name, "ogr")
                    
                    if layer.isValid():
                        print(f"Layer {layer_name} is valid, geometry type: {layer.geometryType()}")
                        if self._is_objects_layer_name(layer_name):
                            print(f"Processing {layer_name} as Objects layer")
                            layer_features = list(layer.getFeatures())
                            print(f"  Found {len(layer_features)} features in {layer_name}")
                            features['objects'].extend(layer_features)
                        elif self._is_features_layer_name(layer_name):
                            print(f"Processing {layer_name} as Features layer")
                            layer_features = list(layer.getFeatures())
                            print(f"  Found {len(layer_features)} features in {layer_name}")
                            features['features'].extend(layer_features)
                        elif self._is_small_finds_layer_name(layer_name):
                            print(f"Processing {layer_name} as Small Finds layer")
                            layer_features = list(layer.getFeatures())
                            print(f"  Found {len(layer_features)} features in {layer_name}")
                            features['small_finds'].extend(layer_features)
                        else:
                            print(f"Layer {layer_name} not recognized as Objects, Features, or Small Finds layer")
        
        except Exception as e:
            print(f"Error processing data.gpkg {data_gpkg_path}: {str(e)}")
        
        return features
    
    def _process_individual_layers(self, layer_files: Dict[str, List[str]]) -> Dict[str, List[Any]]:
        """
        Process individual layer files (not in data.gpkg).
        
        Args:
            layer_files: Dictionary mapping layer types to lists of file paths
            
        Returns:
            Dictionary mapping layer types to lists of features
        """
        features = {
            'objects': [],
            'features': []
        }
        
        # Process Objects layer files
        for file_path in layer_files['objects']:
            try:
                layer = QgsVectorLayer(file_path, "temp_objects", "ogr")
                if layer.isValid():
                    features['objects'].extend(list(layer.getFeatures()))
            except Exception as e:
                print(f"Error processing Objects layer {file_path}: {str(e)}")
        
        # Process Features layer files
        for file_path in layer_files['features']:
            try:
                layer = QgsVectorLayer(file_path, "temp_features", "ogr")
                if layer.isValid():
                    features['features'].extend(list(layer.getFeatures()))
            except Exception as e:
                print(f"Error processing Features layer {file_path}: {str(e)}")
        
        return features
    
    def _create_merged_layer(self, layer_name: str, features: List[Any]) -> Optional[Any]:
        """
        Create a merged layer from a list of features.
        
        Args:
            layer_name: Name for the merged layer
            features: List of features to merge
            
        Returns:
            QGIS layer object, or None if failed
        """
        if not features:
            return None
        
        try:
            # Analyze all features to determine compatible geometry type and fields
            geometry_types = set()
            all_fields = set()
            field_types = {}
            
            for feature in features:
                if feature.geometry() and not feature.geometry().isEmpty():
                    geometry_types.add(feature.geometry().type())
                    # Debug: print geometry type for first few features
                    if len(geometry_types) <= 3:
                        geom_type = feature.geometry().type()
                        is_multipart = feature.geometry().isMultipart()
                        print(f"Feature geometry: type={geom_type}, multipart={is_multipart}")
                
                # Collect all unique fields and their types
                for field in feature.fields():
                    field_name = field.name()
                    field_type = field.typeName()
                    all_fields.add(field_name)
                    
                    # Store the most common type for each field
                    if field_name not in field_types:
                        field_types[field_name] = {}
                    if field_type not in field_types[field_name]:
                        field_types[field_name][field_type] = 0
                    field_types[field_name][field_type] += 1
            
            # Determine the most appropriate geometry type by analyzing all features
            polygon_features = []
            line_features = []
            point_features = []
            
            for feature in features:
                if feature.geometry() and not feature.geometry().isEmpty():
                    geom_type = feature.geometry().type()
                    if geom_type == 2:  # PolygonGeometry (type 2 can be either Line or Polygon, but in this context it's Polygon)
                        polygon_features.append(feature)
                    elif geom_type == 1:  # PointGeometry
                        point_features.append(feature)
                    # Note: LineGeometry would be type 2 as well, but we're assuming these are polygons based on user input
            
            # Determine geometry type based on actual features
            if polygon_features:
                # Check if any polygon features are multipart
                has_multipart_polygons = any(f.geometry().isMultipart() for f in polygon_features)
                geom_string = "MultiPolygon" if has_multipart_polygons else "Polygon"
                print(f"Creating {layer_name} layer with {len(polygon_features)} polygon features, multipart: {has_multipart_polygons}")
            elif point_features:
                # Check if any point features are multipart
                has_multipart_points = any(f.geometry().isMultipart() for f in point_features)
                geom_string = "MultiPoint" if has_multipart_points else "Point"
                print(f"Creating {layer_name} layer with {len(point_features)} point features, multipart: {has_multipart_points}")
            else:
                geom_string = "Point"  # Default fallback
                print(f"Creating {layer_name} layer with default Point geometry (no features with geometry found)")
            
            # Get CRS - try project CRS first, then fall back to default
            project_crs = QgsProject.instance().crs()
            if project_crs and project_crs.isValid():
                crs_string = self._get_crs_string(project_crs)
            else:
                crs_string = "EPSG:4326"  # Default fallback
            
            # Create layer URI with fields
            layer_uri = f"{geom_string}?crs={crs_string}"
            
            # Add fields with most common types
            for field_name in sorted(all_fields):
                if field_name in field_types:
                    # Get the most common type for this field
                    most_common_type = max(field_types[field_name].items(), key=lambda x: x[1])[0]
                    layer_uri += f"&field={field_name}:{most_common_type}"
            
            print(f"Layer URI before CRS: {layer_uri}")
            print(f"CRS string: '{crs_string}'")
            
            # Create memory layer
            layer = QgsVectorLayer(layer_uri, layer_name, "memory")
            print(f"Created layer URI: {layer_uri}")
            if not layer.isValid():
                print(f"Failed to create valid layer: {layer_name}")
                return None
            print(f"Successfully created layer: {layer_name}, fields: {layer.fields().count()}")
            
            # Debug: Print field information
            print(f"Layer fields: {[field.name() for field in layer.fields()]}")
            if features:
                first_feature = features[0]
                print(f"First feature fields: {[field.name() for field in first_feature.fields()]}")
            
            # Add features, filtering out incompatible geometries
            layer.startEditing()
            added_count = 0
            skipped_count = 0
            
            print(f"Attempting to add {len(features)} features to {layer_name} layer")
            
            for feature in features:
                if feature.geometry() and not feature.geometry().isEmpty():
                    # Check if geometry type is compatible
                    feature_geom_type = feature.geometry().type()
                    
                    # Define compatibility rules - since we created the layer based on all features,
                    # we should be able to add all features of the correct geometry type
                    is_compatible = False
                    if geom_string == "Point" and feature_geom_type == 1 and not feature.geometry().isMultipart():
                        is_compatible = True
                    elif geom_string == "MultiPoint" and feature_geom_type == 1:
                        is_compatible = True
                    elif geom_string == "Polygon" and feature_geom_type == 2 and not feature.geometry().isMultipart():
                        is_compatible = True
                    elif geom_string == "MultiPolygon" and feature_geom_type == 2:
                        # MultiPolygon layers can accept both single and multipart polygon features
                        is_compatible = True
                    
                    if is_compatible:
                        # Create a new feature with the correct field structure
                        new_feature = QgsFeature(layer.fields())
                        
                        # Copy geometry
                        new_feature.setGeometry(feature.geometry())
                        
                        # Copy attributes by field name
                        for i, field in enumerate(layer.fields()):
                            field_name = field.name()
                            source_field_idx = feature.fields().indexOf(field_name)
                            if source_field_idx >= 0:
                                new_feature[field_name] = feature[field_name]
                            else:
                                # Field doesn't exist in source, set to NULL
                                new_feature[field_name] = None
                        
                        # Add the new feature
                        success = layer.addFeature(new_feature)
                        if success:
                            added_count += 1
                        else:
                            skipped_count += 1
                            print(f"Failed to add feature with geometry: type={feature_geom_type}, multipart={feature.geometry().isMultipart()}")
                            # Get more details about the failure
                            print(f"  Layer error: {layer.lastError()}")
                    else:
                        skipped_count += 1
                        print(f"Skipped feature with incompatible geometry: type={feature_geom_type}, multipart={feature.geometry().isMultipart()} for layer type {geom_string}")
                else:
                    # Create a new feature with the correct field structure for features without geometry
                    new_feature = QgsFeature(layer.fields())
                    
                    # Copy attributes by field name
                    for i, field in enumerate(layer.fields()):
                        field_name = field.name()
                        source_field_idx = feature.fields().indexOf(field_name)
                        if source_field_idx >= 0:
                            new_feature[field_name] = feature[field_name]
                        else:
                            # Field doesn't exist in source, set to NULL
                            new_feature[field_name] = None
                    
                    # Add the new feature
                    success = layer.addFeature(new_feature)
                    if success:
                        added_count += 1
                    else:
                        skipped_count += 1
                        print(f"Failed to add feature without geometry")
                        # Get more details about the failure
                        print(f"  Layer error: {layer.lastError()}")
            
            print(f"Added {added_count} features, skipped {skipped_count} features to {layer_name} layer")
            
            if skipped_count > 0:
                print(f"Warning: Skipped {skipped_count} features with incompatible geometry types for layer '{layer_name}'")
            
            layer.commitChanges()
            
            return layer
            
        except Exception as e:
            print(f"Error creating merged layer {layer_name}: {str(e)}")
            return None
    
    def _is_objects_layer_file(self, filename: str) -> bool:
        """Check if a filename represents an Objects layer file."""
        filename_lower = filename.lower()
        return (filename_lower.endswith('.gpkg') and 
                ('objects' in filename_lower or 'obj' in filename_lower))
    
    def _is_features_layer_file(self, filename: str) -> bool:
        """Check if a filename represents a Features layer file."""
        filename_lower = filename.lower()
        return (filename_lower.endswith('.gpkg') and 
                ('features' in filename_lower or 'feat' in filename_lower))
    
    def _is_small_finds_layer_file(self, filename: str) -> bool:
        """Check if a filename represents a Small Finds layer file."""
        filename_lower = filename.lower()
        return (filename_lower.endswith('.gpkg') and 
                ('small_finds' in filename_lower or 'small_finds' in filename_lower))
    
    def _is_objects_layer_name(self, layer_name: str) -> bool:
        """Check if a layer name represents an Objects layer."""
        # Ignore log layers
        if layer_name.lower().startswith('log_'):
            return False
        
        # Get configured objects layer name
        objects_layer_id = self._settings_manager.get_value('objects_layer', '')
        if objects_layer_id:
            layer_info = self._layer_service.get_layer_info(objects_layer_id)
            if layer_info and layer_info['name'].lower() == layer_name.lower():
                return True
        
        # Fallback to common patterns
        layer_name_lower = layer_name.lower()
        return ('objects' in layer_name_lower or 'objets' in layer_name_lower or 'obj' in layer_name_lower)
    
    def _is_features_layer_name(self, layer_name: str) -> bool:
        """Check if a layer name represents a Features layer."""
        # Ignore log layers
        if layer_name.lower().startswith('log_'):
            return False
        
        # Get configured features layer name
        features_layer_id = self._settings_manager.get_value('features_layer', '')
        if features_layer_id:
            layer_info = self._layer_service.get_layer_info(features_layer_id)
            if layer_info and layer_info['name'].lower() == layer_name.lower():
                return True
        
        # Fallback to common patterns
        layer_name_lower = layer_name.lower()
        return ('features' in layer_name_lower or 'feat' in layer_name_lower)
    
    def _is_small_finds_layer_name(self, layer_name: str) -> bool:
        """Check if a layer name represents a Small Finds layer."""
        # Ignore log layers
        if layer_name.lower().startswith('log_'):
            return False
        
        # Get configured small finds layer name
        small_finds_layer_id = self._settings_manager.get_value('small_finds_layer', '')
        if small_finds_layer_id:
            layer_info = self._layer_service.get_layer_info(small_finds_layer_id)
            if layer_info and layer_info['name'].lower() == layer_name.lower():
                return True
        
        # Fallback to common patterns
        layer_name_lower = layer_name.lower()
        return ('small_finds' in layer_name_lower or 'small_finds' in layer_name_lower)
    
    def _get_crs_string(self, crs) -> str:
        """Get CRS string from QgsCoordinateReferenceSystem object."""
        try:
            return crs.authid()
        except:
            try:
                return crs.description()
            except:
                return "EPSG:4326"  # Default fallback
    
    def _archive_projects(self, project_paths: List[str]) -> None:
        """Archive imported projects to the configured archive folder."""
        try:
            archive_folder = self._settings_manager.get_value('field_project_archive_folder', '')
            if not archive_folder:
                return  # No archive folder configured
            
            # Create archive folder if it doesn't exist
            if not self._file_system_service.path_exists(archive_folder):
                if not self._file_system_service.create_directory(archive_folder):
                    print(f"Warning: Could not create field project archive folder: {archive_folder}")
                    return
            
            for project_path in project_paths:
                if self._file_system_service.path_exists(project_path):
                    project_name = os.path.basename(project_path)
                    archive_path = os.path.join(archive_folder, project_name)
                    
                    # Move the project to archive
                    if self._file_system_service.move_directory(project_path, archive_path):
                        print(f"Archived field project: {project_name}")
                    else:
                        print(f"Warning: Could not archive field project: {project_name}")
                    
        except Exception as e:
            print(f"Error archiving projects: {str(e)}") 