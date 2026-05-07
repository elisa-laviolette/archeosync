# coding=utf-8
"""Tests for ArcheoSync plugin helpers."""

import pytest
from unittest.mock import Mock

try:
    from archeo_sync import ArcheoSyncPlugin
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False


@pytest.mark.qgis
@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class TestArcheoSyncRecordingAreaVariable:
    """Tests for recording area variable source resolution."""

    def setup_method(self):
        self.plugin = ArcheoSyncPlugin.__new__(ArcheoSyncPlugin)

    def test_resolve_recording_area_variable_value_uses_feature_id(self):
        """Selecting source=id should use feature id."""
        feature = Mock()
        feature.attribute.return_value = "ignored"

        result = self.plugin._resolve_recording_area_variable_value(
            source="id",
            feature=feature,
            feature_id=42,
            display_name="Display Name"
        )

        assert result == "42"

    def test_resolve_recording_area_variable_value_uses_custom_field(self):
        """Selecting source=field:<name> should use that field value."""
        feature = Mock()
        feature.attribute.return_value = "RA-001"

        result = self.plugin._resolve_recording_area_variable_value(
            source="field:code",
            feature=feature,
            feature_id=42,
            display_name="Display Name"
        )

        feature.attribute.assert_called_once_with("code")
        assert result == "RA-001"

    def test_resolve_recording_area_variable_value_falls_back_to_display(self):
        """Unknown source should fallback to display name."""
        feature = Mock()

        result = self.plugin._resolve_recording_area_variable_value(
            source="display",
            feature=feature,
            feature_id=42,
            display_name="Display Name"
        )

        assert result == "Display Name"
