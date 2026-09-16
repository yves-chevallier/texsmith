from texsmith.core.callouts import DEFAULT_CALLOUTS, merge_callouts
from texsmith.fragments.callouts import _callout_words
from texsmith.fragments.callouts.words import CALLOUT_WORDS


def test_merge_callouts_flattens_nested_custom_entries() -> None:
    overrides = {
        "custom": {
            "unicorn": {
                "background_color": "fff0ff",
                "border_color": "ff00ff",
                "icon": "🦄",
            }
        }
    }

    merged = merge_callouts(DEFAULT_CALLOUTS, overrides)

    assert "unicorn" in merged
    assert merged["unicorn"]["background_color"].lower() == "fff0ff"
    assert merged["unicorn"]["border_color"].lower() == "ff00ff"
    assert merged["unicorn"]["icon"] == "🦄"


def test_callout_words_are_english_without_a_language() -> None:
    """tmark's labels title the standard kinds; a styled kind gets its own name."""
    words = _callout_words({"callouts_definitions": DEFAULT_CALLOUTS})

    assert words["note"] == "Note"
    assert words["seealso"] == "See also"
    assert words["proof"] == "Proof"
    assert words["bug"] == "Bug"


def test_callout_words_follow_the_document_language() -> None:
    """``language:`` decides the title of an untitled callout, babel name or tag."""
    for language in ("fr", "french", "fr-CA", "canadien"):
        words = _callout_words({"callouts_definitions": DEFAULT_CALLOUTS, "language": language})
        assert words["tip"] == "Astuce", language
        assert words["warning"] == "Avertissement", language
        assert words["seealso"] == "Voir aussi", language
        assert words["proof"] == "Démonstration", language
        assert words["example"] == "Exemple", language

    german = _callout_words({"callouts_definitions": DEFAULT_CALLOUTS, "language": "ngerman"})
    assert german["theorem"] == "Satz"
    # A language with no table of its own keeps the English labels.
    assert _callout_words({"language": "swedish"})["note"] == "Note"


def test_a_declared_kind_carries_its_own_name() -> None:
    """``press.declare.admonitions`` names a kind; that name is its default title."""
    context = {
        "callouts_definitions": DEFAULT_CALLOUTS,
        "language": "fr",
        "press": {"declare": {"admonitions": {"exercise": {"name": "Exercice"}, "note": {}}}},
    }

    words = _callout_words(context)

    assert words["exercise"] == "Exercice"
    # A declaration without a name leaves the kind's own word alone.
    assert words["note"] == "Note"


def test_every_language_covers_the_same_kinds() -> None:
    """A kind translated in one language is translated in all of them."""
    kinds = {frozenset(table) for table in CALLOUT_WORDS.values()}

    assert len(kinds) == 1
    english = _callout_words({"callouts_definitions": DEFAULT_CALLOUTS})
    assert next(iter(kinds)) <= set(english)
