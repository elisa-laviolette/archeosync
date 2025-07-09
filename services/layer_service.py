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

Usage:
    layer_service = QGISLayerService()
    polygon_layers = layer_service.get_polygon_layers()
    raster_layers = layer_service.get_raster_layers()
    selected_layer = layer_service.get_layer_by_id(layer_id)
"""

from typing import List, Optional, Dict, Any
from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer, QgsExpression, QgsExpressionContext, QgsExpressionContextUtils

try:
    from ..core.interfaces import ILayerService
except ImportError:
    from core.interfaces import ILayerService


class QGISLayerService(ILayerService):
    """
    QGIS-specific implementation of layer operations.
    
    This class provides functionality to interact with QGIS layers,
    specifically for selecting polygon layers for recording areas.
    """
    
    def __init__(self):
        """Initialize the layer service."""
        pass
    
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
    
    def get_raster_layers_overlapping_feature(self, feature, recording_areas_layer_id: str) -> List[Dict[str, Any]]:
        """
        Get raster layers that overlap with a specific polygon feature.
        
        Args:
            feature: The polygon feature to check overlap with
            recording_areas_layer_id: The recording areas layer ID (for CRS transformation if needed)
            
        Returns:
            List of dictionaries containing overlapping raster layer information
        """
        overlapping_raster_layers = []
        project = QgsProject.instance()
        
        # Get the recording areas layer for CRS information
        recording_layer = self.get_layer_by_id(recording_areas_layer_id)
        if not recording_layer:
            return overlapping_raster_layers
        
        # Get feature geometry
        feature_geometry = feature.geometry()
        if not feature_geometry:
            return overlapping_raster_layers
        
        # Get feature extent
        feature_extent = feature_geometry.boundingBox()
        
        for layer in project.mapLayers().values():
            if isinstance(layer, QgsRasterLayer):
                # Get raster extent
                raster_extent = layer.extent()
                
                # Check if extents overlap
                if feature_extent.intersects(raster_extent):
                    layer_info = {
                        'id': layer.id(),
                        'name': layer.name(),
                        'source': layer.source(),
                        'crs': layer.crs().authid() if layer.crs() else 'Unknown',
                        'width': layer.width(),
                        'height': layer.height(),
                        'extent': raster_extent
                    }
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
        
        return {
            'id': layer.id(),
            'name': layer.name(),
            'source': layer.source(),
            'crs': layer.crs().authid() if layer.crs() else 'Unknown',
            'feature_count': layer.featureCount(),
            'geometry_type': 'Polygon',
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
        layer = self.get_layer_by_id(layer_id)
        if layer is None:
            return None
        
        fields = []
        for field in layer.fields():
            field_info = {
                'name': field.name(),
                'type': field.typeName(),
                'type_id': field.type(),
                'comment': field.comment() if hasattr(field, 'comment') else '',
                'is_numeric': field.isNumeric(),
                'is_integer': field.type() in [2, 4, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30]  # QGIS integer field types (excluding 6 which is Real/float and 10 which is string)
            }
            fields.append(field_info)
        
        return fields

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

    def get_related_objects_info(self, recording_area_feature, objects_layer_id: str, 
                                number_field: Optional[str], level_field: Optional[str], recording_areas_layer_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about objects related to a recording area feature.
        
        Args:
            recording_area_feature: The recording area feature to get related objects for
            objects_layer_id: The objects layer ID
            number_field: The number field name (optional)
            level_field: The level field name (optional)
            recording_areas_layer_id: The recording areas layer ID (parent layer, required for relation lookup)
                - This is now required because QgsFeature does not provide a .layer() method.
        
        Returns:
            Dictionary with 'last_number' and 'last_level' values, or empty strings if not found
        """
        if not objects_layer_id or not recording_areas_layer_id:
            return {'last_number': '', 'last_level': ''}
        
        # Get the objects layer
        objects_layer = self.get_layer_by_id(objects_layer_id)
        if not objects_layer:
            return {'last_number': '', 'last_level': ''}
        
        # Get relationships where objects layer is the referencing layer (child)
        project = QgsProject.instance()
        relation_manager = project.relationManager()
        
        related_objects = []
        for relation in relation_manager.relations().values():
            if (relation.referencingLayerId() == objects_layer_id and 
                relation.referencedLayerId() == recording_areas_layer_id):
                # Get related features
                related_features = relation.getRelatedFeatures(recording_area_feature)
                related_objects.extend(related_features)
                break
        
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
        
        # Handle multi-character levels or mixed content
        # For simplicity, append a number or increment the last character
        if last_level.isdigit():
            # If it's a number, increment it
            try:
                current_value = int(last_level)
                return str(current_value + 1)
            except (ValueError, TypeError):
                pass
        
        # For other cases, append a number
        return f"{last_level}1" 