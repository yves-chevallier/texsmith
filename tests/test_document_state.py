from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

for candidate in (PROJECT_ROOT, SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from texsmith import DocumentState  # noqa: E402


def test_document_state_counters_track_values() -> None:
    state = DocumentState()

    assert state.peek_counter("custom") == 0
    assert state.next_counter("custom") == 1
    assert state.peek_counter("custom") == 1

    assert state.next_counter("custom") == 2
    state.reset_counter("custom")
    assert state.peek_counter("custom") == 0
