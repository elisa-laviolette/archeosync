"""
Test file to verify style copying functionality in layer service.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from qgis.core import QgsVectorLayer, QgsField, QgsFields, QgsProject, QgsWkbTypes, QgsEditFormConfig
try:
    from qgis.PyQt.QtCore import QVariant
except ImportError:
    from PyQt5.QtCore import QVariant

from archeosync.services.layer_service import QGISLayerService


class TestStyleCopying(unittest.TestCase):
    """Test cases for style copying functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.layer_service = QGISLayerService()
    
    def test_copy_layer_properties_with_default_values(self):
        """Test that field default values are properly copied."""
        from qgis.core import QgsDefaultValue
        # Create a source layer with default values
        source_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string&field=value:integer", "SourceLayer", "memory")
        self.assertTrue(source_layer.isValid())
        
        # Set up form configuration
        form_config = source_layer.editFormConfig()
        form_config.setLayout(QgsEditFormConfig.TabLayout)
        source_layer.setEditFormConfig(form_config)
        
        # Set default values for fields using setDefaultValueDefinition
        name_field_idx = source_layer.fields().indexOf('name')
        value_field_idx = source_layer.fields().indexOf('value')
        
        if name_field_idx >= 0:
            source_layer.setDefaultValueDefinition(name_field_idx, QgsDefaultValue("'Default Name'"))
        if value_field_idx >= 0:
            source_layer.setDefaultValueDefinition(value_field_idx, QgsDefaultValue('42'))
        
        # Create target layer
        target_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string&field=value:integer", "TargetLayer", "memory")
        self.assertTrue(target_layer.isValid())
        
        # Copy properties
        self.layer_service._copy_layer_properties(source_layer, target_layer)
        
        # Verify default values were copied
        if name_field_idx >= 0:
            target_default_def = target_layer.defaultValueDefinition(name_field_idx)
            self.assertTrue(target_default_def.isValid())
            self.assertEqual(target_default_def.expression(), "'Default Name'")
        
        if value_field_idx >= 0:
            target_default_def = target_layer.defaultValueDefinition(value_field_idx)
            self.assertTrue(target_default_def.isValid())
            self.assertEqual(target_default_def.expression(), '42')
    
    def test_copy_layer_properties_with_renderer(self):
        """Test that renderer (symbology) is properly copied."""
        # Create a source layer
        source_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string", "SourceLayer", "memory")
        self.assertTrue(source_layer.isValid())
        
        # Set up a renderer
        from qgis.core import QgsSingleSymbolRenderer, QgsSymbol
        renderer = QgsSingleSymbolRenderer(QgsSymbol.defaultSymbol(QgsWkbTypes.PointGeometry))
        source_layer.setRenderer(renderer)
        
        # Create target layer
        target_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string", "TargetLayer", "memory")
        self.assertTrue(target_layer.isValid())
        
        # Copy properties
        self.layer_service._copy_layer_properties(source_layer, target_layer)
        
        # Verify renderer was copied
        target_renderer = target_layer.renderer()
        self.assertIsNotNone(target_renderer)
        self.assertEqual(target_renderer.type(), renderer.type())
    
    def test_create_empty_layer_copy_integration(self):
        """Test the complete empty layer copy process."""
        from qgis.core import QgsDefaultValue
        # Create a source layer with styling and default values
        source_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string&field=value:integer", "SourceLayer", "memory")
        self.assertTrue(source_layer.isValid())
        
        # Set up form configuration
        form_config = source_layer.editFormConfig()
        form_config.setLayout(QgsEditFormConfig.TabLayout)
        source_layer.setEditFormConfig(form_config)
        
        # Set default values using setDefaultValueDefinition
        name_field_idx = source_layer.fields().indexOf('name')
        if name_field_idx >= 0:
            source_layer.setDefaultValueDefinition(name_field_idx, QgsDefaultValue("'Default Name'"))
        
        # Set up renderer
        from qgis.core import QgsSingleSymbolRenderer, QgsSymbol
        renderer = QgsSingleSymbolRenderer(QgsSymbol.defaultSymbol(QgsWkbTypes.PointGeometry))
        source_layer.setRenderer(renderer)
        
        # Add source layer to project
        project = QgsProject.instance()
        project.addMapLayer(source_layer)
        
        # Create empty layer copy
        new_layer_id = self.layer_service.create_empty_layer_copy(source_layer.id(), "EmptyCopy")
        self.assertIsNotNone(new_layer_id)
        
        # Get the new layer
        new_layer = self.layer_service.get_layer_by_id(new_layer_id)
        self.assertIsNotNone(new_layer)
        
        # Verify styling was copied
        new_renderer = new_layer.renderer()
        self.assertIsNotNone(new_renderer)
        self.assertEqual(new_renderer.type(), renderer.type())
        
        # Verify form configuration was copied
        new_form_config = new_layer.editFormConfig()
        self.assertEqual(new_form_config.layout(), form_config.layout())
        
        # Verify default value was copied
        new_name_field_idx = new_layer.fields().indexOf('name')
        if new_name_field_idx >= 0:
            new_default_def = new_layer.defaultValueDefinition(new_name_field_idx)
            self.assertTrue(new_default_def.isValid())
            self.assertEqual(new_default_def.expression(), "'Default Name'")
        
        # Clean up
        project.removeMapLayer(source_layer)
        project.removeMapLayer(new_layer)
    
    def test_copy_layer_style_and_forms(self):
        """Test that copy_layer_style_and_forms copies symbology and form configuration."""
        from qgis.core import QgsDefaultValue, QgsSingleSymbolRenderer, QgsSymbol

        source_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=name:string&field=value:integer",
            "SourceLayer",
            "memory",
        )
        self.assertTrue(source_layer.isValid())

        form_config = source_layer.editFormConfig()
        form_config.setLayout(QgsEditFormConfig.TabLayout)
        source_layer.setEditFormConfig(form_config)

        name_field_idx = source_layer.fields().indexOf('name')
        if name_field_idx >= 0:
            source_layer.setDefaultValueDefinition(name_field_idx, QgsDefaultValue("'Default Name'"))

        renderer = QgsSingleSymbolRenderer(QgsSymbol.defaultSymbol(QgsWkbTypes.PointGeometry))
        source_layer.setRenderer(renderer)

        target_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=name:string&field=value:integer",
            "TargetLayer",
            "memory",
        )
        self.assertTrue(target_layer.isValid())

        self.layer_service.copy_layer_style_and_forms(source_layer, target_layer)

        target_renderer = target_layer.renderer()
        self.assertIsNotNone(target_renderer)
        self.assertEqual(target_renderer.type(), renderer.type())

        target_form_config = target_layer.editFormConfig()
        self.assertEqual(target_form_config.layout(), form_config.layout())

        if name_field_idx >= 0:
            target_default_def = target_layer.defaultValueDefinition(name_field_idx)
            self.assertTrue(target_default_def.isValid())
            self.assertEqual(target_default_def.expression(), "'Default Name'")

    def test_copy_layer_display_expression(self):
        """Display name formula is copied from definitive to temporary layer."""
        source_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=name:string",
            "Objects",
            "memory",
        )
        target_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=name:string",
            "New Objects",
            "memory",
        )
        self.assertTrue(source_layer.isValid())
        self.assertTrue(target_layer.isValid())

        source_layer.setDisplayExpression('"Objet " || Numero')
        self.layer_service._copy_layer_display_expression(source_layer, target_layer)

        self.assertEqual(
            target_layer.displayExpression(),
            '"Objet " || Numero',
        )

    @patch.object(QGISLayerService, "_remap_layer_relation_references")
    @patch.object(QGISLayerService, "_copy_layer_display_expression")
    @patch.object(QGISLayerService, "copy_layer_style_and_forms")
    @patch.object(QGISLayerService, "copy_layer_relations_for_temporary_layer")
    def test_configure_temporary_import_layer_orchestrates_copy_and_remap(
        self,
        mock_copy_relations,
        mock_copy_style,
        mock_copy_display_expression,
        mock_remap,
    ):
        """Temporary import configuration copies relations, style, then remaps widgets."""
        source_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=id:integer",
            "Objects",
            "memory",
        )
        target_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=id:integer",
            "New Objects",
            "memory",
        )
        self.assertTrue(source_layer.isValid())
        self.assertTrue(target_layer.isValid())
        mock_copy_relations.return_value = {"objects_materials": "archeosync_import_new"}

        self.layer_service.configure_temporary_import_layer(source_layer, target_layer)

        mock_copy_relations.assert_called_once_with(source_layer, target_layer)
        mock_copy_style.assert_called_once_with(source_layer, target_layer)
        mock_copy_display_expression.assert_called_once_with(source_layer, target_layer)
        mock_remap.assert_called_once_with(
            target_layer,
            {"objects_materials": "archeosync_import_new"},
        )

    @patch("archeosync.services.layer_service.uuid.uuid4")
    @patch("archeosync.services.layer_service.QgsProject")
    @patch("qgis.core.QgsRelation")
    def test_copy_layer_relations_for_temporary_layer_remaps_definitive_layer(
        self,
        mock_qgs_relation,
        mock_project,
        mock_uuid4,
    ):
        """Relations involving the definitive layer are cloned for the temporary layer."""
        source_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=id:integer&field=material_id:integer",
            "Objects",
            "memory",
        )
        target_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=id:integer&field=material_id:integer",
            "New Objects",
            "memory",
        )
        self.assertTrue(source_layer.isValid())
        self.assertTrue(target_layer.isValid())

        materials_layer = Mock()
        materials_layer.id.return_value = "materials"

        source_relation = Mock()
        source_relation.referencingLayerId.return_value = source_layer.id()
        source_relation.referencedLayerId.return_value = "materials"
        source_relation.id.return_value = "objects_materials"
        source_relation.name.return_value = "Objects/Materials"
        source_relation.fieldPairs.return_value = {"material_id": "id"}

        new_relation = Mock()
        mock_uuid4.return_value = Mock(hex="abc123def456")
        new_relation.referencingLayerId.return_value = target_layer.id()
        new_relation.referencedLayerId.return_value = "materials"
        mock_qgs_relation.return_value = new_relation

        relation_manager = Mock()
        relation_manager.relations.return_value = {"objects_materials": source_relation}
        relation_manager.addRelation.return_value = True

        project_instance = Mock()
        project_instance.relationManager.return_value = relation_manager
        project_instance.mapLayer.side_effect = lambda layer_id: {
            target_layer.id(): target_layer,
            "materials": materials_layer,
        }.get(layer_id)
        mock_project.instance.return_value = project_instance

        mapping = self.layer_service.copy_layer_relations_for_temporary_layer(
            source_layer,
            target_layer,
        )

        self.assertEqual(
            mapping,
            {"objects_materials": "archeosync_import_abc123def456"},
        )
        new_relation.addFieldPair.assert_called_once_with("material_id", "id")
        relation_manager.addRelation.assert_called_once_with(new_relation)

    def test_copy_field_configurations(self):
        """Test the _copy_field_configurations method specifically."""
        from qgis.core import QgsDefaultValue
        # Create source layer with field configurations
        source_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string&field=value:integer", "SourceLayer", "memory")
        self.assertTrue(source_layer.isValid())
        
        # Set default values using setDefaultValueDefinition
        name_field_idx = source_layer.fields().indexOf('name')
        if name_field_idx >= 0:
            source_layer.setDefaultValueDefinition(name_field_idx, QgsDefaultValue("'Test Default'"))
        
        # Create target layer
        target_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string&field=value:integer", "TargetLayer", "memory")
        self.assertTrue(target_layer.isValid())
        
        # Copy field configurations
        self.layer_service._copy_field_configurations(source_layer, target_layer)
        
        # Verify default value was copied
        target_name_field_idx = target_layer.fields().indexOf('name')
        if target_name_field_idx >= 0:
            target_default_def = target_layer.defaultValueDefinition(target_name_field_idx)
            self.assertTrue(target_default_def.isValid())
            self.assertEqual(target_default_def.expression(), "'Test Default'")


if __name__ == '__main__':
    unittest.main() 