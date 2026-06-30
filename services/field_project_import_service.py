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
- Creates new "New Objects", "New Features", and "New Small Finds" layers in the project
- Copies symbology, form configuration, and project relations from definitive layers to temporary layers
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

import copy
import os
import re
import shutil
import tempfile
import unicodedata
from typing import List, Dict, Optional, Any, Iterable, Tuple
from dataclasses import dataclass

try:
    from qgis.core import QgsVectorLayer, QgsFeature, QgsProject, QgsVectorFileWriter, QgsGeometry, QgsWkbTypes
    from qgis.PyQt.QtCore import QVariant, QObject
    from ..core.interfaces import IFieldProjectImportService, ISettingsManager, ILayerService, IFileSystemService, ValidationResult
    from .field_project_metadata import get_import_layer_names, get_project_kind, is_global_project
except ImportError:
    # For testing without QGIS
    QgsVectorLayer = None
    QgsFeature = None
    QgsProject = None
    QgsVectorFileWriter = None
    QgsGeometry = None
    QVariant = None
    from core.interfaces import IFieldProjectImportService, ISettingsManager, ILayerService, IFileSystemService, ValidationResult
    from services.field_project_metadata import (
        get_import_layer_names,
        get_project_kind,
        is_global_project,
        PROJECT_KIND_GLOBAL,
    )


