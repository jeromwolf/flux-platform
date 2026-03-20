"""Korean maritime terminology dictionary for NL-to-Cypher translation.

Maps Korean maritime terms to their corresponding Neo4j entity labels,
relationship types, and property values.  Used by the NL query pipeline
to improve entity recognition and query accuracy.

Usage::

    from kg.nlp.maritime_terms import (
        ENTITY_SYNONYMS,
        RELATIONSHIP_KEYWORDS,
        PROPERTY_VALUE_MAP,
        resolve_entity,
        resolve_property_value,
    )
"""

from __future__ import annotations

# =========================================================================
# 1. Entity Label Synonyms (Korean -> Neo4j Label)
# =========================================================================

ENTITY_SYNONYMS: dict[str, str] = {
    # Vessel types
    "선박": "Vessel",
    "배": "Vessel",
    "화물선": "CargoShip",
    "컨테이너선": "CargoShip",
    "탱커": "Tanker",
    "유조선": "Tanker",
    "LNG선": "Tanker",
    "어선": "FishingVessel",
    "여객선": "PassengerShip",
    "페리": "PassengerShip",
    "크루즈": "PassengerShip",
    "군함": "NavalVessel",
    "해군함정": "NavalVessel",
    "자율운항선박": "AutonomousVessel",
    "자율운항선": "AutonomousVessel",
    "무인선": "AutonomousVessel",
    # Port types
    "항구": "Port",
    "항만": "Port",
    "무역항": "TradePort",
    "연안항": "CoastalPort",
    "어항": "FishingPort",
    "부두": "Berth",
    "선석": "Berth",
    "정박지": "Anchorage",
    "터미널": "Terminal",
    # Waterways
    "해협": "Waterway",
    "수로": "Channel",
    "통항분리대": "TSS",
    # Cargo
    "화물": "Cargo",
    "위험물": "DangerousGoods",
    "벌크화물": "BulkCargo",
    "산적화물": "BulkCargo",
    "컨테이너": "ContainerCargo",
    # Spatial
    "해역": "SeaArea",
    "바다": "SeaArea",
    "배타적경제수역": "EEZ",
    "EEZ": "EEZ",
    "영해": "TerritorialSea",
    "연안": "CoastalRegion",
    # Temporal
    "항해": "Voyage",
    "항차": "Voyage",
    "입항": "PortCall",
    "사고": "Incident",
    "충돌": "Collision",
    "좌초": "Grounding",
    "오염": "Pollution",
    "해양오염": "Pollution",
    "조난": "Distress",
    "불법조업": "IllegalFishing",
    "기상": "WeatherCondition",
    "날씨": "WeatherCondition",
    "해상상태": "WeatherCondition",
    # Sensors
    "센서": "Sensor",
    "AIS": "AISTransceiver",
    "레이더": "Radar",
    "CCTV": "CCTVCamera",
    "기상관측소": "WeatherStation",
    # Organizations
    "기관": "Organization",
    "정부기관": "GovernmentAgency",
    "해운사": "ShippingCompany",
    "연구소": "ResearchInstitute",
    "선급": "ClassificationSociety",
    # Regulations
    "규정": "Regulation",
    "협약": "Regulation",
    "국제규칙": "Regulation",
    "COLREG": "COLREG",
    "SOLAS": "SOLAS",
    "MARPOL": "MARPOL",
    # Documents
    "문서": "Document",
    "보고서": "Document",
    "논문": "Document",
    "사고보고서": "AccidentReport",
    "검사보고서": "InspectionReport",
    "항행경보": "NavigationalWarning",
    # KRISO
    "실험": "Experiment",
    "시험": "Experiment",
    "시험시설": "TestFacility",
    "시험설비": "TestFacility",
    "예인수조": "TowingTank",
    "해양공학수조": "OceanEngineeringBasin",
    "빙해수조": "IceTank",
    "심해공학수조": "DeepOceanBasin",
    "파력발전시험장": "WaveEnergyTestSite",
    "고압챔버": "HyperbaricChamber",
    "캐비테이션터널": "CavitationTunnel",
    "대형캐비테이션터널": "LargeCavitationTunnel",
    "중형캐비테이션터널": "MediumCavitationTunnel",
    "고속캐비테이션터널": "HighSpeedCavitationTunnel",
    "선박운항시뮬레이터": "BridgeSimulator",
    "시뮬레이터": "BridgeSimulator",
    "데이터셋": "ExperimentalDataset",
    "시험조건": "TestCondition",
    "측정": "Measurement",
    "모형선": "ModelShip",
    "저항": "Resistance",
    "추진": "Propulsion",
    "조종": "Maneuvering",
    "내항": "Seakeeping",
    "내항성능": "Seakeeping",
    "빙성능": "IcePerformance",
    "구조응답": "StructuralResponse",
    # RBAC
    "사용자": "User",
    "역할": "Role",
    "권한": "Permission",
    "데이터등급": "DataClass",
}


# =========================================================================
# 2. Relationship Keywords (Korean phrase -> Relationship type)
# =========================================================================

RELATIONSHIP_KEYWORDS: dict[str, str] = {
    "위치한": "LOCATED_AT",
    "정박한": "DOCKED_AT",
    "묘박한": "ANCHORED_AT",
    "항해중인": "ON_VOYAGE",
    "출발한": "FROM_PORT",
    "도착할": "TO_PORT",
    "운반하는": "CARRIES",
    "수행하는": "PERFORMS",
    "관측된": "PRODUCES",
    "영향받는": "AFFECTS",
    "원인된": "CAUSED_BY",
    "관련된": "INVOLVES",
    "위반한": "VIOLATED",
    "검사한": "INSPECTED_BY",
    "발행한": "ISSUED_BY",
    "소유한": "OWNED_BY",
    "소속된": "BELONGS_TO",
    "실시한": "CONDUCTED_AT",
    "생성한": "PRODUCED",
    "포함하는": "CONTAINS",
    "접근가능한": "CAN_ACCESS",
    "역할가진": "HAS_ROLE",
}


