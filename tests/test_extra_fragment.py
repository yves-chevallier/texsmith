from texsmith.fragments.extra import ExtraFragment


def test_extra_fragment_enables_float_for_strict_figures() -> None:
    fragment = ExtraFragment()
    context = {"content": "\\begin{figure}[H]"}

    config = fragment.build_config(context)

    assert ("float", None) in config.packages


def test_extra_fragment_always_includes_float() -> None:
    fragment = ExtraFragment()
    context: dict[str, str] = {}

    config = fragment.build_config(context)

    assert ("float", None) in config.packages
