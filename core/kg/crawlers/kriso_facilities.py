"""Backward compatibility shim — use maritime.crawlers.kriso_facilities instead."""
import warnings

warnings.warn(
    "Importing from 'kg.crawlers.kriso_facilities' is deprecated. "
    "Use 'maritime.crawlers.kriso_facilities' instead. "
    "This shim will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)

from maritime.crawlers.kriso_facilities import *  # noqa: F401,F403