class FieldProjectImportService(QObject):
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
                 file_system_service: IFileSystemService):
        """
        Initialize the field project import service.
        
        Args:
            settings_manager: Service for managing settings
            layer_service: Service for layer operations
            file_system_service: Service for file system operations
        """
        QObject.__init__(self)
        self._settings_manager = settings_manager
        self._layer_service = layer_service
        self._file_system_service = file_system_service
    
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
            from .import_validation_service import remove_pending_import_layers

            project = QgsProject.instance()
            if project is not None:
                remove_pending_import_layers(
                    project,
                    layer_service=self._layer_service,
                    get_setting=self._settings_manager.get_value,
                )

            self._last_imported_projects = []
            successfully_imported_project_paths: List[str] = []
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
            alternative_objects_merged_count = 0
            alternative_objects_raw_count = 0
            global_projects_count = 0
            source_layer_files_count = 0
            processed_projects = 0
            failed_projects = 0
            
            for project_path in project_paths:
                try:
                    project_import_layers = get_import_layer_names(project_path)
                    project_configured_layers = self._configured_layers_for_project(
                        configured_layers,
                        project_import_layers,
                    )

                    # Scan for layer files in the project
                    layer_files = self._scan_project_layers(
                        project_path,
                        project_import_layers=project_import_layers,
                    )
                    source_layer_files_count += sum(len(paths) for paths in layer_files.values())
                    
                    # Process individual layer files that match configured layers
                    individual_features = self._process_individual_layers_with_matching(
                        layer_files,
                        project_configured_layers,
                    )
                    all_objects_features.extend(individual_features.get('objects', []))
                    all_features_features.extend(individual_features.get('features', []))
                    all_small_finds_features.extend(individual_features.get('small_finds', []))

                    if is_global_project(project_path):
                        global_projects_count += 1

                    alt_paths = layer_files.get('alternative_objects', [])
                    if alt_paths:
                        alt_features = self._process_alternative_objects_layers(
                            alt_paths,
                            project_import_layers,
                        )
                        alternative_objects_raw_count += len(alt_features)
                        converted = self._convert_alternative_features_to_objects(alt_features)
                        alternative_objects_merged_count += len(converted)
                        all_objects_features.extend(converted)
                    
                    processed_projects += 1
                    successfully_imported_project_paths.append(project_path)
                    
                except Exception as e:
                    print(f"Error processing project {project_path}: {str(e)}")
                    failed_projects += 1
                    continue
            
            zone_number_duplicate_warnings: List[Any] = []

            # Filter out duplicates before creating merged layers
            filtered_objects_features = self._filter_duplicates(all_objects_features, existing_objects_layer, "Objects")
            filtered_features_features = self._filter_duplicates(all_features_features, existing_features_layer, "Features")
            filtered_small_finds_features = self._filter_duplicates(all_small_finds_features, existing_small_finds_layer, "Small Finds")
            
            # Create merged layers
            layers_created = 0
            
            if filtered_objects_features:
                objects_layer = self._create_merged_layer("New Objects", filtered_objects_features)
                if objects_layer:
                    QgsProject.instance().addMapLayer(objects_layer)
                    self._apply_definitive_layer_style(objects_layer, "objects_layer")
                    layers_created += 1
            
            if filtered_features_features:
                features_layer = self._create_merged_layer("New Features", filtered_features_features)
                if features_layer:
                    QgsProject.instance().addMapLayer(features_layer)
                    self._apply_definitive_layer_style(features_layer, "features_layer")
                    layers_created += 1
            
            if filtered_small_finds_features:
                small_finds_layer = self._create_merged_layer("New Small Finds", filtered_small_finds_features)
                if small_finds_layer:
                    QgsProject.instance().addMapLayer(small_finds_layer)
                    self._apply_definitive_layer_style(small_finds_layer, "small_finds_layer")
                    layers_created += 1

            # Zone/number warnings apply to objects kept after duplicate filtering (non-exact
            # conflicts). Exact duplicates are silently removed and must not trigger warnings.
            if filtered_objects_features and existing_objects_layer:
                zone_number_duplicate_warnings = self._build_zone_number_duplicate_warnings(
                    filtered_objects_features,
                    existing_objects_layer,
                )
            
            # Store imported projects for later archiving instead of archiving immediately
            self._last_imported_projects = successfully_imported_project_paths
            
            # Store import statistics for summary
            self._last_import_stats = {
                'features_count': len(filtered_features_features),
                'objects_count': len(filtered_objects_features),
                'small_finds_count': len(filtered_small_finds_features),
                'features_duplicates': len(all_features_features) - len(filtered_features_features),
                'objects_duplicates': len(all_objects_features) - len(filtered_objects_features),
                'small_finds_duplicates': len(all_small_finds_features) - len(filtered_small_finds_features),
                'alternative_objects_merged_count': alternative_objects_merged_count,
                'global_projects_count': global_projects_count,
                'is_global_project': global_projects_count > 0,
                'source_layer_files_count': source_layer_files_count,
                'duplicate_objects_warnings': zone_number_duplicate_warnings,
            }
            
            total_detected_features = (
                len(all_objects_features)
                + len(all_features_features)
                + len(all_small_finds_features)
            )
            total_remaining_features = (
                len(filtered_objects_features)
                + len(filtered_features_features)
                + len(filtered_small_finds_features)
            )

            # Prepare result message
            if layers_created > 0:
                message = f"Successfully imported {layers_created} layer(s) from {processed_projects} project(s)"
                if failed_projects > 0:
                    message += f" ({failed_projects} project(s) failed)"
                return ValidationResult(True, message)
            if total_detected_features > 0 and total_remaining_features == 0:
                return ValidationResult(
                    True,
                    "No new entities imported: all detected entities are duplicates of existing project data",
                )
            if total_detected_features > 0:
                return ValidationResult(
                    False,
                    "Import layers were detected but could not be created (check geometry/type compatibility)",
                )
            if source_layer_files_count > 0:
                message = (
                    "Layer files were found but no features could be read "
                    "(check GeoPackage layer names and geometry types; see the QGIS message log for details)"
                )
                if alternative_objects_raw_count > 0:
                    message += (
                        ". Alternative-object rows were read but could not be mapped "
                        "onto the configured Objects layer in this project"
                    )
                return ValidationResult(False, message)
            return ValidationResult(False, "No Objects, Features, or Small Finds layers found in any project")
                
        except Exception as e:
            return ValidationResult(False, f"Error during import: {str(e)}")
    
    def get_last_import_stats(self) -> Dict[str, int]:
        """
        Get the import statistics from the last import operation.
        
        Returns:
            Dictionary containing import statistics
        """
        return getattr(self, '_last_import_stats', {})
    
    def get_last_imported_projects(self) -> List[str]:
        """
        Get the list of projects imported in the last import operation.
        
        Returns:
            List of imported project paths, or empty list if no import has been performed
        """
        return getattr(self, '_last_imported_projects', [])
    
    def clear_last_imported_projects(self) -> None:
        """Clear pending field-project archive paths from a previous import session."""
        self._last_imported_projects = []
        self._last_import_stats = {}
    
    def archive_last_imported_projects(self) -> None:
        """
        Archive the projects from the last import operation.
        This method should be called after validation is complete.
        """
        imported_projects = self.get_last_imported_projects()
        if imported_projects:
            self._archive_projects(imported_projects)
            # Clear the stored projects after archiving
            self._last_imported_projects = []
    
    def _configured_layers_for_project(
        self,
        base_configured_layers: Dict[str, Any],
        project_import_layers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Overlay source-project layer names from field metadata onto configured layer info.

        Used for global projects so OGR layer names match the original project export.
        """
        if not project_import_layers:
            return base_configured_layers

        configured_layers = copy.deepcopy(base_configured_layers)
        for layer_type in ("objects", "features", "small_finds"):
            layer_name = project_import_layers.get(layer_type)
            if layer_name:
                configured_layers[layer_type]["name"] = layer_name
        return configured_layers

    def _scan_project_layers(
        self,
        project_path: str,
        project_import_layers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, List[str]]:
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
            'small_finds': [],
            'alternative_objects': [],
        }
        
        if not os.path.exists(project_path):
            return layer_files
        
        # Look for individual layer files
        for filename in os.listdir(project_path):
            file_path = os.path.join(project_path, filename)
            if not os.path.isfile(file_path):
                continue

            if not filename.lower().endswith(".gpkg"):
                continue

            layer_type = self._classify_import_gpkg_filename(
                filename,
                project_import_layers=project_import_layers,
            )
            if layer_type:
                layer_files[layer_type].append(file_path)
                print(f"[DEBUG] Classified {filename} as {layer_type}")
            elif self._is_readonly_context_layer_file(filename):
                print(f"[DEBUG] Skipping read-only context layer file {filename}")
                continue
            else:
                print(f"[DEBUG] Unrecognized GeoPackage in field project: {filename}")
        
        return layer_files

    def get_project_kind(self, project_path: str) -> str:
        """Return the metadata project kind for a field project directory."""
        return get_project_kind(project_path)
    
    def _get_configured_layer_info(self) -> Dict[str, Any]:
        """
        Get the configured layer information (name, geometry type, and field types) from settings.
        
        Returns:
            Dictionary mapping layer types to their names, geometry types, and field types.
        """
        configured_layers = {
            'objects': {'name': None, 'geometry_type': None, 'field_types': {}},
            'features': {'name': None, 'geometry_type': None, 'field_types': {}},
            'small_finds': {'name': None, 'geometry_type': None, 'field_types': {}}
        }
        
        # QGIS field type name to memory layer URI type mapping
        QGIS_TO_URI_TYPE = {
            "Integer": "integer",
            "Integer64": "integer64",
            "Real": "real",
            "String": "string",
            "Date": "date",
            "DateTime": "datetime",
            "Boolean": "boolean"
        }
        
        # Get objects layer info
        objects_layer_id = self._settings_manager.get_value('objects_layer', '')
        if objects_layer_id:
            layer_info = self._layer_service.get_layer_info(objects_layer_id)
            if layer_info:
                configured_layers['objects']['name'] = layer_info['name']
                configured_layers['objects']['geometry_type'] = layer_info.get('geometry_type', 2)  # Default to polygon
                # Get field types from the actual layer
                layer = self._get_existing_layer('objects_layer')
                if layer:
                    for field in layer.fields():
                        field_type = field.typeName()
                        uri_type = QGIS_TO_URI_TYPE.get(field_type, field_type.lower())
                        configured_layers['objects']['field_types'][field.name()] = uri_type
        
        # Get features layer info
        features_layer_id = self._settings_manager.get_value('features_layer', '')
        if features_layer_id:
            layer_info = self._layer_service.get_layer_info(features_layer_id)
            if layer_info:
                configured_layers['features']['name'] = layer_info['name']
                configured_layers['features']['geometry_type'] = layer_info.get('geometry_type', 2)  # Default to polygon
                # Get field types from the actual layer
                layer = self._get_existing_layer('features_layer')
                if layer:
                    for field in layer.fields():
                        field_type = field.typeName()
                        uri_type = QGIS_TO_URI_TYPE.get(field_type, field_type.lower())
                        configured_layers['features']['field_types'][field.name()] = uri_type
        
        # Get small finds layer info
        small_finds_layer_id = self._settings_manager.get_value('small_finds_layer', '')
        if small_finds_layer_id:
            layer_info = self._layer_service.get_layer_info(small_finds_layer_id)
            if layer_info:
                configured_layers['small_finds']['name'] = layer_info['name']
                configured_layers['small_finds']['geometry_type'] = layer_info.get('geometry_type', 0)  # Default to point
                # Get field types from the actual layer
                layer = self._get_existing_layer('small_finds_layer')
                if layer:
                    for field in layer.fields():
                        field_type = field.typeName()
                        uri_type = QGIS_TO_URI_TYPE.get(field_type, field_type.lower())
                        configured_layers['small_finds']['field_types'][field.name()] = uri_type
        
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
            features['objects'].extend(
                self._collect_features_from_geopackage(
                    file_path,
                    configured_layers['objects']['name'],
                    configured_layers['objects']['geometry_type'],
                )
            )
        
        # Process Features layer files
        for file_path in layer_files['features']:
            features['features'].extend(
                self._collect_features_from_geopackage(
                    file_path,
                    configured_layers['features']['name'],
                    configured_layers['features']['geometry_type'],
                )
            )
        
        # Process Small Finds layer files
        for file_path in layer_files['small_finds']:
            features['small_finds'].extend(
                self._collect_features_from_geopackage(
                    file_path,
                    configured_layers['small_finds']['name'],
                    configured_layers['small_finds']['geometry_type'],
                )
            )
        
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
            elif point_features:
                # Check if any point features are multipart
                has_multipart_points = any(f.geometry().isMultipart() for f in point_features)
                geom_string = "MultiPoint" if has_multipart_points else "Point"
            else:
                # No features have geometry, create a layer without geometry
                geom_string = "None"  # No geometry
            
            # Get CRS - try project CRS first, then fall back to default
            project_crs = QgsProject.instance().crs()
            if project_crs and project_crs.isValid():
                crs_string = self._get_crs_string(project_crs)
            else:
                crs_string = "EPSG:4326"  # Default fallback
            
            # Create layer URI with fields
            layer_uri = f"{geom_string}?crs={crs_string}"
            
            # QGIS field type name to memory layer URI type mapping
            QGIS_TO_URI_TYPE = {
                "Integer": "integer",
                "Integer64": "integer64",
                "Real": "real",
                "String": "string",
                "Date": "date",
                "DateTime": "datetime",
                "Boolean": "boolean"
            }
            
            # Get field types from original configured layers as reference
            reference_field_types = {}
            configured_layers = self._get_configured_layer_info()
            
            # Determine which layer type this merged layer corresponds to
            layer_type = None
            if "objects" in layer_name.lower():
                layer_type = 'objects'
            elif "features" in layer_name.lower():
                layer_type = 'features'
            elif "small" in layer_name.lower() or "petits" in layer_name.lower():
                layer_type = 'small_finds'
            
            if layer_type and configured_layers[layer_type]['field_types']:
                reference_field_types = configured_layers[layer_type]['field_types']
            else:
                reference_field_types = {}
            
            # Add fields with most common types
            for field_name in sorted(all_fields):
                if field_name in field_types:
                    # Get the most common type for this field
                    most_common_type = max(field_types[field_name].items(), key=lambda x: x[1])[0]
                    
                    # Use reference layer type if available, otherwise use detected type
                    if field_name in reference_field_types:
                        reference_type = reference_field_types[field_name]
                        uri_type = QGIS_TO_URI_TYPE.get(reference_type, reference_type.lower())
                    else:
                        uri_type = QGIS_TO_URI_TYPE.get(most_common_type, most_common_type.lower())
                    
                    layer_uri += f"&field={field_name}:{uri_type}"
            
            # Create memory layer with basic structure first
            basic_uri = f"{geom_string}?crs={crs_string}"
            layer = QgsVectorLayer(basic_uri, layer_name, "memory")
            if not layer.isValid():
                return None
            
            # Add fields with proper types using QgsField objects
            from qgis.core import QgsField
            from qgis.PyQt.QtCore import QVariant
            
            # QGIS field type name to QVariant type mapping
            QGIS_TO_QVARIANT = {
                "Integer": QVariant.Int,
                "Integer64": QVariant.LongLong,
                "Real": QVariant.Double,
                "String": QVariant.String,
                "Date": QVariant.Date,
                "DateTime": QVariant.DateTime,
                "Boolean": QVariant.Bool
            }
            
            # Add fields with most common types
            field_list = []
            for field_name in sorted(all_fields):
                if field_name in field_types:
                    # Get the most common type for this field
                    most_common_type = max(field_types[field_name].items(), key=lambda x: x[1])[0]
                    
                    # Use reference layer type if available, otherwise use detected type
                    if field_name in reference_field_types:
                        reference_type = reference_field_types[field_name]
                        # Convert URI type back to QGIS type name for QVariant mapping
                        if reference_type == "integer":
                            qgis_type = "Integer"
                        elif reference_type == "integer64":
                            qgis_type = "Integer64"
                        elif reference_type == "real":
                            qgis_type = "Real"
                        elif reference_type == "string":
                            qgis_type = "String"
                        elif reference_type == "date":
                            qgis_type = "Date"
                        elif reference_type == "datetime":
                            qgis_type = "DateTime"
                        elif reference_type == "boolean":
                            qgis_type = "Boolean"
                        else:
                            qgis_type = most_common_type
                    else:
                        qgis_type = most_common_type
                    
                    # Create QgsField with proper type
                    qvariant_type = QGIS_TO_QVARIANT.get(qgis_type, QVariant.String)
                    new_field = QgsField(field_name, qvariant_type, qgis_type)
                    field_list.append(new_field)
            
            # Add all fields to the layer
            layer.dataProvider().addAttributes(field_list)
            layer.updateFields()
            
            # Add features, filtering out incompatible geometries
            layer.startEditing()
            added_count = 0
            skipped_count = 0
            
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
                        continue
                else:
                    # Feature has no geometry, which is fine for layers with geometry (will be NULL)
                    pass
                
                # Copy attributes by field name (case-insensitive matching)
                # Build a mapping from lower-case source field names to their indices
                source_fields = feature.fields()
                source_field_name_to_index = {source_fields.at(i).name().lower(): i for i in range(source_fields.count())}
                for i, field in enumerate(layer.fields()):
                    field_name = field.name()
                    source_field_idx = source_field_name_to_index.get(field_name.lower(), -1)
                    if source_field_idx >= 0:
                        new_feature[field_name] = feature[source_field_idx]
                    else:
                        # Field doesn't exist in source, set to NULL
                        new_feature[field_name] = None
                
                # Add the new feature
                success = layer.addFeature(new_feature)
                if success:
                    added_count += 1
                else:
                    skipped_count += 1
            
            layer.commitChanges()
            
            return layer
            
        except Exception as e:
            print(f"Error creating merged layer {layer_name}: {str(e)}")
            return None
    
    def _is_readonly_context_layer_file(self, filename: str) -> bool:
        """Return True for recording-area or extra layer exports that must not be imported."""
        if self._is_recording_areas_layer_file(filename):
            return True
        return self._is_extra_field_layer_file(filename)

    def _is_recording_areas_layer_file(self, filename: str) -> bool:
        """Check if a filename represents the recording areas layer file."""
        filename_lower = filename.lower()
        if not filename_lower.endswith('.gpkg'):
            return False
        name_without_ext = filename_lower[:-5]
        recording_areas_layer_id = self._settings_manager.get_value('recording_areas_layer', '')
        if recording_areas_layer_id:
            layer_info = self._layer_service.get_layer_info(recording_areas_layer_id)
            if layer_info and layer_info['name'].lower() == name_without_ext:
                return True
        return False

    def _is_extra_field_layer_file(self, filename: str) -> bool:
        """Check if a filename matches a configured extra field layer."""
        filename_lower = filename.lower()
        if not filename_lower.endswith('.gpkg'):
            return False
        name_without_ext = filename_lower[:-5]
        extra_layers = self._settings_manager.get_value('extra_field_layers', []) or []
        for layer_id in extra_layers:
            layer_info = self._layer_service.get_layer_info(layer_id)
            if layer_info and layer_info['name'].lower() == name_without_ext:
                return True
        return False

    def _normalize_layer_name_for_match(self, name: str) -> str:
        """
        Normalize a layer or filename stem for comparison.

        Applies Unicode compatibility, strips accents, lowercases, and collapses whitespace.
        """
        if not name:
            return ""
        normalized = unicodedata.normalize("NFC", name)
        without_accents = "".join(
            character
            for character in unicodedata.normalize("NFKD", normalized)
            if not unicodedata.combining(character)
        )
        return " ".join(without_accents.lower().strip().split())

    def _classify_import_gpkg_filename(
        self,
        filename: str,
        project_import_layers: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """
        Map a GeoPackage filename to an import layer type using layer names.

        For global projects, names recorded in ``archeosync_project.json`` at export time
        (from the original QGIS project) take precedence over current plugin settings.

        Longer names are checked first so
        ``Objets relevés sans géométrie.gpkg`` is not mistaken for ``Objets relevés.gpkg``.
        """
        if not filename.lower().endswith(".gpkg"):
            return None

        stem = self._normalize_layer_name_for_match(os.path.splitext(filename)[0])
        if not stem:
            return None

        configured_matches: List[tuple] = []
        metadata_types = set()
        if project_import_layers:
            for layer_type in (
                "alternative_objects",
                "objects",
                "features",
                "small_finds",
            ):
                layer_name = project_import_layers.get(layer_type)
                if not layer_name:
                    continue
                normalized_name = self._normalize_layer_name_for_match(layer_name)
                configured_matches.append((len(normalized_name), layer_type, normalized_name))
                metadata_types.add(layer_type)

        for layer_type, setting_key in (
            ("alternative_objects", "alternative_objects_layer"),
            ("objects", "objects_layer"),
            ("features", "features_layer"),
            ("small_finds", "small_finds_layer"),
        ):
            if layer_type in metadata_types:
                continue
            layer_id = self._settings_manager.get_value(setting_key, "")
            if not layer_id:
                continue
            layer_info = self._layer_service.get_layer_info(layer_id)
            if not layer_info or not layer_info.get("name"):
                continue
            normalized_name = self._normalize_layer_name_for_match(layer_info["name"])
            configured_matches.append((len(normalized_name), layer_type, normalized_name))

        configured_matches.sort(key=lambda item: item[0], reverse=True)
        for _, layer_type, normalized_name in configured_matches:
            if stem == normalized_name:
                return layer_type

        if stem in ("objects", "objets", "obj"):
            return "objects"
        if stem in ("features", "feat", "fugaces"):
            return "features"
        if stem in ("small_finds", "smallfinds", "esquilles"):
            return "small_finds"
        return None

    def _is_alternative_objects_layer_file(self, filename: str) -> bool:
        """Check if a filename represents the alternative objects layer file."""
        return self._classify_import_gpkg_filename(filename) == "alternative_objects"

    def _process_alternative_objects_layers(
        self,
        file_paths: List[str],
        project_import_layers: Optional[Dict[str, str]] = None,
    ) -> List[Any]:
        """Load features from alternative objects Geopackage files."""
        features: List[Any] = []
        configured_name = None
        if project_import_layers and project_import_layers.get("alternative_objects"):
            configured_name = project_import_layers["alternative_objects"]
        else:
            alt_layer_id = self._settings_manager.get_value('alternative_objects_layer', '')
            alt_info = self._layer_service.get_layer_info(alt_layer_id) if alt_layer_id else None
            configured_name = alt_info['name'] if alt_info else None
        for file_path in file_paths:
            features.extend(
                self._collect_features_from_geopackage(file_path, configured_name, None)
            )
        return features

    def _convert_alternative_features_to_objects(self, source_features: List[Any]) -> List[Any]:
        """
        Map alternative-object rows onto the configured objects layer schema.

        Returned features have no geometry so they can be merged into New Objects.
        """
        target_layer = self._get_existing_layer('objects_layer')
        if not target_layer:
            if source_features:
                print(
                    "Warning: configured Objects layer is not loaded in the current QGIS project; "
                    "alternative-object rows cannot be converted"
                )
            return []
        if not source_features:
            return []

        converted = []
        target_fields = target_layer.fields()
        for source_feature in source_features:
            new_feature = QgsFeature(target_fields)
            source_fields_by_lower_name = {
                field.name().lower(): field.name()
                for field in source_feature.fields()
            }
            for field in source_feature.fields():
                field_name = field.name()
                if field_name.lower() in ('fid', 'ogc_fid'):
                    continue
                target_idx = target_fields.indexOf(field_name)
                if target_idx >= 0:
                    new_feature.setAttribute(target_idx, source_feature.attribute(field.name()))
            # Complete mapping for case-only differences between schemas.
            for target_idx in range(target_fields.count()):
                target_name = target_fields.at(target_idx).name()
                if target_name.lower() in ('fid', 'ogc_fid'):
                    continue
                current_value = new_feature.attribute(target_idx)
                if current_value is not None:
                    continue
                source_name = source_fields_by_lower_name.get(target_name.lower())
                if source_name is not None:
                    new_feature.setAttribute(target_idx, source_feature.attribute(source_name))
            empty_geometry = QgsGeometry()
            new_feature.setGeometry(empty_geometry)
            converted.append(new_feature)
        return converted

    def _is_objects_layer_file(self, filename: str) -> bool:
        """Check if a filename represents an Objects layer file."""
        return self._classify_import_gpkg_filename(filename) == "objects"

    def _is_features_layer_file(self, filename: str) -> bool:
        """Check if a filename represents a Features layer file."""
        return self._classify_import_gpkg_filename(filename) == "features"

    def _is_small_finds_layer_file(self, filename: str) -> bool:
        """Check if a filename represents a Small Finds layer file."""
        return self._classify_import_gpkg_filename(filename) == "small_finds"
    
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

    def _apply_definitive_layer_style(self, temp_layer: Any, layer_setting_key: str) -> None:
        """
        Apply symbology, forms, and relations from a definitive project layer to a temp layer.

        Args:
            temp_layer: Temporary import layer to configure
            layer_setting_key: Settings key for the definitive layer (e.g. ``objects_layer``)
        """
        source_layer = self._get_existing_layer(layer_setting_key)
        if not source_layer or not temp_layer:
            return
        self._layer_service.configure_temporary_field_import_layer(
            source_layer,
            temp_layer,
            peer_layer_replacements=self._build_peer_temp_layer_replacements(),
        )

    def _build_peer_temp_layer_replacements(self) -> Dict[str, str]:
        """
        Map definitive layer ids to active temporary import layer ids in the project.

        Used when cloning project relations so relations between two definitive import
        layers (e.g. Objects and Features) are reproduced on their temporary counterparts.
        """
        try:
            from .import_validation_service import build_peer_temp_layer_replacements

            project = QgsProject.instance()
            if project is None:
                return {}
            return build_peer_temp_layer_replacements(
                project.mapLayers(),
                self._settings_manager.get_value,
            )
        except Exception as exc:
            print(f"Error building peer temp layer replacements: {exc}")
            return {}

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
            print(f"[DEBUG] No existing layer or no features to filter for {layer_type}")
            return features
        
        # Get all existing features for comparison
        existing_features = list(existing_layer.getFeatures())
        print(f"[DEBUG] Filtering duplicates for {layer_type}: {len(features)} features to check against {len(existing_features)} existing features")

        if layer_type == "Objects":
            return self._filter_object_duplicates(
                features,
                existing_layer,
                existing_features,
            )
        
        # Create a set of existing feature signatures for fast lookup
        existing_signatures = set()
        for existing_feature in existing_features:
            signature = self._create_feature_signature(existing_feature, existing_layer)
            existing_signatures.add(signature)
        
        # Filter out duplicates
        filtered_features = []
        duplicates_count = 0
        for feature in features:
            signature = self._create_feature_signature(feature, existing_layer)
            # Ambiguous rows without zone/number (or other layers) cannot be matched safely.
            if signature == "||NO_GEOM":
                filtered_features.append(feature)
                continue
            if signature not in existing_signatures:
                filtered_features.append(feature)
            else:
                duplicates_count += 1
        print(f"[DEBUG] {duplicates_count} duplicates found and ignored for {layer_type}")
        return filtered_features

    def _filter_object_duplicates(
        self,
        features: List[Any],
        existing_layer: Any,
        existing_features: List[Any],
    ) -> List[Any]:
        """
        Filter imported object features, including cross-layer dedup between geometric
        objects and alternative no-geometry rows using full attribute equality.
        """
        existing_signatures: set = set()
        existing_no_geom_attr_sigs: set = set()
        existing_geometric_attr_sigs: set = set()
        for existing_feature in existing_features:
            existing_signatures.add(
                self._create_feature_signature(existing_feature, existing_layer)
            )
            attr_sig = self._create_attribute_signature(existing_feature, existing_layer)
            if not attr_sig:
                continue
            if self._feature_has_empty_geometry(existing_feature):
                existing_no_geom_attr_sigs.add(attr_sig)
            else:
                existing_geometric_attr_sigs.add(attr_sig)

        geometric_features = [
            feature for feature in features if not self._feature_has_empty_geometry(feature)
        ]
        no_geom_features = [
            feature for feature in features if self._feature_has_empty_geometry(feature)
        ]

        filtered_geometric: List[Any] = []
        kept_geometric_attr_sigs: set = set()
        duplicates_count = 0

        for feature in geometric_features:
            signature = self._create_feature_signature(feature, existing_layer)
            if signature not in existing_signatures:
                filtered_geometric.append(feature)
                attr_sig = self._create_attribute_signature(feature, existing_layer)
                if attr_sig:
                    kept_geometric_attr_sigs.add(attr_sig)
            else:
                duplicates_count += 1

        filtered_no_geom: List[Any] = []
        imported_no_geom_attr_sigs: set = set()

        for feature in no_geom_features:
            attr_sig = self._create_attribute_signature(feature, existing_layer)
            if not attr_sig:
                filtered_no_geom.append(feature)
                continue
            if attr_sig in existing_no_geom_attr_sigs:
                print(
                    f"[DEBUG] Excluding no-geometry object duplicate "
                    f"(attributes={attr_sig}) already in definitive data"
                )
                duplicates_count += 1
                continue
            if attr_sig in existing_geometric_attr_sigs:
                print(
                    f"[DEBUG] Excluding no-geometry object duplicate "
                    f"(attributes={attr_sig}) already represented by definitive geometry"
                )
                duplicates_count += 1
                continue
            if attr_sig in imported_no_geom_attr_sigs:
                print(
                    f"[DEBUG] Excluding no-geometry object duplicate "
                    f"(attributes={attr_sig}) already in this import batch"
                )
                duplicates_count += 1
                continue
            if attr_sig in kept_geometric_attr_sigs:
                print(
                    f"[DEBUG] Excluding no-geometry object duplicate "
                    f"(attributes={attr_sig}) already represented by imported geometry"
                )
                duplicates_count += 1
                continue
            imported_no_geom_attr_sigs.add(attr_sig)
            filtered_no_geom.append(feature)

        print(f"[DEBUG] {duplicates_count} duplicates found and ignored for Objects")
        return filtered_geometric + filtered_no_geom

    def _feature_has_empty_geometry(self, feature: Any) -> bool:
        """Return True when a feature has no geometry or an empty geometry."""
        try:
            if hasattr(feature, "hasGeometry"):
                return not feature.hasGeometry()
        except Exception:
            pass

        geometry = feature.geometry()
        if geometry is None:
            return True
        try:
            if geometry.isNull() or geometry.isEmpty():
                return True
            if hasattr(QgsWkbTypes, "NullGeometry") and geometry.type() == QgsWkbTypes.NullGeometry:
                return True
            if geometry.type() == 4:
                return True
        except Exception:
            return True
        return False

    def _build_existing_no_geometry_object_identity_keys(
        self,
        objects_layer: Optional[Any],
        objects_features: List[Any],
    ) -> set:
        """
        Identity keys for definitive no-geometry rows in the main Objects layer.

        Only the configured Objects layer is used (not alternative-objects), because
        both layers often mirror the same data and would double-count identities.
        """
        if not objects_layer or not objects_features:
            return set()

        keys = self._collect_object_identity_keys(
            objects_features,
            objects_layer,
            only_empty_geometry=True,
        )
        print(
            f"[DEBUG] Loaded {len(keys)} no-geometry object identity key(s) "
            f"from definitive Objects layer"
        )
        return keys

    def _normalize_object_identity_value(self, value: Any) -> Any:
        """Normalize attribute values used in object duplicate identity keys."""
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "" or stripped.lower() == "null":
                return None
            return stripped
        try:
            if isinstance(value, float) and value.is_integer():
                return int(value)
        except (TypeError, ValueError):
            pass
        return value

    def _get_field_index_case_insensitive_on_fields(self, fields: Any, field_name: str) -> int:
        """Return a field index on a QgsFields collection, matching names case-insensitively."""
        field_idx = fields.indexOf(field_name)
        if field_idx >= 0:
            return field_idx
        target = field_name.lower()
        for field in fields:
            if field.name().lower() == target:
                return fields.indexOf(field.name())
        return -1

    def _get_feature_attribute_case_insensitive(self, feature: Any, field_name: str) -> Any:
        """Read a feature attribute by field name using the feature's own field schema."""
        if not field_name:
            return None
        fields = feature.fields()
        if fields is None:
            return None
        field_idx = self._get_field_index_case_insensitive_on_fields(fields, field_name)
        if field_idx < 0:
            return None
        return feature.attribute(field_idx)

    def _resolve_field_name_on_layer(self, layer: Any, field_name: str) -> Optional[str]:
        """Return the canonical field name present on ``layer`` for ``field_name``."""
        field_idx = self._get_field_index_case_insensitive(layer, field_name)
        if field_idx < 0:
            return None
        return layer.fields().at(field_idx).name()

    def _resolve_field_name_on_feature(self, feature: Any, field_name: str) -> Optional[str]:
        """Return the canonical field name present on ``feature`` for ``field_name``."""
        fields = feature.fields()
        if fields is None:
            return None
        field_idx = self._get_field_index_case_insensitive_on_fields(fields, field_name)
        if field_idx < 0:
            return None
        return fields.at(field_idx).name()

    def _get_objects_recording_area_field(self, objects_layer: Any) -> Optional[str]:
        """
        Resolve the recording-area foreign-key field on the objects layer.

        Uses QGIS relations first, then the alternative-objects field setting.
        """
        recording_areas_layer_id = self._settings_manager.get_value("recording_areas_layer", "")
        if recording_areas_layer_id and objects_layer:
            recording_areas_layer = self._layer_service.get_layer_by_id(recording_areas_layer_id)
            if recording_areas_layer:
                relation_field = self._get_recording_area_field_from_relation(
                    objects_layer,
                    recording_areas_layer,
                )
                if relation_field:
                    return relation_field

        configured_field = self._settings_manager.get_value("objects_recording_area_field", "")
        if configured_field:
            return configured_field

        alternative_field = self._settings_manager.get_value(
            "alternative_objects_recording_area_field",
            "",
        )
        return alternative_field or None

    def _get_recording_area_field_from_relation(
        self,
        objects_layer: Any,
        recording_areas_layer: Any,
    ) -> Optional[str]:
        """Return the objects-layer field that references recording areas via project relations."""
        try:
            from qgis.core import QgsProject

            relation_manager = QgsProject.instance().relationManager()
            objects_layer_id = objects_layer.id()
            recording_areas_layer_id = recording_areas_layer.id()
            for relation in relation_manager.relations().values():
                referencing_layer = relation.referencingLayer()
                referenced_layer = relation.referencedLayer()
                if referencing_layer is None or referenced_layer is None:
                    continue
                if (
                    referencing_layer.id() == objects_layer_id
                    and referenced_layer.id() == recording_areas_layer_id
                ):
                    field_pairs = relation.fieldPairs()
                    if field_pairs:
                        return list(field_pairs.keys())[0]
        except Exception as exc:
            print(f"Error resolving recording-area relation field: {exc}")
        return None

    def _get_field_index_case_insensitive(self, layer: Any, field_name: str) -> int:
        """Return a field index, matching field names case-insensitively when needed."""
        return self._get_field_index_case_insensitive_on_fields(layer.fields(), field_name)

    def _get_object_identity_key(
        self,
        feature: Any,
        reference_layer: Any,
        recording_area_field: Optional[str] = None,
    ) -> Optional[Tuple[Any, Any]]:
        """
        Build a duplicate identity for objects without geometry (alternative-object rows).

        Matches the duplicate-objects detector: recording area + object number.
        """
        number_field = self._settings_manager.get_value("objects_number_field", "")
        if not number_field or reference_layer is None:
            return None

        resolved_number_field = self._resolve_field_name_on_layer(reference_layer, number_field)
        if not resolved_number_field:
            return None

        object_number = self._normalize_object_identity_value(
            self._get_feature_attribute_case_insensitive(feature, resolved_number_field)
        )
        if object_number is None or object_number == "":
            return None

        candidate_recording_fields: List[str] = []
        if recording_area_field:
            candidate_recording_fields.append(recording_area_field)
        else:
            relation_field = self._get_objects_recording_area_field(reference_layer)
            if relation_field:
                candidate_recording_fields.append(relation_field)
            configured_field = self._settings_manager.get_value("objects_recording_area_field", "")
            if configured_field and configured_field not in candidate_recording_fields:
                candidate_recording_fields.append(configured_field)
            alternative_field = self._settings_manager.get_value(
                "alternative_objects_recording_area_field",
                "",
            )
            if alternative_field and alternative_field not in candidate_recording_fields:
                candidate_recording_fields.append(alternative_field)

        recording_area_id = None
        for field_name in candidate_recording_fields:
            resolved_field = self._resolve_field_name_on_feature(feature, field_name)
            if not resolved_field:
                continue
            recording_area_id = self._normalize_object_identity_value(
                self._get_feature_attribute_case_insensitive(feature, resolved_field)
            )
            if recording_area_id is not None and recording_area_id != "":
                break
            recording_area_id = None

        if recording_area_id is None or recording_area_id == "":
            return None

        return (recording_area_id, object_number)

    def _build_zone_number_duplicate_warnings(
        self,
        imported_features: List[Any],
        reference_layer: Optional[Any],
    ) -> List[Any]:
        """
        Detect zone/number conflicts in the import batch and against definitive objects.

        Computed synchronously during import so the summary can show warnings immediately,
        including when some objects remain in New Objects (async detector merges later).
        """
        if not imported_features or reference_layer is None:
            return []

        try:
            from ..core.data_structures import WarningData
        except ImportError:
            from core.data_structures import WarningData

        recording_area_field = self._get_objects_recording_area_field(reference_layer) or ""
        number_field = self._settings_manager.get_value("objects_number_field", "") or ""
        recording_area_field_arg = recording_area_field or None

        existing_identity_counts: Dict[Tuple[Any, Any], int] = {}
        for feature in reference_layer.getFeatures():
            identity_key = self._get_object_identity_key(
                feature,
                reference_layer,
                recording_area_field=recording_area_field_arg,
            )
            if identity_key is None:
                continue
            existing_identity_counts[identity_key] = existing_identity_counts.get(identity_key, 0) + 1

        batch_counts: Dict[Tuple[Any, Any], int] = {}
        for feature in imported_features:
            identity_key = self._get_object_identity_key(
                feature,
                reference_layer,
                recording_area_field=recording_area_field_arg,
            )
            if identity_key is None:
                continue
            batch_counts[identity_key] = batch_counts.get(identity_key, 0) + 1

        recording_areas_layer_id = self._settings_manager.get_value("recording_areas_layer", "")
        recording_areas_layer = None
        if recording_areas_layer_id:
            recording_areas_layer = self._layer_service.get_layer_by_id(recording_areas_layer_id)
        recording_area_names = self._build_recording_area_name_lookup(recording_areas_layer)

        warnings: List[Any] = []
        warned_identities = set()

        for identity_key, import_count in batch_counts.items():
            recording_area_id, object_number = identity_key
            recording_area_name = recording_area_names.get(recording_area_id, str(recording_area_id))
            definitive_count = existing_identity_counts.get(identity_key, 0)

            if definitive_count > 0 and identity_key not in warned_identities:
                warned_identities.add(identity_key)
                warnings.append(
                    WarningData(
                        message=(
                            f"Recording Area '{recording_area_name}' has {definitive_count} objects "
                            f"with number {object_number} in {reference_layer.name()} and New Objects"
                        ),
                        recording_area_name=recording_area_name,
                        layer_name=reference_layer.name(),
                        filter_expression=(
                            f'"{recording_area_field}" = \'{recording_area_id}\' '
                            f'AND "{number_field}" = {object_number}'
                        ),
                        object_number=object_number,
                        second_layer_name="New Objects",
                        second_filter_expression=(
                            f'"{recording_area_field}" = \'{recording_area_id}\' '
                            f'AND "{number_field}" = {object_number}'
                        ),
                    )
                )
                continue

            if import_count > 1 and identity_key not in warned_identities:
                warned_identities.add(identity_key)
                warnings.append(
                    WarningData(
                        message=(
                            f"Recording Area '{recording_area_name}' has {import_count} objects "
                            f"with number {object_number} in New Objects"
                        ),
                        recording_area_name=recording_area_name,
                        layer_name="New Objects",
                        filter_expression=(
                            f'"{recording_area_field}" = \'{recording_area_id}\' '
                            f'AND "{number_field}" = {object_number}'
                        ),
                        object_number=object_number,
                    )
                )

        return warnings

    def _build_recording_area_name_lookup(
        self,
        recording_areas_layer: Optional[Any],
    ) -> Dict[Any, str]:
        """Build a feature-id to display-name map for recording areas (single pass)."""
        if recording_areas_layer is None:
            return {}

        lookup: Dict[Any, str] = {}
        name_fields = ["name", "title", "label", "description", "comment"]
        name_field_indices = [
            recording_areas_layer.fields().indexOf(field_name) for field_name in name_fields
        ]
        try:
            for feature in recording_areas_layer.getFeatures():
                feature_id = feature.id()
                display_name = None
                for field_idx in name_field_indices:
                    if field_idx < 0:
                        continue
                    name_value = feature[field_idx]
                    if name_value and str(name_value) != "NULL":
                        display_name = str(name_value)
                        break
                lookup[feature_id] = display_name or str(feature_id)
        except Exception as exc:
            print(f"Error building recording area name lookup: {exc}")
        return lookup

    def _get_recording_area_display_name(
        self,
        recording_areas_layer: Optional[Any],
        recording_area_id: Any,
    ) -> str:
        """Resolve a human-readable recording area label for warning messages."""
        if recording_areas_layer is None:
            return str(recording_area_id)
        lookup = self._build_recording_area_name_lookup(recording_areas_layer)
        return lookup.get(recording_area_id, str(recording_area_id))

    def _collect_object_identity_keys(
        self,
        features: List[Any],
        reference_layer: Any,
        only_empty_geometry: bool = False,
        recording_area_field: Optional[str] = None,
    ) -> set:
        """
        Collect recording-area/number identity keys for a list of object features.

        When ``only_empty_geometry`` is True, geometric definitive objects are ignored
        so a no-geometry import is not excluded solely because a polygon with the same
        zone/number already exists (that case is handled by duplicate warnings).
        """
        keys = set()
        if recording_area_field is None:
            recording_area_field = self._get_objects_recording_area_field(reference_layer)
        for feature in features:
            if only_empty_geometry and not self._feature_has_empty_geometry(feature):
                continue
            identity_key = self._get_object_identity_key(
                feature,
                reference_layer,
                recording_area_field=recording_area_field,
            )
            if identity_key is not None:
                keys.add(identity_key)
        return keys
    
    def _build_attribute_signatures(
        self,
        features: List[Any],
        layer: Any,
        only_empty_geometry: bool = False,
    ) -> set:
        """
        Collect attribute signatures for a list of object features.

        When ``only_empty_geometry`` is True, only no-geometry features are included.
        """
        signatures: set = set()
        for feature in features:
            if only_empty_geometry and not self._feature_has_empty_geometry(feature):
                continue
            attr_sig = self._create_attribute_signature(feature, layer)
            if attr_sig:
                signatures.add(attr_sig)
        return signatures

    def _create_attribute_signature(self, feature: Any, layer: Any) -> str:
        """
        Create a signature from feature attributes, excluding geometry and fid fields.
        """
        attributes = []
        for field in feature.fields():
            field_name = field.name()
            if field_name.lower() in ("fid", "ogc_fid"):
                continue
            if self._is_virtual_field(layer, field_name):
                continue
            value = feature[field_name]
            if value is None:
                continue
            attributes.append(f"{field_name}:{str(value)}")
        attributes.sort()
        return "|".join(attributes)

    def _create_feature_signature(self, feature: Any, layer: Any) -> str:
        """
        Create a unique signature for a feature based on its attributes and geometry.
        
        Args:
            feature: QGIS feature to create signature for
            layer: QGIS layer to use for virtual field detection
            
        Returns:
            String signature representing the feature
        """
        attr_signature = self._create_attribute_signature(feature, layer)
        # Create signature from geometry (normalized to handle Polygon vs MultiPolygon)
        geometry = feature.geometry()
        if geometry and not geometry.isEmpty():
            # Normalize geometry by converting to single geometry type
            if geometry.isMultipart():
                # For multipart geometries, use the first part
                geom_parts = geometry.asGeometryCollection()
                if geom_parts:
                    geom_signature = geom_parts[0].asWkt()
                else:
                    geom_signature = geometry.asWkt()
            else:
                geom_signature = geometry.asWkt()
        else:
            geom_signature = "NO_GEOM"
        signature = f"{attr_signature}||{geom_signature}"
        return signature
    
    def _is_virtual_field(self, layer: Any, field_name: str) -> bool:
        """
        Check if a field is a virtual/computed field using the QGIS API and by parsing the QML style file for expression fields.
        Args:
            layer: QGIS layer to check
            field_name: Name of the field to check
        Returns:
            True if the field appears to be virtual/computed
        """
        try:
            # Get the field index
            field_idx = layer.fields().indexOf(field_name)
            if field_idx < 0:
                return False
            # Check QML style file for expression fields (most reliable for your use case)
            if hasattr(layer, 'styleURI'):
                qml_path = layer.styleURI()
                if qml_path and qml_path.endswith('.qml'):
                    virtual_fields = self._parse_qml_expression_fields(qml_path)
                    if field_name in virtual_fields:
                        return True
            # Also check QGIS API (for completeness)
            from qgis.core import QgsFields
            origin = layer.fields().fieldOrigin(field_idx)
            if origin == QgsFields.OriginExpression:
                return True
            # Fallback to previous checks if needed
            field_def = layer.fields().at(field_idx)
            if hasattr(field_def, 'isVirtual') and field_def.isVirtual():
                return True
            if hasattr(field_def, 'expression') and field_def.expression():
                return True
            return False
        except Exception as e:
            print(f"[DEBUG] Exception in _is_virtual_field for {field_name}: {str(e)}")
            return False

    def _parse_qml_expression_fields(self, qml_path):
        """Parse QML file to extract expression fields."""
        import xml.etree.ElementTree as ET
        try:
            tree = ET.parse(qml_path)
            root = tree.getroot()
            # Find expressionfields section
            expressionfields = root.find('.//expressionfields')
            if expressionfields is None:
                return {}
            virtual_fields = {}
            for field in expressionfields.findall('field'):
                name = field.get('name')
                expression = field.get('expression')
                if name and expression:
                    virtual_fields[name] = expression
            return virtual_fields
        except Exception as e:
            return {}

    def _geopackage_basename(self, file_path: str) -> str:
        """Return the filename stem for a GeoPackage path."""
        return os.path.splitext(os.path.basename(file_path))[0]

    def _expand_layer_name_candidates(self, names: Iterable[str]) -> List[str]:
        """Return OGR layer name variants (spaces, underscores, accent folding)."""
        expanded: List[str] = []
        for name in names:
            if not name:
                continue
            variants = [name]
            variants.append(name.replace(" ", "_"))
            variants.append(name.replace(" ", ""))
            folded = self._normalize_layer_name_for_match(name)
            if folded and folded != name.lower():
                variants.append(folded)
                variants.append(folded.replace(" ", "_"))
            for variant in variants:
                if variant and variant not in expanded:
                    expanded.append(variant)
        return expanded

    def _preferred_layer_names(
        self,
        file_path: str,
        configured_name: Optional[str],
    ) -> List[str]:
        """Build an ordered list of OGR layer names to try for a GeoPackage file."""
        raw_names: List[str] = []
        if configured_name:
            raw_names.append(configured_name)
        basename = self._geopackage_basename(file_path)
        if basename:
            raw_names.append(basename)
        return self._expand_layer_name_candidates(raw_names)

    def _normalized_geopackage_path(self, file_path: str) -> str:
        """Return a canonical absolute path for GeoPackage cache invalidation."""
        return os.path.normcase(os.path.abspath(os.path.normpath(file_path)))

    def _release_ogr_handles_for_geopackage(self, file_path: str) -> None:
        """
        Drop pooled OGR handles and project layers that still reference a GeoPackage.

        QGIS keeps GeoPackage datasets open in a global connection pool. After a
        cancelled import the pool may still serve the previous file snapshot even
        when the on-disk GeoPackage was modified externally.
        """
        if not file_path:
            return

        normalized_path = self._normalized_geopackage_path(file_path)

        try:
            project = QgsProject.instance()
            if project is not None:
                layers_to_remove: List[str] = []
                for layer_id, layer in project.mapLayers().items():
                    if QgsVectorLayer is None or not isinstance(layer, QgsVectorLayer):
                        continue
                    source = layer.source() or ""
                    base_source = source.split("|", 1)[0]
                    if self._normalized_geopackage_path(base_source) == normalized_path:
                        layers_to_remove.append(layer_id)
                for layer_id in layers_to_remove:
                    project.removeMapLayer(layer_id)
        except Exception as exc:
            print(f"Warning: could not remove project layers for {file_path}: {exc}")

        for candidate in {file_path, normalized_path}:
            try:
                from qgis.core import QgsProviderRegistry

                metadata = QgsProviderRegistry.instance().providerMetadata("ogr")
                if metadata is not None and hasattr(metadata, "invalidateConnections"):
                    metadata.invalidateConnections(candidate)
            except Exception as exc:
                print(f"Warning: could not invalidate OGR connections for {candidate}: {exc}")

    def _checkpoint_geopackage_wal(self, file_path: str) -> None:
        """Merge WAL pages into the main GeoPackage file before copying it."""
        try:
            import sqlite3

            connection = sqlite3.connect(file_path, timeout=5.0)
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.close()
        except Exception as exc:
            print(f"Warning: WAL checkpoint failed for {file_path}: {exc}")

    def _snapshot_geopackage_for_read(self, file_path: str) -> Tuple[str, Optional[str]]:
        """
        Copy a GeoPackage to a temporary file so OGR reads the current on-disk content.

        Uses SQLite's online backup API so uncheckpointed WAL changes are included.
        Falls back to WAL checkpoint + file copy when backup is unavailable.

        Returns:
            Tuple of (path_to_read, temp_path_to_delete_or_None)
        """
        if not file_path or not os.path.isfile(file_path):
            return file_path, None

        self._release_ogr_handles_for_geopackage(file_path)

        fd, temp_path = tempfile.mkstemp(
            suffix=".gpkg",
            prefix="archeosync_import_",
        )
        os.close(fd)

        try:
            import sqlite3

            source_conn = sqlite3.connect(f"file:{file_path}?mode=ro", uri=True)
            dest_conn = sqlite3.connect(temp_path)
            source_conn.backup(dest_conn)
            dest_conn.close()
            source_conn.close()
            print(
                f"[DEBUG] GeoPackage snapshot created via SQLite backup: "
                f"{file_path} -> {temp_path}"
            )
            return temp_path, temp_path
        except Exception as exc:
            print(
                f"Warning: SQLite backup failed for {file_path}: {exc}. "
                "Falling back to WAL checkpoint + file copy."
            )
            try:
                self._checkpoint_geopackage_wal(file_path)
                shutil.copy2(file_path, temp_path)
                return temp_path, temp_path
            except OSError as copy_exc:
                print(
                    f"Warning: could not snapshot GeoPackage {file_path} for fresh read: {copy_exc}. "
                    "Falling back to direct OGR access."
                )
                self._cleanup_geopackage_snapshot(temp_path)
                return file_path, None

    def _cleanup_geopackage_snapshot(self, temp_path: Optional[str]) -> None:
        """Remove a temporary GeoPackage snapshot created for import reads."""
        if not temp_path:
            return
        try:
            if os.path.isfile(temp_path):
                os.remove(temp_path)
        except OSError as exc:
            print(f"Warning: could not delete temporary GeoPackage snapshot {temp_path}: {exc}")

    def _ogr_sub_layer_names(self, file_path: str) -> List[str]:
        """List OGR layer names contained in a GeoPackage file."""
        names: List[str] = []

        def _append_name(layer_name: Optional[str]) -> None:
            if layer_name and layer_name not in names:
                names.append(layer_name)

        try:
            from qgis.core import QgsProviderRegistry

            metadata = QgsProviderRegistry.instance().providerMetadata("ogr")
            if metadata and hasattr(metadata, "querySublayers"):
                for entry in metadata.querySublayers(file_path):
                    if not isinstance(entry, str):
                        continue
                    if "layername=" in entry:
                        _append_name(self._parse_ogr_layer_name(entry))
                    else:
                        _append_name(entry.strip())
        except Exception as exc:
            print(f"Error querying GeoPackage sublayers for {file_path}: {exc}")

        try:
            probe = QgsVectorLayer(file_path, "probe", "ogr")
            if not probe.isValid():
                return names
            sub_layers = probe.subLayers() if hasattr(probe, "subLayers") else []
            if not sub_layers and hasattr(probe.dataProvider(), "subLayers"):
                sub_layers = probe.dataProvider().subLayers()
            for entry in sub_layers:
                _append_name(self._parse_ogr_layer_name(entry))
        except Exception as exc:
            print(f"Error listing GeoPackage sublayers for {file_path}: {exc}")
        return names

    def _parse_ogr_layer_name(self, entry: str) -> Optional[str]:
        """Extract the OGR layer name from a sublayer descriptor string."""
        if "layername=" not in entry:
            return None
        layer_name = entry.split("layername=", 1)[1]
        if "(" in layer_name:
            layer_name = layer_name.split("(", 1)[0]
        layer_name = layer_name.strip().strip("|")
        return layer_name or None

    def _read_fresh_layer_features(self, layer: Any) -> List[Any]:
        """
        Reload an OGR-backed layer from disk and return detached feature copies.

        QGIS may keep GeoPackage pages cached between imports in the same session.
        Each import reads a temporary snapshot of the file so pooled OGR handles
        cannot return data from a previous cancelled import.
        """
        if layer is None or not getattr(layer, "isValid", lambda: False)():
            return []

        try:
            if hasattr(layer, "reload"):
                layer.reload()
            else:
                provider = layer.dataProvider() if hasattr(layer, "dataProvider") else None
                if provider is not None and hasattr(provider, "reloadData"):
                    provider.reloadData()
        except Exception as exc:
            print(f"Warning: could not reload layer before reading features: {exc}")

        features: List[Any] = []
        for feature in layer.getFeatures():
            if QgsFeature is not None:
                features.append(QgsFeature(feature))
            else:
                features.append(feature)
        return features

    def _try_read_geopackage_layer_features(
        self,
        read_path: str,
        layer_name: str,
        source_path: str,
        expected_geometry_type: Optional[Any],
    ) -> List[Any]:
        """Read detached features from one GeoPackage sublayer."""
        uri = f"{read_path}|layername={layer_name}"
        layer = QgsVectorLayer(uri, layer_name, "ogr")
        if not layer.isValid():
            return []

        layer_features = self._read_fresh_layer_features(layer)
        if not layer_features:
            return []

        if (
            expected_geometry_type is not None
            and not self._is_valid_geometry_type(layer, expected_geometry_type)
        ):
            print(
                f"Warning: geometry type mismatch for {source_path} ({layer_name}), "
                f"importing {len(layer_features)} feature(s) anyway"
            )
        return layer_features

    def _collect_features_from_geopackage(
        self,
        file_path: str,
        configured_name: Optional[str],
        expected_geometry_type: Optional[Any],
    ) -> List[Any]:
        """
        Read features from the configured GeoPackage layer.

        Preferred layer names (configured name, file basename) are tried first so a
        re-import after edits does not accidentally read a different sublayer that
        still contains more rows. Other OGR sublayers are only used as a fallback.
        """
        if not file_path or not os.path.isfile(file_path):
            return []

        read_path, snapshot_path = self._snapshot_geopackage_for_read(file_path)
        try:
            preferred_names = self._expand_layer_name_candidates(
                self._preferred_layer_names(read_path, configured_name)
            )
            sublayer_names = self._expand_layer_name_candidates(
                self._ogr_sub_layer_names(read_path)
            )
            fallback_names = [
                layer_name
                for layer_name in sublayer_names
                if layer_name not in preferred_names
            ]

            for layer_name in preferred_names:
                layer_features = self._try_read_geopackage_layer_features(
                    read_path,
                    layer_name,
                    file_path,
                    expected_geometry_type,
                )
                if layer_features:
                    print(
                        f"Read {len(layer_features)} feature(s) from {file_path} "
                        f"(layer: {layer_name})"
                    )
                    return layer_features

            best_features: List[Any] = []
            best_layer_name: Optional[str] = None
            for layer_name in fallback_names:
                layer_features = self._try_read_geopackage_layer_features(
                    read_path,
                    layer_name,
                    file_path,
                    expected_geometry_type,
                )
                if len(layer_features) > len(best_features):
                    best_features = layer_features
                    best_layer_name = layer_name

            if not best_features:
                fallback = QgsVectorLayer(
                    read_path,
                    self._geopackage_basename(read_path) or "layer",
                    "ogr",
                )
                if fallback.isValid():
                    layer_features = self._read_fresh_layer_features(fallback)
                    if layer_features:
                        best_features = layer_features
                        best_layer_name = self._geopackage_basename(read_path)

            if best_features:
                print(
                    f"Read {len(best_features)} feature(s) from {file_path}"
                    f"{f' (layer: {best_layer_name})' if best_layer_name else ''}"
                )
            elif preferred_names or fallback_names:
                tried = preferred_names + fallback_names
                print(f"No features read from {file_path} (tried: {', '.join(tried)})")

            return best_features
        finally:
            self._cleanup_geopackage_snapshot(snapshot_path)

    def _load_geopackage_layer(
        self,
        file_path: str,
        preferred_layer_names: Optional[List[str]] = None,
    ) -> Optional[QgsVectorLayer]:
        """
        Load a vector layer from a GeoPackage, trying several OGR layer name candidates.

        Args:
            file_path: Path to the .gpkg file
            preferred_layer_names: Ordered layer names to try (configured name, basename, …)

        Returns:
            A valid QgsVectorLayer, or None if every attempt failed
        """
        if not file_path or not os.path.isfile(file_path):
            return None

        self._release_ogr_handles_for_geopackage(file_path)

        candidates: List[str] = []
        for name in preferred_layer_names or []:
            if name and name not in candidates:
                candidates.append(name)

        best_layer: Optional[QgsVectorLayer] = None
        best_count = -1

        def _consider(layer: QgsVectorLayer) -> None:
            nonlocal best_layer, best_count
            if not layer.isValid():
                return
            count = layer.featureCount()
            if count < 0:
                count = len(list(layer.getFeatures()))
            if count > best_count:
                best_layer = layer
                best_count = count

        for layer_name in candidates:
            uri = f"{file_path}|layername={layer_name}"
            _consider(QgsVectorLayer(uri, layer_name, "ogr"))

        _consider(QgsVectorLayer(file_path, self._geopackage_basename(file_path) or "layer", "ogr"))

        for layer_name in self._ogr_sub_layer_names(file_path):
            if layer_name in candidates:
                continue
            uri = f"{file_path}|layername={layer_name}"
            _consider(QgsVectorLayer(uri, layer_name, "ogr"))

        if best_layer is not None:
            return best_layer

        print(
            f"Failed to load GeoPackage {file_path} "
            f"(tried: {', '.join(candidates) or 'no candidates'})"
        )
        return None

    def _load_layer(self, file_path: str, layer_name: str) -> Optional[QgsVectorLayer]:
        """
        Load a layer from a file path (legacy helper).

        Accepts either a plain .gpkg path or a full OGR URI containing ``|layername=``.
        """
        try:
            if "|layername=" in file_path:
                base_path, _, embedded_name = file_path.partition("|layername=")
                preferred = [embedded_name, layer_name] if layer_name else [embedded_name]
                return self._load_geopackage_layer(base_path, [n for n in preferred if n])
            return self._load_geopackage_layer(
                file_path,
                [layer_name] if layer_name else None,
            )
        except Exception as e:
            print(f"Error loading layer {layer_name} from {file_path}: {str(e)}")
            return None

    def _is_valid_geometry_type(self, layer, expected_type):
        """
        Check if the layer's geometry type matches the expected type(s).
        Accepts both string and integer representations for backward compatibility.
        """
        if expected_type is None:
            return True

        geom_type = layer.geometryType()
        
        # Accept both string and int for expected_type
        if isinstance(expected_type, str):
            expected_type = expected_type.lower()
        
        # Objects and Features: Polygon layers and attribute-only tables (NullGeometry)
        if expected_type in ("polygon", QgsWkbTypes.PolygonGeometry, 2):
            return geom_type in (
                QgsWkbTypes.PolygonGeometry,
                2,
                QgsWkbTypes.NullGeometry,
                4,
            )
        # Small Finds: Point, MultiPoint, or NoGeometry
        elif expected_type in ("point", QgsWkbTypes.PointGeometry, 0):
            return geom_type in (QgsWkbTypes.PointGeometry, QgsWkbTypes.NoGeometry, 0, 4)
        # Features: LineString or MultiLineString (if needed in future)
        elif expected_type in ("linestring", QgsWkbTypes.LineGeometry, 1):
            return geom_type in (QgsWkbTypes.LineGeometry, 1)
        # Fallback: strict equality
        return geom_type == expected_type 