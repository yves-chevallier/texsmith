from emitters import RecordingEmitter

from texsmith.core.mustache import replace_mustaches, replace_mustaches_in_structure


def test_replace_mustaches_with_context(recording_emitter: RecordingEmitter) -> None:
    emitter = recording_emitter
    contexts = ({"title": "Hello", "callouts": {"style": "note"}}, {})
    text = "Title: {{ title }} / Style: {{callouts.style}}"

    result = replace_mustaches(text, contexts, emitter=emitter, source="content")

    assert result == "Title: Hello / Style: note"
    assert not emitter.messages


def test_replace_mustaches_missing_value_warns(recording_emitter: RecordingEmitter) -> None:
    emitter = recording_emitter
    contexts = ({"title": ""}, {})
    payload = {"heading": "Intro {{title}}"}

    resolved = replace_mustaches_in_structure(payload, contexts, emitter=emitter, source="test")

    assert resolved["heading"] == "Intro {{title}}"
    assert emitter.messages  # warning emitted
