"""Backward compatibility shim — use maritime.evaluation.dataset instead."""
import warnings

warnings.warn(
    "Importing from 'kg.evaluation.dataset' is deprecated. "
    "Use 'maritime.evaluation.dataset' instead. "
    "This shim will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)

from maritime.evaluation.dataset import *  # noqa: F401,F403
