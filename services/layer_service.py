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
from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer, QgsExpression, QgsExpressionContext, QgsExpressionContextUtils, QgsFields, QgsField, QgsFeature, QgsGeometry, QgsPointXY, QgsEditFormConfig, QgsDefaultValue, QgsCoordinateReferenceSystem
from PyQt5.QtCore import QVariant

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
            # Check if it's a vector layer with no geometry
            # Geometry types: 0 = NoGeometry
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
        
        # Geometry types: 0 = NoGeometry
        return layer.geometryType() == 0
    
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
            
            # Copy layer properties (forms, field configurations, etc.)
            self._copy_layer_properties(source_layer, memory_layer)
            
            # Try to copy QML style file first (preferred method for complete symbology)
            qml_success = self._copy_qml_style(source_layer, memory_layer)
            
            # If QML style copying failed, use renderer fallback
            if not qml_success:
                print(f"QML style copying failed for {new_layer_name}, using renderer clone as fallback")
                self._copy_renderer_fallback(source_layer, memory_layer)
            
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
        for i in range(source_fields.count()):
            # Copy editor widget setup
            source_editor_widget = source_layer.editorWidgetSetup(i)
            if source_editor_widget and getattr(source_editor_widget, 'type', lambda: None)():
                target_layer.setEditorWidgetSetup(i, source_editor_widget)
            # Copy default value definition
            source_default = source_layer.defaultValueDefinition(i)
            target_layer.setDefaultValueDefinition(i, source_default)

    def _copy_layer_properties(self, source_layer: QgsVectorLayer, target_layer: QgsVectorLayer) -> None:
        """
        Copy layer properties from source to target layer.
        Note: Renderer copying is now handled separately in create_empty_layer_copy
        to prioritize QML style copying.
        """
        try:
            # Copy form configuration
            if hasattr(source_layer, 'editFormConfig'):
                target_layer.setEditFormConfig(source_layer.editFormConfig())
            # Copy field configuration including editor widgets and default values
            self._copy_field_configurations(source_layer, target_layer)
            # Note: Field aliases are handled during field creation in create_empty_layer_copy
            # and through QML style copying which preserves all field properties
        except Exception as e:
            print(f"Error copying layer properties: {e}")
    
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
            print(f"[DEBUG] Starting QML style copy from {source_layer.name()} to {target_layer.name()}")
            
            # Method 1: Try to copy the actual QML file content
            source_style_path = source_layer.styleURI()
            if source_style_path and source_style_path.endswith('.qml') and os.path.exists(source_style_path):
                print(f"[DEBUG] Found QML style file: {source_style_path}")
                
                # Read the QML content
                try:
                    with open(source_style_path, 'r', encoding='utf-8') as f:
                        qml_content = f.read()
                    print(f"[DEBUG] Successfully read QML content ({len(qml_content)} characters)")
                    
                    # Check for virtual fields in QML
                    if '<expressionfields>' in qml_content:
                        print(f"[DEBUG] Found expressionfields section in QML")
                        # Extract virtual field names
                        import re
                        virtual_fields = re.findall(r'<field name="([^"]+)"', qml_content)
                        if virtual_fields:
                            print(f"[DEBUG] Virtual fields found in QML: {virtual_fields}")
                            
                            # Show the expressionfields section
                            start = qml_content.find('<expressionfields>')
                            end = qml_content.find('</expressionfields>')
                            if start != -1 and end != -1:
                                expression_section = qml_content[start:end+len('</expressionfields>')]
                                print(f"[DEBUG] Expression fields section: {expression_section}")
                        else:
                            print(f"[DEBUG] No expressionfields section found in QML")
                    
                    # Create target QML file path
                    target_style_path = os.path.join(os.path.dirname(target_layer.source()), f"{target_layer.name()}.qml")
                    print(f"[DEBUG] Target QML path: {target_style_path}")
                    
                    # Write QML content to target file
                    with open(target_style_path, 'w', encoding='utf-8') as f:
                        f.write(qml_content)
                    print(f"[DEBUG] Successfully wrote QML file: {target_style_path}")
                    
                    # Load the QML style into the target layer
                    load_result = target_layer.loadNamedStyle(target_style_path)
                    print(f"[DEBUG] QML load result: {load_result}")
                    if load_result[1]:  # Check the success boolean (second element)
                        print(f"Successfully loaded QML style from {target_style_path} to {target_layer.name()}")
                        
                        # Parse QML file to find expression fields and add them as virtual fields
                        virtual_fields = self._parse_qml_expression_fields(target_style_path)
                        if virtual_fields:
                            print(f"[DEBUG] Found virtual fields in QML: {list(virtual_fields.keys())}")
                            
                            # Add virtual fields to the layer
                            provider = target_layer.dataProvider()
                            for field_name, expression in virtual_fields.items():
                                # Check if the field already exists as a regular field
                                existing_field_idx = target_layer.fields().indexOf(field_name)
                                if existing_field_idx >= 0:
                                    print(f"[DEBUG] Field {field_name} already exists as regular field, converting to virtual")
                                    # Remove the regular field and add it as virtual
                                    provider.deleteAttributes([existing_field_idx])
                                    target_layer.updateFields()
                                
                                # Add the virtual field
                                virtual_field = QgsField(field_name, QVariant.String, "string")
                                virtual_field.setAlias(field_name)
                                # Set the expression for the virtual field
                                target_layer.addExpressionField(expression, virtual_field)
                                print(f"[DEBUG] Added virtual field {field_name} with expression: {expression}")
                        
                        # Check fields after QML loading and virtual field addition
                        print(f"[DEBUG] Fields in target layer after QML loading:")
                        for i, field in enumerate(target_layer.fields()):
                            is_virtual = hasattr(field, 'isVirtual') and field.isVirtual()
                            print(f"[DEBUG]   Field {i}: {field.name()} (virtual: {is_virtual})")
                        
                        target_layer.triggerRepaint()
                        return True
                    else:
                        print(f"Failed to load QML style into target layer: {load_result[0]}")
                        
                except Exception as e:
                    print(f"[DEBUG] Error reading/writing QML file: {str(e)}")
            
            # Method 2: Use QGIS's built-in style copying (more reliable)
            print(f"[DEBUG] Trying QGIS built-in style copying")
            import tempfile
            
            # Create temporary file for style export
            with tempfile.NamedTemporaryFile(suffix='.qml', delete=False) as temp_file:
                temp_qml_path = temp_file.name
            
            try:
                # Export source layer style to temporary QML file
                export_result = source_layer.saveNamedStyle(temp_qml_path)
                if export_result[0]:
                    print(f"[DEBUG] Successfully exported style to temporary file: {temp_qml_path}")
                    
                    # Read the exported QML content
                    with open(temp_qml_path, 'r', encoding='utf-8') as f:
                        exported_qml_content = f.read()
                    print(f"[DEBUG] Exported QML content length: {len(exported_qml_content)} characters")
                    
                    # Create target QML file path
                    target_style_path = os.path.join(os.path.dirname(target_layer.source()), f"{target_layer.name()}.qml")
                    
                    # Write the exported QML content to target file
                    with open(target_style_path, 'w', encoding='utf-8') as f:
                        f.write(exported_qml_content)
                    print(f"[DEBUG] Successfully wrote exported QML to: {target_style_path}")
                    
                    # Load the style into the target layer
                    load_result = target_layer.loadNamedStyle(target_style_path)
                    print(f"[DEBUG] QML load result (method 2): {load_result}")
                    if load_result[1]:  # Check the success boolean (second element)
                        print(f"Successfully copied complete style from {source_layer.name()} to {target_layer.name()}")
                        
                        # Parse QML file to find expression fields and add them as virtual fields
                        virtual_fields = self._parse_qml_expression_fields(target_style_path)
                        if virtual_fields:
                            print(f"[DEBUG] Found virtual fields in QML: {list(virtual_fields.keys())}")
                            
                            # Add virtual fields to the layer
                            provider = target_layer.dataProvider()
                            for field_name, expression in virtual_fields.items():
                                # Check if the field already exists as a regular field
                                existing_field_idx = target_layer.fields().indexOf(field_name)
                                if existing_field_idx >= 0:
                                    print(f"[DEBUG] Field {field_name} already exists as regular field, converting to virtual")
                                    # Remove the regular field and add it as virtual
                                    provider.deleteAttributes([existing_field_idx])
                                    target_layer.updateFields()
                                
                                # Add the virtual field
                                virtual_field = QgsField(field_name, QVariant.String, "string")
                                virtual_field.setAlias(field_name)
                                # Set the expression for the virtual field
                                target_layer.addExpressionField(expression, virtual_field)
                                print(f"[DEBUG] Added virtual field {field_name} with expression: {expression}")
                        
                        # Check fields after QML loading and virtual field addition
                        print(f"[DEBUG] Fields in target layer after QML loading (method 2):")
                        for i, field in enumerate(target_layer.fields()):
                            is_virtual = hasattr(field, 'isVirtual') and field.isVirtual()
                            print(f"[DEBUG]   Field {i}: {field.name()} (virtual: {is_virtual})")
                        
                        target_layer.triggerRepaint()
                        return True
                    else:
                        print(f"Failed to load exported style into target layer: {load_result[0]}")
                else:
                    print(f"Failed to export style from source layer")
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_qml_path)
                except:
                    pass
            
            # Method 3: Direct renderer and form copying as fallback
            print(f"[DEBUG] Using direct renderer and form copying as fallback")
            success = False
            
            # Copy renderer
            if hasattr(source_layer, 'renderer') and hasattr(target_layer, 'setRenderer'):
                try:
                    target_layer.setRenderer(source_layer.renderer().clone())
                    print(f"[DEBUG] Successfully copied renderer")
                    success = True
                except Exception as e:
                    print(f"[DEBUG] Error copying renderer: {str(e)}")
            
            # Copy form configuration
            if hasattr(source_layer, 'editFormConfig'):
                try:
                    target_layer.setEditFormConfig(source_layer.editFormConfig())
                    print(f"[DEBUG] Successfully copied form configuration")
                    success = True
                except Exception as e:
                    print(f"[DEBUG] Error copying form configuration: {str(e)}")
            
            # Copy field configurations
            try:
                self._copy_field_configurations(source_layer, target_layer)
                print(f"[DEBUG] Successfully copied field configurations")
                success = True
            except Exception as e:
                print(f"[DEBUG] Error copying field configurations: {str(e)}")
            
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