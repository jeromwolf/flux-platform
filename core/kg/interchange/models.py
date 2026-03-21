"""Data models for KG interchange import/export operations.

Provides frozen dataclasses for configuring and reporting on KG
import/export operations across multiple serialization formats.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExportConfig:
    """Configuration for KG export operations.

    Attributes:
        labels: Node labels to include in export. None means export all labels.
        relationship_types: Relationship types to include. None means export all.
        include_properties: Whether to include node/edge property data.
        pretty_print: Whether to format output with indentation.
        max_nodes: Maximum number of nodes to export. None means no limit.
        context_uri: Base URI for JSON-LD @context declarations.
    """

    labels: list[str] | None = None
    relationship_types: list[str] | None = None
    include_properties: bool = True
    pretty_print: bool = True
    max_nodes: int | None = None
    context_uri: str = "https://schema.org/"


@dataclass(frozen=True)
class ImportConfig:
    """Configuration for KG import operations.

    Attributes:
        merge_strategy: Cypher write strategy — "CREATE" or "MERGE".
        batch_size: Number of records per transaction batch.
        label_column: CSV column name containing the node label.
        id_column: CSV column name containing the node identifier.
    """

    merge_strategy: str = "CREATE"
    batch_size: int = 500
    label_column: str = "labels"
    id_column: str = "id"


@dataclass
class ExportResult:
    """Result of a KG export operation.

    Attributes:
        format: Serialization format used — "json-ld", "graphml", or "csv".
        node_count: Number of nodes included in the export.
        edge_count: Number of edges included in the export.
        data: Serialized output string ready for writing to file or network.
        errors: List of non-fatal error messages encountered during export.

    Properties:
        success: True when no errors were recorded.
    """

    format: str
    node_count: int = 0
    edge_count: int = 0
    data: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Return True when the export completed without errors."""
        return len(self.errors) == 0
