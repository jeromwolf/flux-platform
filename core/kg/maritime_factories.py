"""Backward compatibility shim — use maritime.factories instead."""
import warnings

warnings.warn(
    "Importing from 'kg.maritime_factories' is deprecated. "
    "Use 'maritime.factories' instead. "
    "This shim will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)

from maritime.factories import *  # noqa: F401,F403
