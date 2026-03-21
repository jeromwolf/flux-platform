"""Backward compatibility shim — use maritime.schema.load_sample_data instead."""
import warnings

warnings.warn(
    "Importing from 'kg.schema.load_sample_data' is deprecated. "
    "Use 'maritime.schema.load_sample_data' instead. "
    "This shim will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)

from maritime.schema.load_sample_data import *  # noqa: F401,F403
