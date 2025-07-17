"""
Test file to verify virtual field handling during layer copying.
"""

import unittest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from qgis.core import QgsVectorLayer, QgsField, QgsFields, QgsProject, QgsWkbTypes, QgsEditFormConfig
from PyQt5.QtCore import QVariant

from archeosync.services.layer_service import QGISLayerService
from archeosync.services.project_creation_service import QGISProjectCreationService


class TestVirtualFields(unittest.TestCase):
    """Test cases for virtual field handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.layer_service = QGISLayerService()
        
        # Mock dependencies for project creation service
        self.mock_settings_manager = Mock()
        self.mock_file_system_service = Mock()
        self.mock_raster_processing_service = Mock()
        self.mock_translation_service = Mock()
        
        self.project_creation_service = QGISProjectCreationService(
            self.mock_settings_manager,
            self.layer_service,
            self.mock_file_system_service,
            self.mock_raster_processing_service,
            self.mock_translation_service
        )
    
    def test_virtual_fields_excluded_from_copying(self):
        """Test that virtual fields are excluded when copying layer structure."""
        # Test the _is_virtual_field method directly with mocked fields
        
        # Create regular field mock
        regular_field = Mock()
        regular_field.name.return_value = "regular_field"
        regular_field.isVirtual.return_value = False
        regular_field.type.return_value = QVariant.String
        regular_field.comment.return_value = ""
        regular_field.alias.return_value = ""
        regular_field.expression.return_value = ""
        regular_field.defaultValueDefinition.return_value = None
        
        # Create virtual field mock
        virtual_field = Mock()
        virtual_field.name.return_value = "virtual_field"
        virtual_field.isVirtual.return_value = True
        virtual_field.type.return_value = QVariant.String
        virtual_field.comment.return_value = ""
        virtual_field.alias.return_value = ""
        virtual_field.expression.return_value = ""
        virtual_field.defaultValueDefinition.return_value = None
        
        # Test that regular field is not detected as virtual
        self.assertFalse(self.project_creation_service._is_virtual_field(regular_field))
        
        # Test that virtual field is detected as virtual
        self.assertTrue(self.project_creation_service._is_virtual_field(virtual_field))
    
    def test_virtual_field_detection_with_qml(self):
        """Test virtual field detection using QML files."""
        # Create a temporary QML file with expression fields
        qml_content = """<?xml version="1.0" encoding="UTF-8"?>
