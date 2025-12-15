"""Helpers to fetch Noto font files on demand."""

from __future__ import annotations

from pathlib import Path
import urllib.request

from texsmith.fonts.cache import FontCache
from texsmith.fonts.constants import (
    CJK_ALIASES,
    filename_base,
    guess_cjk_path,
    style_suffix,
)
from texsmith.fonts.logging import FontPipelineLogger


class NotoFontDownloader:
    """Download individual Noto font files into the font cache."""

    def __init__(
        self,
        *,
        cache: FontCache | None = None,
        logger: FontPipelineLogger | None = None,
    ):
        self.cache = cache or FontCache()
        self.logger = logger or FontPipelineLogger()
        self.fonts_dir = self.cache.path("fonts")

    def _download(self, url: str, dest: Path) -> bool:
        try:
            with urllib.request.urlopen(url) as response:
                data = response.read()
        except Exception:
            return False
        if len(data) < 1024:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest.write_bytes(data)
        except Exception:
            return False
        return True

    def _download_font_file(self, filename: str, dir_base: str | None, dest: Path) -> bool:
        base = filename_base(filename)
        alias = CJK_ALIASES.get(base)
        if alias:
            real_base, rel_dir = alias
            real_filename = filename.replace(base, real_base, 1)
            cjk_url = f"https://raw.githubusercontent.com/notofonts/noto-cjk/main/{rel_dir}{real_filename}"
            if self._download(cjk_url, dest):
                return True

        dir_part = dir_base or base
        url_candidates = [
            f"https://cdn.jsdelivr.net/gh/notofonts/notofonts.github.io/fonts/{dir_part}/unhinted/otf/{filename}",
            f"https://raw.githubusercontent.com/notofonts/notofonts.github.io/master/fonts/{dir_part}/unhinted/otf/{filename}",
            f"https://raw.githubusercontent.com/notofonts/notofonts.github.io/master/fonts/{dir_part}/full/otf/{filename}",
        ]

        if "CJK" in filename or alias:
            guess = guess_cjk_path(filename)
            if guess:
                url_candidates.append(
                    f"https://raw.githubusercontent.com/notofonts/noto-cjk/main/{guess}{filename}"
                )

        for url in url_candidates:
            if self._download(url, dest):
                return True
        return dest.exists()

    def ensure(
        self,
        *,
        font_name: str,
        styles: list[str] | tuple[str, ...] | set[str] | None,
        extension: str,
        dir_base: str | None,
    ) -> None:
        styles = list(styles or ["regular", "bold"])
        for style in styles:
            suffix = style_suffix(style)
            filename = f"{font_name}-{suffix}{extension}"
            dest = self.fonts_dir / filename
            if dest.exists():
                continue
            if self._download_font_file(filename, dir_base, dest):
                self.logger.info("Downloaded font %s", filename)
                continue
            # Last-resort fallback to plain NotoSans to avoid missing files.
            if font_name != "NotoSans":
                fallback_filename = f"NotoSans-{suffix}{extension}"
                fallback_dest = self.fonts_dir / fallback_filename
                if fallback_dest.exists():
                    continue
                if self._download_font_file(fallback_filename, "noto-sans", fallback_dest):
                    self.logger.info("Downloaded fallback font %s", fallback_filename)


__all__ = ["NotoFontDownloader"]
