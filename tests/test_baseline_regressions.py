from __future__ import annotations

from pathlib import Path

import pytest

from texsmith.api import Document
from texsmith.api.templates import TemplateSession
from texsmith.core.fragments import (
    FragmentDefinition,
    FragmentPiece,
    register_fragment,
    render_fragments,
)
from texsmith.core.templates.manifest import TemplateError, TemplateInfo, TemplateSlot
from texsmith.core.templates.runtime import load_template_runtime


def test_attribute_precedence_prefers_user_over_frontmatter_and_fragments(tmp_path: Path) -> None:
    markdown = tmp_path / "doc.md"
    markdown.write_text(
        "---\npress:\n  callouts:\n    style: classic\n---\nBody\n",
        encoding="utf-8",
    )

    session = TemplateSession(load_template_runtime("article"))
    session.add_document(Document.from_markdown(markdown))
    session.update_options({"press": {"callouts": {"style": "minimal"}}})

    result = session.render(tmp_path / "build")

    assert result.context["callout_style"] == "minimal"


def test_template_info_adds_default_mainmatter_slot() -> None:
    info = TemplateInfo.model_validate(
        {
            "name": "demo",
            "version": "0.0.0",
            "entrypoint": "main.tex",
            "slots": {"custom": TemplateSlot()},
        }
    )
    slots, default_slot = info.resolve_slots()

    assert "mainmatter" in slots
    assert slots["mainmatter"].default is True
    assert default_slot == "mainmatter"


def test_fragment_slot_validation_blocks_template_slot_targets(tmp_path: Path) -> None:
    template_path = tmp_path / "conflict.jinja.tex"
    template_path.write_text("payload", encoding="utf-8")

    piece = FragmentPiece(template_path=template_path, kind="inline", slot="mainmatter")
    definition = FragmentDefinition(name="phase1-conflict", pieces=[piece])
    register_fragment(definition)

    with pytest.raises(TemplateError, match="Fragments cannot target slot 'mainmatter'"):
        render_fragments(
            ["phase1-conflict"],
            context={},
            output_dir=tmp_path / "out",
            declared_slots={"mainmatter"},
            template_name="phase1",
        )
