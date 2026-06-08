"""
CSV Import Service for ArcheoSync plugin.

This module provides functionality for importing CSV files containing point data
into QGIS memory point layers. It handles validation of required columns (X, Y, Z),
column mapping across multiple files, and layer creation.

The temporary layer ``Imported_CSV_Points`` includes a string field ``identifier`` when the CSV
has no column named ``identifier`` (case-insensitive): values come from that column when present,
otherwise from the plugin setting ``csv_topo_identifier_column``, from a single unambiguous text
column per file, or after user selection when several text columns exist.

When the configured definitive topo layer defines a survey date field (auto-detected or
via ``csv_topo_date_field``), ``Imported_CSV_Points`` receives that field with the same
name and QGIS type. The attribute is filled from each CSV basename for rows that do not
already provide a value.

Rows that match an existing definitive topo point on identifier (``PtID``, ``identifier``,
etc.), geometry, and survey day are excluded before the temporary layer is created.

Key Features:
- Validates CSV files have required X, Y, Z columns (case-insensitive)
- Maps columns across multiple CSV files
- Creates point vector layers from CSV data (Point or PointZ depending on configured definitive layer)
- Loads layers into QGIS project as temporary layers
- Copies symbology, form configuration, and project relations from the configured total station points layer
- Handles different column names and data types

Architecture Benefits:
- Single Responsibility: Focuses only on CSV import operations
- Dependency Inversion: Implements ICSVImportService interface
- Testability: All QGIS dependencies can be mocked
- Extensibility: Easy to add new import formats or validation rules

Usage:
    csv_service = CSVImportService(qgis_iface)
    
    # Validate CSV files
    result = csv_service.validate_csv_files(['file1.csv', 'file2.csv'])
    if result.is_valid:
        # Import files
        import_result = csv_service.import_csv_files(['file1.csv', 'file2.csv'])
"""

import csv
import os
from typing import List, Dict, Optional, Any, Set, Tuple, Union

try:
    from .csv_filename_date import parse_date_from_filename
    from .field_type_utils import is_temporal_qgs_field, temporal_memory_uri_type_for_qgs_field
except ImportError:
    from csv_filename_date import parse_date_from_filename
    from field_type_utils import is_temporal_qgs_field, temporal_memory_uri_type_for_qgs_field

try:
    from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY, QgsFields, QgsField, QgsWkbTypes
    from qgis.PyQt.QtCore import QVariant
    from ..core.interfaces import ICSVImportService, ValidationResult
except ImportError:
    # For testing without QGIS
    QgsVectorLayer = None
    QgsFeature = None
    QgsGeometry = None
    QgsPointXY = None
    QgsField = None
    QgsWkbTypes = None
    QVariant = None
    from core.interfaces import ICSVImportService, ValidationResult


