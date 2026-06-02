"""Tests for global field project import behaviour."""

import os
import tempfile
import unittest
from unittest.mock import Mock, MagicMock

import pytest

try:
    from qgis.core import QgsFeature, QgsGeometry
    from services.field_project_import_service import FieldProjectImportService
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

import importlib.util

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = importlib.util.spec_from_file_location(
    "field_project_metadata",
    os.path.join(_ROOT, "services", "field_project_metadata.py"),
)
_metadata = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_metadata)
write_project_metadata = _metadata.write_project_metadata
get_import_layer_names = _metadata.get_import_layer_names
PROJECT_KIND_GLOBAL = _metadata.PROJECT_KIND_GLOBAL

pytestmark = pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")


@pytest.mark.qgis
class TestFieldProjectImportGlobal(unittest.TestCase):
    """Tests for scanning and merging global project layers."""

    def setUp(self):
        self.settings_manager = Mock()
        self.layer_service = Mock()
        self.file_system_service = Mock()
        self.service = FieldProjectImportService(
            self.settings_manager,
            self.layer_service,
            self.file_system_service,
        )
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_readonly_context_files_are_skipped(self):
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'recording_areas_layer': 'ra_id',
            'extra_field_layers': ['extra_id'],
        }.get(key, default)

        self.layer_service.get_layer_info.side_effect = lambda layer_id: {
            'ra_id': {'name': 'Zones'},
            'extra_id': {'name': 'ContextLayer'},
        }.get(layer_id)

        self.assertTrue(self.service._is_readonly_context_layer_file('Zones.gpkg'))
        self.assertTrue(self.service._is_readonly_context_layer_file('ContextLayer.gpkg'))
        self.assertFalse(self.service._is_readonly_context_layer_file('Objects.gpkg'))

    def test_scan_uses_metadata_layer_names_over_settings(self):
        """Global project metadata must drive classification when settings names differ."""
        write_project_metadata(
            self.temp_dir,
            PROJECT_KIND_GLOBAL,
            "POLYGON((0 0,1 0,1 1,0 1,0 0))",
            "EPSG:4326",
            import_layers={
                "objects": "Objets relevés",
                "alternative_objects": "Objets relevés sans géométrie",
                "features": "Fugaces",
            },
        )
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            "objects_layer": "obj_id",
            "alternative_objects_layer": "alt_id",
            "features_layer": "feat_id",
            "small_finds_layer": "",
        }.get(key, default)
        self.layer_service.get_layer_info.side_effect = lambda layer_id: {
            "obj_id": {"name": "Wrong Objects Name"},
            "alt_id": {"name": "Wrong Alt Name"},
            "feat_id": {"name": "Wrong Features Name"},
        }.get(layer_id)

        open(os.path.join(self.temp_dir, "Objets relevés.gpkg"), "w").close()
        open(os.path.join(self.temp_dir, "Objets relevés sans géométrie.gpkg"), "w").close()
        open(os.path.join(self.temp_dir, "Fugaces.gpkg"), "w").close()

        layer_files = self.service._scan_project_layers(
            self.temp_dir,
            project_import_layers=get_import_layer_names(self.temp_dir),
        )
        self.assertEqual(len(layer_files["objects"]), 1)
        self.assertEqual(len(layer_files["alternative_objects"]), 1)
        self.assertEqual(len(layer_files["features"]), 1)

    def test_scan_classifies_objets_releves_gpkg_files(self):
        """Scan must pick up French object layer GeoPackages by configured name."""
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            "objects_layer": "obj_id",
            "alternative_objects_layer": "alt_id",
            "features_layer": "feat_id",
            "small_finds_layer": "",
            "recording_areas_layer": "",
            "extra_field_layers": [],
        }.get(key, default)

        self.layer_service.get_layer_info.side_effect = lambda layer_id: {
            "obj_id": {"name": "Objets relevés"},
            "alt_id": {"name": "Objets relevés sans géométrie"},
            "feat_id": {"name": "Fugaces"},
        }.get(layer_id)

        open(os.path.join(self.temp_dir, "Objets relevés.gpkg"), "w").close()
        open(os.path.join(self.temp_dir, "Objets relevés sans géométrie.gpkg"), "w").close()
        open(os.path.join(self.temp_dir, "Fugaces.gpkg"), "w").close()

        layer_files = self.service._scan_project_layers(self.temp_dir)
        self.assertEqual(len(layer_files["objects"]), 1)
        self.assertEqual(len(layer_files["alternative_objects"]), 1)
        self.assertEqual(len(layer_files["features"]), 1)

    def test_scan_keeps_objects_when_objects_is_also_extra_field_layer(self):
        """Objects.gpkg must be importable even if the objects layer is listed as extra field."""
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'recording_areas_layer': 'ra_id',
            'objects_layer': 'obj_id',
            'alternative_objects_layer': '',
            'features_layer': '',
            'small_finds_layer': '',
            'extra_field_layers': ['obj_id'],
        }.get(key, default)

        self.layer_service.get_layer_info.side_effect = lambda layer_id: {
            'ra_id': {'name': 'Zones'},
            'obj_id': {'name': 'Objects'},
        }.get(layer_id)

        open(os.path.join(self.temp_dir, 'Objects.gpkg'), 'w').close()
        open(os.path.join(self.temp_dir, 'Zones.gpkg'), 'w').close()

        layer_files = self.service._scan_project_layers(self.temp_dir)
        self.assertEqual(layer_files['objects'], [os.path.join(self.temp_dir, 'Objects.gpkg')])

    def test_scan_ignores_readonly_and_collects_alternative(self):
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'recording_areas_layer': 'ra_id',
            'objects_layer': 'obj_id',
            'alternative_objects_layer': 'alt_id',
            'features_layer': '',
            'small_finds_layer': '',
            'extra_field_layers': ['extra_id'],
        }.get(key, default)

        self.layer_service.get_layer_info.side_effect = lambda layer_id: {
            'ra_id': {'name': 'Zones'},
            'obj_id': {'name': 'Objects'},
            'alt_id': {'name': 'AltTable'},
            'extra_id': {'name': 'ContextLayer'},
        }.get(layer_id)

        open(os.path.join(self.temp_dir, 'Zones.gpkg'), 'w').close()
        open(os.path.join(self.temp_dir, 'ContextLayer.gpkg'), 'w').close()
        open(os.path.join(self.temp_dir, 'Objects.gpkg'), 'w').close()
        open(os.path.join(self.temp_dir, 'AltTable.gpkg'), 'w').close()

        layer_files = self.service._scan_project_layers(self.temp_dir)
        self.assertEqual(layer_files['objects'], [os.path.join(self.temp_dir, 'Objects.gpkg')])
        self.assertEqual(layer_files['alternative_objects'], [os.path.join(self.temp_dir, 'AltTable.gpkg')])
        self.assertNotIn(os.path.join(self.temp_dir, 'Zones.gpkg'), layer_files['objects'])

    def test_convert_alternative_features_to_objects_clears_geometry(self):
        target_layer = MagicMock()
        target_field = MagicMock()
        target_field.name.return_value = 'number'
        target_fields = MagicMock()
        target_fields.indexOf.side_effect = lambda name: 0 if name == 'number' else -1
        target_fields.__iter__ = lambda self: iter([target_field])
        target_layer.fields.return_value = target_fields

        source_field = MagicMock()
        source_field.name.return_value = 'number'
        source_fields = MagicMock()
        source_fields.__iter__ = lambda self: iter([source_field])
        source_fields.indexOf = Mock(return_value=-1)

        source_feature = MagicMock()
        source_feature.fields.return_value = source_fields
        source_feature.attribute.return_value = 42
        source_feature.geometry.return_value = MagicMock()

        self.service._get_existing_layer = Mock(return_value=target_layer)

        converted = self.service._convert_alternative_features_to_objects([source_feature])
        self.assertEqual(len(converted), 1)
        self.assertTrue(converted[0].geometry().isEmpty())

    def test_get_project_kind_reads_metadata(self):
        write_project_metadata(self.temp_dir, PROJECT_KIND_GLOBAL, "POLYGON((0 0,1 0,1 1,0 1,0 0))", "EPSG:4326")
        self.assertEqual(self.service.get_project_kind(self.temp_dir), PROJECT_KIND_GLOBAL)
