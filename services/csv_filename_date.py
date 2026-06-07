"""
Parse survey dates embedded in topo CSV filenames.

Topo CSV files are often named after the survey day (for example ``07062025.csv`` or
``points_2025-06-07.csv``). This module extracts a calendar date from the filename stem
and returns it in ISO ``YYYY-MM-DD`` form for QGIS date fields.
"""

from __future__ import annotations

import os
import re
from datetime import date
from typing import Iterable, Optional, Tuple

# (regex, group order: 'ymd' or 'dmy', year digit count)
_FILENAME_DATE_PATTERNS: Tuple[Tuple[re.Pattern[str], str, int], ...] = (
    (re.compile(r"(?<!\d)(\d{4})[-_/\.](\d{2})[-_/\.](\d{2})(?!\d)"), "ymd", 4),
    (re.compile(r"(?<!\d)(\d{2})[-_/\.](\d{2})[-_/\.](\d{4})(?!\d)"), "dmy", 4),
    (re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)"), "ymd", 4),
    (re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)"), "dmy", 4),
    (re.compile(r"(?<!\d)(\d{2})[-_/\.](\d{2})[-_/\.](\d{2})(?!\d)"), "dmy", 2),
    (re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)"), "dmy", 2),
)


def _expand_year(year: str, year_digits: int) -> str:
    """Normalize a year component to four digits (``26`` -> ``2026``)."""
    if year_digits == 2:
        return str(2000 + int(year))
    return year


def _to_iso_date(year: str, month: str, day: str) -> Optional[str]:
    """Return ISO date string when the components form a valid calendar date."""
    try:
        parsed = date(int(year), int(month), int(day))
    except (TypeError, ValueError):
        return None
    return parsed.isoformat()


def _groups_to_iso(groups: Iterable[str], order: str, year_digits: int) -> Optional[str]:
    """Convert regex capture groups to an ISO date string."""
    y, m, d = groups
    if order == "dmy":
        d, m, y = groups
    return _to_iso_date(_expand_year(y, year_digits), m, d)


def parse_date_from_filename(filename: str) -> Optional[str]:
    """
    Extract a survey date from a CSV filename.

    Supported patterns include ``YYYY-MM-DD``, ``YYYYMMDD``, ``DDMMYYYY``, ``DDMMYY``,
    ``DD-MM-YY``, and the same layouts with ``/``, ``_``, or ``.`` separators.
    Two-digit years are expanded as ``2000 + YY`` (for example ``26`` -> ``2026``).
    Compact ``DDMMYY`` segments may appear inside alphanumeric names (for example
    ``PINC150725`` -> 15 July 2025). When several candidates appear in the stem,
    the leftmost valid date wins.

    Args:
        filename: File path or basename (with or without ``.csv`` extension).

    Returns:
        ISO date string ``YYYY-MM-DD``, or ``None`` when no valid date is found.
    """
    stem = os.path.splitext(os.path.basename(filename))[0]
    if not stem:
        return None

    for pattern, order, year_digits in _FILENAME_DATE_PATTERNS:
        for match in pattern.finditer(stem):
            iso = _groups_to_iso(match.groups(), order, year_digits)
            if iso:
                return iso
    return None
