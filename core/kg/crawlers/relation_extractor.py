"""Backward compatibility shim — use maritime.crawlers.relation_extractor instead."""
import warnings

warnings.warn(
    "Importing from 'kg.crawlers.relation_extractor' is deprecated. "
    "Use 'maritime.crawlers.relation_extractor' instead. "
    "This shim will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)

from maritime.crawlers.relation_extractor import *  # noqa: F401,F403
