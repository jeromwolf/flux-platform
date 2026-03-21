"""Backward compatibility shim — use maritime.n10s.owl_exporter instead."""
import warnings

warnings.warn(
    "Importing from 'kg.n10s.owl_exporter' is deprecated. "
    "Use 'maritime.n10s.owl_exporter' instead. "
    "This shim will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)

from maritime.n10s.owl_exporter import *  # noqa: F401,F403
