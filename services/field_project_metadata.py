"""
Field project metadata helpers for ArcheoSync.

Stores lightweight JSON metadata alongside generated field projects to distinguish
global projects from per-recording-area projects during import.
"""

import json
import os
from typing import Any, Dict, Optional

METADATA_FILENAME = "archeosync_project.json"
PROJECT_KIND_GLOBAL = "global"
PROJECT_KIND_RECORDING_AREA = "recording_area"


def metadata_path(project_dir: str) -> str:
    """Return the absolute path to the metadata file inside a project directory."""
    return os.path.join(project_dir, METADATA_FILENAME)


IMPORT_LAYER_TYPES = (
    "objects",
    "features",
    "small_finds",
    "alternative_objects",
)


def write_project_metadata(
    project_dir: str,
    project_kind: str,
    extent_wkt: str,
    crs: str,
    import_layers: Optional[Dict[str, str]] = None,
) -> bool:
    """
    Write archeosync_project.json into the field project directory.

    Args:
        project_dir: Directory containing the generated .qgs project
        project_kind: ``global`` or ``recording_area``
        extent_wkt: WKT geometry describing the project extent (may be empty for zone projects)
        crs: CRS auth id string for the field project
        import_layers: Optional map of import keys (``objects``, ``features``, …) to the
            source layer display names used for exported ``.gpkg`` filenames

    Returns:
        True if the file was written successfully
    """
    try:
        payload = {
            "project_kind": project_kind,
            "extent_wkt": extent_wkt or "",
            "crs": crs or "",
        }
        if import_layers:
            payload["import_layers"] = {
                key: value
                for key, value in import_layers.items()
                if key in IMPORT_LAYER_TYPES and isinstance(value, str) and value
            }
        path = metadata_path(project_dir)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return True
    except OSError as exc:
        print(f"Error writing field project metadata: {exc}")
        return False


def read_project_metadata(project_dir: str) -> Optional[Dict[str, Any]]:
    """Load metadata from a field project directory, or None if missing/invalid."""
    path = metadata_path(project_dir)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error reading field project metadata: {exc}")
        return None


def get_project_kind(project_dir: str) -> str:
    """
    Return the project kind for a field project directory.

    Defaults to ``recording_area`` when metadata is absent (legacy projects).
    """
    metadata = read_project_metadata(project_dir)
    if not metadata:
        return PROJECT_KIND_RECORDING_AREA
    kind = metadata.get("project_kind")
    if kind in (PROJECT_KIND_GLOBAL, PROJECT_KIND_RECORDING_AREA):
        return kind
    return PROJECT_KIND_RECORDING_AREA


def is_global_project(project_dir: str) -> bool:
    """Return True when the directory contains metadata for a global field project."""
    return get_project_kind(project_dir) == PROJECT_KIND_GLOBAL


def get_import_layer_names(project_dir: str) -> Dict[str, str]:
    """
    Return layer display names recorded when the field project was created.

    These names match the original QGIS project layer names used for ``.gpkg`` exports.
    """
    metadata = read_project_metadata(project_dir)
    if not metadata:
        return {}
    layers = metadata.get("import_layers")
    if not isinstance(layers, dict):
        return {}
    return {
        key: value
        for key, value in layers.items()
        if key in IMPORT_LAYER_TYPES and isinstance(value, str) and value
    }
