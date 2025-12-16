from __future__ import annotations

from pathlib import Path

import pytest

from texsmith.core.fragments import (
    FragmentDefinition,
    FragmentPiece,
    inject_fragment_attributes,
    register_fragment,
)
from texsmith.core.templates.manifest import (
    TemplateAttributeSpec,
    TemplateError,
    TemplateInfo,
)


def _inline_fragment(tmp_path: Path, name: str, attr_name: str) -> str:
    template_path = tmp_path / f"{name}.jinja.tex"
    template_path.write_text("", encoding="utf-8")
    piece = FragmentPiece(template_path=template_path, kind="inline", slot="extra_packages")
    fragment = FragmentDefinition(
        name=name,
        pieces=[piece],
        attributes={attr_name: TemplateAttributeSpec(default="x")},
    )
    register_fragment(fragment)
    return name


def test_template_attribute_owners_default_to_template_name() -> None:
    info = TemplateInfo.model_validate(
        {
            "name": "demo",
            "version": "0.0.0",
            "entrypoint": "main.tex",
            "attributes": {"title": {"default": "Hello"}},
        }
    )

    owners = info.attribute_owners()

    assert owners["title"] == "demo"


def test_conflicting_attribute_owner_between_template_and_fragment(tmp_path: Path) -> None:
    owners = {"callout_style": "demo-template"}
    frag_name = _inline_fragment(tmp_path, "frag-owner-conflict", "callout_style")

    with pytest.raises(TemplateError, match="already owned"):
        inject_fragment_attributes(
            [frag_name], context={}, overrides=None, declared_attribute_owners=owners
        )


def test_conflict_between_fragments(tmp_path: Path) -> None:
    frag_one = _inline_fragment(tmp_path, "frag-one", "code")
    frag_two = _inline_fragment(tmp_path, "frag-two", "code")

    with pytest.raises(TemplateError, match="already owned"):
        inject_fragment_attributes([frag_one, frag_two], context={}, overrides=None)


def test_explicit_fragment_owner_conflicts_with_template(tmp_path: Path) -> None:
    owners = {"foo": "template-owner"}
    template_path = tmp_path / "frag-explicit-owner.jinja.tex"
    template_path.write_text("", encoding="utf-8")
    fragment = FragmentDefinition(
        name="frag-explicit-owner",
        pieces=[FragmentPiece(template_path=template_path, kind="inline", slot="extra_packages")],
        attributes={"foo": TemplateAttributeSpec(default="x", owner="custom-owner")},
    )
    register_fragment(fragment)

    with pytest.raises(TemplateError, match="already owned"):
        inject_fragment_attributes(
            [fragment.name],
            context={},
            overrides=None,
            declared_attribute_owners=owners,
        )
