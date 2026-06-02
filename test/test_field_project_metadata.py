"""Tests for field project metadata helpers."""

import importlib.util
import json
import os
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = importlib.util.spec_from_file_location(
    "field_project_metadata",
    os.path.join(_ROOT, "services", "field_project_metadata.py"),
)
_metadata = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_metadata)

METADATA_FILENAME = _metadata.METADATA_FILENAME
PROJECT_KIND_GLOBAL = _metadata.PROJECT_KIND_GLOBAL
PROJECT_KIND_RECORDING_AREA = _metadata.PROJECT_KIND_RECORDING_AREA
get_project_kind = _metadata.get_project_kind
is_global_project = _metadata.is_global_project
metadata_path = _metadata.metadata_path
read_project_metadata = _metadata.read_project_metadata
write_project_metadata = _metadata.write_project_metadata


class TestFieldProjectMetadata(unittest.TestCase):
    """Unit tests for archeosync_project.json helpers."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_and_read_global_metadata(self):
        extent = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        self.assertTrue(
            write_project_metadata(self.temp_dir, PROJECT_KIND_GLOBAL, extent, "EPSG:2154")
        )
        self.assertEqual(metadata_path(self.temp_dir), os.path.join(self.temp_dir, METADATA_FILENAME))
        data = read_project_metadata(self.temp_dir)
        self.assertIsNotNone(data)
        self.assertEqual(data["project_kind"], PROJECT_KIND_GLOBAL)
        self.assertEqual(data["extent_wkt"], extent)
        self.assertEqual(data["crs"], "EPSG:2154")

    def test_get_project_kind_defaults_to_recording_area(self):
        self.assertEqual(get_project_kind(self.temp_dir), PROJECT_KIND_RECORDING_AREA)
        self.assertFalse(is_global_project(self.temp_dir))

    def test_is_global_project(self):
        write_project_metadata(self.temp_dir, PROJECT_KIND_GLOBAL, "", "EPSG:4326")
        self.assertTrue(is_global_project(self.temp_dir))

    def test_invalid_json_returns_none(self):
        path = metadata_path(self.temp_dir)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertIsNone(read_project_metadata(self.temp_dir))
