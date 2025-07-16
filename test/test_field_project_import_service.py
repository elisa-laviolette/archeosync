"""
Tests for the Field Project Import Service.

This module tests the FieldProjectImportService implementation to ensure
it correctly processes both data.gpkg files and individual layer files
from completed field projects.
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List

# Test QGIS availability
try:
    from qgis.core import QgsVectorLayer, QgsFeature, QgsProject, QgsGeometry, QgsPointXY
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

from services.field_project_import_service import FieldProjectImportService
from core.interfaces import ValidationResult





def create_mock_layer_with_fields():
    """Create a properly mocked QGIS layer with fields."""
    mock_layer = MagicMock()
    mock_layer.isValid.return_value = True
    mock_layer.geometryType.return_value = 2  # PolygonGeometry
    mock_layer.startEditing.return_value = True
    mock_layer.commitChanges.return_value = True
    mock_layer.addFeature.return_value = True
    mock_layer.lastError.return_value = ""
    
    # Mock layer fields
    mock_field = Mock()
    mock_field.name.return_value = "id"
    mock_field.typeName.return_value = "Integer"
    
    # Create a proper fields object that can be iterated
    mock_fields = Mock()
    mock_fields.count.return_value = 1
    mock_fields.__iter__ = lambda self: iter([mock_field])
    mock_fields.__getitem__ = lambda self, index: mock_field if index == 0 else None
    mock_fields.indexOf = lambda field_name: 0 if field_name == "id" else -1
    
    mock_layer.fields.return_value = mock_fields
    
    return mock_layer


# Helper to create a mock QgsFeature with correct behavior
def make_qgsfeature_mock(fields):
    feature = Mock()
    feature.setGeometry = Mock()
    feature.fields.return_value = fields
    feature.__getitem__ = lambda self, key: 1 if key == "id" else None
    feature.__setitem__ = lambda self, key, value: None
    feature.__contains__ = lambda self, key: key == "id"
    return feature

# Helper to create a mock feature that can be iterated (for getFeatures())
def create_iterable_mock_feature():
    mock_feature = MagicMock()
    mock_geometry = MagicMock()
    mock_geometry.type.return_value = 2  # PolygonGeometry
    mock_geometry.isMultipart.return_value = False
    mock_geometry.isEmpty.return_value = False
    mock_feature.geometry.return_value = mock_geometry
    
    # Mock feature fields
    mock_field = MagicMock()
    mock_field.name.return_value = "id"
    mock_field.typeName.return_value = "Integer"
    
    # Create a proper fields object that can be iterated
    mock_fields = MagicMock()
    mock_fields.count.return_value = 1
    mock_fields.__iter__ = lambda self: iter([mock_field])
    mock_fields.__getitem__ = lambda self, index: mock_field if index == 0 else None
    mock_fields.indexOf = lambda field_name: 0 if field_name == "id" else -1
    
    mock_feature.fields.return_value = mock_fields
    
    # Make the feature subscriptable for attribute access
    mock_feature.__getitem__.side_effect = lambda field_name: 1 if field_name == "id" else None
    mock_feature.__contains__.side_effect = lambda field_name: field_name == "id"
    
    return mock_feature


@pytest.mark.qgis
@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class TestFieldProjectImportService:
    """Test cases for FieldProjectImportService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.settings_manager = Mock()
        self.layer_service = Mock()
        self.file_system_service = Mock()
        
        self.field_import_service = FieldProjectImportService(
            self.settings_manager,
            self.layer_service,
            self.file_system_service
        )
    
    def test_field_import_service_creation(self):
        """Test that the field import service can be created."""
        assert self.field_import_service is not None
        assert hasattr(self.field_import_service, 'import_field_projects')
    
    def test_import_field_projects_empty_list(self):
        """Test importing field projects with empty list."""
        result = self.field_import_service.import_field_projects([])
        
        assert result.is_valid is True
        assert "No projects to import" in result.message
    
    @patch('os.path.exists')
    @patch('services.field_project_import_service.QgsVectorLayer')
    def test_import_field_projects_no_layers_found(self, mock_vector_layer, mock_exists):
        """Test importing field projects when no layers are found."""
        # Mock that project directory exists but no data.gpkg
        mock_exists.return_value = False
        
        # Use string path instead of mock
        project_path = "/test/project1"
        result = self.field_import_service.import_field_projects([project_path])
        
        assert result.is_valid is False
        assert "No Objects or Features layers found" in result.message
    
    @patch('services.field_project_import_service.QgsFeature')
    @patch('os.path.exists')
    @patch('services.field_project_import_service.QgsVectorLayer')
    @patch('services.field_project_import_service.QgsProject')
    def test_import_field_projects_with_data_gpkg(self, mock_project, mock_vector_layer, mock_exists, mock_qgsfeature):
        """Test importing field projects with data.gpkg file."""
        # Mock that data.gpkg exists
        def exists_side_effect(path):
            return path.endswith("data.gpkg")
        mock_exists.side_effect = exists_side_effect
        
        # Mock Objects sublayer using the helper function
        mock_objects_layer = create_mock_layer_with_fields()
        mock_feature = create_iterable_mock_feature()
        mock_objects_layer.getFeatures.return_value = [mock_feature]
        
        # Mock data layer
        mock_data_layer = MagicMock()
        mock_data_layer.isValid.return_value = True
        
        # Mock dataProvider and subLayers properly
        mock_data_provider = MagicMock()
        mock_data_layer.dataProvider.return_value = mock_data_provider
        # Return actual strings that can be split
        mock_data_provider.subLayers.return_value = [
            "0!!::!!Objects_abc123!!::!!Point!!::!!EPSG:4326"
        ]
        
        # Mock merged layer
        mock_merged_layer = create_mock_layer_with_fields()
        mock_merged_layer.addFeature.return_value = True
        mock_merged_layer.lastError.return_value = ""
        mock_merged_layer.startEditing.return_value = True
        mock_merged_layer.commitChanges.return_value = True
        
        # Patch QgsFeature to return a proper mock
        def feature_side_effect(fields):
            return make_qgsfeature_mock(fields)
        mock_qgsfeature.side_effect = feature_side_effect
        
        # Mock project instance and CRS
        mock_project_instance = Mock()
        mock_crs = Mock()
        mock_crs.authid.return_value = "EPSG:3857"
        mock_crs.isValid.return_value = True
        mock_project_instance.crs.return_value = mock_crs
        mock_project.instance.return_value = mock_project_instance
        
        # Patch addMapLayer to accept any argument
        mock_project_instance.addMapLayer = Mock()

        # Mock vector layer creation with proper side effect
        def vector_layer_side_effect(*args, **kwargs):
            if len(args) > 1 and args[0].endswith("data.gpkg") and args[1] == "temp_data":
                return mock_data_layer
            elif len(args) > 1 and "Objects_abc123" in args[1]:
                return mock_objects_layer
            elif len(args) > 1 and "New Objects" in args[1]:
                return mock_merged_layer
            else:
                return mock_merged_layer
        
        mock_vector_layer.side_effect = vector_layer_side_effect

        result = self.field_import_service.import_field_projects(["/test/project1"])
        
        assert result.is_valid is True
        assert "Successfully imported 1 layer(s)" in result.message
    
    @patch('services.field_project_import_service.QgsFeature')
    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('os.path.isfile')
    @patch('services.field_project_import_service.QgsVectorLayer')
    @patch('services.field_project_import_service.QgsProject')
    def test_import_field_projects_with_individual_layers(self, mock_project, mock_vector_layer, mock_isfile, mock_listdir, mock_exists, mock_qgsfeature):
        """Test importing field projects with individual layer files."""
        # Mock that project directory exists but no data.gpkg
        def exists_side_effect(path):
            return not path.endswith("data.gpkg")
        mock_exists.side_effect = exists_side_effect
        
        # Mock directory listing to include individual layer files
        mock_listdir.return_value = ["Objects.gpkg", "Features.gpkg", "other_file.txt"]
        
        # Mock that Objects.gpkg is a file
        def isfile_side_effect(path):
            return "Objects.gpkg" in path or "Features.gpkg" in path
        mock_isfile.side_effect = isfile_side_effect
        
        # Mock Objects layer file
        mock_objects_layer = create_mock_layer_with_fields()
        mock_feature = create_iterable_mock_feature()
        mock_objects_layer.getFeatures.return_value = [mock_feature]
        
        # Mock merged layer
        mock_merged_layer = create_mock_layer_with_fields()
        mock_merged_layer.addFeature.return_value = True
        mock_merged_layer.lastError.return_value = ""
        mock_merged_layer.startEditing.return_value = True
        mock_merged_layer.commitChanges.return_value = True
        
        # Patch QgsFeature to return a proper mock
        def feature_side_effect(fields):
            return make_qgsfeature_mock(fields)
        mock_qgsfeature.side_effect = feature_side_effect
        
        # Mock project instance and CRS
        mock_project_instance = Mock()
        mock_crs = Mock()
        mock_crs.authid.return_value = "EPSG:3857"
        mock_crs.isValid.return_value = True
        mock_project_instance.crs.return_value = mock_crs
        mock_project.instance.return_value = mock_project_instance
        
        # Patch addMapLayer to accept any argument
        mock_project_instance.addMapLayer = Mock()

        # Mock vector layer creation with proper side effect
        def vector_layer_side_effect(*args, **kwargs):
            if len(args) > 1 and "Objects.gpkg" in args[0] and args[1] == "temp_objects":
                return mock_objects_layer
            elif len(args) > 1 and "New Objects" in args[1]:
                return mock_merged_layer
            else:
                return mock_merged_layer
        
        mock_vector_layer.side_effect = vector_layer_side_effect
        
        # Use string path instead of mock
        project_path = "/test/project1"
        result = self.field_import_service.import_field_projects([project_path])
        
        assert result.is_valid is True
        assert "Successfully imported 1 layer(s)" in result.message
    
    @patch('services.field_project_import_service.QgsFeature')
    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('services.field_project_import_service.QgsVectorLayer')
    @patch('services.field_project_import_service.QgsProject')
    def test_import_field_projects_with_both_data_gpkg_and_individual_layers(self, mock_project, mock_vector_layer, mock_listdir, mock_exists, mock_qgsfeature):
        """Test importing field projects with both data.gpkg and individual layer files."""
        # Mock that both data.gpkg and individual files exist
        def exists_side_effect(path):
            return True
        mock_exists.side_effect = exists_side_effect
        
        # Mock directory listing to include individual layer files
        mock_listdir.return_value = ["Objects.gpkg", "Features.gpkg", "other_file.txt"]
        
        # Mock Objects sublayer from data.gpkg using helper functions
        mock_objects_sublayer = create_mock_layer_with_fields()
        mock_feature1 = create_iterable_mock_feature()
        mock_objects_sublayer.getFeatures.return_value = [mock_feature1]
        
        # Mock data layer
        mock_data_layer = MagicMock()
        mock_data_layer.isValid.return_value = True
        
        # Mock dataProvider and subLayers properly
        mock_data_provider = MagicMock()
        mock_data_layer.dataProvider.return_value = mock_data_provider
        # Return actual strings that can be split
        mock_data_provider.subLayers.return_value = [
            "0!!::!!Objects_abc123!!::!!Point!!::!!EPSG:4326"
        ]
        
        # Mock the sublayer access properly
        mock_data_layer.dataProvider.return_value.subLayers.return_value = [
            "0!!::!!Objects_abc123!!::!!Point!!::!!EPSG:4326"
        ]
        
        # Mock individual Objects layer file
        mock_objects_individual = create_mock_layer_with_fields()
        mock_feature2 = create_iterable_mock_feature()
        mock_objects_individual.getFeatures.return_value = [mock_feature2]
        
        # Mock merged layer
        mock_merged_layer = create_mock_layer_with_fields()
        mock_merged_layer.addFeature.return_value = True
        mock_merged_layer.lastError.return_value = ""
        
        # Mock project instance and CRS
        mock_project_instance = Mock()
        mock_crs = Mock()
        mock_crs.authid.return_value = "EPSG:3857"
        mock_crs.isValid.return_value = True
        mock_project_instance.crs.return_value = mock_crs
        mock_project.instance.return_value = mock_project_instance
        
        # Patch addMapLayer to accept any argument
        mock_project_instance.addMapLayer = Mock()

        # Mock vector layer creation with proper side effect
        def vector_layer_side_effect(*args, **kwargs):
            if len(args) > 1 and args[0].endswith("data.gpkg") and args[1] == "temp_data":
                return mock_data_layer
            elif len(args) > 1 and "Objects_abc123" in args[1]:
                return mock_objects_sublayer
            elif len(args) > 1 and "Objects.gpkg" in args[0] and args[1] == "temp_objects":
                return mock_objects_individual
            elif len(args) > 1 and "New Objects" in args[1]:
                return mock_merged_layer
            else:
                return mock_merged_layer
        
        mock_vector_layer.side_effect = vector_layer_side_effect
        
        # Patch QgsFeature to return a proper mock
        def feature_side_effect(fields):
            return make_qgsfeature_mock(fields)
        mock_qgsfeature.side_effect = feature_side_effect
        
        # Use string path instead of mock
        project_path = "/test/project1"
        result = self.field_import_service.import_field_projects([project_path])
        
        assert result.is_valid is True
        assert "Successfully imported 1 layer(s)" in result.message
    
    def test_is_objects_layer_file(self):
        """Test detection of Objects layer files."""
        assert self.field_import_service._is_objects_layer_file("Objects.gpkg") is True
        assert self.field_import_service._is_objects_layer_file("objects.gpkg") is True
        assert self.field_import_service._is_objects_layer_file("Obj.gpkg") is True
        assert self.field_import_service._is_objects_layer_file("Features.gpkg") is False
        assert self.field_import_service._is_objects_layer_file("other.txt") is False
    
    def test_is_features_layer_file(self):
        """Test detection of Features layer files."""
        assert self.field_import_service._is_features_layer_file("Features.gpkg") is True
        assert self.field_import_service._is_features_layer_file("features.gpkg") is True
        assert self.field_import_service._is_features_layer_file("Feat.gpkg") is True
        assert self.field_import_service._is_features_layer_file("Objects.gpkg") is False
        assert self.field_import_service._is_features_layer_file("other.txt") is False
    
    def test_is_objects_layer_name(self):
        """Test detection of Objects layer names."""
        # Test with configured layer name
        self.settings_manager.get_value.return_value = "objects_layer_id"
        mock_layer_info = {"name": "MyObjects"}
        self.layer_service.get_layer_info.return_value = mock_layer_info
        
        assert self.field_import_service._is_objects_layer_name("MyObjects") is True
        assert self.field_import_service._is_objects_layer_name("myobjects") is True
        
        # Test fallback patterns
        self.layer_service.get_layer_info.return_value = None
        assert self.field_import_service._is_objects_layer_name("Objects") is True
        assert self.field_import_service._is_objects_layer_name("objects") is True
        assert self.field_import_service._is_objects_layer_name("Obj") is True
        assert self.field_import_service._is_objects_layer_name("Features") is False
        assert self.field_import_service._is_objects_layer_name("other") is False
    
    def test_is_features_layer_name(self):
        """Test detection of Features layer names."""
        # Test with configured layer name
        self.settings_manager.get_value.return_value = "features_layer_id"
        mock_layer_info = {"name": "MyFeatures"}
        self.layer_service.get_layer_info.return_value = mock_layer_info
        
        assert self.field_import_service._is_features_layer_name("MyFeatures") is True
        assert self.field_import_service._is_features_layer_name("myfeatures") is True
        
        # Test fallback patterns
        self.layer_service.get_layer_info.return_value = None
        assert self.field_import_service._is_features_layer_name("Features") is True
        assert self.field_import_service._is_features_layer_name("features") is True
        assert self.field_import_service._is_features_layer_name("Feat") is True
        assert self.field_import_service._is_features_layer_name("Objects") is False
        assert self.field_import_service._is_features_layer_name("other") is False
    
    @patch('services.field_project_import_service.QgsProject')
    def test_get_crs_string(self, mock_project):
        """Test getting CRS string from QgsCoordinateReferenceSystem."""
        # Mock CRS with authid
        mock_crs = Mock()
        mock_crs.authid.return_value = "EPSG:3857"
        
        result = self.field_import_service._get_crs_string(mock_crs)
        assert result == "EPSG:3857"
        
        # Test fallback to description
        mock_crs.authid.side_effect = Exception("No authid")
        mock_crs.description.return_value = "WGS 84 / Pseudo-Mercator"
        
        result = self.field_import_service._get_crs_string(mock_crs)
        assert result == "WGS 84 / Pseudo-Mercator"
        
        # Test fallback to default
        mock_crs.description.side_effect = Exception("No description")
        
        result = self.field_import_service._get_crs_string(mock_crs)
        assert result == "EPSG:4326"

    @patch('services.field_project_import_service.QgsFeature')
    @patch('os.path.exists')
    @patch('services.field_project_import_service.QgsVectorLayer')
    @patch('services.field_project_import_service.QgsProject')
    def test_import_field_projects_archives_projects_when_configured(self, mock_project, mock_vector_layer, mock_exists, mock_qgsfeature):
        """Test that field projects are archived after successful import when archive folder is configured."""
        # Mock that data.gpkg exists
        def exists_side_effect(path):
            return path.endswith("data.gpkg")
        mock_exists.side_effect = exists_side_effect
        
        # Mock settings to return archive folder
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'field_project_archive_folder': '/archive/path'
        }.get(key, default)
        
        # Mock file system service
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.create_directory.return_value = True
        self.file_system_service.move_directory.return_value = True
        
        # Mock data layer
        mock_data_layer = Mock()
        mock_data_layer.isValid.return_value = True
        
        # Mock dataProvider and subLayers properly
        mock_data_provider = Mock()
        mock_data_layer.dataProvider.return_value = mock_data_provider
        # Return actual strings that can be split
        mock_data_provider.subLayers.return_value = [
            "0!!::!!Objects_abc123!!::!!Point!!::!!EPSG:4326"
        ]
        
        # Mock Objects sublayer
        mock_objects_layer = create_mock_layer_with_fields()
        mock_feature = create_iterable_mock_feature()
        mock_objects_layer.getFeatures.return_value = [mock_feature]
        
        # Mock merged layer
        mock_merged_layer = create_mock_layer_with_fields()
        mock_merged_layer.addFeature.return_value = True
        mock_merged_layer.lastError.return_value = ""
        
        # Mock project instance and CRS
        mock_project_instance = Mock()
        mock_crs = Mock()
        mock_crs.authid.return_value = "EPSG:3857"
        mock_crs.isValid.return_value = True
        mock_project_instance.crs.return_value = mock_crs
        mock_project.instance.return_value = mock_project_instance
        
        # Patch addMapLayer to accept any argument
        mock_project_instance.addMapLayer = Mock()

        # Mock vector layer creation with proper side effect
        def vector_layer_side_effect(*args, **kwargs):
            if len(args) > 1 and args[0].endswith("data.gpkg") and args[1] == "temp_data":
                return mock_data_layer
            elif len(args) > 1 and "Objects" in args[1]:
                return mock_objects_layer
            elif len(args) > 1 and "New Objects" in args[1]:
                return mock_merged_layer
            else:
                return mock_merged_layer
        
        mock_vector_layer.side_effect = vector_layer_side_effect
        
        # Patch QgsFeature to return a proper mock
        def feature_side_effect(fields):
            return make_qgsfeature_mock(fields)
        mock_qgsfeature = Mock()
        mock_qgsfeature.side_effect = feature_side_effect
        
        # Use string path instead of mock
        project_path = "/test/project1"
        result = self.field_import_service.import_field_projects([project_path])
        
        # Verify import was successful
        assert result.is_valid is True
        assert "Successfully imported 1 layer(s)" in result.message
        
        # Verify archive folder was checked
        self.settings_manager.get_value.assert_called_with('field_project_archive_folder', '')
        
        # Verify project was moved to archive
        self.file_system_service.move_directory.assert_called_once()

    @patch('services.field_project_import_service.QgsFeature')
    @patch('os.path.exists')
    @patch('services.field_project_import_service.QgsVectorLayer')
    @patch('services.field_project_import_service.QgsProject')
    def test_import_field_projects_does_not_archive_when_not_configured(self, mock_project, mock_vector_layer, mock_exists, mock_qgsfeature):
        """Test that field projects are not archived when archive folder is not configured."""
        # Mock that data.gpkg exists
        def exists_side_effect(path):
            return path.endswith("data.gpkg")
        mock_exists.side_effect = exists_side_effect
        
        # Mock settings - no archive folder configured
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'field_project_archive_folder': ''  # Empty archive folder
        }.get(key, default)
        
        # Mock data layer
        mock_data_layer = Mock()
        mock_data_layer.isValid.return_value = True
        
        # Mock dataProvider and subLayers properly
        mock_data_provider = Mock()
        mock_data_layer.dataProvider.return_value = mock_data_provider
        # Return actual strings that can be split
        mock_data_provider.subLayers.return_value = [
            "0!!::!!Objects_abc123!!::!!Point!!::!!EPSG:4326"
        ]
        
        # Mock Objects sublayer
        mock_objects_layer = create_mock_layer_with_fields()
        mock_feature = create_iterable_mock_feature()
        mock_objects_layer.getFeatures.return_value = [mock_feature]
        
        # Mock merged layer
        mock_merged_layer = create_mock_layer_with_fields()
        mock_merged_layer.addFeature.return_value = True
        mock_merged_layer.lastError.return_value = ""
        
        # Mock project instance and CRS
        mock_project_instance = Mock()
        mock_crs = Mock()
        mock_crs.authid.return_value = "EPSG:3857"
        mock_crs.isValid.return_value = True
        mock_project_instance.crs.return_value = mock_crs
        mock_project.instance.return_value = mock_project_instance
        
        # Patch addMapLayer to accept any argument
        mock_project_instance.addMapLayer = Mock()

        # Mock vector layer creation with proper side effect
        def vector_layer_side_effect(*args, **kwargs):
            if len(args) > 1 and args[0].endswith("data.gpkg") and args[1] == "temp_data":
                return mock_data_layer
            elif len(args) > 1 and "Objects" in args[1]:
                return mock_objects_layer
            elif len(args) > 1 and "New Objects" in args[1]:
                return mock_merged_layer
            else:
                return mock_merged_layer
        
        mock_vector_layer.side_effect = vector_layer_side_effect
        
        # Patch QgsFeature to return a proper mock
        def feature_side_effect(fields):
            return make_qgsfeature_mock(fields)
        mock_qgsfeature = Mock()
        mock_qgsfeature.side_effect = feature_side_effect
        
        # Use string path instead of mock
        project_path = "/test/project1"
        result = self.field_import_service.import_field_projects([project_path])
        
        # Verify import was successful
        assert result.is_valid is True
        assert "Successfully imported 1 layer(s)" in result.message
        
        # Verify archive folder was checked
        self.settings_manager.get_value.assert_called_with('field_project_archive_folder', '')
        
        # Verify project was NOT moved to archive
        self.file_system_service.move_directory.assert_not_called() 