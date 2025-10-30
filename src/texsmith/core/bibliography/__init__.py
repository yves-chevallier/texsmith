"""Bibliography facade exposed through the TeXSmith public API.

Architecture
: `BibliographyCollection` centralises reference merging, deduplication, and
  portable export so higher layers can treat bibliographies as immutable
  dictionaries. The collection records provenance internally so API consumers
  can report issues with source context.
: `DoiBibliographyFetcher` encapsulates remote lookups so IO code remains outside
  the pure transformation layers. Callers provide a DOI and receive parsed
  BibTeX data ready to inject into the collection.
: `bibliography_data_from_string` accepts inline BibTeX payloads and converts
  them into `BibliographyData` objects, enabling templating systems to embed
  references alongside content.

Implementation Rationale
: The public API needs a stable, documented entry point that is decoupled from
  the evolving internal package layout. Re-exporting the curated primitives keeps
  backward compatibility guarantees manageable.
: Aggregation logic lives in `collection.py` so both the CLI and the programmatic
  API can reuse it. By funnelling access through this module we expose
  documentation and doctest examples close to the import surface users reach for
  first.

Usage Example

```pycon
>>> from texsmith.core.bibliography import BibliographyCollection, bibliography_data_from_string
>>> collection = BibliographyCollection()
>>> payload = \"\"\"@article{doe2023,
...   author = {Doe, Jane},
...   title = {A Minimal Example},
...   year = {2023},
... }\"\"\"
>>> inline = bibliography_data_from_string(payload, "doe2023")
>>> collection.load_data(inline, source="inline.bib")
>>> reference = collection.find("doe2023")
>>> reference["fields"]["title"]
'A Minimal Example'
```
"""

from __future__ import annotations

from .collection import BibliographyCollection
from .doi import DoiBibliographyFetcher, DoiLookupError
from .issues import BibliographyIssue
from .parsing import bibliography_data_from_inline_entry, bibliography_data_from_string


__all__ = [
    "BibliographyCollection",
    "BibliographyIssue",
    "DoiBibliographyFetcher",
    "DoiLookupError",
    "bibliography_data_from_inline_entry",
    "bibliography_data_from_string",
]
