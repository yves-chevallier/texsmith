---
press:
  declare:
    glossary:
      watchdog: A timer that resets the board when the firmware stops kicking it.
---

# Constructs

## Counters {#sec:counters}

The first finding is #(fw:watchdog) and the second is #(fw:ota). See
@fw:watchdog, @fw:ota and the site-wide @req:reset defined on the next page.

### Log buffer wiped {#fw:log-wrap}

Referenced as @fw:log-wrap, and the section as @sec:counters.

## Figures

![A watchdog trace](trace.svg)

Figure: The watchdog trace. {#fig:trace}

::: figure {cols=2}
![Left](trace.svg){#fig:left}
![Right](trace.svg){#fig:right}

Figure: Two views. {#fig:views}
:::

See @fig:trace and @fig:left.

## Tables

| Id | Finding |
| --- | --- |
| #(fw:table) | Defined in a table cell. |

Table: Findings by id. {#tbl:findings}

```yaml table
columns: [Key, Value]
rows:
  - ["Cell **bold**", "Cell two"]
```

Table: A structured table. {#tbl:yaml}

See @tbl:findings and @tbl:yaml.

## Listings and equations

```python
print("hello")
```

Listing: A greeting. {#lst:hello}

$$
E = mc^2
$$ {#eq:einstein}

See @lst:hello and @eq:einstein.

## Callouts

!!! note "Kept as written"
    A Material admonition passes through.

::: warning {title="Careful"}
A TMark callout with @fw:watchdog inside.
:::

::: theorem {#thm:one title="Pythagoras"}
$a^2 + b^2 = c^2$.
:::

::: note {collapsed=true}
Collapsed.
:::

See @thm:one.

## Asides and index

::: aside
A block aside.
:::

A sentence with {aside side=left}[an inline aside], an index entry
{index}[watchdog][timer] and a glossary term @gls:watchdog.

## Inline roles

{sc}[Small caps], {keys}[Ctrl+S], {mark}[marked], {underline}[underlined]
and [a span]{#span-id .custom lang=fr}. Only [on the site]{media=web}; only
[in print]{media=print}.

::: pkg.module
    handler: python

After the unclosed directive, @fw:ota still resolves.
