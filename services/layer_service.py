"""
Layer service implementation for ArcheoSync plugin.

This module provides a service for managing QGIS layers, specifically for selecting
polygon layers from the current QGIS project.

Key Features:
- Get all polygon layers from current QGIS project
- Get all raster layers from current QGIS project
- Validate layer geometry types
- Provide layer selection functionality
- Layer metadata access
- Spatial relationship checking between raster and polygon layers
- Create empty layers with same structure as existing layers
- Configure temporary import layers with definitive-layer style, forms, and relations

Usage:
    layer_service = QGISLayerService()
    polygon_layers = layer_service.get_polygon_layers()
    raster_layers = layer_service.get_raster_layers()
    selected_layer = layer_service.get_layer_by_id(layer_id)
    empty_layer = layer_service.create_empty_layer_copy(source_layer_id, "Empty Layer")
"""

from typing import List, Optional, Dict, Any, Tuple
import os
import tempfile
import uuid
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFields,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsEditFormConfig,
    QgsDefaultValue,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsWkbTypes,
    QgsProject,
)
from qgis.PyQt.QtCore import QVariant

try:
    from ..core.interfaces import ILayerService
    from .import_validation_service import IMPORT_LAYER_MAPPINGS
except ImportError:
    from core.interfaces import ILayerService
    from services.import_validation_service import IMPORT_LAYER_MAPPINGS

IMPORT_RELATION_ID_PREFIX = "archeosync_import_"


