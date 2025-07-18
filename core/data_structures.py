"""
Data structures for the ArcheoSync plugin.
"""
from dataclasses import dataclass
from typing import List, Optional, Union


@dataclass
class WarningData:
    """Data structure for warning information with filtering details."""
    message: str
    recording_area_name: str
    layer_name: str
    filter_expression: str
    # Additional fields for specific warning types
    object_number: Optional[int] = None
    skipped_numbers: Optional[List[int]] = None
    # Fields for between-layer warnings
    second_layer_name: Optional[str] = None
    second_filter_expression: Optional[str] = None
    # Fields for out-of-bounds warnings
    out_of_bounds_features: Optional[List[dict]] = None
    # Fields for distance warnings
    distance_issues: Optional[List[dict]] = None
    # Fields for missing total station warnings
    missing_total_station_issues: Optional[List[dict]] = None
    # Fields for height difference warnings
    height_difference_issues: Optional[List[dict]] = None


@dataclass
class ImportSummaryData:
    """Data class containing import summary statistics."""
    csv_points_count: int = 0
    features_count: int = 0
    objects_count: int = 0
    small_finds_count: int = 0
    csv_duplicates: int = 0
    features_duplicates: int = 0
    objects_duplicates: int = 0
    small_finds_duplicates: int = 0
    duplicate_objects_warnings: List[Union[str, WarningData]] = None
    skipped_numbers_warnings: List[Union[str, WarningData]] = None
    out_of_bounds_warnings: List[Union[str, WarningData]] = None
    distance_warnings: List[Union[str, WarningData]] = None
    missing_total_station_warnings: List[Union[str, WarningData]] = None
    duplicate_total_station_identifiers_warnings: List[Union[str, WarningData]] = None
    height_difference_warnings: List[Union[str, WarningData]] = None
    
    def __post_init__(self):
        """Initialize default values for mutable fields."""
        if self.duplicate_objects_warnings is None:
            self.duplicate_objects_warnings = []
        if self.skipped_numbers_warnings is None:
            self.skipped_numbers_warnings = []
        if self.out_of_bounds_warnings is None:
            self.out_of_bounds_warnings = []
        if self.distance_warnings is None:
            self.distance_warnings = []
        if self.missing_total_station_warnings is None:
            self.missing_total_station_warnings = []
        if self.duplicate_total_station_identifiers_warnings is None:
            self.duplicate_total_station_identifiers_warnings = []
        if self.height_difference_warnings is None:
            self.height_difference_warnings = [] 