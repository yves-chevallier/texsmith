# Numbering

The series continue across pages in navigation order: #(fw:more) follows the
findings of the previous page, and #(req:reset) is the first requirement
of the site-wide series declared in `mkdocs.yml`.

Back references: @fw:watchdog, @fw:log-wrap, @fig:trace, @tbl:findings and
@sec:counters are all defined on the previous page. An unknown key stays
visible: @fw:missing.

![Another trace](trace.svg)

Figure: A second figure, numbered after the first page's. {#fig:second}

See @fig:second.
