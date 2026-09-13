"""The decisions a flag and the front matter both claim."""

from __future__ import annotations

from texsmith.core.conversion.policy import (
    declared_template,
    demote_deprecated,
    deprecated_level,
    numbered_setting,
    strict_enabled,
)
from texsmith.diagnostics import NO_SPAN, Diagnostic, Severity


class TestStrict:
    def test_the_flag_alone_turns_it_on(self) -> None:
        assert strict_enabled(None, True) is True

    def test_the_front_matter_alone_turns_it_on(self) -> None:
        assert strict_enabled({"press": {"features": {"strict": True}}}) is True

    def test_off_by_default(self) -> None:
        assert strict_enabled({"press": {"features": {}}}) is False
        assert strict_enabled(None) is False

    def test_the_front_matter_cannot_turn_the_flag_off(self) -> None:
        """There is no ``--no-strict``, so nothing should read as one."""
        assert strict_enabled({"press": {"features": {"strict": False}}}, True) is True


class TestDeprecated:
    def test_the_flag_wins_over_the_front_matter(self) -> None:
        front = {"press": {"diagnostics": {"deprecated": "off"}}}
        assert deprecated_level(front, "info") == "info"

    def test_the_front_matter_answers_without_a_flag(self) -> None:
        assert deprecated_level({"press": {"diagnostics": {"deprecated": "off"}}}) == "off"

    def test_an_unusable_value_falls_back(self) -> None:
        assert deprecated_level({"press": {"diagnostics": {"deprecated": "loud"}}}) == "warning"
        assert deprecated_level(None, "loud") == "warning"

    def test_a_boolean_is_read_as_the_switch_it_looks_like(self) -> None:
        assert deprecated_level({"diagnostics": {"deprecated": False}}) == "off"

    def test_only_the_transition_codes_are_demoted(self) -> None:
        other = Diagnostic("asset-missing", Severity.WARNING, NO_SPAN, "gone")
        assert demote_deprecated(other, "off") is other
        legacy = Diagnostic("deprecated", Severity.WARNING, NO_SPAN, "old spelling")
        assert demote_deprecated(legacy, "off") is None
        lowered = demote_deprecated(legacy, "info")
        assert lowered is not None and lowered.severity is Severity.INFO


class TestTemplate:
    def test_the_press_spelling(self) -> None:
        assert declared_template({"press": {"template": " book "}}) == "book"

    def test_the_deprecated_root_spelling_is_normalised_first(self) -> None:
        assert declared_template({"template": "book"}) == "book"

    def test_nothing_declared(self) -> None:
        assert declared_template({"press": {}}) is None
        assert declared_template(None) is None


class TestNumbered:
    def test_the_default(self) -> None:
        assert numbered_setting(None, None) is True

    def test_the_front_matter_answers(self) -> None:
        assert numbered_setting({"numbered": False}, None) is False

    def test_an_attribute_overrides_the_front_matter(self) -> None:
        """``--attribute numbered=…`` is typed for this run; the front matter is the document's."""
        assert numbered_setting({"numbered": False}, {"numbered": True}) is True
        assert numbered_setting({"numbered": True}, {"numbered": False}) is False

    def test_an_absent_attribute_leaves_the_front_matter_alone(self) -> None:
        assert numbered_setting({"numbered": False}, {"paper": "a4"}) is False
