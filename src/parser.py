"""Streaming analysis engine for Instagram data exports.

The core design constraint: Instagram's export can contain files tens of
megabytes large (a multi-year `liked_posts.json` easily exceeds 80 MB).
Loading a file like that with `json.load()` materializes the entire
Python object graph in memory before you can inspect a single record.
On a memory-constrained device that is the difference between "instant
analysis" and an out-of-memory crash.

Every function below reads its input with `ijson`, which parses JSON
incrementally and yields records as they're found. Memory use scales
with the *aggregate being built* (a set of usernames, a running count),
not with the size of the file on disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import ijson

from .exceptions import CorruptedJSONError, InvalidExportFormatError, UnsupportedExportVersionError
from .models import EngagementSummary, RelationshipAnalysis

# Instagram's export nests `following.json` under this key, but ships
# `followers_1.json` as a bare top-level array. Two prefixes, one engine.
FOLLOWERS_RECORD_PATH = "item"
FOLLOWING_RECORD_PATH = "relationships_following.item"


def _stream_usernames(path: Path, record_path: str) -> Iterator[str]:
    """Yield each account's username from a relationships export,
    without ever holding the full parsed structure in memory."""
    if not path.exists():
        raise InvalidExportFormatError(str(path), "file does not exist")

    try:
        with path.open("rb") as fh:
            for entry in ijson.items(fh, record_path):
                string_list_data = entry.get("string_list_data") or []
                if not string_list_data or "value" not in string_list_data[0]:
                    continue
                yield string_list_data[0]["value"]
    except ijson.JSONError as exc:
        raise CorruptedJSONError(str(path), exc) from exc


def load_followers(path: Path) -> set[str]:
    """Load `followers_1.json` into a set of usernames."""
    usernames = set(_stream_usernames(path, FOLLOWERS_RECORD_PATH))
    if not usernames:
        raise UnsupportedExportVersionError(
            str(path), "no records found under top-level array — export shape may have changed"
        )
    return usernames


def load_following(path: Path) -> set[str]:
    """Load `following.json` into a set of usernames."""
    usernames = set(_stream_usernames(path, FOLLOWING_RECORD_PATH))
    if not usernames:
        raise UnsupportedExportVersionError(
            str(path), "no records found under 'relationships_following' — export shape may have changed"
        )
    return usernames


def analyze_relationships(followers_path: Path, following_path: Path) -> RelationshipAnalysis:
    """Compare a followers export against a following export and compute
    who doesn't follow back plus the overall reciprocity percentage.

    This is the entire "who unfollowed me" feature: two streamed sets and
    a set difference. No data ever leaves this process — both files are
    read from local disk and the result is returned in memory.
    """
    followers = load_followers(followers_path)
    following = load_following(following_path)
    return RelationshipAnalysis.compute(followers, following)


def stream_count_engagements(path: Path, record_path: str = "item") -> EngagementSummary:
    """Stream a large, flat engagement export (e.g. `liked_posts.json`)
    and summarize it without materializing the full list.

    Each record is expected to expose its target account the same way
    Instagram's export does: a `title` field naming the account the
    engagement was made on. Records without one are counted but not
    attributed to a target.
    """
    if not path.exists():
        raise InvalidExportFormatError(str(path), "file does not exist")

    total_events = 0
    targets: set[str] = set()

    try:
        with path.open("rb") as fh:
            for entry in ijson.items(fh, record_path):
                total_events += 1
                title = entry.get("title")
                if title:
                    targets.add(title)
    except ijson.JSONError as exc:
        raise CorruptedJSONError(str(path), exc) from exc

    return EngagementSummary(
        total_events=total_events,
        unique_targets=len(targets),
        raw_bytes_processed=path.stat().st_size,
    )
