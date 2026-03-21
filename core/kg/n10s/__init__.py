"""Neosemantics (n10s) integration for the Maritime KG platform.

Provides:
- N10sConfig: Graph configuration and namespace management
- N10sImporter: OWL/Turtle ontology import into Neo4j via n10s
- OWLExporter: Python ontology → OWL/Turtle export (requires maritime domain)
"""

from kg.n10s.config import N10sConfig
from kg.n10s.importer import N10sImporter

__all__ = [
    "N10sConfig",
    "N10sImporter",
]

# OWLExporter is a maritime-domain component; available only when maritime domain is installed.
try:
    from kg.n10s.owl_exporter import OWLExporter  # noqa: F401

    __all__ += ["OWLExporter"]
except ImportError:
    pass  # maritime domain not installed
