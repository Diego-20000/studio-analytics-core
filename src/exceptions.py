"""Custom exception hierarchy for the parsing engine.

Every exception a caller can catch is rooted at StudioAnalyticsError, so
consumers of this package can choose to catch broadly (StudioAnalyticsError)
or narrowly (a specific subtype) without ever needing to catch bare
`Exception` and risk swallowing unrelated bugs.
"""

from __future__ import annotations


class StudioAnalyticsError(Exception):
    """Base class for all errors raised by this package."""


class InvalidExportFormatError(StudioAnalyticsError):
    """Raised when a JSON file does not match the expected export schema.

    Typically means a required top-level key is missing or a field has
    the wrong type — e.g. a relationships file that isn't a list, or a
    list entry missing `string_list_data`.
    """

    def __init__(self, source: str, reason: str) -> None:
        self.source = source
        self.reason = reason
        super().__init__(f"{source}: invalid export format ({reason})")


class CorruptedJSONError(StudioAnalyticsError):
    """Raised when a file cannot be parsed as JSON at all (truncated,
    binary garbage, wrong encoding, etc.)."""

    def __init__(self, source: str, original: Exception) -> None:
        self.source = source
        self.original = original
        super().__init__(f"{source}: not valid JSON ({original})")


class UnsupportedExportVersionError(StudioAnalyticsError):
    """Raised when the export's shape suggests a schema version this
    parser was never validated against, rather than guessing and
    silently producing wrong numbers."""

    def __init__(self, source: str, detail: str) -> None:
        self.source = source
        self.detail = detail
        super().__init__(f"{source}: unsupported export version ({detail})")
