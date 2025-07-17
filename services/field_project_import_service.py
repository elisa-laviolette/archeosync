"""
Field Project Import Service for ArcheoSync plugin.

This module provides functionality for importing completed field projects and merging
their Objects and Features layers. It processes individual layer files that match
the configured layer names and have the same geometry type.

Key Features:
- Processes individual layer files (Objects.gpkg, Features.gpkg, etc.)
- Only imports layers with names matching the configured objects, features, and small finds layers
- Only imports layers with the same geometry type as the configured layers
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
    from qgis.core import QgsVectorLayer, QgsFeature, QgsProject, QgsVectorFileWriter, QgsGeometry, QgsWkbTypes
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
    2. Processing individual layer files that match configured layer names and geometry types
    3. Extracting Objects, Features, and Small Finds layers
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
            # Get existing layers to check for duplicates
            existing_objects_layer = self._get_existing_layer('objects_layer')
            existing_features_layer = self._get_existing_layer('features_layer')
            existing_small_finds_layer = self._get_existing_layer('small_finds_layer')
            
            # Get configured layer info for name and geometry type matching
            configured_layers = self._get_configured_layer_info()
            
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
                    
                    # Process individual layer files that match configured layers
                    print(f"Processing individual layer files: {len(layer_files.get('objects', []))} objects, {len(layer_files.get('features', []))} features")
                    
                    individual_features = self._process_individual_layers_with_matching(layer_files, configured_layers)
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
            
            # Filter out duplicates before creating merged layers
            filtered_objects_features = self._filter_duplicates(all_objects_features, existing_objects_layer, "Objects")
            filtered_features_features = self._filter_duplicates(all_features_features, existing_features_layer, "Features")
            filtered_small_finds_features = self._filter_duplicates(all_small_finds_features, existing_small_finds_layer, "Small Finds")
            
            print(f"After duplicate filtering - objects: {len(filtered_objects_features)}, features: {len(filtered_features_features)}, small finds: {len(filtered_small_finds_features)}")
            
            # Create merged layers
            layers_created = 0
            
            if filtered_objects_features:
                objects_layer = self._create_merged_layer("New Objects", filtered_objects_features)
                if objects_layer:
                    QgsProject.instance().addMapLayer(objects_layer)
                    layers_created += 1
            
            if filtered_features_features:
                features_layer = self._create_merged_layer("New Features", filtered_features_features)
                if features_layer:
                    QgsProject.instance().addMapLayer(features_layer)
                    layers_created += 1
            
            if filtered_small_finds_features:
                small_finds_layer = self._create_merged_layer("New Small Finds", filtered_small_finds_features)
                if small_finds_layer:
                    QgsProject.instance().addMapLayer(small_finds_layer)
                    layers_created += 1
            
            # Archive projects if archive folder is configured
            if self._settings_manager.get_value('field_project_archive_folder', ''):
                self._archive_projects(project_paths)
            
            # Store import statistics for summary
            self._last_import_stats = {
                'features_count': len(filtered_features_features),
                'objects_count': len(filtered_objects_features),
                'small_finds_count': len(filtered_small_finds_features),
                'features_duplicates': len(all_features_features) - len(filtered_features_features),
                'objects_duplicates': len(all_objects_features) - len(filtered_objects_features),
                'small_finds_duplicates': len(all_small_finds_features) - len(filtered_small_finds_features)
            }
            
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
    
    def get_last_import_stats(self) -> Dict[str, int]:
        """
        Get the statistics from the last import operation.
        
        Returns:
            Dictionary containing import statistics with keys:
            - features_count: Number of features imported
            - objects_count: Number of objects imported
            - small_finds_count: Number of small finds imported
            - features_duplicates: Number of duplicate features detected
            - objects_duplicates: Number of duplicate objects detected
            - small_finds_duplicates: Number of duplicate small finds detected
        """
        return getattr(self, '_last_import_stats', {
            'features_count': 0,
            'objects_count': 0,
            'small_finds_count': 0,
            'features_duplicates': 0,
            'objects_duplicates': 0,
            'small_finds_duplicates': 0
        })
    
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
    
    def _get_configured_layer_info(self) -> Dict[str, Any]:
        """
        Get the configured layer information (name and geometry type) from settings.
        
        Returns:
            Dictionary mapping layer types to their names and geometry types.
        """
        configured_layers = {
            'objects': {'name': None, 'geometry_type': None},
            'features': {'name': None, 'geometry_type': None},
            'small_finds': {'name': None, 'geometry_type': None}
        }
        
        # Get objects layer info
        objects_layer_id = self._settings_manager.get_value('objects_layer', '')
        if objects_layer_id:
            layer_info = self._layer_service.get_layer_info(objects_layer_id)
            if layer_info:
                configured_layers['objects']['name'] = layer_info['name']
                configured_layers['objects']['geometry_type'] = layer_info.get('geometry_type', 2)  # Default to polygon
        
        # Get features layer info
        features_layer_id = self._settings_manager.get_value('features_layer', '')
        if features_layer_id:
            layer_info = self._layer_service.get_layer_info(features_layer_id)
            if layer_info:
                configured_layers['features']['name'] = layer_info['name']
                configured_layers['features']['geometry_type'] = layer_info.get('geometry_type', 2)  # Default to polygon
        
        # Get small finds layer info
        small_finds_layer_id = self._settings_manager.get_value('small_finds_layer', '')
        if small_finds_layer_id:
            layer_info = self._layer_service.get_layer_info(small_finds_layer_id)
            if layer_info:
                configured_layers['small_finds']['name'] = layer_info['name']
                configured_layers['small_finds']['geometry_type'] = layer_info.get('geometry_type', 0)  # Default to point
        
        return configured_layers

    def _process_individual_layers_with_matching(self, layer_files: Dict[str, List[str]], configured_layers: Dict[str, Any]) -> Dict[str, List[Any]]:
        """
        Process individual layer files and match them to configured layers.
        
        Args:
            layer_files: Dictionary mapping layer types to lists of file paths
            configured_layers: Dictionary containing configured layer info (name, geometry type)
            
        Returns:
            Dictionary mapping layer types to lists of features
        """
        features = {
            'objects': [],
            'features': [],
            'small_finds': []
        }
        
        # Process Objects layer files
        for file_path in layer_files['objects']:
            expected_name = configured_layers['objects']['name']
            layer = self._load_layer(f"{file_path}|layername={expected_name}", expected_name)
            if not layer:
                print(f"Skipping Objects layer {expected_name} in {file_path} (not found or invalid)")
                continue
            if not self._is_valid_geometry_type(layer, configured_layers['objects']['geometry_type']):
                print(f"Skipping Objects layer {layer.name()} with incompatible geometry type: {layer.geometryType()} (expected: {configured_layers['objects']['geometry_type']})")
                continue
            features['objects'].extend(list(layer.getFeatures()))
            print(f"Imported Objects layer {layer.name()} with {layer.featureCount()} features")
        
        # Process Features layer files
        for file_path in layer_files['features']:
            expected_name = configured_layers['features']['name']
            layer = self._load_layer(f"{file_path}|layername={expected_name}", expected_name)
            if not layer:
                print(f"Skipping Features layer {expected_name} in {file_path} (not found or invalid)")
                continue
            if not self._is_valid_geometry_type(layer, configured_layers['features']['geometry_type']):
                print(f"Skipping Features layer {layer.name()} with incompatible geometry type: {layer.geometryType()} (expected: {configured_layers['features']['geometry_type']})")
                continue
            features['features'].extend(list(layer.getFeatures()))
            print(f"Imported Features layer {layer.name()} with {layer.featureCount()} features")
        
        # Process Small Finds layer files
        for file_path in layer_files['small_finds']:
            expected_name = configured_layers['small_finds']['name']
            layer = self._load_layer(f"{file_path}|layername={expected_name}", expected_name)
            if not layer:
                print(f"Skipping Small Finds layer {expected_name} in {file_path} (not found or invalid)")
                continue
            if not self._is_valid_geometry_type(layer, configured_layers['small_finds']['geometry_type']):
                print(f"Skipping Small Finds layer {layer.name()} with incompatible geometry type: {layer.geometryType()} (expected: {configured_layers['small_finds']['geometry_type']})")
                continue
            features['small_finds'].extend(list(layer.getFeatures()))
            print(f"Imported Small Finds layer {layer.name()} with {layer.featureCount()} features")
        
        return features

    def _matches_configured_layer_name(self, layer_name: str, configured_name: Optional[str]) -> bool:
        """
        Check if a layer name matches the configured layer name.
        
        Args:
            layer_name: The layer name to check
            configured_name: The configured layer name to match against
            
        Returns:
            True if the names match, False otherwise
        """
        if not configured_name:
            return False
        
        # Exact match (case-insensitive)
        return layer_name.lower() == configured_name.lower()
    
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
                # Check if feature has geometry
                has_geometry = feature.geometry() and not feature.geometry().isEmpty()
                if has_geometry:
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
                # Check if feature has geometry
                has_geometry = feature.geometry() and not feature.geometry().isEmpty()
                if has_geometry:
                    geom_type = feature.geometry().type()
                    if geom_type == 2:  # PolygonGeometry (type 2 can be either Line or Polygon, but in this context it's Polygon)
                        polygon_features.append(feature)
                    elif geom_type == 1:  # PointGeometry
                        point_features.append(feature)
                    elif geom_type == 0:  # NoGeometry - but check if it's actually a point
                        # For small finds, geometry type 0 might actually be Point geometry
                        # Check if this is a small finds layer and assume Point geometry
                        if "petits objets" in layer_name.lower() or "small" in layer_name.lower():
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
                # No features have geometry, create a layer without geometry
                geom_string = "None"  # No geometry
                print(f"Creating {layer_name} layer with no geometry (all features are attribute-only)")
            
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
                # Create a new feature with the correct field structure
                new_feature = QgsFeature(layer.fields())
                
                # Handle geometry based on layer type and feature geometry
                if geom_string == "None":
                    # Layer has no geometry, so don't set any geometry
                    pass
                elif feature.geometry() and not feature.geometry().isEmpty():
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
                    elif geom_string == "Point" and feature_geom_type == 0:
                        # For small finds, geometry type 0 might actually be Point geometry
                        is_compatible = True
                    
                    if is_compatible:
                        # Copy geometry
                        new_feature.setGeometry(feature.geometry())
                    else:
                        skipped_count += 1
                        print(f"Skipped feature with incompatible geometry: type={feature_geom_type}, multipart={feature.geometry().isMultipart()} for layer type {geom_string}")
                        continue
                else:
                    # Feature has no geometry, which is fine for layers with geometry (will be NULL)
                    pass
                
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
                    if feature.geometry() and not feature.geometry().isEmpty():
                        print(f"Failed to add feature with geometry: type={feature.geometry().type()}, multipart={feature.geometry().isMultipart()}")
                    else:
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
        
        # Check if it's a .gpkg file
        if not filename_lower.endswith('.gpkg'):
            return False
        
        # Remove .gpkg extension for name comparison
        name_without_ext = filename_lower[:-5]  # Remove '.gpkg'
        
        # First, check against configured objects layer name
        objects_layer_id = self._settings_manager.get_value('objects_layer', '')
        if objects_layer_id:
            layer_info = self._layer_service.get_layer_info(objects_layer_id)
            if layer_info and layer_info['name'].lower() == name_without_ext:
                return True
        
        # Fallback to common patterns (but be more specific)
        return (name_without_ext == 'objects' or 
                name_without_ext == 'objets' or 
                name_without_ext == 'obj')
    
    def _is_features_layer_file(self, filename: str) -> bool:
        """Check if a filename represents a Features layer file."""
        filename_lower = filename.lower()
        
        # Check if it's a .gpkg file
        if not filename_lower.endswith('.gpkg'):
            return False
        
        # Remove .gpkg extension for name comparison
        name_without_ext = filename_lower[:-5]  # Remove '.gpkg'
        
        # First, check against configured features layer name
        features_layer_id = self._settings_manager.get_value('features_layer', '')
        if features_layer_id:
            layer_info = self._layer_service.get_layer_info(features_layer_id)
            if layer_info and layer_info['name'].lower() == name_without_ext:
                return True
        
        # Fallback to common patterns (but be more specific)
        return (name_without_ext == 'features' or 
                name_without_ext == 'feat' or
                name_without_ext == 'fugaces')
    
    def _is_small_finds_layer_file(self, filename: str) -> bool:
        """Check if a filename represents a Small Finds layer file."""
        filename_lower = filename.lower()
        
        # Check if it's a .gpkg file
        if not filename_lower.endswith('.gpkg'):
            return False
        
        # Remove .gpkg extension for name comparison
        name_without_ext = filename_lower[:-5]  # Remove '.gpkg'
        
        # First, check against configured small finds layer name
        small_finds_layer_id = self._settings_manager.get_value('small_finds_layer', '')
        if small_finds_layer_id:
            layer_info = self._layer_service.get_layer_info(small_finds_layer_id)
            if layer_info and layer_info['name'].lower() == name_without_ext:
                return True
        
        # Fallback to common patterns (but be more specific)
        return (name_without_ext == 'small_finds' or 
                name_without_ext == 'smallfinds' or
                name_without_ext == 'esquilles')
    
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

    def _get_existing_layer(self, layer_setting_key: str) -> Optional[Any]:
        """
        Get an existing layer from the current project based on settings.
        
        Args:
            layer_setting_key: The settings key for the layer (e.g., 'objects_layer', 'features_layer')
            
        Returns:
            QGIS layer object, or None if not found
        """
        layer_id = self._settings_manager.get_value(layer_setting_key, '')
        if layer_id:
            return self._layer_service.get_layer_by_id(layer_id)
        return None
    
    def _filter_duplicates(self, features: List[Any], existing_layer: Optional[Any], layer_type: str) -> List[Any]:
        """
        Filter out features that already exist in the current project layer.
        
        Args:
            features: List of features to filter
            existing_layer: Existing layer to check against, or None
            layer_type: Type of layer for logging purposes
            
        Returns:
            List of features with duplicates removed
        """
        if not existing_layer or not features:
            return features
        
        print(f"Checking {len(features)} {layer_type} features against existing layer...")
        
        # Get all existing features for comparison
        existing_features = list(existing_layer.getFeatures())
        print(f"Found {len(existing_features)} existing {layer_type} features to compare against")
        
        # Create a set of existing feature signatures for fast lookup
        existing_signatures = set()
        for existing_feature in existing_features:
            signature = self._create_feature_signature(existing_feature)
            existing_signatures.add(signature)
        
        # Filter out duplicates
        filtered_features = []
        duplicates_count = 0
        
        for feature in features:
            signature = self._create_feature_signature(feature)
            if signature not in existing_signatures:
                filtered_features.append(feature)
            else:
                duplicates_count += 1
        
        print(f"Filtered out {duplicates_count} duplicate {layer_type} features")
        return filtered_features
    
    def _create_feature_signature(self, feature: Any) -> str:
        """
        Create a unique signature for a feature based on its attributes and geometry.
        
        Args:
            feature: QGIS feature to create signature for
            
        Returns:
            String signature representing the feature
        """
        # Create signature from attributes
        attributes = []
        for field in feature.fields():
            field_name = field.name()
            value = feature[field_name]
            # Convert value to string, handling None values
            if value is None:
                attr_str = f"{field_name}:NULL"
            else:
                attr_str = f"{field_name}:{str(value)}"
            attributes.append(attr_str)
        
        # Sort attributes for consistent signature
        attributes.sort()
        attr_signature = "|".join(attributes)
        
        # Create signature from geometry
        geometry = feature.geometry()
        if geometry and not geometry.isEmpty():
            # Use WKT (Well-Known Text) representation for geometry
            geom_signature = geometry.asWkt()
        else:
            geom_signature = "NO_GEOMETRY"
        
        # Combine attributes and geometry signatures
        return f"{attr_signature}|GEOM:{geom_signature}" 

    def _load_layer(self, file_path: str, layer_name: str) -> Optional[QgsVectorLayer]:
        """
        Load a layer from a file path.
        
        Args:
            file_path: Path to the layer file (e.g., 'Objects.gpkg')
            layer_name: Name to give to the loaded layer in QGIS
            
        Returns:
            QGIS VectorLayer object, or None if loading failed
        """
        try:
            layer = QgsVectorLayer(file_path, layer_name, "ogr")
            if layer.isValid():
                return layer
            else:
                print(f"Failed to load layer {layer_name} from {file_path}: {layer.lastError().message()}")
                return None
        except Exception as e:
            print(f"Error loading layer {layer_name} from {file_path}: {str(e)}")
            return None

    def _is_valid_geometry_type(self, layer, expected_type):
        """
        Check if the layer's geometry type matches the expected type(s).
        Accepts both string and integer representations for backward compatibility.
        """
        geom_type = layer.geometryType()
        
        # Accept both string and int for expected_type
        if isinstance(expected_type, str):
            expected_type = expected_type.lower()
        
        # Objects and Features: Polygon or MultiPolygon
        if expected_type in ("polygon", QgsWkbTypes.PolygonGeometry, 2):
            return geom_type in (QgsWkbTypes.PolygonGeometry, 2)
        # Small Finds: Point, MultiPoint, or NoGeometry
        elif expected_type in ("point", QgsWkbTypes.PointGeometry, 0):
            return geom_type in (QgsWkbTypes.PointGeometry, QgsWkbTypes.NoGeometry, 0, 4)
        # Features: LineString or MultiLineString (if needed in future)
        elif expected_type in ("linestring", QgsWkbTypes.LineGeometry, 1):
            return geom_type in (QgsWkbTypes.LineGeometry, 1)
        # Fallback: strict equality
        return geom_type == expected_type 