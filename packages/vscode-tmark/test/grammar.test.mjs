import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { tokenize } from "./tokenize.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const sample = readFileSync(join(here, "sample.md"), "utf8");

/** Find the token holding `text` on the first line matching `lineRe`. */
function token(lines, lineRe, text) {
  const src = sample.split(/\r?\n/);
  const i = src.findIndex((l) => lineRe.test(l));
  assert.notEqual(i, -1, `no line matches ${lineRe}`);
  const tok = lines[i].find((t) => t.text === text);
  assert.ok(tok, `no token ${JSON.stringify(text)} on line ${i + 1}: ${lines[i].map((t) => JSON.stringify(t.text)).join(" ")}`);
  return tok;
}

function hasScope(tok, scope) {
  assert.ok(
    tok.scopes.some((s) => s === scope || s.startsWith(scope + ".")),
    `expected scope ${scope} on ${JSON.stringify(tok.text)}, got: ${tok.scopes.join(" ")}`,
  );
}
function lacksScope(tok, scope) {
  assert.ok(
    !tok.scopes.some((s) => s === scope || s.startsWith(scope + ".")),
    `unexpected scope ${scope} on ${JSON.stringify(tok.text)}: ${tok.scopes.join(" ")}`,
  );
}

// [line regex, token text, scope that must be present]
const EXPECT = [
  // attributes and headings
  [/^## Boot sequence/, "sec:boot", "entity.other.attribute-name.id.tmark"],
  [/^## Boot sequence/, "#", "keyword.other.sigil.define.tmark"],
  [/^## Boot sequence/, "draft", "entity.other.attribute-name.class.tmark"],
  [/^## Boot sequence/, "lang", "entity.other.attribute-name.attribute.tmark"],
  [/^## Boot sequence/, "en", "string.unquoted.tmark"],
  // references and citations
  [/^The device powers/, "sec:boot", "support.type.reference.tmark"],
  [/^The device powers/, "fig:boot", "support.type.reference.tmark"],
  [/^The device powers/, " fig:crash", "support.type.reference.tmark"],
  [/^Time is relative/, "ein05", "support.type.reference.tmark"],
  [/^Time is relative/, ";", "punctuation.separator.reference.tmark"],
  [/^Time is relative/, "-", "keyword.operator.suppress-author.tmark"],
  [/^Cite in place/, "doi:10.1002/andp.19053221004", "support.type.reference.tmark"],
  [/^Cite in place/, "https://doi.org/10.1002/andp.19053221004", "support.type.reference.tmark"],
  [/^Pandoc import/, "ein05, p. 33", "support.type.reference.tmark"],
  [/^Pandoc import/, "\\@", "constant.character.escape.tmark"],
  // roles
  [/^\{lead\}/, "lead", "entity.name.function.role.tmark"],
  [/^\{lead\}/, "Boot sequence.", "meta.role.content.tmark"],
  [/^\{lead\}/, "aside", "entity.name.function.role.tmark"],
  [/^but \{aside side=left\}/, "side", "entity.other.attribute-name.role.tmark"],
  [/^but \{aside side=left\}/, "left", "string.unquoted.tmark"],
  [/^but \{aside side=left\}/, "Prandtl 1921", "markup.bold.markdown"],
  [/^\{index main=true/, "true", "string.unquoted.tmark"],
  [/^\{index main=true/, "byte order", "meta.role.content.tmark"],
  [/^\{index main=true/, "endianness", "meta.role.content.tmark"],
  [/^\{index main=true/, "latex", "variable.parameter.positional.role.tmark"],
  [/^\{index main=true/, "\\clearpage", "string.other.argument.role.tmark"],
  [/^Inline \{code py\}/, "py", "variable.parameter.positional.role.tmark"],
  [/^Inline \{code py\}/, "#!", "keyword.control.shebang.tmark"],
  [/^Inline \{code py\}/, "latex", "invalid.deprecated.role.tmark"],
  [/^Inline \{code py\}/, "margin", "invalid.deprecated.role.tmark"],
  [/^\{index:physics\}/, ":physics", "invalid.deprecated.tmark"],
  [/^\{index:physics\}/, "title", "variable.other.moustache.tmark"],
  [/^\{index:physics\}/, "press.template", "variable.other.moustache.tmark"],
  // definitions
  [/^#\[endianness\]/, "endianness", "entity.other.attribute-name.index.tmark"],
  [/^#\[endianness\]/, "fw", "support.type.counter-prefix.tmark"],
  [/^#\[endianness\]/, "boot-loop", "entity.other.attribute-name.counter.tmark"],
  [/^An anchor on/, "this claim", "meta.span.tmark"],
  [/^An anchor on/, "claim:one", "entity.other.attribute-name.id.tmark"],
  [/^An anchor on/, "media", "entity.other.attribute-name.attribute.tmark"],
  [/^\{include\}/, "include", "entity.name.function.role.tmark"],
  [/^\{include\}/, "chapters/boot.md", "string.other.argument.role.tmark"],
  // inline sugar
  [/^Small caps/, "x", "markup.smallcaps.tmark"],
  [/^Small caps/, "==", "punctuation.definition.highlight.begin.tmark"],
  [/^Small caps/, "~~", "punctuation.definition.strikethrough.markdown"],
  [/^Small caps/, "2", "markup.subscript.tmark"],
  [/^Small caps/, "ctrl", "markup.inline.raw.keystroke.tmark"],
  [/^insert \^\^new/, "new", "markup.underline.insert.tmark"],
  [/^insert \^\^new/, "1", "variable.other.footnote.tmark"],
  [/^insert \^\^new/, "an inline note", "meta.footnote.inline.tmark"],
  [/^insert \^\^new/, "75%", "constant.numeric.progressbar.tmark"],
  [/^\{>>a critic/, "a critic comment", "comment.block.critic.tmark"],
  [/^\{>>a critic/, "added", "markup.inserted.critic.tmark"],
  [/^\{>>a critic/, "old", "markup.deleted.critic.tmark"],
  [/^Math \$a/, "a", "markup.math.inline.markdown"],
  [/^Math \$a/, "b", "markup.math.inline.markdown"],
  [/^Math \$a/, "eq:inline", "entity.other.attribute-name.id.tmark"],
  // lists
  [/^- \[ \] open/, "[ ]", "constant.language.task.tmark"],
  [/^- \[x\] done/, "[x]", "constant.language.task.tmark"],
  [/^- \[x\] done/, "bold", "markup.bold.markdown"],
  [/^- \[x\] done/, "ref", "support.type.reference.tmark"],
  [/^:   Definition/, "   Definition, indented continuation lines aligned.", "meta.definition.tmark"],
  [/^- \[\.\] partial/, "[.]", "constant.language.task.tmark"],
  [/^- plain item/, "ref", "support.type.reference.tmark"],
  [/^- plain item/, "sc", "entity.name.function.role.tmark"],
  [/^:   Definition/, ":", "keyword.operator.definition.tmark"],
  [/^\[\^1\]: The footnote/, "1", "variable.other.footnote.tmark"],
  [/^\[\^1\]: The footnote/, "ein05", "support.type.reference.tmark"],
  [/^\*\[HTML\]:/, "HTML", "entity.name.tag.abbr.tmark"],
  // captions, tables, images
  [/^Table: Fruit/, "Table", "keyword.other.caption.tmark"],
  [/^Table: Fruit/, "tbl:stock", "entity.other.attribute-name.id.tmark"],
  [/^\| #\(n:joy\)/, "n", "support.type.counter-prefix.tmark"],
  [/^\| #\(n:joy\)/, "sec:boot", "support.type.reference.tmark"],
  [/^!\[Trace\]/, "width", "entity.other.attribute-name.attribute.tmark"],
  [/^!\[Trace\]/, "fig:trace", "entity.other.attribute-name.id.tmark"],
  [/^Figure: Full/, "Figure", "keyword.other.caption.tmark"],
  [/^Figure: Full/, "Markdown", "markup.bold.markdown"],
  [/^Listing: Bubble/, "Listing", "keyword.other.caption.tmark"],
  // containers and admonitions
  [/^::: figure/, ":::", "keyword.control.directive.tmark"],
  [/^::: figure/, "figure", "entity.name.type.directive.container.tmark"],
  [/^::: figure/, "cols", "entity.other.attribute-name.attribute.tmark"],
  [/^::: warning/, "\"LaTeX toolchain\"", "string.quoted.double.tmark"],
  [/^Install TeX Live before/, "sec:boot", "support.type.reference.tmark"],
  [/^Install TeX Live before/, "texsmith --build", "markup.inline.raw.string.markdown"],
  [/^::: margin/, "margin", "invalid.deprecated.tmark"],
  [/^!!! warning/, "!!!", "keyword.control.directive.tmark"],
  [/^!!! warning/, "warning", "entity.name.type.directive.admonition.tmark"],
  [/^!!! warning/, "\"LaTeX toolchain\"", "string.quoted.double.title.tmark"],
  [/^    Install TeX Live, see/, "sec:boot", "support.type.reference.tmark"],
  [/^    Install TeX Live, see/, "aside", "entity.name.function.role.tmark"],
  [/^    A second paragraph/, "A second paragraph.", "meta.directive.admonition.tmark"],
  [/^\?\?\? note/, "???", "keyword.control.directive.tmark"],
  [/^\?\?\? note/, " inline end", "entity.other.attribute-name.class.tmark"],
  [/^    Body with/, "term", "entity.other.attribute-name.index.tmark"],
  [/^\/\/\/ caption/, "///", "invalid.deprecated.tmark"],
  // data directives and fences
  [/^```yaml table/, "yaml", "fenced_code.block.language.markdown"],
  [/^```yaml table/, "table", "keyword.control.directive.node.tmark"],
  [/^columns: \[A, B\]/, "columns: [A, B]", "meta.embedded.block.yaml"],
  [/^```python image/, "image", "keyword.control.directive.node.tmark"],
  [/^```python image/, "include", "entity.other.attribute-name.fence.tmark"],
  [/^```python image/, "\"plot.py\"", "string.quoted.double.tmark"],
  [/^import matplotlib/, "import matplotlib.pyplot as plt", "meta.embedded.block.python"],
  [/^```python title/, "title", "entity.other.attribute-name.fence.tmark"],
  [/^```python title/, "\"2-3\"", "string.quoted.double.tmark"],
  [/^```grid table/, "grid", "fenced_code.block.language.markdown"],
  [/^```latex raw/, "raw", "keyword.control.directive.node.tmark"],
  // math blocks
  [/^\$\$ \{#eq:pythagoras\}/, "eq:pythagoras", "entity.other.attribute-name.id.tmark"],
  [/^x\^2 \+ y\^2/, " y", "markup.math.block.markdown"],
  // misc blocks
  [/^--8<--/, "--8<--", "invalid.deprecated.tmark"],
  [/^--8<--/, "\"snippets/file.md\"", "string.quoted.double.tmark"],
  [/^\[TOC\]/, "[TOC]", "keyword.control.toc.tmark"],
];

// [line regex, token text (or null for every token), scope that must be absent]
const FORBID = [
  [/^\+-----\+/, null, "meta.reference"],
  [/^\\clearpage % not/, null, "meta.role"],
  [/^\\clearpage % not/, null, "meta.reference"],
  [/^plain = /, null, "meta.reference"],
  [/^plain = /, null, "meta.index-entry"],
  [/^<!-- a comment/, null, "meta.reference"],
  [/^<!-- a comment/, null, "meta.role"],
  [/^Pandoc import/, null, "meta.reference.bare"], // me@example.com must stay plain
  [/^      fw: \{name/, null, "meta.counter-item"], // front matter is YAML
  [/^Small caps/, null, "markup.bold.markdown"], // __x__ is small caps, not bold
];

for (const scope of ["text.html.markdown", "text.html.markdown.tmark"]) {
  test(`grammar as ${scope}`, async () => {
    const lines = await tokenize(sample, scope);
    for (const [lineRe, text, expected] of EXPECT) hasScope(token(lines, lineRe, text), expected);
    const src = sample.split(/\r?\n/);
    for (const [lineRe, text, forbidden] of FORBID) {
      const i = src.findIndex((l) => lineRe.test(l));
      assert.notEqual(i, -1, `no line matches ${lineRe}`);
      for (const tok of lines[i]) {
        if (text === null || tok.text === text) lacksScope(tok, forbidden);
      }
    }
  });
}

test("the whole spec tokenises without an unclosed construct", async () => {
  const spec = readFileSync(join(here, "../../../specs/tmark.md"), "utf8");
  const lines = await tokenize(spec);
  const last = lines.at(-1).flatMap((t) => t.scopes);
  assert.ok(!last.some((s) => s.startsWith("meta.role") || s.startsWith("meta.directive.pymdownx")), last.join(" "));
});
