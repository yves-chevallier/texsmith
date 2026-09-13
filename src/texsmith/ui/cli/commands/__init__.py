"""CLI command implementations exposed via `texsmith.ui.cli`.

The package holds one module per command. It deliberately re-exports nothing:
``from .render import render`` would rebind the ``render`` attribute of this
package from the *submodule* to the *function*, so
``texsmith.ui.cli.commands.render`` would mean one thing to ``import`` and
another to ``getattr`` — which is what let a test patch a module global by
hanging it off a function object. Import the command from its module:
``from texsmith.ui.cli.commands.render import render``.
"""

from __future__ import annotations


__all__: list[str] = []
