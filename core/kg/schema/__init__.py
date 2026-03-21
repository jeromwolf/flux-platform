"""Neo4j schema management (constraints, indexes, sample data)."""

from kg.schema.init_schema import init_schema

__all__ = ["init_schema"]

# Maritime sample data loader is optional; available only when maritime domain is installed.
try:
    from kg.schema.load_sample_data import load_sample_data  # noqa: F401

    __all__ += ["load_sample_data"]
except ImportError:
    pass  # maritime domain not installed
