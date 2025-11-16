from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from texsmith.builtin_templates.letter import Template


def build_overrides(**press_values):
    press = {
        "from": {"name": "Alice Sender"},
        "to": {"name": "Bob Receiver"},
    }
    press.update(press_values)
    return {"press": press}


def test_letter_template_defaults_to_din_for_english() -> None:
    template = Template()
    context = template.prepare_context("Body", overrides=build_overrides())

    assert context["letter_standard"] == "din"
    assert context["letter_standard_option"] == "DIN"
    assert context["subject_prefix"] == r"Subject:~"


def test_letter_template_switches_to_sn_for_french() -> None:
    template = Template()
    context = template.prepare_context(
        "Body",
        overrides=build_overrides(language="fr-CH", object="Objet"),
    )

    assert context["letter_standard"] == "sn-left"
    assert context["letter_standard_option"] == "SNleft"
    assert context["subject_prefix"] == r"Objet~:~"
    assert context["has_subject"] is True


def test_letter_template_accepts_standard_override() -> None:
    template = Template()
    context = template.prepare_context(
        "Body",
        overrides=build_overrides(standard="sn-right", language="en-UK"),
    )

    assert context["letter_standard"] == "sn-right"
    assert context["letter_standard_option"] == "SNright"