<qgis version="3.28.0-Firenze" styleCategories="AllStyleCategories" hasScaleBasedVisibilityFlag="0" minScale="0" maxScale="0" simplifyDrawingHints="1" simplifyLocal="1" simplifyAlgorithm="0" readOnly="0">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
    <Private>0</Private>
  </flags>
  <temporal enabled="0" mode="0" fetchMode="0">
    <fixedRange>
      <start></start>
      <end></end>
    </fixedRange>
  </temporal>
  <renderer-v2 enableorderby="0" forceraster="0" referencescale="-1" type="singleSymbol" symbollevels="0">
    <symbols>
      <symbol is_animated="0" name="0" clip_to_extent="1" force_rhr="0" frame_rate="10" alpha="1" type="marker">
        <data_defined_properties>
          <Option type="Map">
            <Option value="" name="name" type="QString"/>
            <Option name="properties"/>
            <Option value="collection" name="type" type="QString"/>
          </Option>
        </data_defined_properties>
        <layer id="{7c900a05-b124-4d20-9db7-c854bb8ab5cd}" pass="0" class="SimpleMarker" enabled="1" locked="0">
          <Option type="Map">
            <Option value="0" name="angle" type="QString"/>
            <Option value="square" name="cap_style" type="QString"/>
            <Option value="175,108,174,255,hsv:0.83611111111111114,0.3843137254901961,0.68627450980392157,1" name="color" type="QString"/>
            <Option value="1" name="horizontal_anchor_point" type="QString"/>
            <Option value="bevel" name="joinstyle" type="QString"/>
            <Option value="circle" name="name" type="QString"/>
            <Option value="0,0" name="offset" type="QString"/>
            <Option value="3x:0,0,0,0,0,0" name="offset_map_unit_scale" type="QString"/>
            <Option value="MM" name="offset_unit" type="QString"/>
            <Option value="35,35,35,255,rgb:0.13725490196078433,0.13725490196078433,0.13725490196078433,1" name="outline_color" type="QString"/>
            <Option value="solid" name="outline_style" type="QString"/>
            <Option value="0" name="outline_width" type="QString"/>
            <Option value="3x:0,0,0,0,0,0" name="outline_width_map_unit_scale" type="QString"/>
            <Option value="MM" name="outline_width_unit" type="QString"/>
            <Option value="diameter" name="scale_method" type="QString"/>
            <Option value="2" name="size" type="QString"/>
            <Option value="3x:0,0,0,0,0,0" name="size_map_unit_scale" type="QString"/>
            <Option value="MM" name="size_unit" type="QString"/>
            <Option value="1" name="vertical_anchor_point" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option value="" name="name" type="QString"/>
              <Option name="properties"/>
              <Option value="collection" name="type" type="QString"/>
            </Option>
          </data_defined_properties>
        </layer>
      </symbol>
    </symbols>
    <rotation/>
    <sizescale/>
    <data-defined-properties>
      <Option type="Map">
        <Option value="" name="name" type="QString"/>
        <Option name="properties"/>
        <Option value="collection" name="type" type="QString"/>
      </Option>
    </data-defined-properties>
  </renderer-v2>
  <selection mode="Default">
    <selectionColor invalid="1"/>
  </selection>
  <customproperties>
    <Option/>
  </customproperties>
  <blendMode>0</blendMode>
  <featureBlendMode>0</featureBlendMode>
  <layerOpacity>1</layerOpacity>
  <geometryOptions geometryPrecision="0" removeDuplicateNodes="0">
    <activeChecks type="StringList">
      <Option value="" type="QString"/>
    </activeChecks>
    <checkConfiguration/>
  </geometryOptions>
  <legend showLabelLegend="0" type="default-vector"/>
  <referencedLayers/>
  <fieldConfiguration>
    <field name="name" configurationFlags="NoFlag">
      <editWidget type="">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
    <field name="value" configurationFlags="NoFlag">
      <editWidget type="">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
  </fieldConfiguration>
  <aliases>
    <alias name="" field="name" index="0"/>
    <alias name="" field="value" index="1"/>
  </aliases>
  <splitPolicies>
    <policy policy="Duplicate" field="name"/>
    <policy policy="Duplicate" field="value"/>
  </splitPolicies>
  <duplicatePolicies>
    <policy policy="Duplicate" field="name"/>
    <policy policy="Duplicate" field="value"/>
  </duplicatePolicies>
  <defaults>
    <default expression="'Default Name'" field="name" applyOnUpdate="0"/>
    <default expression="" field="value" applyOnUpdate="0"/>
  </defaults>
  <constraints>
    <constraint notnull_strength="0" constraints="0" field="name" exp_strength="0" unique_strength="0"/>
    <constraint notnull_strength="0" constraints="0" field="value" exp_strength="0" unique_strength="0"/>
  </constraints>
  <constraintExpressions>
    <constraint desc="" field="name" exp=""/>
    <constraint desc="" field="value" exp=""/>
  </constraintExpressions>
  <expressionfields>
    <field name="virtual_field" expression="'name' || '_computed'" type="10" comment="" precision="0" length="0" subType=""/>
  </expressionfields>
  <attributeactions/>
  <attributetableconfig sortOrder="0" sortExpression="" actionWidgetStyle="dropDown">
    <columns/>
  </attributetableconfig>
  <conditionalstyles>
    <rowstyles/>
    <fieldstyles/>
  </conditionalstyles>
  <storedexpressions/>
  <editform tolerant="1"></editform>
  <editforminit/>
  <editforminitcodesource>0</editforminitcodesource>
  <editforminitfilepath></editforminitfilepath>
  <editforminitcode><![CDATA[]]></editforminitcode>
  <featformsuppress>0</featformsuppress>
  <editorlayout>tablayout</editorlayout>
  <attributeEditorForm>
    <labelStyle labelColor="" overrideLabelColor="0" overrideLabelFont="0">
      <labelFont bold="0" description=".AppleSystemUIFont,13,-1,5,50,0,0,0,0,0" underline="0" italic="0" style="" strikethrough="0"/>
    </labelStyle>
    <attributeEditorField showLabel="1" verticalStretch="0" name="name" horizontalStretch="0" index="0">
      <labelStyle labelColor="" overrideLabelColor="0" overrideLabelFont="0">
        <labelFont bold="0" description=".AppleSystemUIFont,13,-1,5,50,0,0,0,0,0" underline="0" italic="0" style="" strikethrough="0"/>
      </labelStyle>
    </attributeEditorField>
    <attributeEditorField showLabel="1" verticalStretch="0" name="value" horizontalStretch="0" index="1">
      <labelStyle labelColor="" overrideLabelColor="0" overrideLabelFont="0">
        <labelFont bold="0" description=".AppleSystemUIFont,13,-1,5,50,0,0,0,0,0" underline="0" italic="0" style="" strikethrough="0"/>
      </labelStyle>
    </attributeEditorField>
  </attributeEditorForm>
  <editable/>
  <labelOnTop/>
  <reuseLastValue/>
  <dataDefinedFieldProperties/>
  <widgets/>
  <previewExpression></previewExpression>
  <mapTip enabled="1"></mapTip>
  <layerGeometryType>0</layerGeometryType>
</qgis>"""
        
        with tempfile.NamedTemporaryFile(suffix='.qml', delete=False, mode='w', encoding='utf-8') as f:
            f.write(qml_content)
            qml_path = f.name
        
        try:
            # Test the QML parsing method
            virtual_fields = self._parse_qml_expression_fields(qml_path)
            
            # Should find the virtual field
            self.assertIn('virtual_field', virtual_fields)
            self.assertEqual(virtual_fields['virtual_field'], "'name' || '_computed'")
            
        finally:
            # Clean up
            os.unlink(qml_path)
    
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
            print(f"Error parsing QML file: {str(e)}")
            return {}


if __name__ == '__main__':
    unittest.main() 