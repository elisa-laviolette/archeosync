# coding=utf-8
"""Tests for map theme service."""

import pytest
from unittest.mock import Mock, patch, MagicMock

try:
    from services.map_theme_service import QGISMapThemeService
    SERVICE_AVAILABLE = True
except ImportError:
    SERVICE_AVAILABLE = False


@pytest.mark.unit
@pytest.mark.skipif(not SERVICE_AVAILABLE, reason="map_theme_service not available")
class TestQGISMapThemeService:
    """Unit tests for QGISMapThemeService."""

    def setup_method(self):
        self.service = QGISMapThemeService()

    def test_list_map_themes_returns_theme_names(self):
        """list_map_themes should return names from the project collection."""
        project = Mock()
        collection = Mock()
        collection.mapThemes.return_value = ["Field", "Office"]
        project.mapThemeCollection.return_value = collection

        assert self.service.list_map_themes(project) == ["Field", "Office"]
        collection.mapThemes.assert_called_once()

    def test_apply_theme_to_current_project_noop_when_empty(self):
        """Empty theme name should not call applyTheme."""
        iface = Mock()
        with patch("services.map_theme_service.QgsProject") as mock_project_cls:
            self.service.apply_theme_to_current_project("", iface)
            mock_project_cls.instance.assert_not_called()
        iface.layerTreeView.assert_not_called()

    def test_apply_theme_to_current_project_warns_when_theme_missing(self):
        """Unknown theme name should log a warning and skip applyTheme."""
        iface = Mock()
        collection = Mock()
        collection.hasMapTheme.return_value = False
        project = Mock()
        project.mapThemeCollection.return_value = collection

        with patch("services.map_theme_service.QgsProject") as mock_project_cls:
            mock_project_cls.instance.return_value = project
            with patch("builtins.print") as mock_print:
                self.service.apply_theme_to_current_project("Missing", iface)

        collection.hasMapTheme.assert_called_once_with("Missing")
        collection.applyTheme.assert_not_called()
        mock_print.assert_called()
        iface.layerTreeView.assert_not_called()

    def test_apply_theme_to_current_project_applies_existing_theme(self):
        """Existing theme should be applied via mapThemeCollection.applyTheme."""
        iface = Mock()
        layer_tree_view = Mock()
        model = Mock()
        root = Mock()
        layer_tree_view.layerTreeModel.return_value = model
        layer_tree_view.model.return_value.rootGroup.return_value = root
        iface.layerTreeView.return_value = layer_tree_view

        collection = Mock()
        collection.hasMapTheme.return_value = True
        project = Mock()
        project.mapThemeCollection.return_value = collection
        project.layerTreeRoot.return_value = root

        with patch("services.map_theme_service.QgsProject") as mock_project_cls:
            mock_project_cls.instance.return_value = project
            self.service.apply_theme_to_current_project("Field", iface)

        collection.applyTheme.assert_called_once_with("Field", root, model)
