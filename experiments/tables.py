from __future__ import annotations

from collections.abc import Sequence
from html import escape
from typing import Any, Literal
import warnings

from bs4 import BeautifulSoup
import markdown
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
import yaml


class TableConfigWarning(UserWarning):
    """Warn about non-fatal issues in table configuration."""


def warn_extra_keys(cls: type[BaseModel], values: Any, context: str) -> Any:
    if not isinstance(values, dict):
        return values
    allowed = set(cls.model_fields)
    for field in cls.model_fields.values():
        if field.alias:
            allowed.add(field.alias)
    extras = sorted(set(values) - allowed)
    if extras:
        warnings.warn(
            f"Unsupported key(s) in {context}: {', '.join(extras)}",
            TableConfigWarning,
            stacklevel=4,
        )
    return values


class TablePrintOptions(BaseModel):
    orientation: str | None = None
    resize: bool | None = None

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def warn_unknown(cls, values: Any) -> Any:
        return warn_extra_keys(cls, values, "print options")


class TableColumn(BaseModel):
    alignment: str | None = None
    width: str | None = None

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def warn_unknown(cls, values: Any) -> Any:
        return warn_extra_keys(cls, values, "column definition")


class TableRowSpec(BaseModel):
    height: str | None = None
    alignment: str | None = None
    span: Sequence[int | str] | None = None

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def warn_unknown(cls, values: Any) -> Any:
        return warn_extra_keys(cls, values, "row specification")


class TableData(BaseModel):
    type: Literal["embedded"] = "embedded"
    data: list[list[Any | None]]

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def coerce_embedded(cls, values: Any) -> Any:
        if isinstance(values, list):
            return {"type": "embedded", "data": values}
        if isinstance(values, dict):
            return warn_extra_keys(cls, values, "table data")
        raise TypeError("`data` must be a list of rows or a mapping with type/data.")

    @field_validator("data", mode="before")
    @classmethod
    def ensure_rows(cls, value: Any) -> Any:
        if not isinstance(value, list):
            raise TypeError("`data` must be a list of rows.")
        coerced: list[list[Any | None]] = []
        for index, row in enumerate(value):
            if row is None:
                coerced.append([])
                continue
            if not isinstance(row, list):
                raise TypeError(f"Row {index} must be a list.")
            coerced.append(row)
        return coerced


class TableSpec(BaseModel):
    width: str | None = None
    caption: str | None = None
    label: str | None = None
    header: bool = False
    print_options: TablePrintOptions | None = Field(default=None, alias="print")
    columns: list[TableColumn] = Field(default_factory=list)
    rows: list[TableRowSpec] = Field(default_factory=list)
    data: TableData

    model_config = ConfigDict(validate_by_name=True, extra="forbid")


CELL_MARKDOWN = markdown.Markdown(
    extensions=["attr_list"],
    output_format="html5",
)


def parse_table_config(source: str) -> TableSpec:
    try:
        loaded = yaml.safe_load(source)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in table fence: {exc}") from exc
    if loaded is None:
        raise ValueError("Empty table configuration.")
    try:
        return TableSpec.model_validate(loaded)
    except ValidationError as exc:
        raise ValueError(f"Invalid table configuration: {exc}") from exc


def markdown_inline_to_html(value: str) -> str:
    CELL_MARKDOWN.reset()
    rendered = CELL_MARKDOWN.convert(value)
    if rendered.startswith("<p>") and rendered.endswith("</p>"):
        return rendered[3:-4]
    return rendered


def apply_column_style(column: TableColumn) -> str:
    style_parts: list[str] = []
    if column.alignment and column.alignment != "auto":
        style_parts.append(f"text-align: {column.alignment};")
    if column.width and column.width != "auto":
        style_parts.append(f"width: {column.width};")
    return " ".join(style_parts)