class QGISLayerService(ILayerService):
    """
    QGIS-specific implementation of layer operations.
    
    This class provides functionality to interact with QGIS layers,
    specifically for selecting polygon layers for recording areas.
    """
    
    def __init__(self):
        """Initialize the layer service."""
        self._recording_area_relation_cache: Dict[Tuple[str, str], Any] = {}
        self._layer_fields_cache: Dict[str, Optional[List[Dict[str, Any]]]] = {}

    def _vector_layer_has_no_geometry(self, layer: QgsVectorLayer) -> bool:
        """
        Return True for attribute-only vector layers (no geometry column).

        QGIS 3 uses QgsWkbTypes.NullGeometry (4) and isSpatial() == False for tables.
        Older code incorrectly treated geometryType() == 0 as no geometry; that value is
        UnknownGeometry in QGIS 3, not NullGeometry.
        """
        if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
            return False

        try:
            if hasattr(layer, "isSpatial") and not layer.isSpatial():
                return True
        except Exception:
            pass

        geom_type = layer.geometryType()
        if geom_type == QgsWkbTypes.NullGeometry:
            return True

        try:
            if QgsWkbTypes.flatType(layer.wkbType()) == QgsWkbTypes.NoGeometry:
                return True
        except Exception:
            pass

        return False
    
    def get_polygon_layers(self) -> List[Dict[str, Any]]:
        """
        Get all polygon layers from the current QGIS project.
        
        Returns:
            List of dictionaries containing layer information
        """
        polygon_layers = []
        project = QgsProject.instance()
        
        for layer in project.mapLayers().values():
            # Check if it's a vector layer with polygon geometry
            # Geometry types: 2 = Polygon/MultiPolygon, 3 = Polygon
            if isinstance(layer, QgsVectorLayer) and layer.geometryType() in [2, 3]:
                layer_info = {
                    'id': layer.id(),
                    'name': layer.name(),
                    'source': layer.source(),
                    'crs': layer.crs().authid() if layer.crs() else 'Unknown',
                    'feature_count': layer.featureCount()
                }
                polygon_layers.append(layer_info)
        
        return polygon_layers
    
    def get_raster_layers(self) -> List[Dict[str, Any]]:
        """
        Get all raster layers from the current QGIS project.
        
        Returns:
            List of dictionaries containing raster layer information
        """
        raster_layers = []
        project = QgsProject.instance()
        
        for layer in project.mapLayers().values():
            if isinstance(layer, QgsRasterLayer):
                layer_info = {
                    'id': layer.id(),
                    'name': layer.name(),
                    'source': layer.source(),
                    'crs': layer.crs().authid() if layer.crs() else 'Unknown',
                    'width': layer.width(),
                    'height': layer.height(),
                    'extent': layer.extent()
                }
                raster_layers.append(layer_info)
        
        return raster_layers
    
    def get_raster_layers_overlapping_feature(
        self,
        feature,
        recording_areas_layer_id: str,
        project_rasters: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get raster layers that overlap with a specific polygon feature.
        
        Args:
            feature: The polygon feature to check overlap with
            recording_areas_layer_id: The recording areas layer ID (for CRS transformation if needed)
            project_rasters: Optional precomputed raster metadata from :meth:`get_raster_layers`
                to avoid scanning the project for every feature
            
        Returns:
            List of dictionaries containing overlapping raster layer information
        """
        feature_geometry = feature.geometry()
        if not feature_geometry:
            return []

        feature_extent = feature_geometry.boundingBox()
        raster_layers = project_rasters if project_rasters is not None else self.get_raster_layers()
        if not raster_layers and recording_areas_layer_id:
            recording_layer = self.get_layer_by_id(recording_areas_layer_id)
            if not recording_layer:
                return []

        overlapping_raster_layers = []
        for layer_info in raster_layers:
            raster_extent = layer_info.get('extent')
            if raster_extent is None:
                continue
            if feature_extent.intersects(raster_extent):
                overlapping_raster_layers.append(layer_info)

        return overlapping_raster_layers
    
    def get_polygon_and_multipolygon_layers(self) -> List[Dict[str, Any]]:
        """
        Get all polygon and multipolygon layers from the current QGIS project.
        This method is specifically for objects and features layers which can be
        either polygon or multipolygon geometry types.
        
        Returns:
            List of dictionaries containing layer information
        """
        layers = []
        project = QgsProject.instance()
        
        for layer in project.mapLayers().values():
            # Check if it's a vector layer with polygon or multipolygon geometry
            # Geometry types: 2 = Polygon/MultiPolygon, 3 = Polygon
            if isinstance(layer, QgsVectorLayer) and layer.geometryType() in [2, 3]:
                layer_info = {
                    'id': layer.id(),
                    'name': layer.name(),
                    'source': layer.source(),
                    'crs': layer.crs().authid() if layer.crs() else 'Unknown',
                    'feature_count': layer.featureCount()
                }
                layers.append(layer_info)
        
        return layers

    def get_point_and_multipoint_layers(self) -> List[Dict[str, Any]]:
        """
        Get all point and multipoint layers from the current QGIS project.
        This method is specifically for total station points layers which can be
        either point or multipoint geometry types.
        
        Returns:
            List of dictionaries containing layer information
        """
        layers = []
        project = QgsProject.instance()
        
        for layer in project.mapLayers().values():
            # Check if it's a vector layer with point or multipoint geometry
            # Geometry types: 0 = Point/MultiPoint (QgsWkbTypes.PointGeometry)
            if isinstance(layer, QgsVectorLayer) and layer.geometryType() == 0:
                layer_info = {
                    'id': layer.id(),
                    'name': layer.name(),
                    'source': layer.source(),
                    'crs': layer.crs().authid() if layer.crs() else 'Unknown',
                    'feature_count': layer.featureCount()
                }
                layers.append(layer_info)
        
        return layers

    def get_no_geometry_layers(self) -> List[Dict[str, Any]]:
        """
        Get all layers with no geometry from the current QGIS project.
        This method is specifically for small finds layers without geometry.
        
        Returns:
            List of dictionaries containing layer information
        """
        layers = []
        project = QgsProject.instance()
        
        for layer in project.mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and self._vector_layer_has_no_geometry(layer):
                layer_info = {
                    'id': layer.id(),
                    'name': layer.name(),
                    'source': layer.source(),
                    'crs': layer.crs().authid() if layer.crs() else 'Unknown',
                    'feature_count': layer.featureCount()
                }
                layers.append(layer_info)
        
        return layers
    
    def get_vector_layers(self) -> List[Dict[str, Any]]:
        """
        Get all vector layers from the current QGIS project.
        
        Returns:
            List of dictionaries containing vector layer information
        """
        vector_layers = []
        project = QgsProject.instance()
        
        for layer in project.mapLayers().values():
            if isinstance(layer, QgsVectorLayer):
                layer_info = {
                    'id': layer.id(),
                    'name': layer.name(),
                    'source': layer.source(),
                    'crs': layer.crs().authid() if layer.crs() else 'Unknown',
                    'feature_count': layer.featureCount(),
                    'geometry_type': layer.geometryType()
                }
                vector_layers.append(layer_info)
        
        return vector_layers
    
    def get_layer_by_id(self, layer_id: str) -> Optional[QgsVectorLayer]:
        """
        Get a layer by its ID.
        
        Args:
            layer_id: The layer ID to find
            
        Returns:
            The layer if found, None otherwise
        """
        project = QgsProject.instance()
        layer = project.mapLayer(layer_id)
        
        if isinstance(layer, (QgsVectorLayer, QgsRasterLayer)):
            return layer
        return None
    
    def get_layer_by_name(self, layer_name: str) -> Optional[QgsVectorLayer]:
        """
        Get a layer by its name.
        
        Args:
            layer_name: The layer name to find
            
        Returns:
            The layer if found, None otherwise
        """
        project = QgsProject.instance()
        for layer in project.mapLayers().values():
            if layer.name() == layer_name:
                return layer
        return None
    
    def is_valid_polygon_layer(self, layer_id: str) -> bool:
        """
        Check if a layer is a valid polygon layer.
        
        Args:
            layer_id: The layer ID to check
            
        Returns:
            True if the layer is a valid polygon layer, False otherwise
        """
        layer = self.get_layer_by_id(layer_id)
        if layer is None:
            return False
        
        # Geometry types: 2 = Polygon/MultiPolygon, 3 = Polygon
        return layer.geometryType() in [2, 3]
    
    def is_valid_polygon_or_multipolygon_layer(self, layer_id: str) -> bool:
        """
        Check if a layer is a valid polygon or multipolygon layer.
        This method is specifically for objects and features layers.
        
        Args:
            layer_id: The layer ID to check
            
        Returns:
            True if the layer is a valid polygon or multipolygon layer, False otherwise
        """
        layer = self.get_layer_by_id(layer_id)
        if layer is None:
            return False
        
        # Geometry types: 2 = Polygon/MultiPolygon, 3 = Polygon
        return layer.geometryType() in [2, 3]

    def is_valid_point_or_multipoint_layer(self, layer_id: str) -> bool:
        """
        Check if a layer is a valid point or multipoint layer.
        This method is specifically for total station points layers.
        
        Args:
            layer_id: The layer ID to check
            
        Returns:
            True if the layer is a valid point or multipoint layer, False otherwise
        """
        layer = self.get_layer_by_id(layer_id)
        if layer is None:
            return False
        
        # Geometry types: 0 = Point/MultiPoint (QgsWkbTypes.PointGeometry)
        return layer.geometryType() == 0

    def is_valid_no_geometry_layer(self, layer_id: str) -> bool:
        """
        Check if a layer has no geometry.
        This method is specifically for small finds layers without geometry.
        
        Args:
            layer_id: The layer ID to check
            
        Returns:
            True if the layer has no geometry, False otherwise
        """
        layer = self.get_layer_by_id(layer_id)
        if layer is None:
            return False

        return self._vector_layer_has_no_geometry(layer)
    
    def get_layer_info(self, layer_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a layer.
        
        Args:
            layer_id: The layer ID to get info for
            
        Returns:
            Dictionary with layer information or None if not found
        """
        layer = self.get_layer_by_id(layer_id)
        if layer is None:
            return None
        
        # Get the actual geometry type from the layer
        geometry_type = layer.geometryType()
        
        return {
            'id': layer.id(),
            'name': layer.name(),
            'source': layer.source(),
            'crs': layer.crs().authid() if layer.crs() else 'Unknown',
            'feature_count': layer.featureCount(),
            'geometry_type': geometry_type,
            'is_valid': layer.isValid()
        }
    
    def get_layer_fields(self, layer_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get field information from a layer.

        Args:
            layer_id: The layer ID to get fields for

        Returns:
            List of field information dictionaries or None if layer not found
        """
        if layer_id in self._layer_fields_cache:
            return self._layer_fields_cache[layer_id]

        layer = self.get_layer_by_id(layer_id)
        if layer is None:
            return None
        
        fields = []
        for field in layer.fields():
            type_name = field.typeName()
            type_id = field.type()
            try:
                from .field_type_utils import is_temporal_field
            except ImportError:
                from field_type_utils import is_temporal_field
            field_info = {
                'name': field.name(),
                'type': type_name,
                'type_id': type_id,
                'comment': field.comment() if hasattr(field, 'comment') else '',
                'is_numeric': field.isNumeric(),
                'is_integer': field.type() in [2, 4, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30],  # QGIS integer field types (excluding 6 which is Real/float and 10 which is string)
                'is_temporal': is_temporal_field(type_name=type_name, type_id=type_id),
            }
            fields.append(field_info)

        self._layer_fields_cache[layer_id] = fields
        return fields

    def _find_relation_to_recording_area(
        self,
        child_layer_id: str,
        recording_areas_layer_id: str,
    ):
        """Return the QgsRelation linking a child layer to recording areas, with caching."""
        cache_key = (child_layer_id, recording_areas_layer_id)
        if cache_key in self._recording_area_relation_cache:
            return self._recording_area_relation_cache[cache_key]

        relation = None
        project = QgsProject.instance()
        relation_manager = project.relationManager()
        for candidate in relation_manager.relations().values():
            if (
                candidate.referencingLayerId() == child_layer_id
                and candidate.referencedLayerId() == recording_areas_layer_id
            ):
                relation = candidate
                break

        self._recording_area_relation_cache[cache_key] = relation
        return relation

    def get_selected_features_count(self, layer_id: str) -> int:
        """
        Get the number of selected features in a layer.
        
        Args:
            layer_id: The layer ID to get selected features count for
            
        Returns:
            Number of selected features, 0 if layer not found or no features selected
        """
        layer = self.get_layer_by_id(layer_id)
        if layer is None:
            return 0
        
        # Get the number of selected features
        return len(layer.selectedFeatures())

    def get_selected_features_info(self, layer_id: str) -> List[Dict[str, Any]]:
        """
        Get information about selected features in a layer.
        
        Args:
            layer_id: The layer ID to get selected features for
            
        Returns:
            List of dictionaries containing feature information with 'name' field,
            sorted alphabetically by name
        """
        layer = self.get_layer_by_id(layer_id)
        if layer is None:
            return []
        
        selected_features = layer.selectedFeatures()
        features_info = []
        
        expr_str = layer.displayExpression()
        expr = None
        context = None
        if expr_str:
            expr = QgsExpression(expr_str)
            context = QgsExpressionContext()
            context.appendScope(QgsExpressionContextUtils.layerScope(layer))
        
        for feature in selected_features:
            feature_name = str(feature.id())
            
            # Try to get name from display expression
            if expr and context:
                context.setFeature(feature)
                try:
                    result = expr.evaluate(context)
                    if result and str(result) != 'NULL':
                        feature_name = str(result)
                except:
                    pass
            
            # Try to get name from common name fields
            if feature_name == str(feature.id()):
                name_fields = ['name', 'title', 'label', 'description', 'comment']
                for field_name in name_fields:
                    field_idx = layer.fields().indexOf(field_name)
                    if field_idx >= 0:
                        value = feature.attribute(field_idx)
                        if value and str(value) != 'NULL':
                            feature_name = str(value)
                            break
            
            features_info.append({'name': feature_name})
        
        # Sort by name
        features_info.sort(key=lambda x: x['name'].lower())
        return features_info

    def get_layer_relationships(self, layer_id: str) -> List[Any]:
        """
        Get all relationships for a layer.
        
        Args:
            layer_id: The layer ID to get relationships for
            
        Returns:
            List of relationship objects or empty list if no relationships found
        """
        layer = self.get_layer_by_id(layer_id)
        if layer is None:
            return []
        
        project = QgsProject.instance()
        relation_manager = project.relationManager()
        
        # Get all relations where this layer is either the referencing or referenced layer
        relations = []
        
        # Get relations where this layer is the referencing layer (child)
        for relation in relation_manager.relations().values():
            if relation.referencingLayerId() == layer_id:
                relations.append(relation)
        
        # Get relations where this layer is the referenced layer (parent)
        for relation in relation_manager.relations().values():
            if relation.referencedLayerId() == layer_id:
                relations.append(relation)
        
        return relations

    def get_related_objects_info(
        self,
        recording_area_feature,
        objects_layer_id: str,
        number_field: Optional[str],
        level_field: Optional[str],
        recording_areas_layer_id: Optional[str] = None,
        related_features_cache: Optional[Dict[Tuple[str, int], List[Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Get information about objects related to a recording area feature.
        
        Args:
            recording_area_feature: The recording area feature to get related objects for
            objects_layer_id: The objects layer ID
            number_field: The number field name (optional)
            level_field: The level field name (optional)
            recording_areas_layer_id: The recording areas layer ID (parent layer, required for relation lookup)
                - This is now required because QgsFeature does not provide a .layer() method.
            related_features_cache: Optional cache keyed by ``(child_layer_id, recording_area_feature.id())``
                so repeated lookups during dialog preparation reuse ``getRelatedFeatures`` results.
        
        Returns:
            Dictionary with 'last_number' and 'last_level' values, or empty strings if not found
        """
        if not objects_layer_id or not recording_areas_layer_id:
            return {'last_number': '', 'last_level': ''}
        
        # Get the objects layer
        objects_layer = self.get_layer_by_id(objects_layer_id)
        if not objects_layer:
            return {'last_number': '', 'last_level': ''}

        cache_key = (objects_layer_id, recording_area_feature.id())
        if related_features_cache is not None and cache_key in related_features_cache:
            related_objects = related_features_cache[cache_key]
        else:
            relation = self._find_relation_to_recording_area(
                objects_layer_id,
                recording_areas_layer_id,
            )
            if relation is None:
                related_objects = []
            else:
                related_objects = list(relation.getRelatedFeatures(recording_area_feature))
            if related_features_cache is not None:
                related_features_cache[cache_key] = related_objects
        
        if not related_objects:
            return {'last_number': '', 'last_level': ''}
        
        # Get field indices
        number_field_idx = -1
        level_field_idx = -1
        
        if number_field:
            number_field_idx = objects_layer.fields().indexOf(number_field)
        
        if level_field:
            level_field_idx = objects_layer.fields().indexOf(level_field)
        
        # Find highest number and last level
        highest_number = None
        level_values = []
        
        for obj_feature in related_objects:
            # Get number value
            if number_field_idx >= 0:
                number_value = obj_feature.attribute(number_field_idx)
                if number_value is not None and str(number_value) != 'NULL':
                    try:
                        number_int = int(number_value)
                        if highest_number is None or number_int > highest_number:
                            highest_number = number_int
                    except (ValueError, TypeError):
                        pass
            
            # Get level value
            if level_field_idx >= 0:
                level_value = obj_feature.attribute(level_field_idx)
                if level_value is not None and str(level_value) != 'NULL':
                    level_values.append(str(level_value))
        
        # Determine last level
        last_level = ''
        if level_values:
            # Sort based on field type
            field_info = self.get_layer_fields(objects_layer_id)
            if field_info:
                level_field_info = next((f for f in field_info if f['name'] == level_field), None)
                if level_field_info and level_field_info['is_integer']:
                    # Numeric field - sort numerically
                    try:
                        numeric_levels = [int(v) for v in level_values]
                        numeric_levels.sort()
                        last_level = str(numeric_levels[-1])
                    except (ValueError, TypeError):
                        # Fall back to alphabetical sorting
                        level_values.sort()
                        last_level = level_values[-1]
                else:
                    # String field - sort alphabetically
                    level_values.sort()
                    last_level = level_values[-1]
        
        return {
            'last_number': str(highest_number) if highest_number is not None else '',
            'last_level': last_level
        }

    def calculate_next_level(self, last_level: str, level_field: str, objects_layer_id: str) -> str:
        """
        Calculate the next level value based on the last level and field type.
        
        Args:
            last_level: The last level value (can be empty string)
            level_field: The level field name
            objects_layer_id: The objects layer ID
            
        Returns:
            The next level value as a string
        """
        if not last_level:
            # If no last level, start with appropriate default
            field_info = self.get_layer_fields(objects_layer_id)
            if field_info:
                level_field_info = next((f for f in field_info if f['name'] == level_field), None)
                if level_field_info and level_field_info['is_integer']:
                    return '1'  # Start with 1 for numeric fields
                else:
                    return 'a'  # Start with 'a' for string fields
            return 'a'  # Default to 'a' if field info not available
        
        # Get field type to determine increment logic
        field_info = self.get_layer_fields(objects_layer_id)
        if field_info:
            level_field_info = next((f for f in field_info if f['name'] == level_field), None)
            if level_field_info and level_field_info['is_integer']:
                # Numeric field - increment by 1
                try:
                    current_value = int(last_level)
                    return str(current_value + 1)
                except (ValueError, TypeError):
                    # Fall back to string increment if conversion fails
                    pass
        
        # String field - increment alphabetically
        # Handle single character levels (a, b, c, ...)
        if len(last_level) == 1 and last_level.isalpha():
            if last_level.lower() == 'z':
                # Preserve case: if original was uppercase, use 'AA', otherwise 'aa'
                return 'AA' if last_level.isupper() else 'aa'
            else:
                # Preserve case when incrementing
                if last_level.isupper():
                    return chr(ord(last_level) + 1)
                else:
                    return chr(ord(last_level) + 1)
        
        # Handle multi-character levels
        if len(last_level) >= 2:
            # Check if it's just numbers (pure numeric)
            if last_level.isdigit():
                try:
                    current_value = int(last_level)
                    return str(current_value + 1)
                except (ValueError, TypeError):
                    pass
            # Check if it's a letter followed by numbers (like 'A1', 'A2', etc.)
            elif last_level[0].isalpha() and last_level[1:].isdigit():
                letter = last_level[0]
                number = int(last_level[1:])
                return f"{letter}{number + 1}"
            # Check if it's a numeric string with possible leading/trailing spaces
            elif last_level.strip().isdigit():
                try:
                    current_value = int(last_level.strip())
                    return str(current_value + 1)
                except (ValueError, TypeError):
                    pass
        
        # For other cases, if last_level is a numeric string, increment numerically
        if last_level.isdigit():
            try:
                current_value = int(last_level)
                return str(current_value + 1)
            except (ValueError, TypeError):
                pass
        
        # For all other cases, append '1'
        return f"{last_level}1"

    def create_empty_layer_copy(self, source_layer_id: str, new_layer_name: str) -> Optional[str]:
        """
        Create an empty layer with the same structure (fields, geometry type, CRS) as the source layer.
        
        Args:
            source_layer_id: The ID of the source layer to copy structure from
            new_layer_name: The name for the new empty layer
            
        Returns:
            The ID of the newly created layer, or None if creation failed
        """
        source_layer = self.get_layer_by_id(source_layer_id)
        if source_layer is None or not isinstance(source_layer, QgsVectorLayer):
            return None
        
        try:
            # Get the correct geometry type from the source layer
            source_geometry_type = source_layer.geometryType()
            geometry_type_string = self._get_geometry_type_string(source_geometry_type)
            
            # Create a memory layer with the same structure
            memory_layer = QgsVectorLayer(f"{geometry_type_string}?crs={source_layer.crs().authid()}", new_layer_name, "memory")
            
            if not memory_layer.isValid():
                print(f"Error: Could not create valid memory layer for {new_layer_name}")
                return None
            
            # Copy fields from source layer
            source_fields = source_layer.fields()
            memory_provider = memory_layer.dataProvider()
            
            # Add all fields to the memory layer (including virtual fields)
            field_list = []
            for field in source_fields:
                new_field = QgsField(field.name(), field.type(), field.typeName(), field.length(), field.precision(), field.comment())
                # Set field alias if it exists
                if field.alias():
                    new_field.setAlias(field.alias())
                field_list.append(new_field)
            
            memory_provider.addAttributes(field_list)
            memory_layer.updateFields()
            
            self.copy_layer_style_and_forms(source_layer, memory_layer)
            
            # Add the layer to the project
            project = QgsProject.instance()
            project.addMapLayer(memory_layer)
            
            print(f"Successfully created empty layer copy: {new_layer_name} (ID: {memory_layer.id()})")
            return memory_layer.id()
            
        except Exception as e:
            print(f"Error creating empty layer copy: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def copy_layer_style_and_forms(
        self,
        source_layer: QgsVectorLayer,
        target_layer: QgsVectorLayer,
    ) -> None:
        """
        Copy symbology, form layout, and field widget configuration from source to target.

        Uses QML style copying when available, with a renderer clone as fallback.

        Args:
            source_layer: Layer to copy style and forms from
            target_layer: Layer to apply style and forms to
        """
        if source_layer is None or target_layer is None:
            return
        if not isinstance(source_layer, QgsVectorLayer) or not isinstance(target_layer, QgsVectorLayer):
            return

        self._copy_layer_properties(source_layer, target_layer)

        qml_success = self._copy_qml_style(source_layer, target_layer)
        if not qml_success:
            print(
                f"QML style copying failed for {target_layer.name()}, "
                f"using renderer clone as fallback"
            )
            self._copy_renderer_fallback(source_layer, target_layer)

    def configure_temporary_import_layer(
        self,
        source_layer: QgsVectorLayer,
        target_layer: QgsVectorLayer,
        peer_layer_replacements: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Apply definitive-layer style, forms, and project relations to a temporary import layer.

        Order of operations:

        1. Clone project relations involving the definitive layer.
        2. Copy symbology, display expression, and form widgets from the definitive layer.
        3. Re-apply field widgets and edit form (QML/virtual-field copy can reset them).
        4. Remap relation ids in field widgets and form layout to the cloned relations.

        Args:
            source_layer: Configured definitive project layer
            target_layer: Temporary import layer to configure
            peer_layer_replacements: Optional map of definitive layer id to other active
                temporary import layer ids (e.g. Objects -> New Objects while Features
                already has New Features)
        """
        if source_layer is None or target_layer is None:
            return
        if not isinstance(source_layer, QgsVectorLayer) or not isinstance(target_layer, QgsVectorLayer):
            return

        relation_id_mapping = self.copy_layer_relations_for_temporary_layer(
            source_layer,
            target_layer,
            peer_layer_replacements=peer_layer_replacements,
        )
        self.copy_layer_style_and_forms(source_layer, target_layer)
        # QML copy may add virtual fields and reset editor widgets before remap runs.
        self._restore_field_and_form_configuration_after_style_copy(
            source_layer,
            target_layer,
        )
        self._copy_layer_display_expression(source_layer, target_layer)
        self._remap_layer_relation_references(
            target_layer,
            relation_id_mapping,
            source_layer,
        )

    def configure_temporary_topo_csv_layer(
        self,
        source_layer: QgsVectorLayer,
        target_layer: QgsVectorLayer,
        peer_layer_replacements: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Apply symbology and relations to a CSV topo import layer safely.

        Unlike :meth:`configure_temporary_import_layer`, this avoids copying the full
        QML style and edit form from the definitive layer. CSV temp layers are built
        from CSV headers and usually do not share the definitive layer schema; loading
        the complete style/form tree can segfault QGIS.

        Args:
            source_layer: Configured definitive total station points layer
            target_layer: Temporary ``Imported_CSV_Points`` layer to configure
            peer_layer_replacements: Optional map of definitive layer id to active
                temporary import layer ids for relation cloning
        """
        if source_layer is None or target_layer is None:
            return
        if not isinstance(source_layer, QgsVectorLayer) or not isinstance(target_layer, QgsVectorLayer):
            return

        relation_id_mapping = self.copy_layer_relations_for_temporary_layer(
            source_layer,
            target_layer,
            peer_layer_replacements=peer_layer_replacements,
        )
        self._copy_renderer_fallback(source_layer, target_layer)
        self._copy_layer_display_expression(source_layer, target_layer)
        self._copy_overlapping_field_configurations(source_layer, target_layer)
        self._remap_layer_relation_references(
            target_layer,
            relation_id_mapping,
            source_layer,
        )

    def _restore_field_and_form_configuration_after_style_copy(
        self,
        source_layer: QgsVectorLayer,
        target_layer: QgsVectorLayer,
    ) -> None:
        """
        Re-apply field widgets and edit form after QML/style copy.

        ``loadNamedStyle`` and virtual-field creation can reset or misalign editor
        widget setups copied from the definitive layer. Restoring them here keeps
        relation remapping reliable for temporary import layers.
        """
        if source_layer is None or target_layer is None:
            return
        if not isinstance(source_layer, QgsVectorLayer) or not isinstance(
            target_layer, QgsVectorLayer
        ):
            return

        self._override_qml_field_configurations_with_current(source_layer, target_layer)
        if hasattr(source_layer, "editFormConfig") and hasattr(
            target_layer, "setEditFormConfig"
        ):
            try:
                target_layer.setEditFormConfig(
                    self._clone_edit_form_config(source_layer.editFormConfig())
                )
            except Exception as e:
                print(
                    f"Error restoring edit form for {target_layer.name()} "
                    f"after style copy: {e}"
                )

    def _clone_edit_form_config(
        self,
        form_config: Optional[QgsEditFormConfig],
    ) -> QgsEditFormConfig:
        """Return a deep copy of an edit form config so remapping never mutates the source."""
        if form_config is None:
            return QgsEditFormConfig()
        return QgsEditFormConfig(form_config)

    def _copy_layer_display_expression(
        self,
        source_layer: QgsVectorLayer,
        target_layer: QgsVectorLayer,
    ) -> None:
        """
        Copy the feature display name expression from source to target layer.

        In QGIS this is the layer's display expression (``previewExpression`` in QML),
        used in identify results, attribute tables, and relation pickers.
        """
        if not hasattr(source_layer, "displayExpression") or not hasattr(
            target_layer, "setDisplayExpression"
        ):
            return
        try:
            target_layer.setDisplayExpression(source_layer.displayExpression() or "")
        except Exception as e:
            print(
                f"Error copying display expression from {source_layer.name()} to "
                f"{target_layer.name()}: {e}"
            )

    def copy_layer_relations_for_temporary_layer(
        self,
        source_layer: QgsVectorLayer,
        target_layer: QgsVectorLayer,
        peer_layer_replacements: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Copy project relations from a definitive layer to a temporary import layer.

        Definitive project relations are never modified. Each clone receives a new
        ``archeosync_import_*`` id and remapped layer ids. When other definitive layers
        already have active temporary import counterparts, their ids are remapped too
        via ``peer_layer_replacements``.

        Args:
            source_layer: Definitive layer whose relations should be cloned
            target_layer: Temporary import layer that should receive cloned relations
            peer_layer_replacements: Optional map of definitive layer id to temporary
                import layer id for other import layers present in the project

        Returns:
            Mapping of source relation id to newly created relation id
        """
        relation_id_mapping: Dict[str, str] = {}
        if source_layer is None or target_layer is None:
            return relation_id_mapping
        if not isinstance(source_layer, QgsVectorLayer) or not isinstance(target_layer, QgsVectorLayer):
            return relation_id_mapping

        try:
            project = QgsProject.instance()
            if project is None:
                return relation_id_mapping

            relation_manager = project.relationManager()
            if relation_manager is None:
                return relation_id_mapping

            source_layer_id = source_layer.id()
            target_layer_id = target_layer.id()
            if not source_layer_id or not target_layer_id:
                return relation_id_mapping

            layer_replacements = dict(peer_layer_replacements or {})
            layer_replacements[source_layer_id] = target_layer_id

            definitive_relation_snapshots = self._snapshot_definitive_project_relations(
                relation_manager
            )

            self._remove_relations_for_layer(relation_manager, target_layer_id)

            for source_relation_id, snapshot in definitive_relation_snapshots.items():
                try:
                    if (
                        snapshot["referencing_id"] != source_layer_id
                        and snapshot["referenced_id"] != source_layer_id
                    ):
                        continue

                    tgt_referencing_id = layer_replacements.get(
                        snapshot["referencing_id"],
                        snapshot["referencing_id"],
                    )
                    tgt_referenced_id = layer_replacements.get(
                        snapshot["referenced_id"],
                        snapshot["referenced_id"],
                    )

                    if project.mapLayer(tgt_referencing_id) is None:
                        continue
                    if project.mapLayer(tgt_referenced_id) is None:
                        continue

                    new_relation = self._build_cloned_relation(
                        snapshot,
                        tgt_referencing_id,
                        tgt_referenced_id,
                        project,
                    )
                    if new_relation is None:
                        continue

                    add_result = relation_manager.addRelation(new_relation)
                    if add_result is False:
                        rel_label = (
                            snapshot.get("name")
                            or source_relation_id
                            or new_relation.id()
                        )
                        validation_error = None
                        for attr in (
                            "validationError",
                            "validationErrorString",
                            "errorString",
                        ):
                            if hasattr(new_relation, attr):
                                try:
                                    validation_error = getattr(new_relation, attr)()
                                    break
                                except Exception:
                                    pass
                        print(
                            f"addRelation rejected for temporary layer "
                            f"'{target_layer.name()}' ({rel_label}): "
                            f"{validation_error or 'unknown reason'}"
                        )
                    else:
                        relation_id_mapping[source_relation_id] = new_relation.id()
                except Exception as relation_error:
                    print(
                        f"Error copying relation for {target_layer.name()}: "
                        f"{relation_error}"
                    )

            self._restore_definitive_project_relations(
                relation_manager,
                definitive_relation_snapshots,
            )

            return relation_id_mapping
        except Exception as e:
            print(
                f"Error copying relations from {source_layer.name()} to "
                f"{target_layer.name()}: {e}"
            )
            import traceback
            traceback.print_exc()
            return relation_id_mapping

    def _is_import_clone_relation_id(self, relation_id: str) -> bool:
        """Return True when a relation id was created for a temporary import layer."""
        return str(relation_id or "").startswith(IMPORT_RELATION_ID_PREFIX)

    def _is_temporary_import_layer(self, layer: Any) -> bool:
        """Return True when a layer is one of the known temporary import layers."""
        return (
            layer is not None
            and hasattr(layer, "name")
            and layer.name() in IMPORT_LAYER_MAPPINGS
        )

    def _snapshot_definitive_project_relations(
        self,
        relation_manager: Any,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Capture definitive project relations so they can be restored if QGIS mutates them.
        """
        snapshots: Dict[str, Dict[str, Any]] = {}
        for relation_id, relation in relation_manager.relations().items():
            if self._is_import_clone_relation_id(relation_id):
                continue
            snapshots[relation_id] = self._snapshot_relation(relation)
        return snapshots

    def _snapshot_relation(self, relation: Any) -> Dict[str, Any]:
        """Serialize a QgsRelation for later comparison or restoration."""
        field_pairs = (
            relation.fieldPairs() if hasattr(relation, "fieldPairs") else {}
        )
        return {
            "id": relation.id() if hasattr(relation, "id") else "",
            "name": relation.name() if hasattr(relation, "name") else "",
            "referencing_id": relation.referencingLayerId(),
            "referenced_id": relation.referencedLayerId(),
            "field_pairs": dict(field_pairs) if field_pairs else {},
            "strength": (
                relation.relationStrength()
                if hasattr(relation, "relationStrength")
                else None
            ),
        }

    def _relation_snapshot_matches(
        self,
        relation: Any,
        snapshot: Dict[str, Any],
    ) -> bool:
        """Return True when a live relation still matches its definitive snapshot."""
        if relation is None or not relation.isValid():
            return False
        return (
            relation.referencingLayerId() == snapshot["referencing_id"]
            and relation.referencedLayerId() == snapshot["referenced_id"]
        )

    def _restore_definitive_project_relations(
        self,
        relation_manager: Any,
        snapshots: Dict[str, Dict[str, Any]],
    ) -> None:
        """Re-create any definitive relation that was altered while cloning import relations."""
        for relation_id, snapshot in snapshots.items():
            current_relation = relation_manager.relation(relation_id)
            if self._relation_snapshot_matches(current_relation, snapshot):
                continue
            self._restore_relation_from_snapshot(relation_manager, snapshot)

    def _restore_relation_from_snapshot(
        self,
        relation_manager: Any,
        snapshot: Dict[str, Any],
    ) -> None:
        """Restore a single definitive project relation from a snapshot."""
        from qgis.core import QgsRelation

        relation_id = snapshot.get("id")
        if not relation_id:
            return

        try:
            relation_manager.removeRelation(relation_id)
        except Exception:
            pass

        restored = QgsRelation()
        restored.setId(relation_id)
        relation_name = snapshot.get("name")
        if relation_name and hasattr(restored, "setName"):
            restored.setName(relation_name)

        self._bind_relation_layers(
            restored,
            snapshot["referencing_id"],
            snapshot["referenced_id"],
            None,
            None,
        )

        field_pairs = self._normalize_relation_field_pairs(snapshot.get("field_pairs"))
        for referencing_field, referenced_field in field_pairs:
            restored.addFieldPair(str(referencing_field), str(referenced_field))

        strength = snapshot.get("strength")
        if strength is not None and hasattr(restored, "setRelationStrength"):
            restored.setRelationStrength(strength)

        relation_manager.addRelation(restored)

    def _build_cloned_relation(
        self,
        snapshot: Dict[str, Any],
        tgt_referencing_id: str,
        tgt_referenced_id: str,
        project: QgsProject,
    ) -> Optional[Any]:
        """Build a new import-clone relation from a definitive relation snapshot."""
        from qgis.core import QgsRelation

        field_pairs = self._normalize_relation_field_pairs(snapshot.get("field_pairs"))
        if not field_pairs:
            return None

        relation_manager = project.relationManager()
        existing_ids = set(relation_manager.relations().keys())
        new_relation_id = f"{IMPORT_RELATION_ID_PREFIX}{uuid.uuid4().hex[:12]}"
        while new_relation_id in existing_ids:
            new_relation_id = f"{IMPORT_RELATION_ID_PREFIX}{uuid.uuid4().hex[:12]}"

        new_relation = QgsRelation()
        new_relation.setId(new_relation_id)
        relation_name = snapshot.get("name") or ""
        if relation_name and hasattr(new_relation, "setName"):
            new_relation.setName(relation_name)

        tgt_referencing_layer = project.mapLayer(tgt_referencing_id)
        tgt_referenced_layer = project.mapLayer(tgt_referenced_id)
        self._bind_relation_layers(
            new_relation,
            tgt_referencing_id,
            tgt_referenced_id,
            tgt_referencing_layer,
            tgt_referenced_layer,
        )

        if (
            new_relation.referencingLayerId() != tgt_referencing_id
            or new_relation.referencedLayerId() != tgt_referenced_id
        ):
            return None

        for referencing_field, referenced_field in field_pairs:
            new_relation.addFieldPair(
                str(referencing_field),
                str(referenced_field),
            )

        strength = snapshot.get("strength")
        if strength is not None and hasattr(new_relation, "setRelationStrength"):
            new_relation.setRelationStrength(strength)

        return new_relation

    def remove_import_clone_relations(self, project: Optional[QgsProject] = None) -> int:
        """
        Remove project relations created for temporary import layers.

        Returns:
            Number of import-clone relations removed
        """
        project = project or QgsProject.instance()
        if project is None:
            return 0

        relation_manager = project.relationManager()
        if relation_manager is None:
            return 0

        removed = 0
        for relation_id in list(relation_manager.relations().keys()):
            if self._is_import_clone_relation_id(relation_id):
                relation_manager.removeRelation(relation_id)
                removed += 1
        return removed

    def _remove_relations_for_layer(self, relation_manager: Any, layer_id: str) -> None:
        """Remove existing project relations that involve the given layer."""
        if not relation_manager or not layer_id:
            return
        for relation_id, relation in list(relation_manager.relations().items()):
            if (
                relation.referencingLayerId() == layer_id
                or relation.referencedLayerId() == layer_id
            ):
                relation_manager.removeRelation(relation_id)

    def _bind_relation_layers(
        self,
        relation: Any,
        referencing_layer_id: str,
        referenced_layer_id: str,
        referencing_layer: Any,
        referenced_layer: Any,
    ) -> None:
        """Bind a QgsRelation to target layers, handling QGIS API differences."""
        try:
            if hasattr(relation, "setReferencingLayerId"):
                relation.setReferencingLayerId(referencing_layer_id)
            else:
                relation.setReferencingLayer(referencing_layer_id)
        except Exception:
            try:
                relation.setReferencingLayer(referencing_layer)
            except Exception:
                pass

        try:
            if hasattr(relation, "setReferencedLayerId"):
                relation.setReferencedLayerId(referenced_layer_id)
            else:
                relation.setReferencedLayer(referenced_layer_id)
        except Exception:
            try:
                relation.setReferencedLayer(referenced_layer)
            except Exception:
                pass

        if relation.referencingLayerId() != referencing_layer_id:
            try:
                relation.setReferencingLayer(referencing_layer)
            except Exception:
                pass
        if relation.referencedLayerId() != referenced_layer_id:
            try:
                relation.setReferencedLayer(referenced_layer)
            except Exception:
                pass

    def _normalize_relation_field_pairs(self, field_pairs_obj: Any) -> List[Tuple[str, str]]:
        """Normalize QgsRelation.fieldPairs() output to (referencing, referenced) tuples."""
        field_pairs_list: List[Tuple[str, str]] = []
        if not field_pairs_obj:
            return field_pairs_list
        try:
            if hasattr(field_pairs_obj, "items"):
                field_pairs_list = [
                    (str(key), str(value))
                    for key, value in field_pairs_obj.items()
                ]
            elif hasattr(field_pairs_obj, "keys") and hasattr(field_pairs_obj, "values"):
                keys = list(field_pairs_obj.keys())
                values = list(field_pairs_obj.values())
                field_pairs_list = [
                    (str(key), str(value)) for key, value in zip(keys, values)
                ]
            elif hasattr(field_pairs_obj, "__iter__"):
                keys = list(field_pairs_obj)
                values = (
                    list(field_pairs_obj.values())
                    if hasattr(field_pairs_obj, "values")
                    else []
                )
                if keys and values and len(keys) == len(values):
                    field_pairs_list = [
                        (str(key), str(value)) for key, value in zip(keys, values)
                    ]
        except Exception:
            field_pairs_list = []
        return field_pairs_list

    def _remap_layer_relation_references(
        self,
        target_layer: QgsVectorLayer,
        relation_id_mapping: Dict[str, str],
        source_layer: Optional[QgsVectorLayer] = None,
    ) -> None:
        """
        Update relation ids in field widgets and edit-form layout after relation cloning.

        QGIS fills the RelationReference dropdown from
        ``target_layer.referencingRelations(field_index)``. Widgets copied from the
        definitive layer often keep a stale relation id that still exists in the
        project but no longer applies to the temporary layer, which leaves the
        Relation field empty in the UI.
        """
        if target_layer is None:
            return

        relation_id_mapping = relation_id_mapping or {}

        try:
            from qgis.core import QgsEditorWidgetSetup

            project = QgsProject.instance()
            relation_manager = (
                project.relationManager() if project is not None else None
            )

            target_fields = target_layer.fields()
            for field_index in range(target_fields.count()):
                field_name = target_fields.at(field_index).name()
                editor_widget = target_layer.editorWidgetSetup(field_index)
                source_widget = None
                if source_layer is not None:
                    source_field_idx = source_layer.fields().indexOf(field_name)
                    if source_field_idx >= 0:
                        source_widget = source_layer.editorWidgetSetup(
                            source_field_idx
                        )

                uses_relation_reference = (
                    (editor_widget and editor_widget.type() == "RelationReference")
                    or (
                        source_widget
                        and source_widget.type() == "RelationReference"
                    )
                )
                if not uses_relation_reference:
                    continue

                base_widget = editor_widget or source_widget
                base_config = (
                    dict(base_widget.config()) if base_widget is not None else {}
                )
                cloned_relation = self._find_cloned_relation_for_field(
                    target_layer=target_layer,
                    field_index=field_index,
                    source_layer=source_layer,
                    relation_id_mapping=relation_id_mapping,
                    relation_manager=relation_manager,
                    base_config=base_config,
                )
                if cloned_relation is None or not cloned_relation.isValid():
                    print(
                        f"No cloned relation found for field '{field_name}' on "
                        f"'{target_layer.name()}'"
                    )
                    continue

                new_config = self._relation_reference_config_for_relation(
                    cloned_relation,
                    base_config,
                )
                target_layer.setEditorWidgetSetup(
                    field_index,
                    QgsEditorWidgetSetup("RelationReference", new_config),
                )

            if relation_id_mapping and hasattr(target_layer, "editFormConfig"):
                form_config = target_layer.editFormConfig()
                if form_config is not None:
                    self._remap_edit_form_relation_references(
                        form_config,
                        relation_id_mapping,
                    )
                    target_layer.setEditFormConfig(form_config)
        except Exception as e:
            print(
                f"Error remapping relation references for {target_layer.name()}: {e}"
            )

    def _find_cloned_relation_for_field(
        self,
        target_layer: QgsVectorLayer,
        field_index: int,
        source_layer: Optional[QgsVectorLayer],
        relation_id_mapping: Dict[str, str],
        relation_manager: Any,
        base_config: Dict[str, Any],
    ) -> Any:
        """Resolve the cloned project relation that applies to a target-layer field."""
        from qgis.core import QgsRelation

        field_name = target_layer.fields().at(field_index).name()
        invalid_relation = QgsRelation()

        old_relation_id = base_config.get("Relation")
        if old_relation_id is not None:
            old_relation_id = str(old_relation_id)
            mapped_relation_id = relation_id_mapping.get(old_relation_id)
            if mapped_relation_id and relation_manager is not None:
                mapped_relation = relation_manager.relation(mapped_relation_id)
                if mapped_relation.isValid():
                    return mapped_relation

        target_relations: List[Any] = []
        if hasattr(target_layer, "referencingRelations"):
            try:
                target_relations = list(
                    target_layer.referencingRelations(field_index)
                )
            except Exception:
                target_relations = []

        if len(target_relations) == 1:
            return target_relations[0]

        if (
            len(target_relations) > 1
            and relation_manager is not None
            and old_relation_id
        ):
            source_relation = relation_manager.relation(old_relation_id)
            if source_relation.isValid():
                source_referenced_id = source_relation.referencedLayerId()
                for relation in target_relations:
                    if relation.referencedLayerId() == source_referenced_id:
                        return relation

        if relation_manager is not None and relation_id_mapping:
            for new_relation_id in relation_id_mapping.values():
                relation = relation_manager.relation(new_relation_id)
                if not relation.isValid():
                    continue
                if relation.referencingLayerId() != target_layer.id():
                    continue
                field_pairs = self._normalize_relation_field_pairs(
                    relation.fieldPairs() if hasattr(relation, "fieldPairs") else None
                )
                if any(
                    referencing_field == field_name
                    for referencing_field, _ in field_pairs
                ):
                    return relation

        if source_layer is not None and relation_manager is not None:
            source_field_idx = source_layer.fields().indexOf(field_name)
            if source_field_idx >= 0 and hasattr(
                source_layer, "referencingRelations"
            ):
                try:
                    source_relations = list(
                        source_layer.referencingRelations(source_field_idx)
                    )
                except Exception:
                    source_relations = []
                for source_relation in source_relations:
                    source_relation_id = (
                        source_relation.id()
                        if hasattr(source_relation, "id")
                        else ""
                    )
                    mapped_relation_id = relation_id_mapping.get(
                        str(source_relation_id)
                    )
                    if mapped_relation_id:
                        mapped_relation = relation_manager.relation(
                            mapped_relation_id
                        )
                        if mapped_relation.isValid():
                            return mapped_relation

        return invalid_relation

    def _relation_reference_config_for_relation(
        self,
        relation: Any,
        base_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a RelationReference widget config bound to a project relation."""
        config = dict(base_config or {})
        relation_id = relation.id() if hasattr(relation, "id") else ""
        if relation_id:
            config["Relation"] = str(relation_id)

        referenced_layer = (
            relation.referencedLayer() if hasattr(relation, "referencedLayer") else None
        )
        if referenced_layer is not None:
            config["ReferencedLayerId"] = referenced_layer.id()
            config["ReferencedLayerName"] = referenced_layer.name()
            if hasattr(referenced_layer, "dataProvider"):
                provider = referenced_layer.dataProvider()
                if provider is not None:
                    if hasattr(provider, "name"):
                        config["ReferencedLayerProviderKey"] = provider.name()
                    if hasattr(provider, "dataSourceUri"):
                        config["ReferencedLayerDataSource"] = provider.dataSourceUri()

        return config

    def _remap_edit_form_relation_references(
        self,
        form_config: QgsEditFormConfig,
        relation_id_mapping: Dict[str, str],
    ) -> None:
        """Recursively remap relation ids inside an edit form layout tree."""
        if not hasattr(form_config, "invisibleRootContainer"):
            return
        root_container = form_config.invisibleRootContainer()
        if root_container is not None:
            self._remap_container_relation_references(
                root_container,
                relation_id_mapping,
            )

    def _remap_container_relation_references(
        self,
        container: Any,
        relation_id_mapping: Dict[str, str],
    ) -> None:
        """Walk a form container tree and update relation editor widgets."""
        if container is None:
            return
        children = container.children() if hasattr(container, "children") else []
        for child in children:
            if hasattr(child, "relationId") and hasattr(child, "setRelationId"):
                current_relation_id = child.relationId()
                if current_relation_id:
                    current_relation_id = str(current_relation_id)
                if current_relation_id in relation_id_mapping:
                    child.setRelationId(relation_id_mapping[current_relation_id])
            if hasattr(child, "children"):
                self._remap_container_relation_references(child, relation_id_mapping)

    def _get_geometry_type_string(self, geometry_type: int) -> str:
        """
        Convert QGIS geometry type to string for layer creation.
        
        Args:
            geometry_type: QGIS geometry type constant
            
        Returns:
            String representation of geometry type
        """
        from qgis.core import QgsWkbTypes
        
        if geometry_type == QgsWkbTypes.PointGeometry:
            return "Point"
        elif geometry_type == QgsWkbTypes.LineGeometry:
            return "LineString"
        elif geometry_type == QgsWkbTypes.PolygonGeometry:
            return "Polygon"
        else:
            # Default to Polygon for unknown types
            return "Polygon"
    
    def _copy_field_configurations(self, source_layer: QgsVectorLayer, target_layer: QgsVectorLayer) -> None:
        """
        Copy field editor widget setups and default value definitions from source to target layer.
        """
        source_fields = source_layer.fields()
        target_fields = target_layer.fields()
        
        # Create a mapping of field names to their configurations
        field_configs = {}
        for i in range(source_fields.count()):
            field_name = source_fields[i].name()
            field_configs[field_name] = {
                'editor_widget': source_layer.editorWidgetSetup(i),
                'default_value': source_layer.defaultValueDefinition(i),
                'constraints': source_layer.constraints(i) if hasattr(source_layer, 'constraints') else None
            }
        
        # Apply configurations to target layer by field name
        for field_name, config in field_configs.items():
            target_field_idx = target_fields.indexOf(field_name)
            
            if target_field_idx >= 0:
                # Copy editor widget setup
                if config['editor_widget'] and hasattr(config['editor_widget'], 'type'):
                    target_layer.setEditorWidgetSetup(target_field_idx, config['editor_widget'])
                
                # Copy default value definition
                if config['default_value'] and config['default_value'].isValid():
                    target_layer.setDefaultValueDefinition(target_field_idx, config['default_value'])
                
                # Copy field constraints if available
                if config['constraints'] and hasattr(target_layer, 'setConstraints'):
                    target_layer.setConstraints(target_field_idx, config['constraints'])

    def _copy_overlapping_field_configurations(
        self,
        source_layer: QgsVectorLayer,
        target_layer: QgsVectorLayer,
    ) -> None:
        """
        Copy field widget setups for fields present on both layers.

        Used for CSV topo imports where the temporary layer schema differs from the
        definitive layer; copying the full edit form would reference missing fields.
        """
        source_fields = source_layer.fields()
        target_fields = target_layer.fields()
        target_field_names = {target_fields[i].name() for i in range(target_fields.count())}

        for source_index in range(source_fields.count()):
            field_name = source_fields[source_index].name()
            if field_name not in target_field_names:
                continue

            target_field_idx = target_fields.indexOf(field_name)
            if target_field_idx < 0:
                continue

            editor_widget = source_layer.editorWidgetSetup(source_index)
            if editor_widget and hasattr(editor_widget, "type"):
                target_layer.setEditorWidgetSetup(target_field_idx, editor_widget)

            default_value = source_layer.defaultValueDefinition(source_index)
            if default_value and default_value.isValid():
                target_layer.setDefaultValueDefinition(target_field_idx, default_value)

            if hasattr(source_layer, "constraints") and hasattr(target_layer, "setConstraints"):
                constraints = source_layer.constraints(source_index)
                if constraints:
                    target_layer.setConstraints(target_field_idx, constraints)

    def _copy_layer_properties(self, source_layer: QgsVectorLayer, target_layer: QgsVectorLayer) -> None:
        """
        Copy layer properties from source to target layer.
        Note: Renderer copying is now handled separately in create_empty_layer_copy
        to prioritize QML style copying.
        """
        try:
            # Copy form configuration without sharing the QgsEditFormConfig object.
            if hasattr(source_layer, 'editFormConfig'):
                source_form_config = source_layer.editFormConfig()
                target_layer.setEditFormConfig(
                    self._clone_edit_form_config(source_form_config)
                )
            
            # Copy field configuration including editor widgets and default values
            self._copy_field_configurations(source_layer, target_layer)
            
            # Copy field aliases
            self._copy_field_aliases(source_layer, target_layer)
            
            # Copy other layer properties
            self._copy_advanced_layer_properties(source_layer, target_layer)
            
        except Exception as e:
            print(f"Error copying layer properties: {e}")
            import traceback
            traceback.print_exc()
    
    def _copy_field_aliases(self, source_layer: QgsVectorLayer, target_layer: QgsVectorLayer) -> None:
        """Copy field aliases from source to target layer."""
        try:
            source_fields = source_layer.fields()
            target_fields = target_layer.fields()
            
            for i in range(source_fields.count()):
                source_field = source_fields[i]
                source_alias = source_field.alias()
                
                if source_alias:
                    target_field_idx = target_fields.indexOf(source_field.name())
                    
                    if target_field_idx >= 0:
                        target_field = target_fields[target_field_idx]
                        target_field.setAlias(source_alias)
        except Exception as e:
            print(f"Error copying field aliases: {e}")
    
    def _copy_advanced_layer_properties(self, source_layer: QgsVectorLayer, target_layer: QgsVectorLayer) -> None:
        """Copy advanced layer properties like constraints, split policies, etc."""
        try:
            # Copy field constraints
            if hasattr(source_layer, 'constraints') and hasattr(target_layer, 'setConstraints'):
                source_fields = source_layer.fields()
                target_fields = target_layer.fields()
                
                for i in range(source_fields.count()):
                    source_field = source_fields[i]
                    target_field_idx = target_fields.indexOf(source_field.name())
                    
                    if target_field_idx >= 0:
                        source_constraints = source_layer.constraints(i)
                        if source_constraints:
                            target_layer.setConstraints(target_field_idx, source_constraints)
            
            # Copy split policies
            if hasattr(source_layer, 'splitPolicy') and hasattr(target_layer, 'setSplitPolicy'):
                source_fields = source_layer.fields()
                target_fields = target_layer.fields()
                
                for i in range(source_fields.count()):
                    source_field = source_fields[i]
                    target_field_idx = target_fields.indexOf(source_field.name())
                    
                    if target_field_idx >= 0:
                        source_split_policy = source_layer.splitPolicy(i)
                        target_layer.setSplitPolicy(target_field_idx, source_split_policy)
            
            # Copy duplicate policies
            if hasattr(source_layer, 'duplicatePolicy') and hasattr(target_layer, 'setDuplicatePolicy'):
                source_fields = source_layer.fields()
                target_fields = target_layer.fields()
                
                for i in range(source_fields.count()):
                    source_field = source_fields[i]
                    target_field_idx = target_fields.indexOf(source_field.name())
                    
                    if target_field_idx >= 0:
                        source_duplicate_policy = source_layer.duplicatePolicy(i)
                        target_layer.setDuplicatePolicy(target_field_idx, source_duplicate_policy)
                        
        except Exception as e:
            print(f"Error copying advanced layer properties: {e}")
    
    def _fix_valuerelation_layer_references(self, target_layer: QgsVectorLayer, project: 'QgsProject') -> None:
        """
        Fix ValueRelation widget configurations to use correct layer IDs in the field project.
        """
        try:
            target_fields = target_layer.fields()
            
            for i in range(target_fields.count()):
                field_name = target_fields[i].name()
                editor_widget = target_layer.editorWidgetSetup(i)
                
                if editor_widget and editor_widget.type() == 'ValueRelation':
                    config_dict = editor_widget.config()
                    old_layer_id = config_dict.get('Layer')
                    
                    if old_layer_id:
                        # Try to find the layer by name in the project
                        found_layer = None
                        for layer in project.mapLayers().values():
                            if layer.name() == 'Matériaux' and old_layer_id != layer.id():
                                found_layer = layer
                                break
                        
                        if found_layer:
                            # Update the configuration with the new layer ID
                            config_dict['Layer'] = found_layer.id()
                            from qgis.core import QgsEditorWidgetSetup
                            new_widget_setup = QgsEditorWidgetSetup('ValueRelation', config_dict)
                            target_layer.setEditorWidgetSetup(i, new_widget_setup)
            
        except Exception as e:
            print(f"Error fixing ValueRelation layer references: {e}")
            import traceback
            traceback.print_exc()

    def _override_qml_field_configurations_with_current(self, source_layer: QgsVectorLayer, target_layer: QgsVectorLayer) -> None:
        """
        Override field configurations loaded from QML with the current layer's field configurations.
        This ensures that we get the latest field settings, not the outdated ones stored in QML files.
        """
        try:
            # Copy current field configurations from source layer
            self._copy_field_configurations(source_layer, target_layer)
            
            # Copy field aliases
            self._copy_field_aliases(source_layer, target_layer)
            
            # Copy advanced layer properties
            self._copy_advanced_layer_properties(source_layer, target_layer)
            
        except Exception as e:
            print(f"Error overriding QML field configurations: {e}")
            import traceback
            traceback.print_exc()
    
    def _copy_renderer_fallback(self, source_layer: QgsVectorLayer, target_layer: QgsVectorLayer) -> None:
        """
        Copy renderer as a fallback when QML style copying fails.
        This provides basic symbology copying but is less complete than QML style copying.
        """
        try:
            if hasattr(source_layer, 'renderer') and hasattr(target_layer, 'setRenderer'):
                target_layer.setRenderer(source_layer.renderer().clone())
                print(f"Copied renderer from {source_layer.name()} to {target_layer.name()} (fallback)")
        except Exception as e:
            print(f"Error copying renderer fallback: {e}")
    
    def _copy_qml_style(self, source_layer: QgsVectorLayer, target_layer: QgsVectorLayer) -> bool:
        """
        Copy QML style file from source layer to target layer if it exists.
        This is the preferred method for copying complete symbology.
        
        Args:
            source_layer: The source layer to copy style from
            target_layer: The target layer to copy style to
            
        Returns:
            True if QML style copying was successful, False otherwise
        """
        try:
            # Method 1: Always use QGIS's built-in style copying (most reliable)
            # This ensures we get the current style, not just what's in the styleURI
            print(f"[DEBUG] Using QGIS built-in style copying for {source_layer.name()}")
            import tempfile
            
            # Create temporary file for style export
            with tempfile.NamedTemporaryFile(suffix='.qml', delete=False) as temp_file:
                temp_qml_path = temp_file.name
            
            try:
                # Export source layer style to temporary QML file
                # This always exports the current style, regardless of styleURI
                export_result = source_layer.saveNamedStyle(temp_qml_path)
                if export_result[0]:
                    print(f"[DEBUG] Successfully exported current style to temporary file: {temp_qml_path}")
                    
                    # Read the exported QML content
                    with open(temp_qml_path, 'r', encoding='utf-8') as f:
                        exported_qml_content = f.read()
                    print(f"[DEBUG] Exported QML content length: {len(exported_qml_content)} characters")
                    
                    # Load from the temporary export file (memory layers have no writable .qml path)
                    load_result = target_layer.loadNamedStyle(temp_qml_path)
                    if load_result[1]:  # Check the success boolean (second element)
                        print(f"Successfully copied complete style from {source_layer.name()} to {target_layer.name()}")
                        
                        # IMPORTANT: After loading QML style, we need to override field configurations
                        # with the current layer's field configurations to ensure we get the latest settings
                        self._override_qml_field_configurations_with_current(source_layer, target_layer)
                        
                        # Parse QML file to find expression fields and add them as virtual fields
                        virtual_fields = self._parse_qml_expression_fields(temp_qml_path)
                        if virtual_fields:
                            # Add virtual fields to the layer
                            provider = target_layer.dataProvider()
                            for field_name, expression in virtual_fields.items():
                                # Check if the field already exists as a regular field
                                existing_field_idx = target_layer.fields().indexOf(field_name)
                                if existing_field_idx >= 0:
                                    # Remove the regular field and add it as virtual
                                    provider.deleteAttributes([existing_field_idx])
                                    target_layer.updateFields()
                                
                                # Add the virtual field
                                virtual_field = QgsField(field_name, QVariant.String, "string")
                                virtual_field.setAlias(field_name)
                                # Set the expression for the virtual field
                                target_layer.addExpressionField(expression, virtual_field)
                        
                        target_layer.triggerRepaint()
                        return True
                    else:
                        print(f"Failed to load exported style into target layer: {load_result[0]}")
                else:
                    print(f"Failed to export style from source layer: {export_result[1]}")
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_qml_path)
                except:
                    pass
            
            # Method 2: Try to copy the actual QML file content if it exists and is different from current style
            source_style_path = source_layer.styleURI()
            if source_style_path and source_style_path.endswith('.qml') and os.path.exists(source_style_path):
                # Only use this if the styleURI file is different from what we just exported
                try:
                    with open(source_style_path, 'r', encoding='utf-8') as f:
                        qml_content = f.read()
                    
                    with tempfile.NamedTemporaryFile(
                        suffix='.qml', delete=False, mode='w', encoding='utf-8'
                    ) as temp_target_file:
                        temp_target_file.write(qml_content)
                        temp_target_qml_path = temp_target_file.name

                    load_result = (False, "")
                    virtual_fields: Dict[str, str] = {}
                    try:
                        load_result = target_layer.loadNamedStyle(temp_target_qml_path)
                        if load_result[1]:  # Check the success boolean (second element)
                            print(
                                f"Successfully loaded QML style from source URI to "
                                f"{target_layer.name()}"
                            )
                            virtual_fields = self._parse_qml_expression_fields(
                                temp_target_qml_path
                            )
                    finally:
                        try:
                            os.unlink(temp_target_qml_path)
                        except OSError:
                            pass

                    if load_result[1]:
                        if virtual_fields:
                            # Add virtual fields to the layer
                            provider = target_layer.dataProvider()
                            for field_name, expression in virtual_fields.items():
                                # Check if the field already exists as a regular field
                                existing_field_idx = target_layer.fields().indexOf(field_name)
                                if existing_field_idx >= 0:
                                    # Remove the regular field and add it as virtual
                                    provider.deleteAttributes([existing_field_idx])
                                    target_layer.updateFields()
                                
                                # Add the virtual field
                                virtual_field = QgsField(field_name, QVariant.String, "string")
                                virtual_field.setAlias(field_name)
                                # Set the expression for the virtual field
                                target_layer.addExpressionField(expression, virtual_field)
                        
                        target_layer.triggerRepaint()
                        return True
                    else:
                        print(f"Failed to load QML style into target layer: {load_result[0]}")
                        
                except Exception as e:
                    print(f"Error copying QML file content: {str(e)}")
            
            # Method 3: Direct renderer and form copying as fallback
            success = False
            
            # Copy renderer
            if hasattr(source_layer, 'renderer') and hasattr(target_layer, 'setRenderer'):
                try:
                    target_layer.setRenderer(source_layer.renderer().clone())
                    success = True
                    print(f"Copied renderer from {source_layer.name()} to {target_layer.name()}")
                except Exception as e:
                    print(f"Error copying renderer: {str(e)}")
            
            # Copy form configuration
            if hasattr(source_layer, 'editFormConfig'):
                try:
                    target_layer.setEditFormConfig(source_layer.editFormConfig())
                    success = True
                    print(f"Copied form configuration from {source_layer.name()} to {target_layer.name()}")
                except Exception as e:
                    print(f"Error copying form configuration: {str(e)}")
            
            # Copy field configurations
            try:
                self._copy_field_configurations(source_layer, target_layer)
                success = True
                print(f"Copied field configurations from {source_layer.name()} to {target_layer.name()}")
            except Exception as e:
                print(f"Error copying field configurations: {str(e)}")
            
            if success:
                target_layer.triggerRepaint()
                print(f"Used fallback method to copy styles from {source_layer.name()} to {target_layer.name()}")
                return True
                        
        except Exception as e:
            print(f"Error in QML style copying: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return False
    
    def _is_virtual_field(self, field, layer=None) -> bool:
        """
        Check if a field is a virtual/computed field that should be excluded from copying.
        
        Args:
            field: QgsField object to check
            layer: Optional QgsVectorLayer to check for QML style file
            
        Returns:
            True if the field appears to be virtual/computed
        """
        try:
            # Method 1: Check if it's a virtual field (computed field)
            if hasattr(field, 'isVirtual') and field.isVirtual():
                return True
            
            # Method 2: Check if it's a computed field (QVariant.Invalid type)
            if hasattr(field, 'type') and field.type() == 100:  # QVariant.Invalid
                return True
            
            # Method 3: Check if the field has an expression (computed field)
            if hasattr(field, 'expression') and field.expression():
                return True
            
            # Method 4: Check if the field has a default value expression
            if hasattr(field, 'defaultValueDefinition') and field.defaultValueDefinition():
                default_def = field.defaultValueDefinition()
                if hasattr(default_def, 'expression') and default_def.expression():
                    return True
            
            # Method 5: Check QML style file for expression fields (most reliable)
            if layer and hasattr(layer, 'styleURI'):
                qml_path = layer.styleURI()
                if qml_path and qml_path.endswith('.qml'):
                    virtual_fields = self._parse_qml_expression_fields(qml_path)
                    if field.name() in virtual_fields:
                        return True
            
            # Method 6: Check if the field has a comment indicating it's computed
            if hasattr(field, 'comment') and field.comment():
                comment = field.comment().lower()
                if any(keyword in comment for keyword in ['computed', 'virtual', 'expression', 'calculated']):
                    return True
            
            # Method 7: Check if the field has an alias that suggests it's computed
            if hasattr(field, 'alias') and field.alias():
                alias = field.alias().lower()
                if any(keyword in alias for keyword in ['computed', 'virtual', 'expression', 'calculated']):
                    return True
            
            return False
        except Exception:
            # If we can't determine, assume it's not virtual
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
            print(f"Error parsing QML file {qml_path}: {str(e)}")
            return {}

    def remove_layer_from_project(self, layer_id: str) -> bool:
        """
        Remove a layer from the current QGIS project.
        
        Args:
            layer_id: The ID of the layer to remove
            
        Returns:
            True if the layer was successfully removed, False otherwise
        """
        try:
            project = QgsProject.instance()
            layer = project.mapLayer(layer_id)
            
            if layer is None:
                return False
            
            # Remove the layer from the project
            project.removeMapLayer(layer)
            return True
            
        except Exception as e:
            print(f"Error removing layer {layer_id}: {str(e)}")
            return False 

    def copy_virtual_fields(self, source_layer, target_layer):
        """
        Copy all virtual fields (expression fields) from source_layer to target_layer.
        If a field exists in target_layer, it will be overwritten as a virtual field with the same expression.
        """
        from qgis.PyQt.QtCore import QVariant
        import os
        import tempfile
        
        print(f"[DEBUG] Copying virtual fields from {source_layer.name()} to {target_layer.name()}")
        
        # Use the proven approach: export source layer style and parse it
        try:
            # Create temporary file for style export
            with tempfile.NamedTemporaryFile(suffix='.qml', delete=False) as temp_file:
                temp_qml_path = temp_file.name
            
            try:
                # Export source layer style to temporary QML file
                export_result = source_layer.saveNamedStyle(temp_qml_path)
                if export_result[0]:
                    print(f"[DEBUG] Successfully exported style to temporary file: {temp_qml_path}")
                    
                    # Parse QML file to find expression fields
                    virtual_fields = self._parse_qml_expression_fields(temp_qml_path)
                    print(f"[DEBUG] Found {len(virtual_fields)} virtual fields in exported style")
                    
                    if virtual_fields:
                        # Add virtual fields to the target layer
                        provider = target_layer.dataProvider()
                        for field_name, expression in virtual_fields.items():
                            print(f"[DEBUG] Adding virtual field: {field_name} = {expression}")
                            
                            # Check if the field already exists as a regular field
                            existing_field_idx = target_layer.fields().indexOf(field_name)
                            if existing_field_idx >= 0:
                                # Remove the regular field and add it as virtual
                                print(f"[DEBUG] Removing existing field '{field_name}' to replace with virtual field")
                                provider.deleteAttributes([existing_field_idx])
                                target_layer.updateFields()
                            
                            # Add the virtual field
                            virtual_field = QgsField(field_name, QVariant.String, "string")
                            virtual_field.setAlias(field_name)
                            # Set the expression for the virtual field
                            target_layer.addExpressionField(expression, virtual_field)
                            print(f"[DEBUG] Successfully added virtual field: {field_name}")
                        
                        target_layer.triggerRepaint()
                        print(f"[DEBUG] Finished copying {len(virtual_fields)} virtual fields")
                    else:
                        print(f"[DEBUG] No virtual fields found in exported style")
                else:
                    print(f"[DEBUG] Failed to export style from source layer: {export_result[1]}")
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_qml_path)
                except:
                    pass
                    
        except Exception as e:
            print(f"[DEBUG] Exception during virtual field copying: {e}")
            import traceback
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")

    def resolve_extent_geometry_from_layer(self, layer_id: str) -> Optional[QgsGeometry]:
        """
        Build an extent geometry from a vector layer.

        Uses the union of selected feature geometries when a selection exists;
        otherwise the union of all feature geometries. The layer bounding box is
        only used as a last resort when the layer has no usable geometries.

        Args:
            layer_id: Source vector layer ID in the current project

        Returns:
            Extent geometry in the layer CRS, or None if the layer is invalid
        """
        layer = self.get_layer_by_id(layer_id)
        if not layer or not isinstance(layer, QgsVectorLayer) or not layer.isValid():
            return None

        selected_ids = layer.selectedFeatureIds()
        if selected_ids:
            geometries = []
            for feature in layer.getFeatures():
                if feature.id() not in selected_ids:
                    continue
                geom = feature.geometry()
                if geom and not geom.isNull() and not geom.isEmpty():
                    geometries.append(geom)
            if geometries:
                combined = QgsGeometry.unaryUnion(geometries)
                if combined and not combined.isNull() and not combined.isEmpty():
                    return combined

        geometries = []
        for feature in layer.getFeatures():
            geom = feature.geometry()
            if geom and not geom.isNull() and not geom.isEmpty():
                geometries.append(geom)
        if geometries:
            combined = QgsGeometry.unaryUnion(geometries)
            if combined and not combined.isNull() and not combined.isEmpty():
                return combined

        extent = layer.extent()
        if extent.isNull() or extent.isEmpty():
            return None
        return QgsGeometry.fromRect(extent)

    def resolve_extent_geometry_from_rectangle(
        self,
        xmin: float,
        ymin: float,
        xmax: float,
        ymax: float,
        crs: Optional[QgsCoordinateReferenceSystem] = None,
    ) -> Optional[QgsGeometry]:
        """
        Build a rectangular extent geometry from numeric bounds.

        Args:
            xmin: Minimum x coordinate
            ymin: Minimum y coordinate
            xmax: Maximum x coordinate
            ymax: Maximum y coordinate
            crs: Optional CRS (unused for geometry construction; callers set project CRS)

        Returns:
            Rectangular polygon geometry, or None when bounds are invalid
        """
        del crs  # CRS is applied at project level
        if xmin >= xmax or ymin >= ymax:
            return None
        from qgis.core import QgsRectangle
        return QgsGeometry.fromRect(QgsRectangle(xmin, ymin, xmax, ymax))

    def transform_geometry_to_layer_crs(
        self,
        geometry: QgsGeometry,
        target_layer: QgsVectorLayer,
        source_crs_authid: Optional[str] = None,
    ) -> Optional[QgsGeometry]:
        """
        Return a copy of a geometry transformed into a layer's CRS when needed.

        Args:
            geometry: Geometry to transform (e.g. project extent)
            target_layer: Layer whose CRS is the target
            source_crs_authid: Auth id of the geometry CRS; defaults to project CRS

        Returns:
            Transformed geometry copy, or None if invalid
        """
        if not geometry or geometry.isNull() or geometry.isEmpty():
            return None
        if not target_layer or not isinstance(target_layer, QgsVectorLayer):
            return None

        result = QgsGeometry(geometry)
        target_crs = target_layer.crs()
        if not target_crs.isValid():
            return result

        if source_crs_authid:
            source_crs = QgsCoordinateReferenceSystem(source_crs_authid)
        else:
            source_crs = QgsProject.instance().crs()

        if not source_crs.isValid() or source_crs == target_crs:
            return result

        try:
            transform = QgsCoordinateTransform(
                source_crs,
                target_crs,
                QgsProject.instance(),
            )
            result.transform(transform)
            return result
        except Exception as exc:
            print(f"Error transforming geometry to layer CRS: {exc}")
            return result

    def get_recording_area_ids_intersecting_geometry(
        self,
        recording_areas_layer_id: str,
        extent_geometry: QgsGeometry,
        extent_crs_authid: Optional[str] = None,
    ) -> List[Any]:
        """
        Return recording-area identifier values for features intersecting an extent.

        Uses QgsFeature.id() values, which match relation filters elsewhere in the plugin.

        Args:
            recording_areas_layer_id: Recording areas layer ID
            extent_geometry: Extent geometry in a CRS compatible with the layer

        Returns:
            List of feature IDs (may be empty)
        """
        layer = self.get_layer_by_id(recording_areas_layer_id)
        if not layer or not isinstance(layer, QgsVectorLayer) or not extent_geometry:
            return []

        extent_in_layer_crs = self.transform_geometry_to_layer_crs(
            extent_geometry,
            layer,
            extent_crs_authid,
        )
        if not extent_in_layer_crs:
            return []

        ids = []
        for feature in layer.getFeatures():
            geom = feature.geometry()
            if not geom or geom.isNull() or geom.isEmpty():
                continue
            if geom.intersects(extent_in_layer_crs):
                ids.append(feature.id())
        return ids 