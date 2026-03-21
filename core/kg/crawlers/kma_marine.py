"""Backward compatibility shim — use maritime.crawlers.kma_marine instead."""
import warnings

warnings.warn(
    "Importing from 'kg.crawlers.kma_marine' is deprecated. "
    "Use 'maritime.crawlers.kma_marine' instead. "
    "This shim will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)

from maritime.crawlers.kma_marine import *  # noqa: F401,F403
