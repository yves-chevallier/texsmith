from __future__ import annotations

from pathlib import Path
import textwrap

from texsmith.api.document import Document
from texsmith.fonts.html_scripts import wrap_scripts_in_html


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


def test_html_scripts_marked_for_foreign_runs(tmp_path: Path) -> None:
    source = _write(
        tmp_path,
        "sample.md",
        """
        ## Chinese Trad. (繁體中文)

        Traditional Chinese characters are used mainly in Taiwan, Hong Kong, and Macau by tens of millions of speakers of Mandarin, Cantonese, and other Sinitic languages.

        少無適俗韻，性本愛丘山。

        誤落塵網中，一去三十年。

        羈鳥戀舊林，池魚思故淵。

        開荒南野際，守拙歸園田。

        久在樊籠裡，復得返自然。

        ## Arabic

        Arabic is spoken by over 400 million people across the Middle East and North Africa and serves as the liturgical language of Islam.

        قِفا نَبْكِ مِنْ ذِكرَى حبيبٍ ومَنزِلِ
        بِسِقطِ اللِّوَى بَيْنَ الدَّخول فَحَوْمَلِ
        فَتُوضِحَ فَالمِقراةِ لَم يَعفُ رَسمُها
        لِما نَسَجَتها مِن جَنُوبٍ وشَمألِ
        تَرَى بَعَرَ الأرْآمِ في عَرَصاتِها
        وَقِيْعانِها كَأنَّهُ حَبُّ فُلْفُلِ

        ## Japanese

        Japanese is the national language of Japan and is spoken by over 125 million people, primarily within the country.

        月日は百代の過客にして、行きかふ年も旅人なり。

        舟に乗り、馬に乗りて、初秋の風に吹かれつつ、

        道のべの小草を分け、山川を越えて、

        心にかかる景色を求めて歩みゆく。
        """,
    )

    html = Document.from_markdown(source).html
    wrapped, usage, summary = wrap_scripts_in_html(html)

    assert '<span data-script="chinese">繁體中文</span>' in wrapped
    assert '<p data-script="chinese">少無適俗韻，性本愛丘山。</p>' in wrapped
    assert '<p data-script="arabics">قِفا نَبْكِ مِنْ ذِكرَى حبيبٍ ومَنزِلِ' in wrapped
    assert '<p data-script="japanese">月日は百代の過客にして、行きかふ年も旅人なり。</p>' in wrapped
    slugs = {entry.get("slug") for entry in usage}
    assert {"chinese", "arabics", "japanese"} <= slugs
    assert summary


#!/usr/bin/env python3
# ruff: noqa: RUF001
