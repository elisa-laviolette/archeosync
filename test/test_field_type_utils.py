"""
Tests for temporal QGIS field type detection helpers.
"""

import importlib.util
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = importlib.util.spec_from_file_location(
    "field_type_utils",
    os.path.join(_ROOT, "services", "field_type_utils.py"),
)
_field_type_utils = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _field_type_utils
_SPEC.loader.exec_module(_field_type_utils)

is_temporal_field = _field_type_utils.is_temporal_field
temporal_memory_uri_type = _field_type_utils.temporal_memory_uri_type


class TestTemporalFieldTypeUtils:
    @pytest.mark.parametrize(
        "type_name",
        [
            "Date",
            "DateTime",
            "date",
            "datetime",
            "timestamp",
            "timestamptz",
            "Timestamp with time zone",
            "timestamp without time zone",
        ],
    )
    def test_recognizes_temporal_type_names(self, type_name):
        assert is_temporal_field(type_name=type_name)

    @pytest.mark.parametrize(
        "type_name",
        ["String", "Integer", "text", "double precision", "character varying"],
    )
    def test_rejects_non_temporal_type_names(self, type_name):
        assert not is_temporal_field(type_name=type_name)

    @pytest.mark.parametrize(
        "type_name,expected_uri",
        [
            ("Date", "date"),
            ("date", "date"),
            ("timestamp", "datetime"),
            ("timestamptz", "datetime"),
            ("Timestamp with time zone", "datetime"),
            ("DateTime", "datetime"),
        ],
    )
    def test_memory_uri_type_mapping(self, type_name, expected_uri):
        assert temporal_memory_uri_type(type_name=type_name) == expected_uri
