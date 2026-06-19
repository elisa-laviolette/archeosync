# coding=utf-8
"""Tests for ArcheoSync plugin helpers."""

import pytest
from unittest.mock import Mock, patch

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


@pytest.mark.qgis
@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class TestArcheoSyncRunImportData:
    """Import Data menu: summary vs file dialog based on pending temporary layers."""

    def _plugin_with_layer_service(self, layer_service):
        iface = Mock()
        iface.mainWindow.return_value = Mock()

        plugin = ArcheoSyncPlugin.__new__(ArcheoSyncPlugin)
        plugin._iface = iface
        plugin._settings_manager = Mock()
        plugin._file_system_service = Mock()
        plugin._csv_import_service = Mock()
        plugin._field_project_import_service = Mock()
        plugin._layer_service = layer_service
        return plugin

    def test_run_import_data_opens_dialog_when_no_temporary_layers(self):
        """Without pending temp layers, Import Data opens the file selection dialog."""
        layer_service = Mock()
        layer_service.get_layer_by_name.return_value = None

        plugin = self._plugin_with_layer_service(layer_service)
        dialog_instance = Mock()

        with patch("archeo_sync.ImportDataDialog", return_value=dialog_instance) as dialog_cls:
            with patch.object(ArcheoSyncPlugin, "_execute_dialog", return_value=False):
                plugin.run_import_data()

        dialog_cls.assert_called_once()
        for name in (
            "New Objects",
            "New Features",
            "New Small Finds",
            "Imported_CSV_Points",
        ):
            layer_service.get_layer_by_name.assert_any_call(name)

    def test_run_import_data_rebuilds_summary_when_temporary_layers_even_if_dock_exists(self):
        """Pending temp layers always rebuild the summary so detectors and the dock UI stay in sync."""
        layer_service = Mock()
        temp_layer = Mock()
        temp_layer.featureCount.return_value = 3
        layer_service.get_layer_by_name.side_effect = (
            lambda name: temp_layer if name == "New Objects" else None
        )

        summary_dock = Mock()
        summary_dock.__class__.__name__ = "ImportSummaryDockWidget"
        main_window = Mock()
        main_window.findChildren.return_value = [summary_dock]

        plugin = self._plugin_with_layer_service(layer_service)
        plugin._iface.mainWindow.return_value = main_window

        with patch("archeo_sync.ImportDataDialog") as dialog_cls:
            with patch.object(plugin, "_show_import_summary") as show_summary:
                plugin.run_import_data()

        dialog_cls.assert_not_called()
        show_summary.assert_called_once()
        args, _kwargs = show_summary.call_args
        assert args[0]["objects_count"] == 3

    def test_run_import_data_rebuilds_summary_when_temporary_layers_but_no_dock(self):
        """Pending temp layers without a dock trigger a new summary from layer feature counts."""
        layer_service = Mock()
        temp_layer = Mock()
        temp_layer.featureCount.return_value = 3
        layer_service.get_layer_by_name.side_effect = (
            lambda name: temp_layer if name == "New Objects" else None
        )

        main_window = Mock()
        main_window.findChildren.return_value = []

        plugin = self._plugin_with_layer_service(layer_service)
        plugin._iface.mainWindow.return_value = main_window

        with patch("archeo_sync.ImportDataDialog") as dialog_cls:
            with patch.object(plugin, "_show_import_summary") as show_summary:
                plugin.run_import_data()

        dialog_cls.assert_not_called()
        show_summary.assert_called_once()
        args, _kwargs = show_summary.call_args
        assert args[0]["objects_count"] == 3
        assert args[0]["csv_points_count"] == 0