class CSVImportService(ICSVImportService):
    """
    Service for importing CSV files into QGIS memory point layers.
    
    This service handles the complete workflow of importing CSV files containing
    point data, including validation, column mapping, and layer creation.
    """
    
    def __init__(
        self,
        qgis_iface: Any,
        file_system_service: Optional[Any] = None,
        settings_manager: Optional[Any] = None,
        layer_service: Optional[Any] = None,
    ):
        """
        Initialize the CSV import service.
        
        Args:
            qgis_iface: QGIS interface object for accessing project and canvas
            file_system_service: Service for file system operations (optional)
            settings_manager: Service for managing settings (optional)
            layer_service: Service for layer operations such as style copying (optional)
        """
        self._iface = qgis_iface
        self._file_system_service = file_system_service
        self._settings_manager = settings_manager
        self._layer_service = layer_service
        self._required_columns = ['X', 'Y', 'Z']
        # Canonical link field on Imported_CSV_Points (must match definitive topo layer / QGIS relations)
        self._identifier_field_name = 'identifier'

    _QGIS_TYPE_TO_URI = {
        "Date": "date",
        "DateTime": "datetime",
        "date": "date",
        "datetime": "datetime",
        "timestamp": "datetime",
        "timestamptz": "datetime",
    }

    def _has_identifier_column_key(self, column_mapping: Dict[str, List[Optional[str]]]) -> bool:
        """True if the mapping already includes a column whose name is ``identifier`` (case-insensitive)."""
        return any(k.strip().upper() == 'IDENTIFIER' for k in column_mapping.keys())

    def _max_string_columns_per_file(
        self,
        column_mapping: Dict[str, List[Optional[str]]],
        field_types: Dict[str, str],
        num_files: int,
    ) -> int:
        """Maximum count of non-required string columns present on a single CSV file."""
        max_n = 0
        for fi in range(num_files):
            n = 0
            for key in column_mapping:
                if key in self._required_columns:
                    continue
                col_list = column_mapping[key]
                if fi >= len(col_list) or not col_list[fi]:
                    continue
                if field_types.get(key, 'string') != 'string':
                    continue
                n += 1
            max_n = max(max_n, n)
        return max_n

    def _is_valid_saved_identifier_key(
        self,
        saved: str,
        column_mapping: Dict[str, List[Optional[str]]],
        num_files: int,
    ) -> bool:
        """True if ``saved`` is a mapping key present in every CSV file (non-null column ref)."""
        if not saved or not isinstance(saved, str):
            return False
        if saved not in column_mapping or saved in self._required_columns:
            return False
        cols = column_mapping[saved]
        for fi in range(num_files):
            if fi >= len(cols) or not cols[fi]:
                return False
        return True

    def _identifier_choice_candidates(
        self,
        column_mapping: Dict[str, List[Optional[str]]],
        num_files: int,
    ) -> List[str]:
        """Non-required mapping keys that appear in at least one file (for user selection)."""
        keys: List[str] = []
        for key in column_mapping:
            if key in self._required_columns:
                continue
            col_list = column_mapping[key]
            lim = min(num_files, len(col_list))
            if any(col_list[fi] for fi in range(lim)):
                keys.append(key)
        return sorted(keys)

    def _resolve_effective_identifier_source_key(
        self,
        column_mapping: Dict[str, List[Optional[str]]],
        num_files: int,
        has_identifier_column: bool,
        identifier_source_column_key: Optional[str],
    ) -> Optional[str]:
        """
        Mapping key used to populate the memory ``identifier`` field when there is no CSV
        ``identifier`` column. None means auto (single string column per file).
        """
        if has_identifier_column:
            return None
        if identifier_source_column_key and self._is_valid_saved_identifier_key(
            identifier_source_column_key.strip(), column_mapping, num_files
        ):
            return identifier_source_column_key.strip()
        if self._settings_manager:
            saved = (self._settings_manager.get_value('csv_topo_identifier_column', '') or '').strip()
            if saved and self._is_valid_saved_identifier_key(saved, column_mapping, num_files):
                return saved
        return None

    def check_csv_identifier_column_requirement(
        self,
        csv_files: List[str],
        column_mapping: Dict[str, List[Optional[str]]],
    ) -> ValidationResult:
        """
        Preflight for topo CSV import: see ``ICSVImportService.check_csv_identifier_column_requirement``.
        """
        field_types = self._detect_field_types(csv_files, column_mapping)
        has_id = self._has_identifier_column_key(column_mapping)
        if has_id:
            return ValidationResult(True, '')
        num_files = len(csv_files)
        max_strings = self._max_string_columns_per_file(column_mapping, field_types, num_files)
        if max_strings <= 1:
            return ValidationResult(True, '')
        effective = self._resolve_effective_identifier_source_key(
            column_mapping, num_files, has_id, None
        )
        if effective:
            return ValidationResult(True, '')
        candidates = self._identifier_choice_candidates(column_mapping, num_files)
        return ValidationResult(
            False,
            "Several text columns are present without an `identifier` column. "
            "Choose which column should populate the point identifier, or set it in plugin settings.",
            code='CSV_IDENTIFIER_AMBIGUOUS',
            extras={'candidates': candidates},
        )

    def _identifier_attribute_value_for_row(
        self,
        column_mapping: Dict[str, List[Optional[str]]],
        field_types: Dict[str, str],
        file_index: int,
        row: Dict[str, str],
        *,
        has_identifier_column: bool,
        configured_source_key: Optional[str],
    ) -> Optional[str]:
        """Value for the ``identifier`` field on the memory layer for this row (or None)."""

        def _normalize_cell(value: Any) -> Optional[str]:
            if value is None:
                return None
            s = str(value).strip()
            return s if s else None

        if has_identifier_column:
            for key in column_mapping:
                if key.strip().upper() != 'IDENTIFIER':
                    continue
                col = column_mapping[key][file_index]
                if col and col in row:
                    return _normalize_cell(row[col])
            return None

        if configured_source_key:
            col_list = column_mapping.get(configured_source_key)
            if not col_list or file_index >= len(col_list):
                return None
            col = col_list[file_index]
            if col and col in row:
                return _normalize_cell(row[col])
            return None

        for key in column_mapping:
            if key in self._required_columns:
                continue
            col_list = column_mapping[key]
            if file_index >= len(col_list):
                continue
            col = col_list[file_index]
            if not col or col not in row:
                continue
            if field_types.get(key, 'string') != 'string':
                continue
            return _normalize_cell(row[col])
        return None

    def _apply_definitive_layer_style(self, temp_layer: Any) -> None:
        """
        Apply symbology, forms, and relations from the definitive topo layer.

        Uses a schema-safe path: CSV temp layers are built from CSV headers and must not
        receive the definitive layer's full QML/form configuration (that can crash QGIS).

        Args:
            temp_layer: Temporary ``Imported_CSV_Points`` layer to configure
        """
        if not self._layer_service:
            return
        source_layer = self._get_configured_total_station_points_layer()
        if not source_layer or not temp_layer:
            return
        self._layer_service.configure_temporary_topo_csv_layer(source_layer, temp_layer)

    def _get_configured_total_station_points_layer(self):
        """
        Return the configured definitive total station points layer when available.

        The ``total_station_points_layer`` setting stores a layer ID. If the setting is
        missing, invalid, or the layer no longer exists in the project, returns ``None``.
        """
        if not self._settings_manager:
            return None
        try:
            layer_id = self._settings_manager.get_value('total_station_points_layer', '')
            if not isinstance(layer_id, str) or not layer_id.strip():
                return None
            from qgis.core import QgsProject
            return QgsProject.instance().mapLayer(layer_id.strip())
        except Exception:
            return None

    def _should_use_pointz_geometry(self) -> bool:
        """
        Decide temporary topo geometry mode from configured definitive points layer.

        Returns ``True`` when the configured definitive layer is 3D (PointZ / has Z),
        otherwise ``False`` for 2D Point layers. Falls back to ``True`` when the
        definitive layer cannot be determined.
        """
        definitive_layer = self._get_configured_total_station_points_layer()
        if definitive_layer is None:
            return True
        try:
            return bool(QgsWkbTypes.hasZ(definitive_layer.wkbType()))
        except Exception:
            return True

    def _build_point_geometry(self, x: float, y: float, z: float, *, use_pointz: bool):
        """
        Build point geometry for temporary topo layer.

        When ``use_pointz`` is True, geometry is built as ``POINT Z`` and preserves
        CSV altitude in geometry. Otherwise geometry is built as 2D ``Point`` and
        altitude is carried only by the ``Z`` attribute field.
        """
        if not use_pointz:
            point = QgsPointXY(x, y)
            return QgsGeometry.fromPointXY(point)
        try:
            return QgsGeometry.fromWkt(f"POINT Z ({x} {y} {z})")
        except Exception:
            # Defensive fallback for mocked/non-standard runtimes.
            point = QgsPointXY(x, y)
            return QgsGeometry.fromPointXY(point)

    def _qgis_field_uri_type(self, field: Any) -> str:
        """Map a definitive layer field type to a memory-layer URI type."""
        if is_temporal_qgs_field(field):
            return temporal_memory_uri_type_for_qgs_field(field)
        type_name = field.typeName() if hasattr(field, "typeName") else ""
        return self._QGIS_TYPE_TO_URI.get(type_name, "string")

    def _find_definitive_layer_field(self, field_name: str) -> Optional[Any]:
        """Return the field definition from the configured definitive topo layer."""
        definitive_layer = self._get_configured_total_station_points_layer()
        if definitive_layer is None or not field_name:
            return None
        try:
            for field in definitive_layer.fields():
                if field.name().lower() == field_name.strip().lower():
                    return field
        except Exception:
            return None
        return None

    def _resolve_topo_date_field_info(
        self,
        column_mapping: Dict[str, List[Optional[str]]],
        csv_files: List[str],
    ) -> Optional[Dict[str, str]]:
        """
        Resolve the survey date field to create on ``Imported_CSV_Points``.

        Uses ``csv_topo_date_field`` when configured, otherwise the first ``Date`` or
        ``DateTime`` field on the definitive topo layer, then a field named ``date``.

        Returns:
            Dict with ``name`` (exact definitive field name) and ``uri_type`` (``date`` or
            ``datetime``), or ``None`` when no suitable field exists.
        """
        definitive_layer = self._get_configured_total_station_points_layer()
        if definitive_layer is None:
            return None

        configured_name = ""
        if self._settings_manager:
            configured_name = (
                self._settings_manager.get_value("csv_topo_date_field", "") or ""
            ).strip()

        if configured_name:
            field = self._find_definitive_layer_field(configured_name)
            if field is None:
                return None
            return {"name": field.name(), "uri_type": self._qgis_field_uri_type(field)}

        try:
            for field in definitive_layer.fields():
                if is_temporal_qgs_field(field):
                    return {
                        "name": field.name(),
                        "uri_type": temporal_memory_uri_type_for_qgs_field(field),
                    }

            for field in definitive_layer.fields():
                if field.name().lower() == "date":
                    return {
                        "name": field.name(),
                        "uri_type": temporal_memory_uri_type_for_qgs_field(field),
                    }
        except Exception:
            return None

        return None

    @staticmethod
    def _column_mapping_has_field(
        column_mapping: Dict[str, List[Optional[str]]],
        field_name: str,
    ) -> bool:
        """True when the unified column mapping already includes ``field_name``."""
        target = field_name.strip().lower()
        return any(key.strip().lower() == target for key in column_mapping.keys())

    @staticmethod
    def _is_empty_attribute_value(value: Any) -> bool:
        """Return True when a CSV cell should be treated as missing for date injection."""
        if value is None:
            return True
        try:
            if hasattr(value, "isNull") and callable(value.isNull) and value.isNull():
                return True
        except Exception:
            pass
        if isinstance(value, str):
            stripped = value.strip()
            return stripped == "" or stripped.lower() == "null"
        return False

    def _survey_date_attribute_value(self, iso_date: Optional[str], uri_type: str) -> Any:
        """Convert an ISO date string to a QGIS attribute value."""
        if not iso_date:
            return None
        try:
            from qgis.PyQt.QtCore import QDate, QDateTime

            qdate = QDate.fromString(iso_date, "yyyy-MM-dd")
            if not qdate.isValid():
                return iso_date
            if uri_type == "datetime":
                return QDateTime(qdate)
            return qdate
        except ImportError:
            return iso_date

    def _field_is_text_like(self, field: Any) -> bool:
        """Return True when a QgsField holds textual identifier values."""
        try:
            if field.type() == QVariant.String:
                return True
        except Exception:
            pass
        type_name = (field.typeName() or "").strip().lower()
        return type_name in (
            "string",
            "str",
            "text",
            "varchar",
            "character varying",
            "char",
        )

    def _get_field_index_case_insensitive(self, layer: Any, field_name: str) -> int:
        """Return a field index, matching field names case-insensitively when needed."""
        if not layer or not field_name:
            return -1
        try:
            field_idx = layer.fields().indexOf(field_name)
            if field_idx >= 0:
                return field_idx
            target = field_name.lower()
            for field in layer.fields():
                if field.name().lower() == target:
                    return layer.fields().indexOf(field.name())
        except Exception:
            return -1
        return -1

    def _guess_topo_identifier_field(self, layer: Any) -> Optional[str]:
        """
        Guess the topo point identifier field on a layer (``PtID``, ``identifier``, etc.).
        """
        if layer is None:
            return None
        try:
            id_candidates = []
            for field in layer.fields():
                field_name = field.name().lower()
                if "id" in field_name and self._field_is_text_like(field):
                    id_candidates.append(field.name())

            if id_candidates:
                return id_candidates[0]

            for field in layer.fields():
                field_name = field.name().lower()
                if self._field_is_text_like(field) and (
                    field_name in ("identifier", "identifiant", "code", "name", "nom")
                    or field_name.endswith("_id")
                    or field_name.endswith("_code")
                ):
                    return field.name()
        except Exception:
            return None
        return None

    def _normalize_topo_identifier_value(self, value: Any) -> Optional[str]:
        """Normalize topo point identifiers for duplicate comparison."""
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized.lower() if normalized else None

    def _normalize_point_geometry_key(self, geometry: Any) -> Optional[str]:
        """Build a stable geometry key for point duplicate comparison."""
        if geometry is None:
            return None
        try:
            if geometry.isEmpty():
                return None
        except Exception:
            return None

        try:
            if geometry.isMultipart():
                points = geometry.asMultiPoint()
                if not points:
                    return None
                point = points[0]
            else:
                point = geometry.asPoint()

            x = round(float(point.x()), 4)
            y = round(float(point.y()), 4)
            try:
                z = round(float(point.z()), 4)
                return f"{x}:{y}:{z}"
            except Exception:
                return f"{x}:{y}"
        except Exception:
            try:
                return geometry.asWkt()
            except Exception:
                return None

    def _normalize_survey_date_key(self, value: Any) -> Optional[str]:
        """Normalize survey dates to ``yyyy-MM-dd`` for duplicate comparison."""
        if self._is_empty_attribute_value(value):
            return None
        try:
            from qgis.PyQt.QtCore import QDate, QDateTime

            if isinstance(value, QDateTime):
                qdate = value.date()
                return qdate.toString("yyyy-MM-dd") if qdate.isValid() else None
            if isinstance(value, QDate):
                return value.toString("yyyy-MM-dd") if value.isValid() else None
        except ImportError:
            pass
        except Exception:
            pass

        text = str(value).strip()
        if not text:
            return None
        if len(text) >= 10 and text[4] == "-" and text[7] == "-":
            return text[:10]
        try:
            from qgis.PyQt.QtCore import QDate

            for fmt in ("yyyy-MM-dd", "dd/MM/yyyy", "yyyy/MM/dd", "dd-MM-yyyy"):
                qdate = QDate.fromString(text, fmt)
                if qdate.isValid():
                    return qdate.toString("yyyy-MM-dd")
        except ImportError:
            pass
        except Exception:
            pass
        return text

    def _build_topo_duplicate_key(
        self,
        identifier_value: Any,
        geometry: Any,
        date_key: Optional[str],
        *,
        require_date: bool,
    ) -> Optional[Union[Tuple[str, str, str], Tuple[str, str]]]:
        """
        Build a duplicate lookup key from identifier, point geometry, and optional survey day.
        """
        normalized_identifier = self._normalize_topo_identifier_value(identifier_value)
        geometry_key = self._normalize_point_geometry_key(geometry)
        if not normalized_identifier or not geometry_key:
            return None
        if require_date:
            if not date_key:
                return None
            return (normalized_identifier, geometry_key, date_key)
        return (normalized_identifier, geometry_key)

    def _resolve_row_survey_date_key(
        self,
        row: Dict[str, str],
        file_index: int,
        column_mapping: Dict[str, List[Optional[str]]],
        file_survey_date: Optional[str],
        date_field_name: Optional[str],
    ) -> Optional[str]:
        """Resolve the survey date key for a CSV row before features are created."""
        if not date_field_name:
            return None

        target = date_field_name.strip().lower()
        for column_name, column_list in column_mapping.items():
            if column_name.strip().lower() != target:
                continue
            if file_index >= len(column_list):
                continue
            col_name = column_list[file_index]
            if col_name and col_name in row and not self._is_empty_attribute_value(row[col_name]):
                return self._normalize_survey_date_key(row[col_name])

        if file_survey_date:
            return self._normalize_survey_date_key(file_survey_date)
        return None

    def _collect_topo_duplicate_keys_from_layer(
        self,
        layer: Any,
        identifier_field: str,
        date_field_name: Optional[str],
        *,
        require_date: bool,
    ) -> Set[Union[Tuple[str, str, str], Tuple[str, str]]]:
        """Collect duplicate lookup keys from an existing topo points layer."""
        keys: Set[Union[Tuple[str, str, str], Tuple[str, str]]] = set()
        if layer is None or not identifier_field:
            return keys

        identifier_idx = self._get_field_index_case_insensitive(layer, identifier_field)
        if identifier_idx < 0:
            return keys

        date_idx = (
            self._get_field_index_case_insensitive(layer, date_field_name)
            if date_field_name
            else -1
        )

        try:
            for feature in layer.getFeatures():
                identifier_value = feature.attribute(identifier_idx)
                date_key = None
                if require_date and date_idx >= 0:
                    date_key = self._normalize_survey_date_key(feature.attribute(date_idx))
                duplicate_key = self._build_topo_duplicate_key(
                    identifier_value,
                    feature.geometry(),
                    date_key,
                    require_date=require_date,
                )
                if duplicate_key is not None:
                    keys.add(duplicate_key)
        except Exception:
            return keys

        return keys

    def _apply_filename_date_to_feature(
        self,
        feature: Any,
        date_field_name: str,
        iso_date: Optional[str],
        layer_field_names: set,
        uri_type: str = "date",
    ) -> None:
        """Set the survey date from the CSV filename when the attribute is still empty."""
        if not iso_date or date_field_name not in layer_field_names:
            return
        try:
            current = feature.attribute(date_field_name)
        except Exception:
            current = None
        if not self._is_empty_attribute_value(current):
            return
        feature.setAttribute(
            date_field_name,
            self._survey_date_attribute_value(iso_date, uri_type),
        )

    def validate_csv_files(self, csv_files: List[str]) -> ValidationResult:
        """
        Validate that all CSV files have required X, Y, Z columns.
        
        Args:
            csv_files: List of CSV file paths to validate
            
        Returns:
            ValidationResult indicating if files are valid and any error messages
        """
        if not csv_files:
            return ValidationResult(False, "No CSV files provided")
        
        for csv_file in csv_files:
            # Check if file exists
            if not os.path.exists(csv_file):
                return ValidationResult(False, f"File not found: {csv_file}")
            
            # Check if file is readable
            if not os.access(csv_file, os.R_OK):
                return ValidationResult(False, f"File not readable: {csv_file}")
            
            # Read CSV headers
            try:
                with open(csv_file, 'r', newline='', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    headers = next(reader, None)
                    
                    if not headers:
                        return ValidationResult(False, f"Empty CSV file: {csv_file}")
                    
                    # Convert headers to uppercase for case-insensitive comparison
                    header_upper = [h.upper() for h in headers]
                    
                    # Check for required columns
                    for required_col in self._required_columns:
                        if required_col.upper() not in header_upper:
                            return ValidationResult(False, f"Missing required column: {required_col}")
                            
            except Exception as e:
                return ValidationResult(False, f"Error reading CSV file {csv_file}: {str(e)}")
        
        return ValidationResult(True, "All CSV files have required X, Y, Z columns")
    
    def get_column_mapping(self, csv_files: List[str]) -> Dict[str, List[Optional[str]]]:
        """
        Get column mapping across multiple CSV files.
        
        Args:
            csv_files: List of CSV file paths to analyze
            
        Returns:
            Dictionary mapping unified column names to lists of column names from each file
        """
        if not csv_files:
            return {}
        
        # Read headers from all files
        all_headers = []
        for csv_file in csv_files:
            try:
                with open(csv_file, 'r', newline='', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    headers = next(reader, None)
                    if headers:
                        all_headers.append(headers)
            except Exception:
                # Skip files that can't be read
                all_headers.append([])
        
        if not all_headers:
            return {}
        
        # Create mapping based on column names (case-insensitive)
        column_mapping = {}
        
        # Start with required columns
        for required_col in self._required_columns:
            column_mapping[required_col] = []
            for headers in all_headers:
                # Find matching column (case-insensitive)
                matching_col = None
                for header in headers:
                    if header.upper() == required_col.upper():
                        matching_col = header
                        break
                column_mapping[required_col].append(matching_col)
        
        # Add all other columns (case-insensitive)
        all_unique_columns = set()
        for headers in all_headers:
            for header in headers:
                if header.upper() not in [col.upper() for col in self._required_columns]:
                    all_unique_columns.add(header.upper())
        
        for column_upper in sorted(all_unique_columns):
            # Find the first occurrence of this column (case-insensitive) to use as the key
            column_key = None
            for headers in all_headers:
                for header in headers:
                    if header.upper() == column_upper:
                        column_key = header
                        break
                if column_key:
                    break
            
            if column_key:
                column_mapping[column_key] = []
                for headers in all_headers:
                    # Find matching column (case-insensitive)
                    matching_col = None
                    for header in headers:
                        if header.upper() == column_upper:
                            matching_col = header
                            break
                    column_mapping[column_key].append(matching_col)
        
        return column_mapping
    
    def get_column_mapping_and_headers(self, csv_files: List[str]):
        """
        Get column mapping and all headers across multiple CSV files.
        Returns (column_mapping, all_headers)
        """
        if not csv_files:
            return {}, []
        all_headers = []
        for csv_file in csv_files:
            try:
                with open(csv_file, 'r', newline='', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    headers = next(reader, None)
                    if headers:
                        all_headers.append(headers)
            except Exception:
                all_headers.append([])
        if not all_headers:
            return {}, all_headers
        column_mapping = {}
        for required_col in self._required_columns:
            column_mapping[required_col] = []
            for headers in all_headers:
                matching_col = None
                for header in headers:
                    if header.upper() == required_col.upper():
                        matching_col = header
                        break
                column_mapping[required_col].append(matching_col)
        all_unique_columns = set()
        for headers in all_headers:
            for header in headers:
                if header.upper() not in [col.upper() for col in self._required_columns]:
                    all_unique_columns.add(header.upper())
        for column_upper in sorted(all_unique_columns):
            column_key = None
            for headers in all_headers:
                for header in headers:
                    if header.upper() == column_upper:
                        column_key = header
                        break
                if column_key:
                    break
            if column_key:
                column_mapping[column_key] = []
                for headers in all_headers:
                    matching_col = None
                    for header in headers:
                        if header.upper() == column_upper:
                            matching_col = header
                            break
                    column_mapping[column_key].append(matching_col)
        return column_mapping, all_headers
    
    def _detect_field_types(self, csv_files: List[str], column_mapping: Dict[str, List[Optional[str]]]) -> Dict[str, str]:
        """
        Detect appropriate field types for each column based on CSV data.
        
        Args:
            csv_files: List of CSV file paths
            column_mapping: Column mapping dictionary
            
        Returns:
            Dictionary mapping column names to QGIS field types
        """
        field_types = {}
        
        # Sample data from each CSV file to determine types
        for column_name, column_list in column_mapping.items():
            if column_name in self._required_columns:
                # X, Y, Z are always numeric
                field_types[column_name] = "real"
                continue
                
            # Sample values from all files for this column
            sample_values = []
            for file_index, csv_file in enumerate(csv_files):
                col_name = column_list[file_index]
                if not col_name:
                    continue
                    
                try:
                    with open(csv_file, 'r', newline='', encoding='utf-8') as file:
                        reader = csv.DictReader(file)
                        # Sample first 10 rows
                        for i, row in enumerate(reader):
                            if i >= 10:
                                break
                            if col_name in row:
                                sample_values.append(row[col_name])
                except Exception:
                    continue
            
            # Determine type based on sample values
            if not sample_values:
                field_types[column_name] = "string"  # Default to string
                continue
                
            # Check if all values can be converted to integers
            all_integers = True
            all_reals = True
            non_empty_values = 0
            
            for value in sample_values:
                if not value or value.strip() == '':
                    continue
                
                non_empty_values += 1
                    
                # Try integer conversion
                try:
                    int(value)
                except (ValueError, TypeError):
                    all_integers = False
                
                # Try real conversion
                try:
                    float(value)
                except (ValueError, TypeError):
                    all_reals = False
                    break
            
            # Determine field type
            if non_empty_values == 0:
                # All values are empty, default to string
                field_types[column_name] = "string"
            elif all_integers:
                field_types[column_name] = "integer"
            elif all_reals:
                field_types[column_name] = "real"
            else:
                field_types[column_name] = "string"
        
        return field_types

    def import_csv_files(
        self,
        csv_files: List[str],
        column_mapping: Optional[Dict[str, List[Optional[str]]]] = None,
        identifier_source_column_key: Optional[str] = None,
    ) -> ValidationResult:
        """
        Import CSV files into a temporary point vector layer and add to QGIS project.

        The memory layer always exposes a string field ``identifier`` when the CSV has no column
        named ``identifier`` (case-insensitive): values come from the configured mapping key
        (plugin setting ``csv_topo_identifier_column`` or ``identifier_source_column_key``), or
        from the sole text column per file when unambiguous.

        Args:
            csv_files: List of CSV file paths to import
            column_mapping: Optional column mapping (if None, will be generated automatically)
            identifier_source_column_key: Optional mapping key for this import (overrides settings)

        Returns:
            ValidationResult indicating if import was successful or any error messages
        """
        # Validate CSV files first
        validation_result = self.validate_csv_files(csv_files)
        if not validation_result.is_valid:
            return validation_result

        # Generate column mapping if not provided
        if column_mapping is None:
            column_mapping = self.get_column_mapping(csv_files)

        try:
            field_types = self._detect_field_types(csv_files, column_mapping)
            has_id = self._has_identifier_column_key(column_mapping)
            num_files = len(csv_files)
            max_strings = self._max_string_columns_per_file(column_mapping, field_types, num_files)
            effective_key = self._resolve_effective_identifier_source_key(
                column_mapping, num_files, has_id, identifier_source_column_key
            )
            if not has_id and max_strings > 1 and effective_key is None:
                candidates = self._identifier_choice_candidates(column_mapping, num_files)
                return ValidationResult(
                    False,
                    "Could not resolve which CSV column should populate the point identifier.",
                    code='CSV_IDENTIFIER_AMBIGUOUS',
                    extras={'candidates': candidates},
                )

            layer_name = "Imported_CSV_Points"
            use_pointz_geometry = self._should_use_pointz_geometry()

            from qgis.core import QgsProject
            project_crs = QgsProject.instance().crs()
            project_crs_string = self._get_crs_string(project_crs)
            geometry_prefix = "PointZ" if use_pointz_geometry else "Point"
            layer_uri = f"{geometry_prefix}?crs={project_crs_string}"

            for column_name in column_mapping.keys():
                if column_name in self._required_columns:
                    layer_uri += f"&field={column_name.lower()}:real"
                else:
                    field_type = field_types.get(column_name, "string")
                    layer_uri += f"&field={column_name.lower()}:{field_type}"

            if not has_id:
                layer_uri += f"&field={self._identifier_field_name}:string"

            import_date_field_info = self._resolve_topo_date_field_info(column_mapping, csv_files)
            if import_date_field_info and not self._column_mapping_has_field(
                column_mapping, import_date_field_info["name"]
            ):
                layer_uri += (
                    f"&field={import_date_field_info['name']}:"
                    f"{import_date_field_info['uri_type']}"
                )

            layer = QgsVectorLayer(layer_uri, layer_name, "memory")

            if not layer.isValid():
                return ValidationResult(False, "Failed to create vector layer")

            layer_field_names = {f.name() for f in layer.fields()}

            import_date_field_name = (
                import_date_field_info["name"] if import_date_field_info else None
            )
            require_survey_date = import_date_field_info is not None
            definitive_layer = self._get_configured_total_station_points_layer()
            existing_topo_duplicate_keys: Set[
                Union[Tuple[str, str, str], Tuple[str, str]]
            ] = set()
            imported_topo_duplicate_keys: Set[
                Union[Tuple[str, str, str], Tuple[str, str]]
            ] = set()
            if definitive_layer is not None:
                identifier_field = self._guess_topo_identifier_field(definitive_layer)
                if identifier_field:
                    existing_topo_duplicate_keys = self._collect_topo_duplicate_keys_from_layer(
                        definitive_layer,
                        identifier_field,
                        import_date_field_name,
                        require_date=require_survey_date,
                    )

            layer.startEditing()

            feature_id = 1
            duplicates_count = 0
            for file_index, csv_file in enumerate(csv_files):
                file_survey_date = parse_date_from_filename(csv_file)
                try:
                    with open(csv_file, 'r', newline='', encoding='utf-8') as file:
                        reader = csv.DictReader(file)

                        for row in reader:
                            feature = QgsFeature(layer.fields())
                            feature.setId(feature_id)

                            x_col = column_mapping['X'][file_index]
                            y_col = column_mapping['Y'][file_index]
                            z_col = column_mapping['Z'][file_index]

                            try:
                                x = float(row[x_col])
                                y = float(row[y_col])
                                z = float(row[z_col])

                                geometry = self._build_point_geometry(
                                    x, y, z, use_pointz=use_pointz_geometry
                                )

                                identifier_value = self._identifier_attribute_value_for_row(
                                    column_mapping,
                                    field_types,
                                    file_index,
                                    row,
                                    has_identifier_column=has_id,
                                    configured_source_key=effective_key,
                                )
                                survey_date_key = self._resolve_row_survey_date_key(
                                    row,
                                    file_index,
                                    column_mapping,
                                    file_survey_date,
                                    import_date_field_name,
                                )
                                duplicate_key = self._build_topo_duplicate_key(
                                    identifier_value,
                                    geometry,
                                    survey_date_key,
                                    require_date=require_survey_date,
                                )
                                if duplicate_key is not None and (
                                    duplicate_key in existing_topo_duplicate_keys
                                    or duplicate_key in imported_topo_duplicate_keys
                                ):
                                    duplicates_count += 1
                                    continue
                                if duplicate_key is not None:
                                    imported_topo_duplicate_keys.add(duplicate_key)

                                feature.setGeometry(geometry)

                                for column_name, column_list in column_mapping.items():
                                    col_name = column_list[file_index]
                                    if col_name and col_name in row:
                                        field_name = column_name.lower()
                                        if field_name in layer_field_names:
                                            value = row[col_name]
                                            field_type = field_types.get(column_name, "string")

                                            if field_type == "integer" and value:
                                                try:
                                                    feature.setAttribute(field_name, int(value))
                                                except (ValueError, TypeError):
                                                    feature.setAttribute(field_name, value)
                                            elif field_type == "real" and value:
                                                try:
                                                    feature.setAttribute(field_name, float(value))
                                                except (ValueError, TypeError):
                                                    feature.setAttribute(field_name, value)
                                            else:
                                                feature.setAttribute(field_name, value)

                                if not has_id and self._identifier_field_name in layer_field_names:
                                    id_val = self._identifier_attribute_value_for_row(
                                        column_mapping,
                                        field_types,
                                        file_index,
                                        row,
                                        has_identifier_column=False,
                                        configured_source_key=effective_key,
                                    )
                                    feature.setAttribute(self._identifier_field_name, id_val)

                                if import_date_field_info:
                                    self._apply_filename_date_to_feature(
                                        feature,
                                        import_date_field_info["name"],
                                        file_survey_date,
                                        layer_field_names,
                                        import_date_field_info["uri_type"],
                                    )

                                layer.addFeature(feature)
                                feature_id += 1

                            except (ValueError, KeyError):
                                continue

                except Exception as e:
                    return ValidationResult(False, f"Error processing CSV file {csv_file}: {str(e)}")

            layer.commitChanges()

            QgsProject.instance().addMapLayer(layer)
            self._apply_definitive_layer_style(layer)

            self._last_imported_files = csv_files
            self._last_import_count = feature_id - 1
            self._last_import_stats = {
                "csv_duplicates": duplicates_count,
            }

            return ValidationResult(
                True,
                f"Successfully imported {feature_id - 1} points from {len(csv_files)} CSV file(s)",
            )

        except Exception as e:
            return ValidationResult(False, f"Error during import: {str(e)}")
    
    def get_last_import_count(self) -> int:
        """
        Get the number of features imported in the last import operation.
        
        Returns:
            Number of features imported, or 0 if no import has been performed
        """
        return getattr(self, '_last_import_count', 0)

    def get_last_import_stats(self) -> Dict[str, int]:
        """
        Get import statistics from the last CSV import operation.

        Returns:
            Dictionary containing ``csv_duplicates`` and related counters.
        """
        return getattr(self, "_last_import_stats", {})
    
    def get_last_imported_files(self) -> List[str]:
        """
        Get the list of files imported in the last import operation.
        
        Returns:
            List of imported file paths, or empty list if no import has been performed
        """
        return getattr(self, '_last_imported_files', [])
    
    def archive_last_imported_files(self) -> None:
        """
        Archive the files from the last import operation.
        This method should be called after validation is complete.
        """
        imported_files = self.get_last_imported_files()
        if imported_files:
            self._archive_csv_files(imported_files)
            # Clear the stored files after archiving
            self._last_imported_files = []
    
    def _archive_csv_files(self, csv_files: List[str]) -> None:
        """
        Move imported CSV files to the archive folder.
        
        Args:
            csv_files: List of CSV file paths to archive
        """
        try:
            # Get archive folder from settings
            archive_folder = self._settings_manager.get_value('csv_archive_folder', '')
            if not archive_folder:
                return  # No archive folder configured
            
            # Create archive folder if it doesn't exist
            if not self._file_system_service.path_exists(archive_folder):
                if not self._file_system_service.create_directory(archive_folder):
                    print(f"Warning: Could not create CSV archive folder: {archive_folder}")
                    return
            
            # Move each CSV file to archive
            for csv_file in csv_files:
                if self._file_system_service.path_exists(csv_file):
                    filename = os.path.basename(csv_file)
                    archive_path = os.path.join(archive_folder, filename)
                    
                    if self._file_system_service.move_file(csv_file, archive_path):
                        print(f"Archived CSV file: {filename}")
                    else:
                        print(f"Warning: Could not archive CSV file: {filename}")
                        
        except Exception as e:
            print(f"Error archiving CSV files: {str(e)}")

    def _get_crs_string(self, crs):
        """Get CRS string representation, handling custom CRS properly."""
        try:
            # Try to get authid first
            authid = crs.authid()
            if authid and authid != '':
                return authid
            
            # For custom CRS, use WKT
            wkt = crs.toWkt()
            if wkt and wkt != '':
                return wkt
            
            # Fallback to proj4 string
            proj4 = crs.toProj4()
            if proj4 and proj4 != '':
                return proj4
            
            # Last resort - use EPSG:4326
            print("Warning: Could not determine CRS, using EPSG:4326 as fallback")
            return "EPSG:4326"
        except Exception as e:
            print(f"Error getting CRS string: {str(e)}, using EPSG:4326 as fallback")
            return "EPSG:4326" 