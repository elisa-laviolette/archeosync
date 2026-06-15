"""
Map theme service for ArcheoSync plugin.

Applies QGIS map themes (QgsMapThemeCollection) to the current main project
at workflow entry points configured in plugin settings.
"""

from typing import List, Any

from qgis.core import QgsProject

try:
    from ..core.interfaces import IMapThemeService
except ImportError:
    from core.interfaces import IMapThemeService


class QGISMapThemeService(IMapThemeService):
    """QGIS implementation for listing and applying map themes."""

    def list_map_themes(self, project: Any) -> List[str]:
        """Return map theme names defined in the given project."""
        if project is None:
            return []
        collection = project.mapThemeCollection()
        if collection is None:
            return []
        return list(collection.mapThemes())

    def apply_theme_to_current_project(self, theme_name: str, iface: Any) -> None:
        """
        Apply a named map theme to the current QgsProject.

        Args:
            theme_name: Name of the map theme, or empty string to skip.
            iface: QGIS interface (used for layer tree model).
        """
        if not theme_name or not str(theme_name).strip():
            return

        theme_name = str(theme_name).strip()
        project = QgsProject.instance()
        collection = project.mapThemeCollection()

        if not collection.hasMapTheme(theme_name):
            print(f"Warning: map theme '{theme_name}' is not defined in the current project.")
            return

        layer_tree_view = iface.layerTreeView()
        model = layer_tree_view.layerTreeModel()
        root = project.layerTreeRoot()
        collection.applyTheme(theme_name, root, model)
