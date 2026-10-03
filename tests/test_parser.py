"""Tests for the streaming parsing engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.exceptions import CorruptedJSONError, InvalidExportFormatError, UnsupportedExportVersionError
from src.models import StringListEntry
from src.parser import analyze_relationships, load_followers, load_following, stream_count_engagements


def _write_followers(path: Path, usernames: list[str]) -> None:
    data = [
        {
            "title": "",
            "media_list_data": [],
            "string_list_data": [
                {"href": f"https://instagram.com/{u}", "value": u, "timestamp": 1690000000}
            ],
        }
        for u in usernames
    ]
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_following(path: Path, usernames: list[str]) -> None:
    data = {
        "relationships_following": [
            {
                "title": "",
                "media_list_data": [],
                "string_list_data": [
                    {"href": f"https://instagram.com/{u}", "value": u, "timestamp": 1690000000}
                ],
            }
            for u in usernames
        ]
    }
    path.write_text(json.dumps(data), encoding="utf-8")


class TestAnalyzeRelationships:
    def test_computes_non_followers_and_reciprocity(self, tmp_path: Path) -> None:
        followers_path = tmp_path / "followers_1.json"
        following_path = tmp_path / "following.json"
        _write_followers(followers_path, ["ana", "bruno", "caro"])
        _write_following(following_path, ["ana", "bruno", "diego"])

        result = analyze_relationships(followers_path, following_path)

        assert result.followers_count == 3
        assert result.following_count == 3
        assert result.not_following_back == ["diego"]
        assert result.reciprocity_percentage == pytest.approx(66.67, abs=0.01)

    def test_full_reciprocity_when_everyone_follows_back(self, tmp_path: Path) -> None:
        followers_path = tmp_path / "followers_1.json"
        following_path = tmp_path / "following.json"
        _write_followers(followers_path, ["ana", "bruno"])
        _write_following(following_path, ["ana", "bruno"])

        result = analyze_relationships(followers_path, following_path)

        assert result.not_following_back == []
        assert result.reciprocity_percentage == 100.0


class TestLoadFollowers:
    def test_missing_file_raises_invalid_export_format(self, tmp_path: Path) -> None:
        with pytest.raises(InvalidExportFormatError):
            load_followers(tmp_path / "does_not_exist.json")

    def test_empty_array_raises_unsupported_version(self, tmp_path: Path) -> None:
        path = tmp_path / "followers_1.json"
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(UnsupportedExportVersionError):
            load_followers(path)

    def test_corrupted_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "followers_1.json"
        path.write_text("{not valid json][", encoding="utf-8")
        with pytest.raises(CorruptedJSONError):
            load_followers(path)

    def test_malformed_record_raises_domain_error(self, tmp_path: Path) -> None:
        path = tmp_path / "followers_1.json"
        path.write_text(
            json.dumps([{"title": "", "string_list_data": [{"value": ""}]}]),
            encoding="utf-8",
        )
        with pytest.raises(InvalidExportFormatError, match="invalid relationship record"):
            load_followers(path)


class TestLoadFollowing:
    def test_wrong_top_level_key_raises_unsupported_version(self, tmp_path: Path) -> None:
        path = tmp_path / "following.json"
        path.write_text(json.dumps({"unexpected_key": []}), encoding="utf-8")
        with pytest.raises(UnsupportedExportVersionError):
            load_following(path)


class TestStreamCountEngagements:
    def test_counts_events_and_unique_targets(self, tmp_path: Path) -> None:
        path = tmp_path / "liked_posts.json"
        data = [
            {"title": "ana", "string_list_data": []},
            {"title": "ana", "string_list_data": []},
            {"title": "bruno", "string_list_data": []},
        ]
        path.write_text(json.dumps(data), encoding="utf-8")

        summary = stream_count_engagements(path)

        assert summary.total_events == 3
        assert summary.unique_targets == 2
        assert summary.raw_bytes_processed == path.stat().st_size

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(InvalidExportFormatError):
            stream_count_engagements(tmp_path / "missing.json")

    def test_non_object_record_raises_domain_error(self, tmp_path: Path) -> None:
        path = tmp_path / "liked_posts.json"
        path.write_text(json.dumps([{"title": "ana"}, "bad"]), encoding="utf-8")

        with pytest.raises(InvalidExportFormatError, match="each engagement record"):
            stream_count_engagements(path)


class TestStringListEntryValidation:
    def test_blank_value_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StringListEntry(value="   ")

    def test_valid_entry_parses(self) -> None:
        entry = StringListEntry(value="ana", href="https://instagram.com/ana", timestamp=123)
        assert entry.value == "ana"
