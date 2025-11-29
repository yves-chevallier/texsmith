# Core

::: texsmith.core.config

::: texsmith.core.context

::: texsmith.core.conversion_contexts

::: texsmith.core.conversion

## Diagnostics emitters

`texsmith.core.diagnostics` defines the `DiagnosticEmitter` protocol plus a few
stock implementations. Pass any emitter into `ConversionService`,
`convert_documents`, or `TemplateSession` to intercept warnings, errors, and
structured events.

| Emitter | Description | Typical usage |
| ------- | ----------- | ------------- |
| `CliEmitter` (`texsmith.ui.cli.diagnostics`) | Rich-powered emitter used by the Typer CLI. Respects `-v` and `--debug`, paints warnings as panels, and streams structured events to the diagnostics sidebar. | Default when running `texsmith`. Import it in automation scripts when you want human-friendly output. |
| `LoggingEmitter` | Forwards `warning`, `error`, and `event` calls to the standard `logging` module. | Daemons, notebooks, or services that rely on existing logging policy. |
| `NullEmitter` | No-op implementation. Useful when you want silent conversions or plan to capture diagnostics out-of-band. | Unit tests and benchmarking. |

Emitters expose a `debug_enabled` flag so downstream handlers can decide whether
to include stack traces or expensive state dumps. Implement your own to route
diagnostics to metrics systems or structured loggers.

::: texsmith.core.diagnostics

::: texsmith.core.exceptions

::: texsmith.core.rules

::: texsmith.adapters.latex.utils

::: texsmith.adapters.docker
