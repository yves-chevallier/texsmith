from __future__ import annotations

import pytest

from texsmith.core.metadata import PressMetadataError, normalise_press_metadata


def test_normalise_press_metadata_copies_common_fields() -> None:
    metadata = {"title": "  Root Title  ", "subtitle": "Subtitle ", "date": "2024-07-01"}

    press = normalise_press_metadata(metadata)

    assert press["title"] == "Root Title"
    assert press["subtitle"] == "Subtitle"
    assert press["date"] == "2024-07-01"


def test_normalise_press_metadata_prefers_press_values() -> None:
    metadata = {
        "title": "Root Title",
        "press": {
            "title": "Press Title",
            "subtitle": "Press Subtitle",
            "date": "2024-01-01",
        },
    }

    with pytest.warns(UserWarning, match=r"Overriding press\.title"):
        press = normalise_press_metadata(metadata)

    assert press["title"] == "Root Title"
    assert press["subtitle"] == "Press Subtitle"
    assert press["date"] == "2024-01-01"
    assert metadata["title"] == "Root Title"
    assert metadata["subtitle"] == "Press Subtitle"
    assert metadata["date"] == "2024-01-01"


def test_normalise_press_metadata_accepts_author_formats() -> None:
    metadata = {
        "author": "Ada Lovelace",
        "authors": [
            "Grace Hopper",
            {"name": "Edsger Dijkstra", "affiliation": "TU Delft"},
        ],
    }

    press = normalise_press_metadata(metadata)

    assert len(press["authors"]) == 3
    names = {entry["name"] for entry in press["authors"]}
    assert {"Ada Lovelace", "Grace Hopper", "Edsger Dijkstra"} == names
    assert any(entry["affiliation"] == "TU Delft" for entry in press["authors"])


def test_normalise_press_metadata_deduplicates_authors() -> None:
    metadata = {
        "author": "Ada Lovelace",
        "press": {
            "authors": [{"name": "Ada Lovelace", "affiliation": None}],
            "author": "Ada Lovelace",
        },
    }

    press = normalise_press_metadata(metadata)

    assert press.get("author") is None
    assert metadata.get("author") is None
    assert press["authors"] == [{"name": "Ada Lovelace", "affiliation": None}]


def test_normalise_press_metadata_flattens_nested_aliases() -> None:
    metadata = {
        "press": {
            "snippet": {"width": "10cm"},
            "glossary": {"style": "long"},
            "cover": {"color": "teal"},
        }
    }

    press = normalise_press_metadata(metadata)

    assert press["width"] == "10cm"
    assert press["glossary_style"] == "long"
    assert press["covercolor"] == "teal"
    assert metadata["width"] == "10cm"
    assert metadata["glossary_style"] == "long"
    assert metadata["covercolor"] == "teal"


def test_normalise_press_metadata_rejects_invalid_author_payload() -> None:
    metadata = {"authors": [{}]}

    try:
        normalise_press_metadata(metadata)
    except PressMetadataError:
        return
    raise AssertionError("Expected PressMetadataError for invalid author payload.")