def render_table_html(spec: TableSpec) -> str:
    soup = BeautifulSoup("", "html.parser")
    table_tag = soup.new_tag("table")

    table_tag["class"] = table_tag.get("class", []) + ["ycr-table"]

    if spec.width == "full":
        table_tag["style"] = "width: 100%;"
    elif spec.width and spec.width != "auto":
        table_tag["style"] = f"width: {spec.width};"

    if spec.print_options:
        for key, value in spec.print_options.model_dump(exclude_none=True).items():
            attr_value = str(value).lower()
            table_tag.attrs[f"data-print-{key}"] = attr_value
            table_tag.attrs[f"data-latex-{key}"] = attr_value

    if spec.columns:
        colgroup = soup.new_tag("colgroup")
        for column in spec.columns:
            col_tag = soup.new_tag("col")
            style = apply_column_style(column)
            if style:
                col_tag["style"] = style
            colgroup.append(col_tag)
        table_tag.append(colgroup)

    caption_html: str | None = None
    if spec.caption:
        caption_tag = soup.new_tag("caption")
        caption_html = markdown_inline_to_html(spec.caption)
        caption_fragment = BeautifulSoup(caption_html, "html.parser")
        for child in caption_fragment.contents:
            caption_tag.append(child)
        table_tag.append(caption_tag)

    data_rows = spec.data.data
    header_rows = data_rows[:1] if spec.header and data_rows else []
    body_rows = data_rows[1:] if spec.header and data_rows else data_rows

    if header_rows:
        thead = soup.new_tag("thead")
        header_spec = spec.rows[0] if spec.rows else None
        for row in header_rows:
            thead.append(
                render_table_row(soup, row, spec.columns, header=True, spec_row=header_spec)
            )
        table_tag.append(thead)

    tbody = soup.new_tag("tbody")
    for index, row in enumerate(body_rows):
        spec_row = (
            spec.rows[index + (1 if header_rows else 0)]
            if index + (1 if header_rows else 0) < len(spec.rows)
            else None
        )
        tbody.append(render_table_row(soup, row, spec.columns, header=False, spec_row=spec_row))
    table_tag.append(tbody)

    if spec.caption or spec.label:
        figure_tag = soup.new_tag("figure")
        if spec.label:
            figure_tag["id"] = spec.label
        figure_tag.append(table_tag)
        if caption_html:
            figcaption_tag = soup.new_tag("figcaption")
            figcaption_fragment = BeautifulSoup(caption_html, "html.parser")
            for child in figcaption_fragment.contents:
                figcaption_tag.append(child)
            figure_tag.append(figcaption_tag)
        return str(figure_tag)

    return str(table_tag)


def render_table_row(
    soup: BeautifulSoup,
    cells: list[Any | None],
    columns: list[TableColumn],
    *,
    header: bool,
    spec_row: TableRowSpec | None,
) -> Any:
    tag_name = "th" if header else "td"
    tr_tag = soup.new_tag("tr")

    if spec_row:
        if spec_row.height and spec_row.height != "auto":
            tr_tag["style"] = f"height: {spec_row.height};"
        if spec_row.alignment and spec_row.alignment != "auto":
            current_style = tr_tag.get("style", "")
            tr_tag["style"] = (current_style + f" vertical-align: {spec_row.alignment};").strip()
        if spec_row.span:
            tr_tag["data-span"] = ",".join(str(item) for item in spec_row.span)

    for index, raw_cell in enumerate(cells):
        cell_tag = soup.new_tag(tag_name)
        column_style = apply_column_style(columns[index]) if index < len(columns) else ""
        if column_style:
            cell_tag["style"] = column_style

        if raw_cell is None:
            cell_content = ""
        elif isinstance(raw_cell, (int, float, bool)):
            cell_content = str(raw_cell)
        else:
            cell_content = str(raw_cell)

        if cell_content:
            rendered = markdown_inline_to_html(cell_content)
            fragment = BeautifulSoup(rendered, "html.parser")
            for child in fragment.contents:
                cell_tag.append(child)
        tr_tag.append(cell_tag)

    return tr_tag


def table_fence_format(
    source: str, language: str, css_class: str, options: dict, md: markdown.Markdown, **kwargs: Any
) -> str:
    try:
        spec = parse_table_config(source)
    except ValueError as exc:
        return f'<pre class="table-error">{escape(str(exc))}</pre>'
    return render_table_html(spec)


TEST_MD = r"""
# Test Table

```table
width: full
caption: Sample Table
label: tbl:sample
header: true
print:
  orientation: landscape
  resize: true
columns:
  - alignment: left
    width: auto
  - alignment: center
    width: 2cm
  - alignment: right
    width: auto
rows:
  - height: auto
    alignment: top
    span: [2, auto]
data:
  - [Cell 1, Cell 2, "**bold** foo"]
  - [Cell 4, null , Cell 6]
  - [Cell 7, Cell 8, null]
```

"""

extensions = [
    "attr_list",
    "pymdownx.superfences",
]

extension_configs = {
    "pymdownx.superfences": {
        "custom_fences": [
            {
                "name": "table",
                "class": "tex-table",
                "format": table_fence_format,
            }
        ]
    }
}

md = markdown.Markdown(
    extensions=extensions,
    extension_configs=extension_configs,
    output_format="html5",
)
body = md.convert(TEST_MD)

print(body)
