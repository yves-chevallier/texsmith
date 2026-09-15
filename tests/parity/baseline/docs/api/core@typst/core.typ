#set document(
title: "Core",
)
#set page(
paper: "a4",
margin: 2.5cm,
numbering: none,
footer: context {
if counter(page).final().first() > 1 {
align(center)[#counter(page).get().first()]
}
},
)
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#set par(justify: true)
#show heading: set block(above: 1.8em, below: 1.0em)
#set heading(numbering: "1.1")

#align(center)[
#text(size: 1.8em, weight: "bold")[Core]]
#v(1.5em)

#ts-callout-style.update("fancy")

= Diagnostics emitters

`texsmith.diagnostics` defines the `DiagnosticEmitter` protocol plus a few
stock implementations. Pass any emitter into `ConversionService`,
`convert_documents`, or `TemplateSession` to see the findings as they happen.

An emitter is a *presenter*. It owns a `DiagnosticSink`, and the sink does
the collecting: it deduplicates, it answers `strict_failed()`, and it owns the
`FileTable` every document of the run registers in — which is why the emitter
you parse with must be the emitter you render with, or a span will name the
wrong file.

#table(
columns: 3,
align: (left, left, left),
table.header([Emitter], [Description], [Typical usage]),
[`CliEmitter` (`texsmith.ui.cli.diagnostics`)], [Rich-powered emitter used by the Typer CLI. Respects `-v` and `–debug`, paints warnings as panels, and streams structured events to the diagnostics sidebar.], [Default when running `texsmith`. Import it in automation scripts when you want human-friendly output.],
[`LoggingEmitter`], [Renders each record as the `path:line:col: severity code: message` line and logs it at the matching level.], [Daemons, notebooks, or services that rely on existing logging policy.],
[`NullEmitter`], [Shows nothing, and still records: the run's diagnostics stay readable on `emitter.sink` and on each `Document`.], [Unit tests, benchmarking, and any caller that reads the findings afterwards.],
)

To write your own, subclass `SinkEmitter` and implement `render(diagnostic,
cause)` and `event(name, payload)`; everything else is the sink's. Emitters
expose a `debug_enabled` flag so downstream handlers can decide whether to
include stack traces or expensive state dumps.
