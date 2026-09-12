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

= Diagnostics emitters

`texsmith.core.diagnostics` defines the `DiagnosticEmitter` protocol plus a few
stock implementations. Pass any emitter into `ConversionService`,
`convert_documents`, or `TemplateSession` to intercept warnings, errors, and
structured events.

#table(
columns: 3,
align: (left, left, left),
table.header([Emitter], [Description], [Typical usage]),
[`CliEmitter` (`texsmith.ui.cli.diagnostics`)], [Rich-powered emitter used by the Typer CLI. Respects `-v` and `–debug`, paints warnings as panels, and streams structured events to the diagnostics sidebar.], [Default when running `texsmith`. Import it in automation scripts when you want human-friendly output.],
[`LoggingEmitter`], [Forwards `warning`, `error`, and `event` calls to the standard `logging` module.], [Daemons, notebooks, or services that rely on existing logging policy.],
[`NullEmitter`], [No-op implementation. Useful when you want silent conversions or plan to capture diagnostics out-of-band.], [Unit tests and benchmarking.],
)

Emitters expose a `debug_enabled` flag so downstream handlers can decide whether
to include stack traces or expensive state dumps. Implement your own to route
diagnostics to metrics systems or structured loggers.
