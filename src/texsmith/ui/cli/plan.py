"""The render command's flags, after they have finished arguing with each other.

Most of ``texsmith``'s options are independent and travel straight into the
:class:`~texsmith.core.conversion.models.ConversionRequest`. A dozen are not:
they imply one another, they are overruled by the document's front matter, or
they mean different things depending on whether a template is in play. Those
are resolved here, once, in one order that can be read.

The resolution is pure — no console, no environment, no click context — so the
command keeps what is genuinely its own (parsing, early exits, printing) and
the precedence of a flag over a front-matter key is a statement rather than
the order two assignments happen to sit in.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from texsmith.core.conversion.policy import (
    deprecated_level,
    numbered_setting,
    strict_enabled,
)
from texsmith.core.templates import TemplateError, coerce_base_level


class RenderOptionError(ValueError):
    """A combination of options that cannot be honoured."""


@dataclass(frozen=True, slots=True)
class RenderPlan:
    """What the flags resolved to."""

    template: str | None
    build_pdf: bool
    classic_output: bool
    promote_title: bool
    base_level: int
    numbered: bool
    strict: bool
    deprecated: str
    #: Lines the command echoes to say what it decided on the caller's behalf.
    notices: tuple[str, ...] = field(default_factory=tuple)

    @property
    def template_selected(self) -> bool:
        """Whether a template wraps the output.

        Derived rather than stored: the command used to carry a separate
        ``template_selected`` boolean and set it in two places, which is two
        chances for it to disagree with ``template``.
        """
        return self.template is not None


def resolve_render_plan(
    *,
    front_matter: Mapping[str, Any] | None,
    template: str | None,
    build_pdf: bool,
    output: Path | None,
    output_format: str,
    print_context: bool,
    has_attributes: bool,
    no_title: bool,
    strip_heading: bool,
    no_promote_title: bool,
    no_promote_defaulted: bool,
    base_level: str | int,
    base_level_defaulted: bool,
    classic_output: bool,
    open_log: bool,
    make_deps: bool,
    strict: bool,
    deprecated: str | None,
    template_options: Mapping[str, Any] | None,
    ci_runner: bool = False,
) -> RenderPlan:
    """Reconcile the flags of one invocation against each other and the front matter."""
    notices: list[str] = []

    # -- what the document asks for, where it may ---------------------------
    strict = strict_enabled(front_matter, strict)
    deprecated_resolved = deprecated_level(front_matter, deprecated)
    numbered = numbered_setting(front_matter, template_options)

    # -- is a template in play? ---------------------------------------------
    # Everything below turns on this one question. ``template`` arrives already
    # resolved against ``press.template``: the command needs that answer before
    # this point, for ``--template-info`` and ``--template-scaffold``, which
    # report on a template and exit without rendering anything.

    # ``--print-context`` inspects the template context; it never builds.
    if print_context:
        build_pdf = False

    # ``--build`` names a template whatever the backend asked for.
    if template is None and build_pdf:
        template = "article"

    # An attribute configures a template, so there has to be one — judged here,
    # before ``-o x.pdf`` can imply a build and a build can imply a template.
    if has_attributes and template is None:
        raise RenderOptionError("--attribute can only be used together with --template.")

    # An output path that names a PDF is a request to build one.
    if output is not None and output.suffix.lower() == ".pdf" and not build_pdf:
        notices.append("Enabling --build to produce PDF output.")
        build_pdf = True

    # A PDF inferred from the output path names a template only for LaTeX —
    # where ``--build`` does so for Typst too, three lines above. The asymmetry
    # is the command's as it stands and is preserved, not tidied: unifying it
    # changes what ``--format typst -o out.pdf`` renders.
    if build_pdf and template is None and output_format != "typst":
        template = "article"
        # A CI runner has no terminal to stream latexmk into.
        if ci_runner:
            classic_output = True

    template_selected = template is not None

    # -- the title, which four flags claim ----------------------------------
    promote_title = not no_promote_title
    if no_title or strip_heading:
        # Both say the heading is not a title: one suppresses the metadata,
        # the other removes the heading, and neither leaves one to promote.
        promote_title = False
    elif not template_selected and no_promote_defaulted:
        # Without a template there is no title block to fill, so promotion is
        # off unless it was asked for.
        promote_title = False

    # -- the heading level the body starts at -------------------------------
    if not template_selected and base_level_defaulted:
        # A bare fragment is pasted into someone else's document, where the
        # top level is a section rather than a chapter.
        base_level = "section"
    try:
        resolved_base_level = int(coerce_base_level(base_level, allow_none=False) or 0)
    except TemplateError as exc:
        raise RenderOptionError(str(exc)) from exc

    # -- the flags that only mean something with --build --------------------
    for flag, enabled in (
        ("--classic-output", classic_output),
        ("--open-log", open_log),
        ("--makefile-deps", make_deps),
    ):
        if enabled and not build_pdf:
            raise RenderOptionError(f"{flag} can only be used together with --build.")

    if print_context and not template_selected:
        raise RenderOptionError("--print-context requires a template (front matter or --template).")

    return RenderPlan(
        template=template,
        build_pdf=build_pdf,
        classic_output=classic_output,
        promote_title=promote_title,
        base_level=resolved_base_level,
        numbered=numbered,
        strict=strict,
        deprecated=deprecated_resolved,
        notices=tuple(notices),
    )


__all__ = ["RenderOptionError", "RenderPlan", "resolve_render_plan"]