@pytest.mark.unit
class TestArcheoSyncMapThemes:
    """Tests for configured map theme application on the main project."""

    def setup_method(self):
        try:
            from archeo_sync import ArcheoSyncPlugin
            self.plugin_cls = ArcheoSyncPlugin
        except ImportError:
            self.plugin_cls = None

    def _plugin(self):
        plugin = self.plugin_cls.__new__(self.plugin_cls)
        plugin._settings_manager = Mock()
        plugin._map_theme_service = Mock()
        plugin._iface = Mock()
        return plugin

    @pytest.mark.skipif(
        not QGIS_AVAILABLE,
        reason="ArcheoSyncPlugin import requires QGIS",
    )
    def test_apply_configured_map_theme_calls_service(self):
        plugin = self._plugin()
        plugin._settings_manager.get_value.return_value = "Field"

        plugin._apply_configured_map_theme("import_map_theme")

        plugin._map_theme_service.apply_theme_to_current_project.assert_called_once_with(
            "Field",
            plugin._iface,
        )

    @pytest.mark.skipif(
        not QGIS_AVAILABLE,
        reason="ArcheoSyncPlugin import requires QGIS",
    )
    def test_apply_configured_map_theme_skips_when_empty(self):
        plugin = self._plugin()
        plugin._settings_manager.get_value.return_value = ""

        plugin._apply_configured_map_theme("import_map_theme")

        plugin._map_theme_service.apply_theme_to_current_project.assert_not_called()

    @pytest.mark.skipif(
        not QGIS_AVAILABLE,
        reason="ArcheoSyncPlugin import requires QGIS",
    )
    def test_handle_import_data_accepted_applies_import_theme(self):
        plugin = self._plugin()
        dialog = Mock()
        dialog.get_selected_csv_files.return_value = []
        dialog.get_selected_completed_projects.return_value = []

        with patch.object(plugin, "_apply_configured_map_theme") as apply_theme:
            plugin._handle_import_data_accepted(dialog)

        apply_theme.assert_called_once_with("import_map_theme")


@pytest.mark.unit
class TestArcheoSyncImportArchiveScope:
    """Tests for scoping archive operations to the current import session."""

    def setup_method(self):
        try:
            from archeo_sync import ArcheoSyncPlugin
            self.plugin_cls = ArcheoSyncPlugin
        except ImportError:
            self.plugin_cls = None

    def _plugin(self):
        plugin = self.plugin_cls.__new__(self.plugin_cls)
        plugin._settings_manager = Mock()
        plugin._map_theme_service = Mock()
        plugin._iface = Mock()
        plugin._csv_import_service = Mock()
        plugin._field_project_import_service = Mock()
        return plugin

    @pytest.mark.skipif(
        not QGIS_AVAILABLE,
        reason="ArcheoSyncPlugin import requires QGIS",
    )
    def test_handle_import_data_clears_stale_project_archive_when_importing_csv_only(self):
        plugin = self._plugin()
        dialog = Mock()
        dialog.get_selected_csv_files.return_value = ["/data/points.csv"]
        dialog.get_selected_completed_projects.return_value = []

        plugin._process_csv_files = Mock(return_value=12)
        plugin._csv_import_service.get_last_import_stats.return_value = {"csv_duplicates": 0}

        with patch.object(plugin, "_apply_configured_map_theme"), \
             patch.object(plugin, "_show_import_summary") as show_summary:
            plugin._handle_import_data_accepted(dialog)

        plugin._field_project_import_service.clear_last_imported_projects.assert_called_once()
        show_summary.assert_called_once()
        summary_data, kwargs = show_summary.call_args
        assert summary_data[0]["csv_points_count"] == 12
        assert kwargs["archive_csv"] is True
        assert kwargs["archive_projects"] is False

    @pytest.mark.skipif(
        not QGIS_AVAILABLE,
        reason="ArcheoSyncPlugin import requires QGIS",
    )
    def test_handle_import_data_clears_stale_csv_archive_when_importing_projects_only(self):
        plugin = self._plugin()
        dialog = Mock()
        dialog.get_selected_csv_files.return_value = []
        dialog.get_selected_completed_projects.return_value = ["/data/project_a"]

        plugin._process_completed_projects = Mock(
            return_value={"objects_count": 3, "features_count": 0, "small_finds_count": 0}
        )

        with patch.object(plugin, "_apply_configured_map_theme"), \
             patch.object(plugin, "_show_import_summary") as show_summary:
            plugin._handle_import_data_accepted(dialog)

        plugin._csv_import_service.clear_last_imported_files.assert_called_once()
        show_summary.assert_called_once()
        _summary_data, kwargs = show_summary.call_args
        assert kwargs["archive_csv"] is False
        assert kwargs["archive_projects"] is True

    @pytest.mark.skipif(
        not QGIS_AVAILABLE,
        reason="ArcheoSyncPlugin import requires QGIS",
    )
    def test_handle_global_prepare_recording_accepted_applies_global_theme(self):
        plugin = self._plugin()
        dialog = Mock()
        dialog.get_global_project_options.return_value = {}

        with patch.object(plugin, "_apply_configured_map_theme") as apply_theme:
            with patch("qgis.PyQt.QtWidgets.QMessageBox"):
                plugin._handle_global_prepare_recording_accepted(
                    dialog=dialog,
                    destination_folder="/tmp",
                    recording_areas_layer_id="layer1",
                )

        apply_theme.assert_called_once_with("global_preparation_map_theme")
