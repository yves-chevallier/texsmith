from texsmith.core.callouts import DEFAULT_CALLOUTS, merge_callouts


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
