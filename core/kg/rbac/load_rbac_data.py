"""Backward compatibility shim — use maritime.rbac.load_rbac_data instead."""
import warnings

warnings.warn(
    "Importing from 'kg.rbac.load_rbac_data' is deprecated. "
    "Use 'maritime.rbac.load_rbac_data' instead. "
    "This shim will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)

from maritime.rbac.load_rbac_data import *  # noqa: F401,F403
