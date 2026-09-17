"""Template-declared containers (``[latex.template] containers`` / ``[typst.template]``).

A template's passes read constructs the language does not know (``::: solution``).
tmark reports such a name as ``container-unknown`` while it *parses*, before any
pass runs, so the template declares the names it reads and the run drops those
records where they are collected. Every other name still warns.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from texsmith.core.conversion import ConversionRequest
from texsmith.core.conversion.service import ConversionService
from texsmith.core.conversion.typst import render_typst_document
from texsmith.core.templates.manifest import TemplateError, TemplateManifest
from texsmith.core.templates.runtime import declared_containers
from texsmith.diagnostics import (
    CONTAINER_UNKNOWN,
    Diagnostic,
    DiagnosticSink,
    NullEmitter,
    Severity,
    Span,
    unknown_container,
)


def _write_template(tmp_path: Path, containers: str, *, typst: bool = False) -> Path:
    root = tmp_path / "tpl"
    root.mkdir(exist_ok=True)
    manifest = [
        "[latex.template]",
        'name = "demo"',
        'version = "0.0.1"',
        'entrypoint = "template.tex"',
        f"containers = {containers}",
        "",
        "[latex.template.slots.mainmatter]",
        "default = true",
    ]
    if typst:
        manifest += [
            "",
            "[typst.template]",
            'name = "demo"',
            'version = "0.0.1"',
            'entrypoint = "template.typ"',
            f"containers = {containers}",
            "",
            "[typst.template.slots.mainmatter]",
            "default = true",
        ]
    (root / "manifest.toml").write_text("\n".join(manifest), encoding="utf-8")
    # ``\VAR{extra_packages}`` is the slot the fragments a container activates
    # (``ts-typesetting``) inject their packages into.
    (root / "template.tex").write_text(
        "\\documentclass{article}\n\\VAR{extra_packages}\n"
        "\\begin{document}\n\\VAR{mainmatter}\n\\end{document}\n",
        encoding="utf-8",
    )
    (root / "template.typ").write_text("{{ mainmatter }}\n", encoding="utf-8")
    return root


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "doc.md"
    source.write_text(
        "# Title\n\n::: foo\ndeclared\n:::\n\n::: bar\nundeclared\n:::\n",
        encoding="utf-8",
    )
    return source


def _codes(emitter: NullEmitter) -> list[tuple[str, str | None]]:
    return [(record.code, unknown_container(record)) for record in emitter.sink]


# Manifest parsing


def test_the_manifest_declares_the_container_names(tmp_path: Path) -> None:
    root = _write_template(tmp_path, '["foo", " bar "]', typst=True)

    manifest = TemplateManifest.load(root / "manifest.toml")

    assert manifest.latex.template.containers == ["foo", "bar"]
    assert manifest.section("typst").containers == ["foo", "bar"]
    assert declared_containers(str(root)) == frozenset({"foo", "bar"})


def test_a_template_without_containers_declares_none(tmp_path: Path) -> None:
    root = _write_template(tmp_path, "[]")

    assert TemplateManifest.load(root / "manifest.toml").latex.template.containers == []
    assert declared_containers(str(root)) == frozenset()
    assert declared_containers(None) == frozenset()


@pytest.mark.parametrize(
    ("declaration", "message"),
    [
        ("[42]", "invalid container name 42"),
        ('["solution", ""]', "invalid container name ''"),
        ('["  "]', "invalid container name"),
        ('"solution"', "expected a list of container names"),
    ],
)
def test_a_bad_container_entry_raises_template_error(
    tmp_path: Path, declaration: str, message: str
) -> None:
    root = _write_template(tmp_path, declaration)

    with pytest.raises(TemplateError, match=message):
        TemplateManifest.load(root / "manifest.toml")


# The sink drops the declared names only


def test_the_sink_drops_a_declared_container_and_keeps_the_others() -> None:
    sink = DiagnosticSink(containers=["foo"])

    def record(name: str) -> Diagnostic:
        return Diagnostic(
            code=CONTAINER_UNKNOWN,
            severity=Severity.WARNING,
            span=Span(0, len(name), len(name) + 1),
            message=f"`::: {name}` is not a known container",
        )

    assert sink.add(record("foo")) is False
    assert sink.add(record("bar")) is True
    assert [item.code for item in sink] == [CONTAINER_UNKNOWN]
    assert sink.counts()[Severity.WARNING] == 1


# A real conversion


def _convert(tmp_path: Path, root: Path) -> tuple[str, NullEmitter]:
    emitter = NullEmitter()
    request = ConversionRequest(
        documents=[_source(tmp_path)],
        bibliography_files=[],
        template=str(root),
        render_dir=tmp_path / "build",
        embed_documents=True,
        emitter=emitter,
    )
    service = ConversionService()
    response = service.execute(request, prepared=service.prepare_documents(request))
    return response.render_result.main_tex_path.read_text(encoding="utf-8"), emitter


def test_a_latex_conversion_warns_for_the_undeclared_container_only(tmp_path: Path) -> None:
    root = _write_template(tmp_path, '["foo"]')

    body, emitter = _convert(tmp_path, root)

    assert ("container-unknown", "bar") in _codes(emitter)
    assert ("container-unknown", "foo") not in _codes(emitter)
    # The mute is the record's, not the document's: both containers are written.
    assert "declared" in body
    assert "undeclared" in body
    assert [entry["code"] for entry in emitter.sink.to_json()] == [CONTAINER_UNKNOWN]


def test_without_a_declaration_both_containers_warn(tmp_path: Path) -> None:
    root = _write_template(tmp_path, "[]")

    _, emitter = _convert(tmp_path, root)

    assert sorted(name for _, name in _codes(emitter)) == ["bar", "foo"]


def test_a_typst_conversion_honours_the_declaration(tmp_path: Path) -> None:
    root = _write_template(tmp_path, '["foo"]', typst=True)
    emitter = NullEmitter()
    request = ConversionRequest(
        documents=[_source(tmp_path)],
        bibliography_files=[],
        template=str(root),
        emitter=emitter,
    )
    service = ConversionService()
    document = service.prepare_documents(request).documents[0]

    render_typst_document(document, request, output_dir=tmp_path / "typst")

    assert ("container-unknown", "bar") in _codes(emitter)
    assert ("container-unknown", "foo") not in _codes(emitter)
