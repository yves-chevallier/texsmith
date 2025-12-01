from __future__ import annotations

from texsmith.templates.letter import Template


def build_overrides(
    *,
    source_dir: str | None = None,
    output_dir: str | None = None,
    **press_values,
):
    press = {
        "from": {"name": "Alice Sender"},
        "to": {"name": "Bob Receiver"},
    }
    press.update(press_values)
    overrides: dict[str, object] = {"press": press}
    if source_dir:
        overrides["source_dir"] = source_dir
    if output_dir:
        overrides["output_dir"] = output_dir
    return overrides


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


def test_letter_template_supports_nf_format_alias() -> None:
    template = Template()
    context = template.prepare_context(
        "Paragraph\n\nWarm regards,",
        overrides=build_overrides(language="fr-FR", format="nf"),
    )

    assert context["letter_standard"] == "nf"
    assert context["letter_standard_option"] == "NF"


def test_letter_template_extracts_closing_from_body() -> None:
    template = Template()
    body = "\\thispagestyle{plain}\nI hope this message finds you well.\n\nWith appreciation,"
    context = template.prepare_context(body, overrides=build_overrides())

    assert context["closing_text"] == "With appreciation,"
    assert "With appreciation" not in context["mainmatter"]
    assert "\\thispagestyle" not in context["mainmatter"]


def test_letter_template_tracks_reference_and_postscript() -> None:
    template = Template()
    overrides = build_overrides(
        back_address="Sender Street\n12345 City",
        reference="ABC-42",
        reference_fields=True,
        ps="Extra note.",
    )
    context = template.prepare_context("Hello world,\n\nSincerely,", overrides=overrides)

    assert context["reference_value"] == "ABC-42"
    assert context["reference_fields_enabled"] is True
    assert context["back_address_lines"][0] == "Sender Street"
    assert context["has_back_address"] is True
    assert context["has_postscript"] is True
    assert context["postscript_text"] == "Extra note."


def test_letter_template_formats_iso_date() -> None:
    template = Template()
    context = template.prepare_context(
        "Body",
        overrides=build_overrides(language="en-UK", date="1903-07-14"),
    )

    assert context["date_value"] == "14 July 1903"


def test_letter_template_formats_iso_date_french() -> None:
    template = Template()
    context = template.prepare_context(
        "Body",
        overrides=build_overrides(language="fr-FR", date="1903-07-14"),
    )

    assert context["date_value"] == "14 juillet 1903"


def test_letter_template_embeds_signature_image(tmp_path) -> None:
    signature = tmp_path / "signature.png"
    signature.write_text("fake")
    output_dir = tmp_path / "render"
    template = Template()
    context = template.prepare_context(
        "Body,\n\nWith regards,",
        overrides=build_overrides(
            signature=str(signature),
            source_dir=str(tmp_path),
            output_dir=str(output_dir),
        ),
    )

    assert context["has_signature_image"] is True
    assert "assets/signatures" in context["signature_image_path"]
    mirrored = output_dir / "assets" / "signatures" / signature.name
    assert mirrored.exists()
    assert context["signature_text"] == "Alice Sender"
