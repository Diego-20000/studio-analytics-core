"""Typed data contracts for Instagram's official personal data export.

Instagram ships relationship data (followers, following) as JSON files
shaped like:

    [
      {
        "title": "",
        "media_list_data": [],
        "string_list_data": [
          {"href": "https://instagram.com/handle", "value": "handle", "timestamp": 1690000000}
        ]
      },
      ...
    ]

These models exist to validate that shape at the boundary — once data
passes through them, downstream code can trust it instead of re-checking
for missing keys everywhere.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class StringListEntry(BaseModel):
    """A single identity record inside `string_list_data`."""

    value: str
    href: str | None = None
    timestamp: int | None = None

    @field_validator("value")
    @classmethod
    def value_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("value must not be blank")
        return v


class RelationshipEntry(BaseModel):
    """One row of a followers/following export — normally corresponds to
    exactly one Instagram account."""

    title: str = ""
    string_list_data: list[StringListEntry] = Field(default_factory=list)

    @property
    def username(self) -> str | None:
        """The first identity value, which is what Instagram's export
        uses to carry the actual @handle. Absent for malformed rows."""
        return self.string_list_data[0].value if self.string_list_data else None


class RelationshipAnalysis(BaseModel):
    """Aggregate result of comparing a followers export against a
    following export."""

    followers_count: int
    following_count: int
    not_following_back: list[str]
    reciprocity_percentage: float

    @classmethod
    def compute(cls, followers: set[str], following: set[str]) -> "RelationshipAnalysis":
        not_following_back = sorted(following - followers)
        reciprocity = (
            100.0 * len(following & followers) / len(following) if following else 0.0
        )
        return cls(
            followers_count=len(followers),
            following_count=len(following),
            not_following_back=not_following_back,
            reciprocity_percentage=round(reciprocity, 2),
        )


class EngagementSummary(BaseModel):
    """Result of a streaming pass over a large engagement export (e.g.
    liked_posts.json), which can be tens of megabytes and must never be
    fully materialized in memory — see parser.stream_count_engagements."""

    total_events: int
    unique_targets: int
    raw_bytes_processed: int = Field(
        description="Bytes read from the source stream; useful for throughput logging."
    )


def coerce_relationship_list(raw: Any, source: str) -> list[RelationshipEntry]:
    """Validate a raw decoded JSON value as a list of RelationshipEntry.

    Centralized so both the followers and following loaders share one
    error path instead of duplicating pydantic's ValidationError handling.
    """
    from pydantic import TypeAdapter

    from .exceptions import InvalidExportFormatError

    if not isinstance(raw, list):
        raise InvalidExportFormatError(source, f"expected a JSON array, got {type(raw).__name__}")

    adapter = TypeAdapter(list[RelationshipEntry])
    try:
        return adapter.validate_python(raw)
    except Exception as exc:  # pydantic.ValidationError
        raise InvalidExportFormatError(source, str(exc)) from exc
