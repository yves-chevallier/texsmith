"""Tests for cross-document references: inventories, citations and diagnostics."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import json
from pathlib import Path

import pytest

from texsmith.core.counters import CounterSpec, clear_registry, get_registry
from texsmith.core.crossrefs import (
    SCHEMA_VERSION,
    Anchor,
    CrossRefValidationError,
    DocumentIdentity,
    attach_pages,
    build_payload,
    document_identifier,
    harvest_aux,
    load_inventory,
    parse_front_matter_crossrefs,
    publish_inventory,
    relocate_inventory,
    render_reference,
    write_inventory,
)
from texsmith.core.diagnostics import LoggingEmitter, use_emitter
from texsmith.diagnostics import DiagnosticSink


@pytest.fixture(autouse=True)
def _clear_counter_registry() -> Iterator[None]:
    clear_registry()
    yield
    clear_registry()


@contextmanager
def _collect() -> Iterator[DiagnosticSink]:
    """Capture the diagnostics the code under test reports."""
    emitter = LoggingEmitter()
    with use_emitter(emitter):
        yield emitter.sink


def _reported(sink: DiagnosticSink, code: str) -> list[str]:
    return [diagnostic.message for diagnostic in sink if diagnostic.code == code]


def _write_inventory(
    directory: Path,
    *,
    stem: str = "firmware-review",
    document_id: str = "RHE-423",
    title: str = "Revue firmware",
    page: int | None = 14,
    source: str = "",
    source_sha256: str = "",
) -> Path:
    payload = build_payload(
        anchors={
            "fw:pas-de-temps": Anchor(key="fw:pas-de-temps", label="FW-10", counter="fw", page=page)
        },
        identity=DocumentIdentity(
            id=document_id,
            title=title,
            output=f"{stem}.pdf",
            source=source,
            source_sha256=source_sha256,
        ),
    )
    return write_inventory(directory / f"{stem}.refs.json", payload)


# ---------------------------------------------------------------------------
# Front matter
# ---------------------------------------------------------------------------


def test_parse_returns_empty_mapping_when_crossrefs_absent() -> None:
    assert parse_front_matter_crossrefs({"title": "x"}) == {}
    assert parse_front_matter_crossrefs(None) == {}


def test_parse_accepts_the_string_shorthand(tmp_path: Path) -> None:
    sources = parse_front_matter_crossrefs(
        {"crossrefs": {"fwrev": "build/firmware-review.refs.json"}}, base_path=tmp_path
    )
    assert sources["fwrev"] == (tmp_path / "build/firmware-review.refs.json").resolve()


def test_parse_accepts_the_mapping_form(tmp_path: Path) -> None:
    sources = parse_front_matter_crossrefs(
        {"crossrefs": {"fwrev": {"inventory": "a.refs.json"}}},
        base_path=tmp_path,
    )
    assert sources["fwrev"] == (tmp_path / "a.refs.json").resolve()


def test_parse_rejects_a_non_mapping_section() -> None:
    with pytest.raises(CrossRefValidationError):
        parse_front_matter_crossrefs({"crossrefs": ["a"]})


def test_parse_rejects_an_unknown_option() -> None:
    with pytest.raises(CrossRefValidationError):
        parse_front_matter_crossrefs({"crossrefs": {"a": {"inventory": "x", "colour": "red"}}})


def test_parse_rejects_a_missing_inventory_path() -> None:
    with pytest.raises(CrossRefValidationError):
        parse_front_matter_crossrefs({"crossrefs": {"a": {}}})


def test_parse_rejects_an_entry_that_is_neither_string_nor_mapping() -> None:
    with pytest.raises(CrossRefValidationError):
        parse_front_matter_crossrefs({"crossrefs": {"a": 42}})


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def test_a_citation_concatenates_the_document_id() -> None:
    identity = DocumentIdentity(id="RHE-423", title="Revue firmware")
    anchor = Anchor(key="fw:x", label="FW-10", page=14)
    assert render_reference(identity, anchor) == "RHE-423-FW-10 p. 14"


def test_a_citation_falls_back_to_the_title_without_a_document_id() -> None:
    identity = DocumentIdentity(title="Revue firmware")
    anchor = Anchor(key="fw:x", label="FW-10", page=14)
    assert render_reference(identity, anchor) == "FW-10 (Revue firmware, p. 14)"


def test_a_citation_falls_back_to_the_bare_label_without_any_identity() -> None:
    assert render_reference(DocumentIdentity(), Anchor(key="fw:x", label="FW-10")) == "FW-10"


def test_a_citation_omits_the_page_until_the_target_is_built() -> None:
    identity = DocumentIdentity(id="RHE-423", title="Revue firmware")
    assert render_reference(identity, Anchor(key="fw:x", label="FW-10")) == "RHE-423-FW-10"


# ---------------------------------------------------------------------------
# Inventory round trip
# ---------------------------------------------------------------------------


def test_inventory_round_trip(tmp_path: Path) -> None:
    path = _write_inventory(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == SCHEMA_VERSION
    assert payload["document"]["id"] == "RHE-423"

    inventory = load_inventory(path)
    assert inventory is not None
    anchor = inventory.anchor("fw:pas-de-temps")
    assert anchor is not None
    assert (anchor.label, anchor.page) == ("FW-10", 14)


def test_missing_inventory_warns_and_returns_none(tmp_path: Path) -> None:
    with _collect() as sink:
        assert load_inventory(tmp_path / "absent.refs.json") is None
    (message,) = _reported(sink, "crossref-inventory-missing")
    assert "is missing" in message


def test_unknown_schema_warns_and_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "x.refs.json"
    path.write_text(json.dumps({"schema": 99, "anchors": {}}), encoding="utf-8")
    with _collect() as sink:
        assert load_inventory(path) is None
    (message,) = _reported(sink, "crossref-inventory-missing")
    assert "schema" in message


def test_stale_inventory_warns(tmp_path: Path) -> None:
    source = tmp_path / "firmware-review.md"
    source.write_text("# a\n", encoding="utf-8")
    path = _write_inventory(tmp_path, source="firmware-review.md", source_sha256="0" * 64)
    with _collect() as sink:
        load_inventory(path)
    (message,) = _reported(sink, "crossref-inventory-stale")
    assert "out of date" in message


def test_publish_inventory_exports_the_allocated_counters(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text("# Doc\n", encoding="utf-8")
    registry = get_registry()
    registry.declare({"fw": CounterSpec(prefix="fw", name="Constat", format="FW-{n:02d}")})
    registry.allocate("fw", "a")
    registry.allocate("fw", "b")

    path = publish_inventory(
        output_dir=tmp_path / "build",
        stem="doc",
        metadata={"document-id": "RHE-1", "title": "Doc"},
        source_path=source,
    )
    assert path is not None
    inventory = load_inventory(path)
    assert inventory is not None
    assert inventory.document.id == "RHE-1"
    assert {key: anchor.label for key, anchor in inventory.anchors.items()} == {
        "fw:a": "FW-01",
        "fw:b": "FW-02",
    }


def test_publish_inventory_writes_nothing_without_anchors(tmp_path: Path) -> None:
    assert (
        publish_inventory(
            output_dir=tmp_path, stem="doc", metadata={"document-id": "X"}, source_path=None
        )
        is None
    )


# ---------------------------------------------------------------------------
# Page harvesting
# ---------------------------------------------------------------------------


def test_harvest_aux_reads_the_page_of_each_label(tmp_path: Path) -> None:
    aux = tmp_path / "doc.aux"
    aux.write_text(
        r"\newlabel{fw:a}{{\relax 2.1}{14}{}{}{}}"
        "\n"
        r"\newlabel{fw:b}{{3}{7}{Titre}{section.3}{}}"
        "\n",
        encoding="utf-8",
    )
    # The first field carries nested TeX markup; only the page is wanted.
    assert harvest_aux(aux) == {"fw:a": 14, "fw:b": 7}


def test_harvest_aux_on_a_missing_file_is_empty(tmp_path: Path) -> None:
    assert harvest_aux(tmp_path / "absent.aux") == {}


def test_attach_pages_folds_the_pages_into_the_inventory(tmp_path: Path) -> None:
    path = _write_inventory(tmp_path, page=None)
    aux = tmp_path / "firmware-review.aux"
    aux.write_text(r"\newlabel{fw:pas-de-temps}{{1}{14}{}{}{}}" "\n", encoding="utf-8")

    assert attach_pages(path, aux) == 1
    inventory = load_inventory(path)
    assert inventory is not None
    anchor = inventory.anchor("fw:pas-de-temps")
    assert anchor is not None and anchor.page == 14


# ---------------------------------------------------------------------------
# Document identity
# ---------------------------------------------------------------------------


def test_document_identifier_reads_the_id_key() -> None:
    assert document_identifier({"id": "TIR-129"}) == "TIR-129"


def test_document_identifier_accepts_the_document_id_alias() -> None:
    assert document_identifier({"document-id": "RHE-423"}) == "RHE-423"


def test_document_identifier_prefers_id_over_the_alias() -> None:
    assert document_identifier({"id": "TIR-129", "document-id": "RHE-423"}) == "TIR-129"


def test_document_identifier_is_empty_without_either_key() -> None:
    assert document_identifier({"title": "x"}) == ""
    assert document_identifier(None) == ""


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


def test_relocate_inventory_keeps_the_source_path_resolvable(tmp_path: Path) -> None:
    render_dir = tmp_path / "render"
    render_dir.mkdir()
    source = tmp_path / "firmware-review.md"
    source.write_text("# a\n", encoding="utf-8")
    inventory = _write_inventory(render_dir, source="../firmware-review.md")

    delivered = relocate_inventory(inventory, tmp_path / "dist")
    assert delivered is not None
    payload = json.loads(delivered.read_text(encoding="utf-8"))
    # Copied verbatim, ``../firmware-review.md`` would no longer resolve from
    # ``dist/`` and the staleness check would go quietly inoperative.
    assert (delivered.parent / payload["document"]["source"]).resolve() == source.resolve()


def test_relocate_inventory_is_a_no_op_in_place(tmp_path: Path) -> None:
    inventory = _write_inventory(tmp_path)
    assert relocate_inventory(inventory, tmp_path) == inventory


def test_an_unresolvable_source_warns(tmp_path: Path) -> None:
    path = _write_inventory(tmp_path, source="../gone.md", source_sha256="0" * 64)
    with _collect() as sink:
        load_inventory(path)
    (message,) = _reported(sink, "crossref-inventory-stale")
    assert "does not resolve" in message
