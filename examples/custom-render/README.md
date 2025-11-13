# Custom Render Example

This example demonstrates how to create a custom render function involving a new html element to be parsed. Here we want to hook onto the following tag and store un local context a counter incremented each time the tag is found.

```html
<span class="data-counter"></span>
```

The content is replaced with the current value of the counter.

This extension shows how to declare a custom render using the decorator:

```python
@renders("span", phase=RenderPhase.INLINE, name="inline_data_counter")
def render_data_counter(element, context) -> None:
```

## Demo

You can run the example with:

```tex
$ uv run python counter.py

\chapter{Counter Example}

This is item \counter{1} but we can also have another
item \counter{2} and even more \counter{3}.
```