"""TeXSmith intermediate representation (IR).

The semantic, backend-agnostic document tree the readers produce and the tmark
writers consume. :mod:`texsmith.ir.model` is generated from the committed tmark
schema (``scripts/gen_ir_models.py``), :mod:`texsmith.ir.codec` carries it over
the ``tmark-py`` boundary and :mod:`texsmith.ir.walk` traverses it.
"""

from __future__ import annotations

from texsmith.ir import codec, model, walk


_mismatch = codec.wheel_schema_mismatch()
if _mismatch is not None:
    raise ImportError(_mismatch)
del _mismatch


__all__ = ["codec", "model", "walk"]
