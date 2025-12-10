from texsmith.fonts.cache import FontCache
from texsmith.fonts.coverage import NotoCoverage
from texsmith.fonts.fallback import FallbackEntry, FallbackIndex, FallbackRepository
from texsmith.fonts.pipeline import FallbackManager
from texsmith.fonts.ucharclasses import UCharClass


def test_fallback_cache_rebuilds_when_signature_differs(tmp_path, monkeypatch) -> None:
    cache = FontCache(root=tmp_path / "fonts-cache")
    repo = FallbackRepository(cache=cache)

    # Seed a stale cache that maps everything to the wrong font.
    stale_entry = FallbackEntry(
        name="Arabic",
        start=0x0600,
        end=0x06FF,
        group="Arabics",
        font={"name": "NotoSansSC", "extension": ".otf", "styles": ["regular"]},
    )
    repo.save(FallbackIndex([stale_entry]), signature="stale")

    # Force the pipeline to prefer a correct Arabic font when rebuilding.
    monkeypatch.setattr(
        "texsmith.fonts.pipeline.generate_ucharclasses_data",
        lambda cache=None, logger=None: [  # noqa: ARG005
            UCharClass(name="Arabic", start=0x0600, end=0x06FF, group="Arabics")
        ],
    )
    monkeypatch.setattr(
        "texsmith.fonts.pipeline.generate_noto_metadata",
        lambda cache=None, logger=None: [  # noqa: ARG005
            NotoCoverage(
                family="Noto Kufi Arabic",
                ranges=((0x0600, 0x06FF),),
                file_base="NotoKufiArabic",
                dir_base="NotoKufiArabic",
                styles=("regular", "bold"),
            )
        ],
    )

    manager = FallbackManager(cache=cache)
    plan = manager.scan_text("السلام", strategy="by_class")

    font_names = {entry["font"]["name"] for entry in plan.summary if entry.get("font")}
    assert "NotoKufiArabic" in font_names
    assert "NotoSansSC" not in font_names


def test_fallback_uses_cached_index_without_rebuilding(monkeypatch) -> None:
    cached_index = FallbackIndex(
        [
            FallbackEntry(
                name="Arabic",
                start=0x0600,
                end=0x06FF,
                group="Arabics",
                font={"name": "CachedFont", "extension": ".otf", "styles": ["regular"]},
            )
        ]
    )

    monkeypatch.setattr(
        FallbackRepository,
        "load",
        lambda self, expected_signature=None: cached_index,  # noqa: ARG005
    )
    monkeypatch.setattr(
        FallbackRepository,
        "load_or_build",
        lambda self, entries: (_ for _ in ()).throw(AssertionError("should not rebuild")),  # noqa: ARG005
    )

    manager = FallbackManager(cache=FontCache(root=None))
    plan = manager.scan_text("سلام", strategy="by_class")
    names = {entry["font"]["name"] for entry in plan.summary if entry.get("font")}
    assert "CachedFont" in names
