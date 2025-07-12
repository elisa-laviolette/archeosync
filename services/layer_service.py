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

from typing import List, Optional, Dict, Any
from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer, QgsExpression, QgsExpressionContext, QgsExpressionContextUtils, QgsFields, QgsField, QgsFeature, QgsGeometry

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
            
            # Add fields to the memory layer
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
            # Get the source layer's style file path
            source_style_path = source_layer.styleURI()
            
            if source_style_path and source_style_path.endswith('.qml'):
                # Try to load the QML style file
                if source_layer.loadNamedStyle(source_style_path)[0]:
                    # If successful, apply the same style to the target layer
                    if target_layer.loadNamedStyle(source_style_path)[0]:
                        print(f"Copied QML style from {source_style_path} to {target_layer.name()}")
                        return True
                    else:
                        print(f"Could not import QML style to {target_layer.name()}")
                else:
                    print(f"Could not load QML style from {source_style_path}")
            
            # Try to export current style to QML and then import it
            import tempfile
            import os
            
            # Create a temporary QML file
            with tempfile.NamedTemporaryFile(suffix='.qml', delete=False) as temp_file:
                temp_qml_path = temp_file.name
            
            try:
                # Export source layer style to temporary QML file
                if source_layer.saveNamedStyle(temp_qml_path)[0]:
                    # Import the style to target layer
                    if target_layer.loadNamedStyle(temp_qml_path)[0]:
                        print(f"Exported and imported style from {source_layer.name()} to {target_layer.name()}")
                        return True
                    else:
                        print(f"Could not import style to {target_layer.name()}")
                else:
                    print(f"Could not export style from {source_layer.name()}")
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_qml_path)
                except:
                    pass
            
            # Additional: Try to copy style using QGIS's built-in style copying
            try:
                # Use QGIS's style copying mechanism which includes all form configurations
                style_result = source_layer.saveNamedStyle(tempfile.mktemp(suffix='.qml'))
                if style_result[0]:
                    temp_style_path = style_result[1]
                    try:
                        if target_layer.loadNamedStyle(temp_style_path)[0]:
                            print(f"Copied complete style including forms from {source_layer.name()} to {target_layer.name()}")
                            return True
                    finally:
                        # Clean up temporary file
                        try:
                            os.unlink(temp_style_path)
                        except:
                            pass
            except Exception as e:
                print(f"Warning: Could not copy style using QGIS mechanism: {str(e)}")
                        
        except Exception as e:
            print(f"Warning: Could not copy QML style: {str(e)}")
        
        return False
    
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