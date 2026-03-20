"""Keyword-based relation extractor for maritime domain.

Extracts entity mentions and relationships from text using keyword matching.
Designed to enrich crawled documents with knowledge graph relationships.

Future extension: Replace keyword matching with NER/RE models.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExtractedRelation:
    """A relation extracted from text."""

    source_id: str
    target_type: str
    target_name: str
    relation_type: str
    confidence: float
    context: str  # Snippet of text where the relation was found


# Maritime domain keyword patterns
VESSEL_TYPE_KEYWORDS = {
    "컨테이너선": "ContainerShip",
    "유조선": "Tanker",
    "벌크선": "BulkCarrier",
    "화물선": "CargoShip",
    "여객선": "PassengerShip",
    "어선": "FishingVessel",
    "자율운항선": "AutonomousVessel",
    "container ship": "ContainerShip",
    "tanker": "Tanker",
    "bulk carrier": "BulkCarrier",
    "cargo ship": "CargoShip",
    "MASS": "AutonomousVessel",
}

PORT_KEYWORDS = {
    "부산항": "KRPUS",
    "인천항": "KRINC",
    "울산항": "KRULS",
    "여수항": "KRYOS",
    "광양항": "KRKWA",
    "목포항": "KRMOK",
    "평택항": "KRPTK",
    "마산항": "KRMAS",
    "Busan": "KRPUS",
    "Incheon": "KRINC",
    "Ulsan": "KRULS",
}

SEA_AREA_KEYWORDS = {
    "동해": "동해",
    "서해": "서해",
    "남해": "남해",
    "동중국해": "동중국해",
    "대한해협": "대한해협",
    "제주해협": "제주해협",
    "East Sea": "동해",
    "Yellow Sea": "서해",
    "South Sea": "남해",
}

TOPIC_KEYWORDS = {
    "선박 설계": "ShipDesign",
    "유체역학": "Hydrodynamics",
    "추진": "Propulsion",
    "저항": "Resistance",
    "내항성능": "Seakeeping",
    "조종성능": "Maneuvering",
    "구조": "Structure",
    "빙해": "IceNavigation",
    "자율운항": "AutonomousNavigation",
    "충돌": "CollisionAvoidance",
    "해양에너지": "OceanEnergy",
    "해양환경": "MarineEnvironment",
    "안전": "Safety",
    "AIS": "AIS",
    "IoT": "IoT",
    "딥러닝": "DeepLearning",
    "머신러닝": "MachineLearning",
    "CFD": "CFD",
    "FEM": "FEM",
    "시뮬레이션": "Simulation",
    "디지털 트윈": "DigitalTwin",
    "deep learning": "DeepLearning",
    "machine learning": "MachineLearning",
    "autonomous": "AutonomousNavigation",
}

REGULATION_KEYWORDS = {
    "SOLAS": "SOLAS",
    "MARPOL": "MARPOL",
    "COLREG": "COLREG",
    "IMO": "IMO",
    "IMDG": "IMDGCode",
    "해사안전법": "MaritimeSafetyAct",
    "선박안전법": "ShipSafetyAct",
    "해양환경관리법": "MarineEnvironmentAct",
}

FACILITY_KEYWORDS = {
    "예인수조": "TF-LTT",
    "해양공학수조": "TF-OEB",
    "빙해수조": "TF-ICE",
    "심해공학수조": "TF-DOB",
    "towing tank": "TF-LTT",
    "ocean engineering basin": "TF-OEB",
    "ice tank": "TF-ICE",
}


class RelationExtractor:
    """Extract relations from text using keyword matching.

    Usage::
        extractor = RelationExtractor()
        relations = extractor.extract_all("docId-123", text, keywords)
    """

    def extract_vessel_types(self, source_id: str, text: str) -> list[ExtractedRelation]:
        """Find vessel type mentions in text."""
        relations = []
        text_lower = text.lower()
        for keyword, vessel_type in VESSEL_TYPE_KEYWORDS.items():
            if keyword.lower() in text_lower:
                idx = text_lower.index(keyword.lower())
                start = max(0, idx - 30)
                end = min(len(text), idx + len(keyword) + 30)
                relations.append(
                    ExtractedRelation(
                        source_id=source_id,
                        target_type="VesselType",
                        target_name=vessel_type,
                        relation_type="ABOUT_VESSEL_TYPE",
                        confidence=0.7,
                        context=text[start:end],
                    )
                )
        return relations

    def extract_ports(self, source_id: str, text: str) -> list[ExtractedRelation]:
        """Find port mentions in text."""
        relations = []
        for keyword, port_code in PORT_KEYWORDS.items():
            if keyword in text:
                idx = text.index(keyword)
                start = max(0, idx - 30)
                end = min(len(text), idx + len(keyword) + 30)
                relations.append(
                    ExtractedRelation(
                        source_id=source_id,
                        target_type="Port",
                        target_name=port_code,
                        relation_type="MENTIONS_PORT",
                        confidence=0.8,
                        context=text[start:end],
                    )
                )
        return relations

    def extract_sea_areas(self, source_id: str, text: str) -> list[ExtractedRelation]:
        """Find sea area mentions in text."""
        relations = []
        for keyword, area_name in SEA_AREA_KEYWORDS.items():
            if keyword in text:
                idx = text.index(keyword)
                start = max(0, idx - 30)
                end = min(len(text), idx + len(keyword) + 30)
                relations.append(
                    ExtractedRelation(
                        source_id=source_id,
                        target_type="SeaArea",
                        target_name=area_name,
                        relation_type="MENTIONS_AREA",
                        confidence=0.75,
                        context=text[start:end],
                    )
                )
        return relations

    def extract_topics(
        self, source_id: str, text: str, keywords: list[str] | None = None
    ) -> list[ExtractedRelation]:
        """Find research topic mentions in text and keywords."""
        relations = []
        search_text = text
        if keywords:
            search_text += " " + " ".join(keywords)

        search_lower = search_text.lower()
        for keyword, topic in TOPIC_KEYWORDS.items():
            if keyword.lower() in search_lower:
                relations.append(
                    ExtractedRelation(
                        source_id=source_id,
                        target_type="Topic",
                        target_name=topic,
                        relation_type="ABOUT_TOPIC",
                        confidence=0.65,
                        context=keyword,
                    )
                )
        return relations

    def extract_regulations(self, source_id: str, text: str) -> list[ExtractedRelation]:
        """Find regulation mentions in text."""
        relations = []
        for keyword, reg_name in REGULATION_KEYWORDS.items():
            if keyword in text:
                idx = text.index(keyword)
                start = max(0, idx - 30)
                end = min(len(text), idx + len(keyword) + 30)
                relations.append(
                    ExtractedRelation(
                        source_id=source_id,
                        target_type="Regulation",
                        target_name=reg_name,
                        relation_type="REFERENCES_REGULATION",
                        confidence=0.85,
                        context=text[start:end],
                    )
                )
        return relations

    def extract_facilities(self, source_id: str, text: str) -> list[ExtractedRelation]:
        """Find KRISO facility mentions in text."""
        relations = []
        text_lower = text.lower()
        for keyword, facility_id in FACILITY_KEYWORDS.items():
            if keyword.lower() in text_lower:
                relations.append(
                    ExtractedRelation(
                        source_id=source_id,
                        target_type="TestFacility",
                        target_name=facility_id,
                        relation_type="USES_FACILITY",
                        confidence=0.8,
                        context=keyword,
                    )
                )
        return relations

    def extract_all(
        self, source_id: str, text: str, keywords: list[str] | None = None
    ) -> list[ExtractedRelation]:
        """Extract all types of relations from text.

        Parameters
        ----------
        source_id : str
            ID of the source entity (e.g., document ID)
        text : str
            Full text to analyze
        keywords : list[str] | None
            Additional keywords (e.g., from paper metadata)

        Returns
        -------
        list[ExtractedRelation]
            All extracted relations, deduplicated
        """
        if not text:
            return []

        all_relations = []
        all_relations.extend(self.extract_vessel_types(source_id, text))
        all_relations.extend(self.extract_ports(source_id, text))
        all_relations.extend(self.extract_sea_areas(source_id, text))
        all_relations.extend(self.extract_topics(source_id, text, keywords))
        all_relations.extend(self.extract_regulations(source_id, text))
        all_relations.extend(self.extract_facilities(source_id, text))

        # Deduplicate by (source_id, target_type, target_name, relation_type)
        seen = set()
        unique = []
        for rel in all_relations:
            key = (rel.source_id, rel.target_type, rel.target_name, rel.relation_type)
            if key not in seen:
                seen.add(key)
                unique.append(rel)

        return unique
