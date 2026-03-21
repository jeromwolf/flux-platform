"""Backward compatibility shim — use maritime.crawlers.maritime_accidents instead."""
import warnings

warnings.warn(
    "Importing from 'kg.crawlers.maritime_accidents' is deprecated. "
    "Use 'maritime.crawlers.maritime_accidents' instead. "
    "This shim will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)

from maritime.crawlers.maritime_accidents import *  # noqa: F401,F403
