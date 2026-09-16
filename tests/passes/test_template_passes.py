"""Template-declared IR passes (``[latex.template] passes`` / ``[typst.template] passes``).

A template brings its own passes along in its manifest; they are resolved when
the manifest loads and run only while that template renders.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import sys
import textwrap

import pytest

from texsmith.core.conversion import ConversionRequest
from texsmith.core.conversion.service import ConversionService
from texsmith.core.conversion.typst import render_typst_document
from texsmith.core.templates.manifest import (
    TemplateError,
    TemplateManifest,
    _resolve_template_pass,
)
from texsmith.core.templates.runtime import load_template_runtime, resolve_template_binding
from texsmith.passes import REGISTRY, build_pipeline


BANNER_MODULE = """
from __future__ import annotations

from dataclasses import replace

from tmark.ir import model

from texsmith.passes import PassContext, spec


@spec("demo-banner", after=("var",))
def run(document, ctx: PassContext):
    ir = document.ir
    if ir is None:
        return document
    marker = "SOLUTION" if ctx.attribute("solution", False) else "STUDENT"
    para = model.Para(
        id=ctx.ids.next(),
        content=(model.Str(id=ctx.ids.next(), text=marker),),
    )
    return document.evolve(ir=replace(ir, blocks=(para, *ir.blocks)))
"""

PLAIN_MODULE = """
from __future__ import annotations


def run(document, ctx):
    return document
"""

SPEC_OBJECT_MODULE = """
from __future__ import annotations

from texsmith.passes import PassSpec


def _run(document, ctx):
    return document


SPEC = PassSpec(name="declared-spec", run=_run, stage="post", after=("slots",))
"""

NOT_CALLABLE_MODULE = """
RUN = "not a pass"
"""

SHADOW_MODULE = """
from __future__ import annotations

from texsmith.passes import PassSpec


def _run(document, ctx):
    return document


