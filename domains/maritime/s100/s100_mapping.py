"""S-100 feature type to KG node/relationship mapping framework.

IHO S-100 is a universal hydrographic data model that includes:
- S-101: Electronic Navigational Charts (ENC)
- S-102: Bathymetric Surface
- S-104: Water Level Information for Surface Navigation
- S-111: Surface Currents
- S-124: Navigational Warnings
- S-421: Route Plan

This module defines the mapping protocol and registry for converting
S-100 feature types into Knowledge Graph nodes and relationships.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class S100FeatureMapping(Protocol):
    """Protocol for S-100 feature type to KG mapping."""

    @property
    def s100_product(self) -> str:
        """S-100 product specification (e.g., 'S-101', 'S-102')."""
        ...

    @property
    def feature_type(self) -> str:
        """S-100 feature type name (e.g., 'DepthArea', 'Buoy')."""
        ...

    @property
    def kg_label(self) -> str:
        """Target KG node label."""
        ...

    def to_kg_properties(self, s100_attrs: dict[str, Any]) -> dict[str, Any]:
        """Convert S-100 attributes to KG node properties."""
        ...


@dataclass(frozen=True)
class S100MappingEntry:
    """Concrete mapping from an S-100 feature type to a KG entity.

    Attributes:
        s100_product: S-100 product spec (e.g., 'S-101').
        feature_type: S-100 feature type name.
        kg_label: Target KG node label.
        property_map: Dict mapping S-100 attribute names to KG property names.
        relationship_type: Optional KG relationship to create.
        relationship_target: Optional target KG label for the relationship.
    """

    s100_product: str
    feature_type: str
    kg_label: str
    property_map: dict[str, str] = field(default_factory=dict)
    relationship_type: str = ""
    relationship_target: str = ""

    def to_kg_properties(self, s100_attrs: dict[str, Any]) -> dict[str, Any]:
        """Convert S-100 attributes to KG properties using the property map.

        Args:
            s100_attrs: Raw S-100 feature attributes.

        Returns:
            Dict of KG node properties.
        """
        result: dict[str, Any] = {}
        for s100_key, kg_key in self.property_map.items():
            if s100_key in s100_attrs:
                result[kg_key] = s100_attrs[s100_key]
        return result


# ---------------------------------------------------------------------------
# S-100 Product Specifications Registry
# ---------------------------------------------------------------------------

S100_PRODUCTS: dict[str, str] = {
    "S-101": "Electronic Navigational Charts (ENC)",
    "S-102": "Bathymetric Surface",
    "S-104": "Water Level Information for Surface Navigation",
    "S-111": "Surface Currents",
    "S-124": "Navigational Warnings",
    "S-421": "Route Plan based on S-100",
}

# ---------------------------------------------------------------------------
# Default Feature Type Mappings (S-101 ENC → KG)
# ---------------------------------------------------------------------------

S101_MAPPINGS: list[S100MappingEntry] = [
    S100MappingEntry(
        s100_product="S-101",
        feature_type="DepthArea",
        kg_label="SeaArea",
        property_map={
            "depthRangeMinimumValue": "minDepth",
            "depthRangeMaximumValue": "maxDepth",
            "DRVAL1": "minDepth",
            "DRVAL2": "maxDepth",
        },
    ),
    S100MappingEntry(
        s100_product="S-101",
        feature_type="AnchorageArea",
        kg_label="Anchorage",
        property_map={
            "featureName": "name",
            "categoryOfAnchorage": "anchorageType",
        },
    ),
    S100MappingEntry(
        s100_product="S-101",
        feature_type="Fairway",
        kg_label="Channel",
        property_map={
            "featureName": "name",
            "depthRangeMinimumValue": "minDepth",
        },
    ),
    S100MappingEntry(
        s100_product="S-101",
        feature_type="Harbour",
        kg_label="Port",
        property_map={
            "featureName": "name",
            "unloCode": "unlocode",
            "countryName": "country",
        },
    ),
    S100MappingEntry(
        s100_product="S-101",
        feature_type="TrafficSeparationScheme",
        kg_label="TSS",
        property_map={
            "featureName": "name",
            "trafficFlow": "trafficFlow",
        },
    ),
    S100MappingEntry(
        s100_product="S-101",
        feature_type="NavigationalSystemOfMarks",
        kg_label="Waterway",
        property_map={
            "featureName": "name",
        },
    ),
]


class S100ToKGMapper:
    """Maps S-100 features to Knowledge Graph entities.

    Maintains a registry of S100MappingEntry instances and provides
    lookup by product + feature type.

    Example::

        mapper = S100ToKGMapper()
        mapper.register(S100MappingEntry(...))
        entry = mapper.lookup("S-101", "DepthArea")
        kg_props = entry.to_kg_properties(s100_feature_attrs)
    """

    def __init__(self) -> None:
        self._registry: dict[str, S100MappingEntry] = {}
        # Register default S-101 mappings
        for mapping in S101_MAPPINGS:
            self.register(mapping)

    def register(self, mapping: S100MappingEntry) -> None:
        """Register a feature type mapping.

        Args:
            mapping: The mapping entry to register.
        """
        key = f"{mapping.s100_product}:{mapping.feature_type}"
        self._registry[key] = mapping

    def lookup(self, product: str, feature_type: str) -> S100MappingEntry | None:
        """Look up a mapping by product and feature type.

        Args:
            product: S-100 product spec (e.g., 'S-101').
            feature_type: Feature type name.

        Returns:
            The mapping entry, or None if not found.
        """
        return self._registry.get(f"{product}:{feature_type}")

    def list_mappings(self, product: str | None = None) -> list[S100MappingEntry]:
        """List all registered mappings, optionally filtered by product.

        Args:
            product: Optional product spec to filter by.

        Returns:
            List of mapping entries.
        """
        if product is None:
            return list(self._registry.values())
        return [m for m in self._registry.values() if m.s100_product == product]

    @property
    def mapping_count(self) -> int:
        """Total number of registered mappings."""
        return len(self._registry)
