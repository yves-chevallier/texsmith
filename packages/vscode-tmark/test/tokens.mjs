// Dump the tokens of a file: `node test/tokens.mjs [file] [--tmark]`
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { tokenize, format } from "./tokenize.mjs";

const args = process.argv.slice(2);
const asTmark = args.includes("--tmark");
const file = args.find((a) => !a.startsWith("--")) ?? join(dirname(fileURLToPath(import.meta.url)), "sample.md");
const scope = asTmark ? "text.html.markdown.tmark" : "text.html.markdown";
const lines = await tokenize(readFileSync(file, "utf8"), scope);
console.log(format(lines, { root: scope }));
