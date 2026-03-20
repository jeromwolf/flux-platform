"""Neo4j schema management (constraints, indexes, sample data)."""

from kg.schema.init_schema import init_schema
from kg.schema.load_sample_data import load_sample_data

__all__ = ["init_schema", "load_sample_data"]
