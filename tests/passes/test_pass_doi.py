"""The ``doi`` pass: pending DOIs fetched, cached, written to a ``.bib`` and re-keyed."""

from __future__ import annotations

from pathlib import Path

import pytest
from tmark.ir import model
from tmark.ir.walk import walk
import yaml

from texsmith.core.bibliography.doi import DoiLookupError
from texsmith.passes.doi import doi_of_key


SMITH = "@article{Smith_2020, title={Aged cheese}, author={Smith, Ann}, year={2020}}\n"
WADHWANI = (
    "@article{Wadhwani_2011, title={Mozzarella}, author={Wadhwani, R.}, year={2011}, "
    "doi={10.3168/jds.2010-3952}}\n"
)


class FakeFetcher:
    """``fetch(doi)`` from a table; anything else is a lookup error."""

    def __init__(self, table: dict[str, str]) -> None:
        self.table = table
        self.calls: list[str] = []

    def fetch(self, value: str) -> str:
        self.calls.append(value)
        try:
            return self.table[value]
        except KeyError:
            raise DoiLookupError(f"offline: {value}") from None


def _keys(document) -> list[str]:
    assert document.ir is not None
    return [
        item.key for node in walk(document.ir) if isinstance(node, model.Ref) for item in node.items
    ]


def test_doi_of_key() -> None:
    assert doi_of_key("doi:10.1000/xyz") == "10.1000/xyz"
    assert doi_of_key("DOI: 10.1000/xyz") == "10.1000/xyz"
    assert doi_of_key("10.1000/xyz") == "10.1000/xyz"
    assert doi_of_key("smith2020") is None
    assert doi_of_key("doi:") is None


def test_pending_dois_are_fetched_written_and_rekeyed(harness, tmp_path: Path) -> None:
    document = harness.load("doi", "refs")
    fetcher = FakeFetcher({"10.1000/xyz": SMITH, "https://doi.org/10.3168/jds.2010-3952": WADHWANI})
    ctx = harness.context(document, output_dir=tmp_path, doi_fetcher=fetcher)
    out = harness.run("doi", document, ctx)

    assert out is not document
    assert _keys(document) == [
        "doi:10.1000/xyz",
        "WAD",
        "doi:10.3168/jds.2010-3952",
        "doi:10.5555/broken",
        "manual",
    ]
    # A citation takes the fetched key, or the front-matter key declaring the same DOI;
    # a DOI that cannot be fetched stays as written.
    assert _keys(out) == ["Smith_2020", "WAD", "WAD", "doi:10.5555/broken", "manual"]
    # Each DOI is fetched once, the front-matter spelling first.
    assert fetcher.calls == [
        "https://doi.org/10.3168/jds.2010-3952",
        "10.1000/xyz",
        "10.5555/broken",
    ]

    bib = tmp_path / "inline-doi-refs.bib"
    assert ctx.bibliography == [bib]
    text = bib.read_text("utf-8")
    assert "@article{WAD," in text and "Wadhwani" in text
    assert "@article{Smith_2020," in text
    assert "manual" not in text  # a manual entry is not a DOI

    # The output-dir cache is written for the next run.
    cache = yaml.safe_load((tmp_path / "texsmith-doi-cache.yaml").read_text("utf-8"))
    assert set(cache["entries"]) == {"10.1000/xyz", "10.3168/jds.2010-3952"}

    assert harness.diagnostics(ctx) == harness.expected_diagnostics("doi", "refs")
    assert harness.structural(out) == harness.expected("doi", "refs")

    # The Ref nodes keep their identity (span rule 1).
    before = [node for node in walk(document.ir) if isinstance(node, model.Ref)]
    after = [node for node in walk(out.ir) if isinstance(node, model.Ref)]
    assert [(n.id, n.span) for n in before] == [(n.id, n.span) for n in after]


def test_cache_is_honoured_offline(harness, tmp_path: Path) -> None:
    (tmp_path / "texsmith-doi-cache.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "entries": {
                    "10.1000/xyz": SMITH,
                    "10.3168/jds.2010-3952": WADHWANI,
                    "10.5555/broken": "@misc{Broken_1999, title={Cached}}",
                },
            }
        ),
        "utf-8",
    )
    document = harness.load("doi", "refs")
    fetcher = FakeFetcher({})
    ctx = harness.context(document, output_dir=tmp_path, doi_fetcher=fetcher)
    out = harness.run("doi", document, ctx)
    assert fetcher.calls == []
    assert _keys(out) == ["Smith_2020", "WAD", "WAD", "Broken_1999", "manual"]
    assert len(ctx.diagnostics) == 0


def test_unparsable_payload_is_reported(harness, tmp_path: Path) -> None:
    document = harness.load("doi", "refs")
    fetcher = FakeFetcher(
        {
            "10.1000/xyz": "this is not bibtex",
            "https://doi.org/10.3168/jds.2010-3952": WADHWANI,
        }
    )
    ctx = harness.context(document, output_dir=tmp_path, doi_fetcher=fetcher)
    out = harness.run("doi", document, ctx)
    assert _keys(out)[0] == "doi:10.1000/xyz"
    codes = [record.code for record in ctx.diagnostics]
    assert codes == ["doi-fetch-failed", "doi-fetch-failed"]
    assert "10.1000/xyz" in ctx.diagnostics.sorted()[0].message


@pytest.mark.parametrize("case", ["plain"])
def test_pass_is_identity_without_dois(harness, case: str, tmp_path: Path) -> None:
    document = harness.load("stubs", case)
    ctx = harness.context(document, output_dir=tmp_path, doi_fetcher=FakeFetcher({}))
    assert harness.run("doi", document, ctx) is document
    assert ctx.bibliography == []
    assert not list(tmp_path.iterdir())
