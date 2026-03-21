"""Backward compatibility shim — use maritime.crawlers.kriso_papers instead."""
import warnings

warnings.warn(
    "Importing from 'kg.crawlers.kriso_papers' is deprecated. "
    "Use 'maritime.crawlers.kriso_papers' instead. "
    "This shim will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)

from maritime.crawlers.kriso_papers import *  # noqa: F401,F403
