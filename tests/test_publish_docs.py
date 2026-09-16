"""Unit tests for the docs publisher (scripts/publish_docs.py).

The shapes checked here are the ones ``mike`` wrote on the ``gh-pages``
branch, because a reader's bookmark into ``latest/`` and the version selector
both depend on them staying the same across the switch to Zensical.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "publish_docs.py"


@pytest.fixture(scope="module")
def publish_docs():
    spec = importlib.util.spec_from_file_location("publish_docs", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_versions_order_newest_first(publish_docs):
    versions = publish_docs.Versions.loads(
        json.dumps(
            [
                {"version": "0.7.0", "title": "0.7.0", "aliases": ["latest"]},
                {"version": "0.10.0", "title": "0.10.0", "aliases": []},
                {"version": "0.9.0", "title": "0.9.0", "aliases": []},
            ]
        )
    )
    assert [entry.version for entry in versions] == ["0.10.0", "0.9.0", "0.7.0"]


def test_adding_a_version_moves_the_alias(publish_docs):
    versions = publish_docs.Versions.loads(
        json.dumps([{"version": "0.7.0", "title": "0.7.0", "aliases": ["latest"]}])
    )
    versions.add("0.8.0", "0.8.0", ["latest"])
    assert json.loads(versions.dumps()) == [
        {"version": "0.8.0", "title": "0.8.0", "aliases": ["latest"]},
        {"version": "0.7.0", "title": "0.7.0", "aliases": []},
    ]


def test_an_alias_cannot_be_a_version(publish_docs):
    versions = publish_docs.Versions.loads(
        json.dumps([{"version": "latest", "title": "latest", "aliases": []}])
    )
    with pytest.raises(publish_docs.PublishError):
        versions.add("0.8.0", "0.8.0", ["latest"])


@pytest.mark.parametrize(
    ("source", "target", "expected"),
    [
        ("latest/index.html", "0.8.0/index.html", "../0.8.0/"),
        (
            "latest/about/author/index.html",
            "0.8.0/about/author/index.html",
            "../../../0.8.0/about/author/",
        ),
        ("latest/404.html", "0.8.0/404.html", "../0.8.0/404.html"),
    ],
)
def test_redirect_href_matches_mike(publish_docs, source, target, expected):
    assert publish_docs.redirect_href(source, target, directory_urls=True) == expected


def test_redirect_href_without_directory_urls(publish_docs):
    assert (
        publish_docs.redirect_href("latest/guide.html", "0.8.0/guide.html", False)
        == "../0.8.0/guide.html"
    )


def test_write_alias_covers_every_page(publish_docs, tmp_path):
    version = tmp_path / "0.8.0"
    (version / "guide").mkdir(parents=True)
    (version / "index.html").write_text("home", encoding="utf-8")
    (version / "guide" / "index.html").write_text("guide", encoding="utf-8")
    (version / "search.json").write_text("[]", encoding="utf-8")

    written = publish_docs.write_alias(tmp_path, "0.8.0", "latest", True)

    assert written == 2
    assert not (tmp_path / "latest" / "search.json").exists()
    page = (tmp_path / "latest" / "guide" / "index.html").read_text(encoding="utf-8")
    assert '<a href="../../0.8.0/guide/">../../0.8.0/guide/</a>' in page
    assert 'content="1; url=../../0.8.0/guide/"' in page
