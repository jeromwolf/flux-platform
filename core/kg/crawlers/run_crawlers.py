"""Backward compatibility shim — use maritime.crawlers.run_crawlers instead."""
import warnings

warnings.warn(
    "Importing from 'kg.crawlers.run_crawlers' is deprecated. "
    "Use 'maritime.crawlers.run_crawlers' instead. "
    "This shim will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)

from maritime.crawlers.run_crawlers import *  # noqa: F401,F403
