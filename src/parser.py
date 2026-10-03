"""Streaming analysis engine for Instagram data exports.

The parser reads the export incrementally so memory use follows the result
being built rather than the size of the JSON file. Each relationship record
is validated at the point where it enters the application.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, BinaryIO

import ijson
from pydantic import ValidationError

from .exceptions import CorruptedJSONError, InvalidExportFormatError, UnsupportedExportVersionError
from .models import EngagementSummary, RelationshipAnalysis, RelationshipEntry

FOLLOWERS_RECORD_PATH = "item"
FOLLOWING_RECORD_PATH = "relationships_following.item"


class _CountingReader:
    """Small binary reader adapter that records bytes actually consumed."""

    def __init__(self, fh: BinaryIO) -> None:
        self._fh = fh
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        data = self._fh.read(size)
        self.bytes_read += len(data)
        return data

    def __getattr__(self, name: str):
        return getattr(self._fh, name)


def _stream_usernames(path: Path, record_path: str) -> Iterator[str]:
    if not path.exists():
        raise InvalidExportFormatError(str(path), "file does not exist")

    try:
        with path.open("rb") as raw_fh:
            fh = _CountingReader(raw_fh)
            for raw_entry in ijson.items(fh, record_path):
                try:
                    entry = RelationshipEntry.model_validate(raw_entry)
                except ValidationError as exc:
                    raise InvalidExportFormatError(
                        str(path), f"invalid relationship record: {exc.errors()[0]['msg']}"
                    ) from exc

                username = entry.username
                if username is not None:
                    yield username
    except ijson.JSONError as exc:
        raise CorruptedJSONError(str(path), exc) from exc


def load_followers(path: Path) -> set[str]:
    usernames = set(_stream_usernames(path, FOLLOWERS_RECORD_PATH))
    if not usernames:
        raise UnsupportedExportVersionError(
            str(path), "no records found under the expected followers structure"
        )
    return usernames


def load_following(path: Path) -> set[str]:
    usernames = set(_stream_usernames(path, FOLLOWING_RECORD_PATH))
    if not usernames:
        raise UnsupportedExportVersionError(
            str(path), "no records found under the expected following structure"
        )
    return usernames


def analyze_relationships(followers_path: Path, following_path: Path) -> RelationshipAnalysis:
    followers = load_followers(followers_path)
    following = load_following(following_path)
    return RelationshipAnalysis.compute(followers, following)


def stream_count_engagements(path: Path, record_path: str = "item") -> EngagementSummary:
    if not path.exists():
        raise InvalidExportFormatError(str(path), "file does not exist")

    total_events = 0
    targets: set[str] = set()

    try:
        with path.open("rb") as raw_fh:
            fh = _CountingReader(raw_fh)
            for entry in ijson.items(fh, record_path):
                if not isinstance(entry, dict):
                    raise InvalidExportFormatError(
                        str(path), f"expected each engagement record to be an object, got {type(entry).__name__}"
                    )
                total_events += 1
                title = entry.get("title")
                if isinstance(title, str) and title.strip():
                    targets.add(title.strip())
            bytes_read = fh.bytes_read
    except ijson.JSONError as exc:
        raise CorruptedJSONError(str(path), exc) from exc

    return EngagementSummary(
        total_events=total_events,
        unique_targets=len(targets),
        raw_bytes_processed=bytes_read,
    )
