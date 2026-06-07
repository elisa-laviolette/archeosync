"""
Tests for parsing survey dates from topo CSV filenames.
"""

import importlib.util
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = importlib.util.spec_from_file_location(
    "csv_filename_date",
    os.path.join(_ROOT, "services", "csv_filename_date.py"),
)
_csv_filename_date = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _csv_filename_date
_SPEC.loader.exec_module(_csv_filename_date)
parse_date_from_filename = _csv_filename_date.parse_date_from_filename


class TestParseDateFromFilename:
    """Unit tests for filename date extraction."""

    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("2025-06-07.csv", "2025-06-07"),
            ("points_2025-06-07.csv", "2025-06-07"),
            ("07062025.csv", "2025-06-07"),
            ("T1_07062025.csv", "2025-06-07"),
            ("survey_20250607.csv", "2025-06-07"),
            ("pts-07-06-2025.csv", "2025-06-07"),
            ("pts_07.06.2025.csv", "2025-06-07"),
            ("07_06_2025.csv", "2025-06-07"),
            ("070626.csv", "2026-06-07"),
            ("T1_070626.csv", "2026-06-07"),
            ("pts-07-06-26.csv", "2026-06-07"),
            ("pts_07.06.26.csv", "2026-06-07"),
            ("PINC150725.csv", "2025-07-15"),
        ],
    )
    def test_parse_supported_formats(self, filename, expected):
        assert parse_date_from_filename(filename) == expected

    @pytest.mark.parametrize(
        "filename",
        [
            "test1.csv",
            "points.csv",
            "no_date_here.csv",
        ],
    )
    def test_parse_returns_none_when_no_date(self, filename):
        assert parse_date_from_filename(filename) is None

    def test_parse_ignores_invalid_dates(self):
        assert parse_date_from_filename("32042025.csv") is None
        assert parse_date_from_filename("00000000.csv") is None
