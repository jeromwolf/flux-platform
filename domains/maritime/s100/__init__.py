"""IHO S-100 Electronic Navigational Chart (ENC) mapping to Knowledge Graph.

This module provides mapping between IHO S-100 feature types and the
IMSP Knowledge Graph ontology, enabling ingestion of S-100 ENC data
(e.g., S-101 bathymetry, S-102 surface currents, S-104 tidal data)
into the maritime knowledge graph.

See: https://iho.int/en/s-100-edition-5-1-0
"""

from maritime.s100.s100_mapping import S100FeatureMapping, S100ToKGMapper
