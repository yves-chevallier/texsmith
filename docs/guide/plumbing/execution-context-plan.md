# Document + ExecutionContext Refactor Plan

Goal: introduce a single SSOT execution context that unifies CLI, front matter,
YAML config, core defaults, fragments, and templates without changing CLI
behavior. Ultimate goal is to reduce code duplication, improve maintainability. Reduce code footprint
by eliminating multiple merge points and normalizations.

## Guiding rules
- Preserve existing CLI output/behavior.
- Keep `legacy_latex_accents` untouched.
- One merge point for attributes and execution settings.
- Avoid compatibility shims; remove duplication instead.
- Run make lint after final changes.
- Run tests frequently to catch regressions early (uv run pytest).
- Make all examples make sure they still build (make clean examples).

## Target objects (proposed)

### Document (existing)
Keep `Document` as the source container for:
- input source path + html
- front matter (raw, normalised once)
- slot selectors/inclusions
- title strategy + numbered/base_level

### ExecutionContext (new)
One resolved view of the conversion runtime for a prepared document:
- document: `Document` (prepared)
- settings: parser, assets, diagrams, manifest, debug html
- language + numbering + base level (resolved)
- template: runtime, overrides, fragments, slot requests
- bibliography: collection + map
- runtime_common: emitter, code settings, emoji mode, etc.

## Merge priority (SSOT)
Highest wins, left to right:
1) CLI options (`ConversionRequest`)
2) Document front matter
3) YAML config files (press metadata)
4) Template defaults (manifest/runtime extras)
5) Core defaults

## Execution steps (to run together)

### Step 1: Inventory and mapping
Status: done.
- Enumerate all attribute sources:
  - CLI request defaults and overrides
  - front matter keys (top-level + press.*)
  - template defaults + runtime extras
  - core defaults in conversion + fragments
- Map each attribute to its owner in ExecutionContext.
- Identify duplicate normalisations (press metadata, fragments list, slots).

#### Inventory snapshot (current)

Attribute sources and touchpoints:
- CLI defaults/overrides: `src/texsmith/ui/cli/commands/render.py`
- Front matter parsing/normalisation: `src/texsmith/core/documents.py`, `src/texsmith/core/conversion/service.py`
- Template overrides + language: `src/texsmith/core/conversion/templates.py`, `src/texsmith/core/templates/runtime.py`
- Fragments list merging: `src/texsmith/core/conversion/service.py`, `src/texsmith/core/templates/wrapper.py`
- Renderer runtime state: `src/texsmith/core/conversion/core.py`

Duplicate/overlapping merges to remove:
- Press metadata normalisation:
  - `src/texsmith/core/documents.py`
  - `src/texsmith/ui/cli/commands/render.py`
  - `src/texsmith/core/conversion/service.py`
  - `src/texsmith/core/templates/session.py`
  - `src/texsmith/core/templates/manifest.py`
- Fragment selection:
  - `src/texsmith/core/conversion/service.py` (`_resolve_fragment_overrides`)
  - `src/texsmith/core/templates/wrapper.py` (fallback list)
- Slot requests:
  - `src/texsmith/core/documents.py` (front matter + selectors)
  - `src/texsmith/core/conversion/templates.py` (slot overrides merge)

Mapping target (ExecutionContext owner):
- Document inputs: `Document`
- Front matter + press metadata: `ExecutionContext` (single normalisation)
- Slots + inclusions: `ExecutionContext.slot_requests`
- Fragments list: `ExecutionContext.fragments`
- Template overrides + runtime extras: `ExecutionContext.template_overrides`
- Language/base level/numbered: `ExecutionContext`
- Asset flags + parser/diagnostics: `ExecutionContext.settings`

### Step 2: Define ExecutionContext dataclass
Status: done.
- Create `ExecutionContext` in `src/texsmith/core/context.py` (or new module).
- Include:
  - `document: Document`
  - `request: ConversionRequest`
  - `template_runtime: TemplateRuntime | None`
  - `template_overrides: dict[str, Any]`
  - `slot_requests: dict[str, str]`
  - `fragments: list[str]`
  - `language: str`
  - `bibliography_collection` + `bibliography_map`
  - `runtime_common: dict[str, object]`
  - `generation: GenerationStrategy`
- Keep fields explicit; avoid nested dicts where possible.

### Step 3: Build a single resolver
Status: done.
- Add `resolve_execution_context(...)` in `core/conversion/`:
  - Inputs: `Document`, `ConversionRequest`, template runtime, overrides.
  - Output: `ExecutionContext`.
- Responsibilities:
  - Normalise press metadata once.
  - Merge template overrides once.
  - Resolve language once.
  - Resolve fragments once (enable/disable).
  - Resolve slot requests once.
  - Build bibliography collection + map once.

### Step 4: Rewire core conversion
Status: done.
- Update `build_binder_context` to accept `ExecutionContext` instead of ad-hoc fields.
- Update `_build_runtime_common` to use `ExecutionContext.runtime_common`.
- Ensure `render_with_fallback` only reads from `ExecutionContext` and `Document`.

### Step 5: Rewire template session + CLI
Status: done.
- TemplateSession: build ExecutionContext once, pass it through the renderer.
- CLI: create `ConversionRequest`, prepare `Document`, and call resolver.
- Keep CLI flags unchanged; confirm help output and behavior are stable.

### Step 6: Remove redundant merges
Status: done.
- Delete duplicate press metadata normalisation in multiple layers.
- Remove repeated fragment/slot merge logic from core + templates.
- Ensure `Document.prepare_for_conversion` only prepares document-level concerns.

### Step 7: Tests and safety checks
Status: done.
- Update tests to assert `ExecutionContext` values directly.
- Keep CLI tests unchanged; add minimal coverage for resolver priority order.
- Run `uv run pytest`, `uv run ruff format .`, `uv run ruff check .`.

## Acceptance criteria
- CLI output and diagnostics unchanged for existing tests.
- One resolver is the only place that merges attributes.
- `ExecutionContext` is the only runtime state object used by core, fragments, templates.
- No duplicate press metadata normalization.

## Risks and mitigations
- Risk: subtle behavior shifts in front matter vs CLI precedence.
  - Mitigation: add explicit tests for priority order.
- Risk: template overrides merge changes.
  - Mitigation: snapshot key template contexts and compare.
