"""
Helpers for recognizing QGIS temporal field types across providers.

PostGIS and other database layers often report ``timestamp``, ``timestamptz``, or
``date`` in :meth:`QgsField.typeName`, whereas memory layers use ``Date`` /
``DateTime``. Import and settings code share these helpers so temporal fields are
detected consistently.
"""

from __future__ import annotations

from typing import Any, Optional, Set

# Lower-case typeName substrings / exact matches for temporal fields.
_TEMPORAL_TYPE_NAME_EXACT = frozenset(
    {"date", "datetime", "time", "timestamp", "timestamptz"}
)
_DATETIME_TYPE_NAME_MARKERS = ("timestamp", "datetime", "timestamptz")


def _temporal_qmeta_type_ids() -> Set[int]:
    """Return Qt meta-type ids that represent date/time values."""
    ids: Set[int] = set()

    try:
        from qgis.PyQt.QtCore import QMetaType

        type_enum = getattr(QMetaType, "Type", None)
        for name in ("QDate", "QTime", "QDateTime"):
            if type_enum is not None and hasattr(type_enum, name):
                ids.add(int(getattr(type_enum, name)))
            elif hasattr(QMetaType, name):
                ids.add(int(getattr(QMetaType, name)))
    except ImportError:
        pass

    try:
        from qgis.PyQt.QtCore import QVariant

        for name in ("Date", "Time", "DateTime"):
            if hasattr(QVariant, name):
                ids.add(int(getattr(QVariant, name)))
    except ImportError:
        pass

    ids.update({14, 15, 16})
    return ids


def _datetime_qmeta_type_ids() -> Set[int]:
    """Return Qt meta-type ids that should map to memory-layer ``datetime`` fields."""
    ids: Set[int] = set()

    try:
        from qgis.PyQt.QtCore import QMetaType

        type_enum = getattr(QMetaType, "Type", None)
        for name in ("QTime", "QDateTime"):
            if type_enum is not None and hasattr(type_enum, name):
                ids.add(int(getattr(type_enum, name)))
            elif hasattr(QMetaType, name):
                ids.add(int(getattr(QMetaType, name)))
    except ImportError:
        pass

    try:
        from qgis.PyQt.QtCore import QVariant

        for name in ("Time", "DateTime"):
            if hasattr(QVariant, name):
                ids.add(int(getattr(QVariant, name)))
    except ImportError:
        pass

    ids.update({15, 16})
    return ids


def is_temporal_field_type_name(type_name: Optional[str]) -> bool:
    """Return True when ``typeName`` describes a date/time field."""
    normalized = (type_name or "").strip().lower()
    if not normalized:
        return False
    if normalized in _TEMPORAL_TYPE_NAME_EXACT:
        return True
    return any(marker in normalized for marker in _DATETIME_TYPE_NAME_MARKERS)


def is_temporal_field_type_id(type_id: Optional[int]) -> bool:
    """Return True when a QGIS field type id represents a date/time value."""
    if type_id is None:
        return False
    try:
        return int(type_id) in _temporal_qmeta_type_ids()
    except (TypeError, ValueError):
        return False


def is_temporal_field(
    *,
    type_name: Optional[str] = None,
    type_id: Optional[int] = None,
) -> bool:
    """Return True when either the type name or type id indicates a temporal field."""
    return is_temporal_field_type_name(type_name) or is_temporal_field_type_id(type_id)


def temporal_memory_uri_type(
    type_name: Optional[str] = None,
    type_id: Optional[int] = None,
) -> str:
    """
    Map a definitive-layer temporal field to a memory-layer URI type.

    Returns ``datetime`` for timestamps and ``date`` for plain dates.
    """
    normalized = (type_name or "").strip().lower()
    if any(marker in normalized for marker in _DATETIME_TYPE_NAME_MARKERS):
        return "datetime"
    if normalized == "time":
        return "datetime"
    if is_temporal_field_type_id(type_id):
        try:
            if int(type_id) in _datetime_qmeta_type_ids():
                return "datetime"
        except (TypeError, ValueError):
            pass
    return "date"


def is_temporal_qgs_field(field: Any) -> bool:
    """Return True for a :class:`QgsField` temporal attribute."""
    type_name = field.typeName() if hasattr(field, "typeName") else None
    type_id = field.type() if hasattr(field, "type") else None
    return is_temporal_field(type_name=type_name, type_id=type_id)


def temporal_memory_uri_type_for_qgs_field(field: Any) -> str:
    """Return the memory-layer URI type for a temporal :class:`QgsField`."""
    type_name = field.typeName() if hasattr(field, "typeName") else None
    type_id = field.type() if hasattr(field, "type") else None
    return temporal_memory_uri_type(type_name=type_name, type_id=type_id)
