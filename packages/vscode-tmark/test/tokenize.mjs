// Tokenise a document with the TMark grammars exactly as VS Code does:
// vscode-textmate + vscode-oniguruma, the built-in Markdown and Markdown Math
// grammars vendored under test/grammars, and both injections registered.
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
// Both packages are CommonJS; require() keeps their named exports intact.
const vsctm = require("vscode-textmate");
const oniguruma = require("vscode-oniguruma");
const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");

const GRAMMARS = {
  "text.html.markdown": join(here, "grammars/markdown.tmLanguage.json"),
  "text.html.markdown.math": join(here, "grammars/md-math.tmLanguage.json"),
  "markdown.math.inline": join(here, "grammars/md-math-inline.tmLanguage.json"),
  "markdown.math.block": join(here, "grammars/md-math-block.tmLanguage.json"),
  "text.html.markdown.tmark": join(root, "syntaxes/tmark.tmLanguage.json"),
  "text.html.markdown.tmark.injection": join(root, "syntaxes/tmark.injection.tmLanguage.json"),
};

// Same shape as VS Code's TMGrammarFactory: an injection registered for a
// scope also applies to the grammars whose root scope extends it.
const INJECTIONS = {
  "text.html.markdown": ["markdown.math.inline", "markdown.math.block", "text.html.markdown.tmark.injection"],
};

const wasmPath = require.resolve("vscode-oniguruma/release/onig.wasm");
const onigLib = oniguruma.loadWASM(readFileSync(wasmPath).buffer).then(() => ({
  createOnigScanner: (patterns) => new oniguruma.OnigScanner(patterns),
  createOnigString: (s) => new oniguruma.OnigString(s),
}));

export const registry = new vsctm.Registry({
  onigLib,
  loadGrammar: async (scopeName) => {
    const path = GRAMMARS[scopeName];
    // Embedded languages (YAML, Python, LaTeX, …) are stubbed: VS Code ships
    // them, the tests only need the fence structure to be right.
    if (!path) return { scopeName, patterns: [] };
    return vsctm.parseRawGrammar(readFileSync(path, "utf8"), path);
  },
  getInjections: (scopeName) => {
    const parts = scopeName.split(".");
    const out = [];
    for (let i = 1; i <= parts.length; i++) {
      out.push(...(INJECTIONS[parts.slice(0, i).join(".")] ?? []));
    }
    return out;
  },
});

/** @returns {Promise<Array<Array<{text: string, scopes: string[]}>>>} one array of tokens per line */
export async function tokenize(text, scopeName = "text.html.markdown") {
  const grammar = await registry.loadGrammar(scopeName);
  if (!grammar) throw new Error(`grammar ${scopeName} not found`);
  let ruleStack = vsctm.INITIAL;
  const lines = text.split(/\r?\n/);
  const result = [];
  for (const line of lines) {
    const { tokens, ruleStack: next } = grammar.tokenizeLine(line, ruleStack);
    result.push(
      tokens.map((t) => ({ text: line.slice(t.startIndex, t.endIndex), scopes: t.scopes })),
    );
    ruleStack = next;
  }
  return result;
}

export function format(lines, { root = "text.html.markdown" } = {}) {
  const out = [];
  lines.forEach((tokens, i) => {
    out.push(`${String(i + 1).padStart(3)} | ${tokens.map((t) => t.text).join("")}`);
    for (const t of tokens) {
      if (!t.text.trim()) continue;
      const scopes = t.scopes.filter((s) => s !== root && s !== "meta.paragraph.markdown");
      out.push(`      ${JSON.stringify(t.text).padEnd(32)} ${scopes.join(" ")}`);
    }
  });
  return out.join("\n");
}
