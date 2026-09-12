"""Tests for the cross-document reference inventory TeXSmith publishes.

Reading an inventory and resolving ``@alias:key`` against it is tmark's since
0.8 (decision D4 of ``specs/tmark-migration.md``); what is tested here is the
writing half: the payload, the anchors of a finished ``tmark.resolve``, the page
numbers harvested from the ``.aux`` and the relocation that keeps
``document.source`` resolvable.
"""

from __future__ import annotations

import json
from pathlib import Path

from texsmith.core.conversion.models import ConversionRequest
from texsmith.core.conversion.service import ConversionService
from texsmith.core.crossrefs import (
    SCHEMA_VERSION,
    Anchor,
    DocumentIdentity,
    anchors_from_resolved,
    attach_pages,
    build_payload,
    document_identifier,
    harvest_aux,
    publish_inventory,
    relocate_inventory,
    write_inventory,
)


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


def _anchors(path: Path) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8"))["anchors"]


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------


def test_inventory_payload_is_stable(tmp_path: Path) -> None:
    path = _write_inventory(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == SCHEMA_VERSION
    assert payload["document"]["id"] == "RHE-423"
    assert payload["anchors"]["fw:pas-de-temps"] == {
        "counter": "fw",
        "label": "FW-10",
        "page": 14,
    }


def test_an_anchor_without_a_page_omits_the_key(tmp_path: Path) -> None:
    path = _write_inventory(tmp_path, page=None)
    assert "page" not in _anchors(path)["fw:pas-de-temps"]


# ---------------------------------------------------------------------------
# Anchors of a resolution
# ---------------------------------------------------------------------------


def test_anchors_come_from_the_resolved_counter_items() -> None:
    resolved = {
        "labels": [
            {"id": "intro", "prefix": "sec", "host": "header", "title": "Intro"},
            {"id": "fw:a", "prefix": "fw", "host": "counter_item", "formatted": "FW-01"},
            {"id": "fw:b", "prefix": "fw", "host": "counter_item", "formatted": "FW-02"},
        ]
    }
    anchors = anchors_from_resolved(resolved)
    # A header is numbered by the backend, so it is not citable across documents.
    assert set(anchors) == {"fw:a", "fw:b"}
    assert anchors["fw:a"] == Anchor(key="fw:a", label="FW-01", counter="fw")


def test_anchors_of_an_unresolved_document_are_empty() -> None:
    assert anchors_from_resolved(None) == {}
    assert anchors_from_resolved({}) == {}


def test_publish_inventory_writes_nothing_without_anchors(tmp_path: Path) -> None:
    assert (
        publish_inventory(
            output_dir=tmp_path,
            stem="doc",
            metadata={"document-id": "X"},
            source_path=None,
            anchors={},
        )
        is None
    )


def test_a_conversion_publishes_the_counters_it_allocated(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text(
        "---\n"
        "id: RHE-1\n"
        "title: Doc\n"
        "press:\n"
        "  declare:\n"
        "    counters:\n"
        "      fw:\n"
        "        name: Constat\n"
        '        format: "FW-{n:02d}"\n'
        "---\n"
        "\n"
        "# Doc\n"
        "\n"
        "Constat {counter}(fw:a) puis {counter}(fw:b).\n",
        encoding="utf-8",
    )
    out = tmp_path / "build"
    ConversionService().execute(ConversionRequest(documents=[source], render_dir=out))

    published = out / "doc.refs.json"
    assert published.exists()
    payload = json.loads(published.read_text(encoding="utf-8"))
    assert payload["document"]["id"] == "RHE-1"
    assert {key: anchor["label"] for key, anchor in payload["anchors"].items()} == {
        "fw:a": "FW-01",
        "fw:b": "FW-02",
    }


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
    assert _anchors(path)["fw:pas-de-temps"]["page"] == 14


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
    # ``dist/`` and tmark's staleness check would go quietly inoperative.
    assert (delivered.parent / payload["document"]["source"]).resolve() == source.resolve()


def test_relocate_inventory_is_a_no_op_in_place(tmp_path: Path) -> None:
    inventory = _write_inventory(tmp_path)
    assert relocate_inventory(inventory, tmp_path) == inventory
