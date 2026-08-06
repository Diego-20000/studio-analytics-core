"""studio-analytics-core: a streaming, privacy-first engine for analyzing
large personal data exports locally.

Public API surface — everything else in this package is an implementation
detail.
"""

from .exceptions import (
    CorruptedJSONError,
    InvalidExportFormatError,
    StudioAnalyticsError,
    UnsupportedExportVersionError,
)
from .models import EngagementSummary, RelationshipAnalysis, RelationshipEntry, StringListEntry
from .parser import analyze_relationships, load_followers, load_following, stream_count_engagements

__version__ = "0.1.0"

__all__ = [
    "analyze_relationships",
    "load_followers",
    "load_following",
    "stream_count_engagements",
    "RelationshipAnalysis",
    "RelationshipEntry",
    "StringListEntry",
    "EngagementSummary",
    "StudioAnalyticsError",
    "InvalidExportFormatError",
    "CorruptedJSONError",
    "UnsupportedExportVersionError",
]
