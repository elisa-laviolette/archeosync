"""
Layer service implementation for ArcheoSync plugin.

This module provides a service for managing QGIS layers, specifically for selecting
polygon layers from the current QGIS project.

Key Features:
- Get all polygon layers from current QGIS project
- Validate layer geometry types
- Provide layer selection functionality
- Layer metadata access

Usage:
    layer_service = QGISLayerService()
    polygon_layers = layer_service.get_polygon_layers()
    selected_layer = layer_service.get_layer_by_id(layer_id)
"""

from typing import List, Optional, Dict, Any
from qgis.core import QgsProject, QgsVectorLayer, QgsExpression, QgsExpressionContext, QgsExpressionContextUtils

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
        
        if isinstance(layer, QgsVectorLayer):
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
            # Try to get a display name from the display expression if available
            if expr and context:
                try:
                    context.setFeature(feature)
                    name = expr.evaluate(context)
                    if name and str(name).strip():
                        features_info.append({'name': str(name).strip()})
                        continue
                except Exception as ex:
                    print(f"LayerService: Error evaluating display expression for feature {feature.id()}: {ex}")
            # Fallback: try to get a name from common field names
            name_fields = ['name', 'NAME', 'Name', 'title', 'TITLE', 'Title', 'label', 'LABEL', 'Label']
            for field_name in name_fields:
                field_idx = layer.fields().indexOf(field_name)
                if field_idx >= 0:
                    try:
                        name = feature.attribute(field_idx)
                        if name and str(name).strip():
                            features_info.append({'name': str(name).strip()})
                            break
                    except Exception as ex:
                        print(f"LayerService: Error extracting field '{field_name}' for feature {feature.id()}: {ex}")
            else:
                # If no name field found, use feature ID
                features_info.append({'name': f"Feature {feature.id()}"})
        
        # Sort by name alphabetically
        features_info.sort(key=lambda x: x['name'].lower())
        
        return features_info 