---
title: Included
---

# Main

Before the include, with HTML and a note[^main].

{include}(parts/chapter.md)

```python
--8<-- "parts/snippet.py"
```

{include base=parts}(deep/leaf.md)

{include}(missing.md)

```py include="parts/absent.py"
```

After.

[^main]: The main note.
