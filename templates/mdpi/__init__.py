"""MDPI journal template integration for texsmith."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from texsmith.templates import TemplateError, WrappableTemplate
from texsmith.latex.utils import escape_latex_chars


_PACKAGE_ROOT = Path(__file__).parent.resolve()


class Template(WrappableTemplate):
    """Expose the MDPI template."""

    _DEFAULT_OPTIONS = ["journal", "article", "submit", "pdftex", "moreauthors"]
    _NOTE_COMMANDS = [
        "firstnote",
        "secondnote",
        "thirdnote",
        "fourthnote",
        "fifthnote",
        "sixthnote",
        "seventhnote",
        "eighthnote",
    ]

    def __init__(self) -> None:
        try:
            super().__init__(_PACKAGE_ROOT)
        except TemplateError as exc:
            raise TemplateError(f"Failed to initialise MDPI template: {exc}") from exc

    def prepare_context(
        self,
        latex_body: str,
        *,
        overrides: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = super().prepare_context(latex_body, overrides=overrides)
        self._apply_metadata(context)

        options = self._build_documentclass_options(context)
        context["documentclass_options"] = ",".join(options) if options else ""

        keywords = self._normalise_keywords(context.get("keywords"))
        context["keywords"] = keywords
        context["keywords_joined"] = "; ".join(keywords)

        abstract_value = self._coerce_string(context.get("abstract"))
        context["abstract"] = abstract_value or ""

        (
            author_block,
            author_names,
            author_citation,
            affiliation_entries,
            correspondence_entry,
            orcid_commands,
            first_note,
            second_note,
            extra_notes,
        ) = self._normalise_authors(
            context.get("authors"),
            context.get("affiliations"),
            context.get("correspondence"),
        )

        if author_block:
            context["author_block"] = author_block
        else:
            fallback_author = self._coerce_string(context.get("author"))
            context["author_block"] = escape_latex_chars(fallback_author or "John Doe")

        context["author_names"] = author_names
        context["author_citation"] = author_citation
        context["affiliation_entries"] = affiliation_entries
        context["correspondence_entry"] = correspondence_entry
        context["orcid_commands"] = orcid_commands
        context["first_note"] = first_note
        context["second_note"] = second_note
        context["extra_notes"] = extra_notes

        if not self._coerce_string(context.get("title_citation")):
            context["title_citation"] = context.get("title", "")
        if not self._coerce_string(context.get("short_title")):
            context["short_title"] = context.get("title", "")

        context.setdefault("acknowledgments", "")
        context.setdefault("funding", "")
        context.setdefault("conflicts", "")
        context.setdefault("data_availability", "")

        other_sections = self._normalise_sections(context.get("sections"))
        context["other_sections"] = other_sections

        bibliography_value = self._coerce_string(context.get("bibliography"))
        context["bibliography"] = bibliography_value or "References/references"

        bibliography_style = self._coerce_string(context.get("bibliography_style"))
        context["bibliography_style"] = bibliography_style or ""

        return context

    def _apply_metadata(self, context: dict[str, Any]) -> None:
        raw_meta = context.get("meta")
        if isinstance(raw_meta, Mapping):
            meta_payload: Mapping[str, Any] = raw_meta.get("meta", raw_meta)
        else:
            meta_payload = {}

        title = self._coerce_string(meta_payload.get("title"))
        if title:
            context["title"] = escape_latex_chars(title)

        title_citation = self._coerce_string(meta_payload.get("title_citation"))
        if title_citation:
            context["title_citation"] = escape_latex_chars(title_citation)

        short_title = self._coerce_string(meta_payload.get("short_title"))
        if short_title:
            context["short_title"] = escape_latex_chars(short_title)

        abstract_value = self._coerce_string(meta_payload.get("abstract"))
        if abstract_value:
            context["abstract"] = escape_latex_chars(abstract_value)

        keywords = meta_payload.get("keywords")
        if keywords is not None:
            context["keywords"] = keywords

        context["authors"] = meta_payload.get("authors") or meta_payload.get("author")
        context["affiliations"] = meta_payload.get("affiliations", [])
        context["correspondence"] = meta_payload.get("correspondence", [])

        for key in (
            "acknowledgments",
            "funding",
            "conflicts",
            "data_availability",
            "featured_application",
            "dataset",
            "dataset_license",
            "key_contribution",
            "simple_summary",
            "conference",
            "encyclopedia_def",
            "featured_graphic",
        ):
            value = self._coerce_string(meta_payload.get(key))
            if value:
                context[key] = escape_latex_chars(value)

        sections = meta_payload.get("sections")
        if sections is not None:
            context["sections"] = sections

        journal = self._coerce_string(meta_payload.get("journal"))
        if journal:
            context["journal"] = journal

        stage = self._coerce_string(meta_payload.get("stage"))
        if stage:
            context["stage"] = stage

        manuscript_type = self._coerce_string(meta_payload.get("manuscript_type"))
        if manuscript_type:
            context["manuscript_type"] = manuscript_type

        more_authors = meta_payload.get("more_authors")
        if more_authors is not None:
            context["more_authors"] = self._coerce_bool(more_authors)

        class_options = meta_payload.get("class_options")
        if class_options is not None:
            context["class_options"] = class_options

        bibliography = self._coerce_string(meta_payload.get("bibliography"))
        if bibliography:
            context["bibliography"] = bibliography

        bibliography_style = self._coerce_string(meta_payload.get("bibliography_style"))
        if bibliography_style:
            context["bibliography_style"] = bibliography_style

        context.pop("meta", None)

    def _build_documentclass_options(self, context: Mapping[str, Any]) -> list[str]:
        raw_options = self._split_options(context.get("class_options"))
        options = [opt for opt in raw_options if opt]

        journal = self._coerce_string(context.get("journal"))
        if journal:
            if options:
                options[0] = journal
            else:
                options.append(journal)

        manuscript_type = self._coerce_string(context.get("manuscript_type"))
        if manuscript_type and manuscript_type not in options:
            if len(options) >= 1:
                options.insert(1, manuscript_type)
            else:
                options.append(manuscript_type)

        stage = self._coerce_string(context.get("stage"))
        if stage and stage not in options:
            options.append(stage)

        if "pdftex" not in options:
            options.append("pdftex")

        more_authors = context.get("more_authors")
        moreauthors_flag = (
            self._coerce_bool(more_authors)
            if more_authors is not None
            else ("moreauthors" in options or not options)
        )
        options = [opt for opt in options if opt != "moreauthors"]
        if moreauthors_flag:
            options.append("moreauthors")

        if not options:
            options = list(self._DEFAULT_OPTIONS)

        # Remove duplicates preserving order
        unique: list[str] = []
        for option in options:
            if option not in unique:
                unique.append(option)
        return unique

    def _normalise_keywords(self, payload: Any) -> list[str]:
        if payload is None:
            return []
        if isinstance(payload, str):
            candidates = [item.strip() for item in payload.replace(";", ",").split(",")]
        elif isinstance(payload, Mapping):
            candidates = [
                self._coerce_string(value)
                for value in payload.values()
                if self._coerce_string(value)
            ]
        elif isinstance(payload, Iterable):
            candidates = [self._coerce_string(item) for item in payload]
        else:
            candidates = []

        return [escape_latex_chars(item) for item in candidates if item]

    def _normalise_sections(self, payload: Any) -> list[dict[str, str]]:
        if not payload:
            return []

        sections: list[dict[str, str]] = []
        if isinstance(payload, Mapping):
            iterable = payload.items()
        elif isinstance(payload, Iterable) and not isinstance(payload, (str, bytes)):
            iterable = enumerate(payload)
        else:
            return sections

        for key, value in iterable:
            if isinstance(value, Mapping):
                title = self._coerce_string(value.get("title") or key)
                content = self._coerce_string(value.get("content"))
            else:
                title = self._coerce_string(key)
                content = self._coerce_string(value)
            if not title or not content:
                continue
            sections.append(
                {
                    "title": escape_latex_chars(title),
                    "content": escape_latex_chars(content),
                }
            )
        return sections

    def _normalise_authors(
        self,
        payload: Any,
        extra_affiliations: Any | None = None,
        correspondence_payload: Any | None = None,
    ) -> tuple[
        str,
        str,
        str,
        list[dict[str, Any]],
        str | None,
        list[dict[str, str]],
        str | None,
        str | None,
        list[dict[str, str]],
    ]:
        if payload is None:
            return ("", "", "", [], None, [], None, None, [])

        if isinstance(payload, Mapping):
            candidates = [payload]
        elif isinstance(payload, Iterable) and not isinstance(payload, (str, bytes)):
            candidates = list(payload)
        elif isinstance(payload, str):
            name = self._coerce_string(payload)
            if not name:
                return ("", "", "", [], None, [], None, None, [])
            escaped_name = escape_latex_chars(name)
            return (
                escaped_name,
                escaped_name,
                escaped_name,
                [],
                None,
                [],
                None,
                None,
                [],
            )
        else:
            return ("", "", "", [], None, [], None, None, [])

        affiliation_registry: dict[str, dict[str, Any]] = {}
        affiliation_order: list[str] = []

        def register_affiliation(spec: Any) -> str:
            key, entry = self._coerce_affiliation(spec)
            if key in affiliation_registry:
                return affiliation_registry[key]["id"]
            identifier = str(len(affiliation_registry) + 1)
            entry["id"] = identifier
            entry.setdefault("emails", [])
            affiliation_registry[key] = entry
            affiliation_order.append(key)
            return identifier

        if extra_affiliations is not None:
            if isinstance(extra_affiliations, Mapping):
                iterable = extra_affiliations.values()
            elif isinstance(extra_affiliations, Iterable) and not isinstance(
                extra_affiliations, (str, bytes)
            ):
                iterable = extra_affiliations
            else:
                iterable = [extra_affiliations]
            for item in iterable:
                register_affiliation(item)

        author_entries: list[dict[str, Any]] = []
        correspondences: list[str] = []
        notes: list[str] = []

        for item in candidates:
            if isinstance(item, str):
                name_value = self._coerce_string(item)
                if not name_value:
                    continue
                escaped_name = escape_latex_chars(name_value)
                author_entries.append(
                    {
                        "name": escaped_name,
                        "indices": [],
                        "email": None,
                        "orcid": None,
                        "short_name": self._extract_short_name(escaped_name),
                        "citation": self._format_citation(escaped_name),
                        "corresponding": False,
                        "note": None,
                    }
                )
                continue

            if not isinstance(item, Mapping):
                continue

            name_value = self._coerce_string(
                item.get("name")
                or item.get("full_name")
                or item.get("fullname")
                or item.get("display")
            )
            if not name_value:
                continue

            escaped_name = escape_latex_chars(name_value)
            affiliations_raw = item.get("affiliations") or item.get("affiliation")
            indices: list[str] = []
            for spec in self._iter_affiliations(affiliations_raw):
                idx = register_affiliation(spec)
                if idx not in indices:
                    indices.append(idx)

            email_value = self._coerce_string(item.get("email"))
            orcid_value = self._coerce_string(item.get("orcid"))
            corresponding_flag = item.get("corresponding")
            if corresponding_flag is None:
                corresponding_flag = item.get("corresponding_author")
            corresponding = self._coerce_bool(corresponding_flag)

            note_value = self._coerce_string(
                item.get("note")
                or item.get("author_note")
                or item.get("footnote")
                or item.get("equal_contribution")
            )

            if email_value and indices:
                for idx in indices:
                    key = next(
                        (k for k, v in affiliation_registry.items() if v["id"] == idx),
                        None,
                    )
                    if key is not None:
                        affiliation_registry[key].setdefault("emails", [])
                        escaped_email = escape_latex_chars(email_value)
                        if escaped_email not in affiliation_registry[key]["emails"]:
                            affiliation_registry[key]["emails"].append(escaped_email)

            if corresponding and email_value:
                correspondences.append(f"{escaped_name} ({escape_latex_chars(email_value)})")
            elif corresponding:
                correspondences.append(escaped_name)

            if note_value:
                notes.append(escape_latex_chars(note_value))

            author_entries.append(
                {
                    "name": escaped_name,
                    "indices": indices,
                    "email": escape_latex_chars(email_value) if email_value else None,
                    "orcid": escape_latex_chars(orcid_value) if orcid_value else None,
                    "short_name": self._extract_short_name(escaped_name),
                    "citation": self._format_citation(escaped_name),
                    "corresponding": corresponding,
                    "note": escape_latex_chars(note_value) if note_value else None,
                }
            )

        if not author_entries:
            return ("", "", "", [], None, [], None, None, [])

        # Build author macros
        orcid_commands: list[dict[str, str]] = []
        author_parts: list[str] = []
        names_list: list[str] = []
        citations: list[str] = []

        for index, entry in enumerate(author_entries):
            indices = list(entry["indices"])
            if entry["corresponding"]:
                indices.append("*")
            superscript = ""
            if indices:
                superscript = f"$^{{{','.join(indices)}}}$"

            orcid_macro = ""
            if entry["orcid"]:
                suffix = self._alphabetic_suffix(len(orcid_commands))
                orcid_commands.append(
                    {
                        "command": suffix,
                        "identifier": entry["orcid"],
                    }
                )
                orcid_macro = f"\\orcid{suffix}{{}}"

            author_parts.append(f"{entry['name']} {superscript}{orcid_macro}")
            names_list.append(entry["name"])
            citations.append(entry["citation"])

        if len(author_parts) == 1:
            author_block = author_parts[0].strip()
        else:
            author_block = ", ".join(author_parts[:-1]) + " and " + author_parts[-1]

        author_names = ", ".join(names_list[:-1]) + (
            (" and " + names_list[-1]) if len(names_list) > 1 else names_list[0]
        )

        author_citation = "; ".join(citations)

        affiliation_entries = [
            {
                "id": affiliation_registry[key]["id"],
                "text": affiliation_registry[key]["text"],
                "emails": ", ".join(affiliation_registry[key].get("emails", [])),
            }
            for key in affiliation_order
        ]

        correspondence_entry = None
        if correspondence_payload:
            if isinstance(correspondence_payload, Mapping):
                iterable = correspondence_payload.values()
            elif isinstance(correspondence_payload, Iterable) and not isinstance(
                correspondence_payload, (str, bytes)
            ):
                iterable = correspondence_payload
            else:
                iterable = [correspondence_payload]
            for item in iterable:
                text = self._coerce_string(item)
                if text:
                    correspondences.append(escape_latex_chars(text))

        if correspondences:
            correspondence_entry = "Correspondence: " + "; ".join(correspondences)

        first_note = notes[0] if len(notes) >= 1 else None
        second_note = notes[1] if len(notes) >= 2 else None
        extra_notes: list[dict[str, str]] = []
        for note_index, note in enumerate(notes[2:], start=2):
            if note_index >= len(self._NOTE_COMMANDS):
                break
            extra_notes.append({"command": f"\\{self._NOTE_COMMANDS[note_index]}", "text": note})

        return (
            author_block,
            author_names,
            author_citation,
            affiliation_entries,
            correspondence_entry,
            orcid_commands,
            first_note,
            second_note,
            extra_notes,
        )

    def _coerce_affiliation(self, payload: Any) -> tuple[str, dict[str, Any]]:
        if isinstance(payload, Mapping):
            fields: list[str] = []
            components: list[str] = []
            for key, value in payload.items():
                coerced = self._coerce_string(value)
                if not coerced:
                    continue
                escaped = escape_latex_chars(coerced)
                fields.append(f"{key}:{escaped}")
                components.append(escaped)
            if components:
                return ("|".join(fields), {"text": ", ".join(components)})

        coerced = self._coerce_string(payload)
        if not coerced:
            return ("", {"text": ""})
        escaped = escape_latex_chars(coerced)
        return (escaped, {"text": escaped})

    def _iter_affiliations(self, payload: Any) -> Iterable[Any]:
        if payload is None:
            return []
        if isinstance(payload, (str, Mapping)):
            return [payload]
        if isinstance(payload, Iterable) and not isinstance(payload, (str, bytes)):
            return list(payload)
        return [payload]

    def _split_options(self, payload: Any) -> list[str]:
        if payload is None:
            return []
        if isinstance(payload, str):
            return [item.strip() for item in payload.split(",") if item.strip()]
        if isinstance(payload, Iterable):
            result = []
            for item in payload:
                token = self._coerce_string(item)
                if token:
                    result.append(token)
            return result
        return [self._coerce_string(payload) or ""]

    def _alphabetic_suffix(self, index: int) -> str:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if index < len(alphabet):
            return alphabet[index]

        base = len(alphabet)
        suffix = ""
        idx = index
        while True:
            idx, remainder = divmod(idx, base)
            suffix = alphabet[remainder] + suffix
            if idx == 0:
                break
            idx -= 1
        return suffix

    def _extract_short_name(self, name: str) -> str:
        tokens = [token.strip() for token in name.split() if token.strip()]
        if not tokens:
            return name
        initials = [token[0].upper() + "." for token in tokens[:-1]]
        last = tokens[-1]
        return f"{' '.join(initials)} {last}".strip()

    def _format_citation(self, name: str) -> str:
        tokens = [token.strip() for token in name.split() if token.strip()]
        if not tokens:
            return name
        last = tokens[-1]
        initials = "".join(token[0].upper() + "." for token in tokens[:-1])
        if initials:
            return f"{last}, {initials}"
        return last

    def _coerce_string(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            candidate = value.strip()
        else:
            candidate = str(value).strip()
        return candidate or None

    def _coerce_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            token = value.strip().lower()
            if token in {"false", "no", "0", "n", ""}:
                return False
            if token in {"true", "yes", "1", "y"}:
                return True
            return False
        return bool(value)


__all__ = ["Template"]
