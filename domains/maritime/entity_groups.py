"""Entity group and color mappings for the Maritime Knowledge Graph.

Centralizes the mapping between Neo4j node labels, their semantic groups,
and display colors. This eliminates duplication between the PoC visualizer
and the production API.
"""

from __future__ import annotations

ENTITY_GROUPS: dict[str, list[str]] = {
    "PhysicalEntity": [
        "Vessel",
        "CargoShip",
        "Tanker",
        "FishingVessel",
        "PassengerShip",
        "NavalVessel",
        "AutonomousVessel",
        "Port",
        "TradePort",
        "CoastalPort",
        "FishingPort",
        "PortFacility",
        "Berth",
        "Anchorage",
        "Terminal",
        "Waterway",
        "TSS",
        "Channel",
        "Cargo",
        "DangerousGoods",
        "BulkCargo",
        "ContainerCargo",
        "Sensor",
        "AISTransceiver",
        "Radar",
        "CCTVCamera",
        "WeatherStation",
    ],
    "SpatialEntity": [
        "SeaArea",
        "EEZ",
        "TerritorialSea",
        "CoastalRegion",
        "GeoPoint",
    ],
    "TemporalEntity": [
        "Voyage",
        "PortCall",
        "TrackSegment",
        "Incident",
        "Collision",
        "Grounding",
        "Pollution",
        "Distress",
        "IllegalFishing",
        "WeatherCondition",
        "Activity",
        "Loading",
        "Unloading",
        "Bunkering",
        "Anchoring",
        "Loitering",
    ],
    "InformationEntity": [
        "Regulation",
        "COLREG",
        "SOLAS",
        "MARPOL",
        "IMDGCode",
        "Document",
        "AccidentReport",
        "InspectionReport",
        "NavigationalWarning",
        "CargoManifest",
        "DataSource",
        "APIEndpoint",
        "StreamSource",
        "FileSource",
        "Service",
        "QueryService",
        "AnalysisService",
        "AlertService",
        "PredictionService",
    ],
    "Observation": [
        "SARObservation",
        "OpticalObservation",
        "CCTVObservation",
        "AISObservation",
        "RadarObservation",
        "WeatherObservation",
    ],
    "Agent": [
        "Organization",
        "GovernmentAgency",
        "ShippingCompany",
        "ResearchInstitute",
        "ClassificationSociety",
        "Person",
        "CrewMember",
        "Inspector",
    ],
    "PlatformResource": [
        "Workflow",
        "WorkflowNode",
        "WorkflowExecution",
        "AIModel",
        "DataPipeline",
        "AIAgent",
        "MCPTool",
        "MCPResource",
    ],
    "MultimodalData": [
        "AISData",
        "SatelliteImage",
        "RadarImage",
        "SensorReading",
        "MaritimeChart",
        "VideoClip",
    ],
    "MultimodalRepresentation": [
        "VisualEmbedding",
        "TrajectoryEmbedding",
        "TextEmbedding",
        "FusedEmbedding",
    ],
    "KRISO": [
        "Experiment",
        "TestFacility",
        "TowingTank",
        "OceanEngineeringBasin",
        "IceTank",
        "DeepOceanBasin",
        "WaveEnergyTestSite",
        "HyperbaricChamber",
        "CavitationTunnel",
        "LargeCavitationTunnel",
        "MediumCavitationTunnel",
        "HighSpeedCavitationTunnel",
        "BridgeSimulator",
        "ExperimentalDataset",
        "TestCondition",
        "ModelShip",
        "Measurement",
        "Resistance",
        "Propulsion",
        "Maneuvering",
        "Seakeeping",
        "IcePerformance",
        "StructuralResponse",
    ],
    "RBAC": [
        "User",
        "Role",
        "DataClass",
        "Permission",
    ],
}

GROUP_COLORS: dict[str, str] = {
    "PhysicalEntity": "#4A90D9",
    "SpatialEntity": "#50C878",
    "TemporalEntity": "#E67E22",
    "InformationEntity": "#9B59B6",
    "Observation": "#E74C3C",
    "Agent": "#F39C12",
    "PlatformResource": "#1ABC9C",
    "MultimodalData": "#3498DB",
    "MultimodalRepresentation": "#5DADE2",
    "KRISO": "#FF6B35",
    "RBAC": "#95A5A6",
}

# Build reverse mapping: label -> group
_LABEL_TO_GROUP: dict[str, str] = {}
for _group, _labels in ENTITY_GROUPS.items():
    for _label in _labels:
        _LABEL_TO_GROUP[_label] = _group


def get_group_for_label(label: str) -> str:
    """Return the entity group name for a given Neo4j label.

    Args:
        label: A Neo4j node label (e.g. ``"Vessel"``, ``"Port"``).

    Returns:
        The group name, or ``"Unknown"`` if the label is not mapped.
    """
    return _LABEL_TO_GROUP.get(label, "Unknown")


def get_color_for_label(label: str) -> str:
    """Return the hex color for a given Neo4j label.

    Args:
        label: A Neo4j node label.

    Returns:
        Hex color string, or ``"#888888"`` for unknown labels.
    """
    group = get_group_for_label(label)
    return GROUP_COLORS.get(group, "#888888")
