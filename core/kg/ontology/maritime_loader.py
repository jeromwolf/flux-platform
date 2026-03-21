"""Backward compatibility shim — use maritime.ontology.maritime_loader instead."""
import warnings

warnings.warn(
    "Importing from 'kg.ontology.maritime_loader' is deprecated. "
    "Use 'maritime.ontology.maritime_loader' instead. "
    "This shim will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)

from maritime.ontology.maritime_loader import *  # noqa: F401,F403
from maritime.ontology.maritime_loader import load_maritime_ontology  # noqa: F401