# =========================================================================
# 3. Property Value Mappings (Korean value -> English property value)
# =========================================================================

PROPERTY_VALUE_MAP: dict[str, dict[str, str]] = {
    "vesselType": {
        "컨테이너선": "ContainerShip",
        "벌크선": "BulkCarrier",
        "탱커": "Tanker",
        "유조선": "Tanker",
        "LNG선": "LNGCarrier",
        "여객선": "PassengerShip",
        "어선": "FishingVessel",
    },
    "currentStatus": {
        "항해중": "UNDERWAY",
        "정박중": "AT_BERTH",
        "묘박중": "AT_ANCHOR",
        "조업중": "FISHING",
        "정지": "STOPPED",
    },
    "incidentType": {
        "충돌": "Collision",
        "좌초": "Grounding",
        "오염": "Pollution",
        "조난": "Distress",
        "화재": "Fire",
    },
    "severity": {
        "경미": "LOW",
        "보통": "MODERATE",
        "심각": "HIGH",
        "치명": "CRITICAL",
    },
    "riskLevel": {
        "낮음": "LOW",
        "보통": "MODERATE",
        "높음": "HIGH",
        "매우높음": "VERY_HIGH",
    },
    "facilityType": {
        "예인수조": "TowingTank",
        "해양공학수조": "OceanEngineeringBasin",
        "빙해수조": "IceTank",
        "심해공학수조": "DeepOceanBasin",
        "파력발전시험장": "WaveEnergyTestSite",
        "고압챔버": "HyperbaricChamber",
        "캐비테이션터널": "CavitationTunnel",
        "시뮬레이터": "BridgeSimulator",
    },
}


# =========================================================================
# 4. Named Entity Mappings (commonly referenced entities)
# =========================================================================

NAMED_ENTITIES: dict[str, dict[str, str]] = {
    # Ports
    "부산항": {"label": "Port", "key": "unlocode", "value": "KRPUS"},
    "인천항": {"label": "Port", "key": "unlocode", "value": "KRICN"},
    "울산항": {"label": "Port", "key": "unlocode", "value": "KRULS"},
    "여수광양항": {"label": "Port", "key": "unlocode", "value": "KRYOS"},
    "평택당진항": {"label": "Port", "key": "unlocode", "value": "KRPTK"},
    # Sea areas
    "남해": {"label": "SeaArea", "key": "name", "value": "남해"},
    "동해": {"label": "SeaArea", "key": "name", "value": "동해"},
    "서해": {"label": "SeaArea", "key": "name", "value": "서해"},
    "대한해협": {"label": "SeaArea", "key": "name", "value": "대한해협"},
    # Organizations
    "KRISO": {"label": "Organization", "key": "orgId", "value": "ORG-KRISO"},
    "해양수산부": {"label": "Organization", "key": "orgId", "value": "ORG-MOF"},
    "부산항만공사": {"label": "Organization", "key": "orgId", "value": "ORG-BPA"},
    "한국선급": {"label": "Organization", "key": "orgId", "value": "ORG-KR"},
    "HMM": {"label": "Organization", "key": "orgId", "value": "ORG-HMM"},
    "해양경찰청": {"label": "Organization", "key": "orgId", "value": "ORG-KCG"},
}


# =========================================================================
# 5. Helper Functions
# =========================================================================


def resolve_entity(korean_term: str) -> str | None:
    """Resolve a Korean term to its Neo4j entity label.

    Args:
        korean_term: Korean text to look up.

    Returns:
        Neo4j label string, or None if not found.
    """
    # Exact match
    if korean_term in ENTITY_SYNONYMS:
        return ENTITY_SYNONYMS[korean_term]

    # Partial match (check if term is contained in any key)
    for key, label in ENTITY_SYNONYMS.items():
        if key in korean_term or korean_term in key:
            return label

    return None


def resolve_property_value(
    property_name: str,
    korean_value: str,
) -> str | None:
    """Resolve a Korean property value to its English equivalent.

    Args:
        property_name: The Neo4j property name (e.g., 'vesselType').
        korean_value: The Korean value to look up.

    Returns:
        English property value, or None if not found.
    """
    prop_map = PROPERTY_VALUE_MAP.get(property_name, {})
    return prop_map.get(korean_value)


def resolve_named_entity(name: str) -> dict[str, str] | None:
    """Resolve a named entity (port, org, sea area) to its Neo4j match criteria.

    Args:
        name: Korean name of the entity.

    Returns:
        Dict with 'label', 'key', 'value' for Cypher MATCH, or None.
    """
    return NAMED_ENTITIES.get(name)


def get_term_context_for_llm() -> str:
    """Generate a compact term reference string for LLM prompts.

    Returns a formatted string listing key Korean-English mappings
    that can be injected into an LLM system prompt.
    """
    lines = ["Korean Maritime Terms Reference:"]

    lines.append("\nEntity Labels:")
    # Group by label to deduplicate
    label_terms: dict[str, list[str]] = {}
    for term, label in ENTITY_SYNONYMS.items():
        label_terms.setdefault(label, []).append(term)
    for label, terms in sorted(label_terms.items()):
        lines.append(f"  {', '.join(terms[:3])} -> :{label}")

    lines.append("\nProperty Values:")
    for prop, mapping in PROPERTY_VALUE_MAP.items():
        entries = [f"{k}={v}" for k, v in list(mapping.items())[:4]]
        lines.append(f"  {prop}: {', '.join(entries)}")

    return "\n".join(lines)
