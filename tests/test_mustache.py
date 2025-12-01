from texsmith.core.mustache import replace_mustaches, replace_mustaches_in_structure


class _StubEmitter:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def warning(self, message: str) -> None:
        self.messages.append(message)


def test_replace_mustaches_with_context() -> None:
    emitter = _StubEmitter()
    contexts = ({"title": "Hello", "callouts": {"style": "note"}}, {})
    text = "Title: {{ title }} / Style: {{callouts.style}}"

    result = replace_mustaches(text, contexts, emitter=emitter, source="content")

    assert result == "Title: Hello / Style: note"
    assert not emitter.messages


def test_replace_mustaches_missing_value_warns() -> None:
    emitter = _StubEmitter()
    contexts = ({"title": ""}, {})
    payload = {"heading": "Intro {{title}}"}

    resolved = replace_mustaches_in_structure(payload, contexts, emitter=emitter, source="test")

    assert resolved["heading"] == "Intro {{title}}"
    assert emitter.messages  # warning emitted