SPEC = PassSpec(name="highlight", run=_run)
"""


@pytest.fixture(autouse=True)
def _isolated_passes() -> Iterator[None]:
    """Keep the global registry, the resolver cache and ``sys.modules`` clean."""
    build_pipeline()  # registers the bundled passes before the snapshot
    snapshot = dict(REGISTRY)
    yield
    REGISTRY.clear()
    REGISTRY.update(snapshot)
    _resolve_template_pass.cache_clear()
    for name in [name for name in sys.modules if name.startswith("tspass_")]:
        del sys.modules[name]


def _write_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, body: str) -> str:
    (tmp_path / f"{name}.py").write_text(textwrap.dedent(body), encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    return name


def _write_template(tmp_path: Path, references: list[str], *, typst: bool = False) -> Path:
    root = tmp_path / "tpl"
    root.mkdir(exist_ok=True)
    declared = ", ".join(f'"{reference}"' for reference in references)
    manifest = [
        "[latex.template]",
        'name = "demo"',
        'version = "0.0.1"',
        'entrypoint = "template.tex"',
        f"passes = [{declared}]",
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
            f"passes = [{declared}]",
            "",
            "[typst.template.slots.mainmatter]",
            "default = true",
        ]
    (root / "manifest.toml").write_text("\n".join(manifest), encoding="utf-8")
    (root / "template.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\n\\VAR{mainmatter}\n\\end{document}\n",
        encoding="utf-8",
    )
    (root / "template.typ").write_text("{{ mainmatter }}\n", encoding="utf-8")
    return root


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "doc.md"
    source.write_text("# Title\n\nBody\n", encoding="utf-8")
    return source


# Manifest parsing


def test_manifest_reuses_the_registered_spec_of_a_decorated_callable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _write_module(tmp_path, monkeypatch, "tspass_banner", BANNER_MODULE)
    root = _write_template(tmp_path, [f"{module}:run"], typst=True)

    manifest = TemplateManifest.load(root / "manifest.toml")

    assert manifest.latex.template.passes == [f"{module}:run"]
    (declared,) = manifest.latex.template.pass_specs()
    # The ``@spec(...)`` registration wins: its name, stage and constraints hold.
    assert declared.name == "demo-banner"
    assert declared.stage == "pre"
    assert declared.after == ("var",)
    assert declared is REGISTRY["demo-banner"]
    assert manifest.section("typst").pass_specs() == (declared,)


def test_manifest_wraps_a_plain_callable_as_a_pre_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _write_module(tmp_path, monkeypatch, "tspass_plain", PLAIN_MODULE)
    root = _write_template(tmp_path, [f"{module}:run"])

    (declared,) = TemplateManifest.load(root / "manifest.toml").latex.template.pass_specs()

    assert declared.name == f"{module}:run"
    assert declared.stage == "pre"
    assert declared.after == ()


def test_manifest_accepts_a_pass_spec_instance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _write_module(tmp_path, monkeypatch, "tspass_object", SPEC_OBJECT_MODULE)
    root = _write_template(tmp_path, [f"{module}:SPEC"])

    (declared,) = TemplateManifest.load(root / "manifest.toml").latex.template.pass_specs()

    assert declared.name == "declared-spec"
    assert declared.stage == "post"


def test_a_template_without_passes_declares_none() -> None:
    runtime = load_template_runtime("article")
    assert runtime.instance.info.pass_specs() == ()


def test_binding_without_a_template_declares_no_passes() -> None:
    binding, _ = resolve_template_binding(
        template=None,
        template_runtime=None,
        template_overrides={},
        slot_requests={},
    )
    assert binding.pass_specs() == ()


# Bad entries fail at template load time


@pytest.mark.parametrize(
    ("reference", "message"),
    [
        ("tspass_missing_module:run", "Could not import module"),
        ("tspass_plain:absent", "has no attribute 'absent'"),
        ("tspass_plain", "Expected the form 'module:attribute'"),
        ("", "empty pass reference"),
    ],
)
def test_a_bad_pass_entry_raises_template_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reference: str, message: str
) -> None:
    _write_module(tmp_path, monkeypatch, "tspass_plain", PLAIN_MODULE)
    root = _write_template(tmp_path, [reference])

    with pytest.raises(TemplateError, match=message):
        TemplateManifest.load(root / "manifest.toml")


def test_a_non_callable_pass_entry_raises_template_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _write_module(tmp_path, monkeypatch, "tspass_notcallable", NOT_CALLABLE_MODULE)
    root = _write_template(tmp_path, [f"{module}:RUN"])

    with pytest.raises(TemplateError, match="non-callable object of type 'str'"):
        TemplateManifest.load(root / "manifest.toml")


def test_a_pass_shadowing_a_bundled_one_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _write_module(tmp_path, monkeypatch, "tspass_shadow", SHADOW_MODULE)
    root = _write_template(tmp_path, [f"{module}:SPEC"])

    with pytest.raises(TemplateError, match="which is a bundled pass"):
        TemplateManifest.load(root / "manifest.toml")


def test_the_same_pass_declared_twice_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _write_module(tmp_path, monkeypatch, "tspass_banner", BANNER_MODULE)
    root = _write_template(tmp_path, [f"{module}:run", f"{module}.run"])

    with pytest.raises(TemplateError, match="declares the pass 'demo-banner' twice"):
        TemplateManifest.load(root / "manifest.toml")


def test_the_error_names_the_template_and_the_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_module(tmp_path, monkeypatch, "tspass_plain", PLAIN_MODULE)
    root = _write_template(tmp_path, ["tspass_plain:absent"])

    with pytest.raises(TemplateError) as excinfo:
        load_template_runtime(str(root))

    message = str(excinfo.value)
    assert "Template 'demo'" in message
    assert "tspass_plain:absent" in message


# Ordering


def test_declared_passes_are_ordered_by_their_constraints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _write_module(tmp_path, monkeypatch, "tspass_banner", BANNER_MODULE)
    root = _write_template(tmp_path, [f"{module}:run"])
    specs = TemplateManifest.load(root / "manifest.toml").latex.template.pass_specs()

    names = [item.name for item in build_pipeline(extra=specs)]

    assert names.index("demo-banner") > names.index("var")
    assert names.index("demo-banner") < names.index("slots")  # a ``pre`` pass


def test_a_declared_post_pass_runs_after_every_pre_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _write_module(tmp_path, monkeypatch, "tspass_object", SPEC_OBJECT_MODULE)
    root = _write_template(tmp_path, [f"{module}:SPEC"])
    specs = TemplateManifest.load(root / "manifest.toml").latex.template.pass_specs()

    pipeline = build_pipeline(extra=specs)
    stages = [item.stage for item in pipeline]

    assert stages == sorted(stages, key=["pre", "post"].index)
    assert [item.name for item in pipeline].index("declared-spec") > stages.index("post")


# The passes run during a conversion


def _latex_main(tmp_path: Path, root: Path, **options: object) -> str:
    source = _source(tmp_path)
    request = ConversionRequest(
        documents=[source],
        bibliography_files=[],
        template=str(root),
        render_dir=tmp_path / "build",
        embed_documents=True,
        template_options=options,
    )
    service = ConversionService()
    response = service.execute(request, prepared=service.prepare_documents(request))
    return response.render_result.main_tex_path.read_text(encoding="utf-8")


def test_latex_conversion_runs_the_declared_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _write_module(tmp_path, monkeypatch, "tspass_banner", BANNER_MODULE)
    root = _write_template(tmp_path, [f"{module}:run"])

    assert "STUDENT" in _latex_main(tmp_path, root)


def test_a_cli_attribute_override_reaches_the_declared_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ``-a solution=true`` arrives as ``template_options`` and is what
    # ``PassContext.attribute`` reads.
    module = _write_module(tmp_path, monkeypatch, "tspass_banner", BANNER_MODULE)
    root = _write_template(tmp_path, [f"{module}:run"])

    assert "SOLUTION" in _latex_main(tmp_path, root, solution=True)


def test_a_template_pass_does_not_leak_into_a_templateless_conversion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _write_module(tmp_path, monkeypatch, "tspass_banner", BANNER_MODULE)
    root = _write_template(tmp_path, [f"{module}:run"])
    # Load the template so the pass is registered, then convert without one.
    load_template_runtime(str(root))
    source = _source(tmp_path)

    request = ConversionRequest(
        documents=[source],
        bibliography_files=[],
        render_dir=tmp_path / "plain",
    )
    service = ConversionService()
    response = service.execute(request, prepared=service.prepare_documents(request))

    body = response.bundle.documents[0].latex
    assert "STUDENT" not in body


def test_typst_conversion_runs_the_declared_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _write_module(tmp_path, monkeypatch, "tspass_banner", BANNER_MODULE)
    root = _write_template(tmp_path, [f"{module}:run"], typst=True)
    source = _source(tmp_path)

    request = ConversionRequest(
        documents=[source],
        bibliography_files=[],
        template=str(root),
        template_options={"solution": True},
    )
    service = ConversionService()
    document = service.prepare_documents(request).documents[0]

    output = render_typst_document(document, request, output_dir=tmp_path / "typst")

    assert "SOLUTION" in output
