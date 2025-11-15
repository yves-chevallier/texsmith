"""Configuration models used by the LaTeX renderer.

CommonConfig

`build_dir` (`Path | None`)
: Base directory for LaTeX artifacts. Provide an absolute or project-relative
  path to override the default export root that books inherit when they do not
  specify one.

`save_html` (`bool`)
: Persist the intermediate HTML render next to the PDF to aid troubleshooting
  before LaTeX compilation.

`mermaid_config` (`Path | None`)
: Path to a Mermaid configuration file. Point to a `.json` or `.mermaid`
  document to customise diagram rendering.

`project_dir` (`Path | None`)
: MkDocs project root used to resolve relative paths when copying additional
  assets.

: BCP 47 language code forwarded to LaTeX for hyphenation, translations, and
: metadata localisation.

`legacy_latex_accents` (`bool`)
: When `True`, escape accented characters, ligatures, and typographic punctuation
  using legacy LaTeX macros. When `False`, keep Unicode glyphs compatible with
  LuaLaTeX/XeLaTeX (default).

`language` (`str | None`)
: BCP 47 language code forwarded to LaTeX for hyphenation, translations, and
  metadata localisation.

CoverConfig

`name` (`str`)
: Identifier of the cover template to apply. The value must match a template
  declared in the cover bundle.

`color` (`str | None`)
: Primary colour override applied by the cover template.

`logo` (`str | None`)
: Project-relative path to a logo asset displayed on the cover.

BookConfig

`root` (`str | None`)
: Navigation entry treated as the starting point for the book. Use it when the
  root differs from the first MkDocs page.

`title` (`str | None`)
: Title displayed on the cover and in output metadata. Falls back to `site_name`
  when omitted.

`subtitle` (`str | None`)
: Optional subtitle appended to the cover and metadata.

`author` (`str | None`)
: Primary author string rendered in the book metadata.

`year` (`int | None`)
: Publication year to freeze in the output when `site_date` is not supplied.

`email` (`str | None`)
: Contact address printed in the credits.

`folder` (`Path | None`)
: Output directory for the rendered book. Defaults to a slug of the title when
  not provided.

`frontmatter` (`list[str]`)
: MkDocs page titles moved before the main matter.

`backmatter` (`list[str]`)
: MkDocs page titles grouped into the appendices.

`base_level` (`int`)
: Heading offset applied to align section numbering with the template
  expectations.

`copy_files` (`dict[str, str]`)
: Mapping of glob patterns to destination paths for copying additional assets
  alongside the book.

`index_is_foreword` (`bool`)
: Treat the `index` page as a foreword, typically removing numbering.

`drop_title_index` (`bool`)
: Suppress the `index` page heading when it acts as a foreword.

`cover` (`CoverConfig`)
: Nested configuration controlling the book cover.

LaTeXConfig

`enabled` (`bool`)
: Toggle LaTeX generation without discarding configuration.

`books` (`list[BookConfig]`)
: Collection of books to produce, inheriting defaults from `CommonConfig`.

`clean_assets` (`bool`)
: Remove stale assets from `build_dir` to avoid accumulating unused files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from slugify import slugify


class CommonConfig(BaseModel):
    """Common configuration propagated to each book."""

    model_config = ConfigDict(extra="forbid")

    build_dir: Path | None = None
    save_html: bool = False
    mermaid_config: Path | None = None
    project_dir: Path | None = None
    language: str | None = None
    legacy_latex_accents: bool = False


class CoverConfig(BaseModel):
    """Metadata used to render book covers."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="circles", description="Cover template name")
    color: str | None = Field(default="black", description="Primary color")
    logo: str | None = Field(default=None, description="Logo path")


class BookConfig(CommonConfig):
    """Configuration for an individual book."""

    root: str | None = None
    title: str | None = None
    subtitle: str | None = None
    author: str | None = None
    year: int | None = None
    email: str | None = None
    folder: Path | None = None
    frontmatter: list[str] = Field(default_factory=list)
    backmatter: list[str] = Field(default_factory=list)
    base_level: int = -2
    copy_files: dict[str, str] = Field(default_factory=dict)
    index_is_foreword: bool = False
    drop_title_index: bool = False
    cover: CoverConfig = Field(default_factory=CoverConfig)

    @model_validator(mode="after")
    def set_folder(self) -> BookConfig:
        """Populate the output folder from the book title when missing."""
        if self.folder is None and self.title:
            self.folder = Path(slugify(self.title, separator="-"))
        return self


class LaTeXConfig(CommonConfig):
    """Configuration for LaTeX taken from ``mkdocs.yml``."""

    enabled: bool = True
    books: list[BookConfig] = Field(default_factory=lambda: [BookConfig()])
    clean_assets: bool = True

    @model_validator(mode="after")
    def propagate(self) -> LaTeXConfig:
        """Propagate common values to nested book configurations."""
        to_propagate = (
            "build_dir",
            "mermaid_config",
            "save_html",
            "project_dir",
            "language",
        )
        for book in self.books:
            for key in to_propagate:
                if getattr(book, key) is None:
                    setattr(book, key, getattr(self, key))
        return self

    def add_extra(self, **extra_data: Any) -> None:
        """Allow consumers to attach additional attributes at runtime."""
        for key, value in extra_data.items():
            object.__setattr__(self, key, value)
