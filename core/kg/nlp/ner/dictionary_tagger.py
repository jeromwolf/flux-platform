"""Dictionary-based Named Entity Tagger.

Performs simple substring matching against a term→NERTagType mapping.
Korean terms are matched exactly (case-sensitive); ASCII/Latin terms
are matched case-insensitively.

This tagger satisfies the NERTagger protocol via duck typing — it does
NOT inherit from NERTagger.
"""

from __future__ import annotations

from kg.nlp.ner.models import NERTag, NERTagType

# ---------------------------------------------------------------------------
# Label-to-NERTagType mapping used by from_maritime_terms()
# ---------------------------------------------------------------------------

# Maps Neo4j entity label strings (from ENTITY_SYNONYMS values) to the
# corresponding NERTagType.  Labels not listed here are silently ignored
# when building the dictionary.
_LABEL_TO_NER_TYPE: dict[str, NERTagType] = {
    # Vessel subtypes → VESSEL
    "Vessel": NERTagType.VESSEL,
    "CargoShip": NERTagType.VESSEL,
    "Tanker": NERTagType.VESSEL,
    "FishingVessel": NERTagType.VESSEL,
    "PassengerShip": NERTagType.VESSEL,
    "NavalVessel": NERTagType.VESSEL,
    "AutonomousVessel": NERTagType.VESSEL,
    # Port subtypes → PORT
    "Port": NERTagType.PORT,
    "TradePort": NERTagType.PORT,
    "CoastalPort": NERTagType.PORT,
    "FishingPort": NERTagType.PORT,
    "Terminal": NERTagType.PORT,
    # Berth
    "Berth": NERTagType.BERTH,
    "Anchorage": NERTagType.BERTH,
    # Sea areas
    "SeaArea": NERTagType.SEA_AREA,
    "EEZ": NERTagType.SEA_AREA,
    "TerritorialSea": NERTagType.SEA_AREA,
    "CoastalRegion": NERTagType.SEA_AREA,
    "Waterway": NERTagType.SEA_AREA,
    "Channel": NERTagType.SEA_AREA,
    "TSS": NERTagType.SEA_AREA,
    # Organizations → ORG
    "Organization": NERTagType.ORG,
    "GovernmentAgency": NERTagType.ORG,
    "ShippingCompany": NERTagType.ORG,
    "ResearchInstitute": NERTagType.ORG,
    "ClassificationSociety": NERTagType.ORG,
    # Facilities → FACILITY
    "TestFacility": NERTagType.FACILITY,
    "TowingTank": NERTagType.FACILITY,
    "OceanEngineeringBasin": NERTagType.FACILITY,
    "IceTank": NERTagType.FACILITY,
    "DeepOceanBasin": NERTagType.FACILITY,
    "WaveEnergyTestSite": NERTagType.FACILITY,
    "HyperbaricChamber": NERTagType.FACILITY,
    "CavitationTunnel": NERTagType.FACILITY,
    "LargeCavitationTunnel": NERTagType.FACILITY,
    "MediumCavitationTunnel": NERTagType.FACILITY,
    "HighSpeedCavitationTunnel": NERTagType.FACILITY,
    "BridgeSimulator": NERTagType.FACILITY,
    # Regulations → REGULATION
    "Regulation": NERTagType.REGULATION,
    "COLREG": NERTagType.REGULATION,
    "SOLAS": NERTagType.REGULATION,
    "MARPOL": NERTagType.REGULATION,
    # Model ships → MODEL_SHIP
    "ModelShip": NERTagType.MODEL_SHIP,
    # Experiments → EXPERIMENT
    "Experiment": NERTagType.EXPERIMENT,
    "ExperimentalDataset": NERTagType.EXPERIMENT,
    "TestCondition": NERTagType.EXPERIMENT,
    "Measurement": NERTagType.EXPERIMENT,
    # Weather → WEATHER
    "WeatherCondition": NERTagType.WEATHER,
    "WeatherStation": NERTagType.WEATHER,
}

# NAMED_ENTITIES label string → NERTagType
_NAMED_ENTITY_LABEL_TO_NER_TYPE: dict[str, NERTagType] = {
    "Port": NERTagType.PORT,
    "SeaArea": NERTagType.SEA_AREA,
    "Organization": NERTagType.ORG,
}


class DictionaryTagger:
    """Named entity tagger backed by an explicit term dictionary.

    Uses simple substring matching: Korean terms are compared with exact
    (case-sensitive) matching; ASCII strings are matched
    case-insensitively.

    Satisfies the NERTagger protocol via duck typing.

    Example::

        tagger = DictionaryTagger.from_maritime_terms()
        tags = tagger.tag("부산항에서 COLREG 협약을 준수한다.")
    """

    def __init__(
        self,
        entries: dict[str, NERTagType] | None = None,
    ) -> None:
        """Initialise with an explicit term→type mapping.

        Args:
            entries: Mapping from surface-form term strings to their
                NERTagType.  If *None*, an empty tagger is created.
        """
        self._entries: dict[str, NERTagType] = dict(entries) if entries else {}

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_maritime_terms(cls) -> DictionaryTagger:
        """Create a DictionaryTagger pre-loaded with maritime terminology.

        Reads ENTITY_SYNONYMS and NAMED_ENTITIES from
        ``maritime.nlp.maritime_terms`` (via the shim at
        ``kg.nlp.maritime_terms``) and maps every entry to the
        appropriate NERTagType.

        Returns:
            A new DictionaryTagger instance covering maritime entities.
        """
        # Lazy import to avoid circular dependencies and allow use of the
        # tagger in environments where maritime terms may not be loaded.
        from kg.nlp.maritime_terms import ENTITY_SYNONYMS, NAMED_ENTITIES  # noqa: PLC0415

        entries: dict[str, NERTagType] = {}

        # --- ENTITY_SYNONYMS: term -> Neo4j label ---
        for term, neo4j_label in ENTITY_SYNONYMS.items():
            ner_type = _LABEL_TO_NER_TYPE.get(neo4j_label)
            if ner_type is not None:
                entries[term] = ner_type

        # --- NAMED_ENTITIES: name -> {label, key, value} ---
        for name, meta in NAMED_ENTITIES.items():
            label = meta.get("label", "")
            ner_type = _NAMED_ENTITY_LABEL_TO_NER_TYPE.get(label)
            if ner_type is not None:
                entries[name] = ner_type

        return cls(entries=entries)

    # ------------------------------------------------------------------
    # NERTagger protocol implementation
    # ------------------------------------------------------------------

    def tag(self, text: str) -> list[NERTag]:
        """Extract named entities from *text* via substring matching.

        Korean terms are matched with exact (case-sensitive) search.
        ASCII/Latin terms are matched case-insensitively.

        Args:
            text: Raw input string to scan.

        Returns:
            List of NERTag instances for every match found, unsorted.
        """
        tags: list[NERTag] = []
        text_lower = text.lower()

        for term, ner_type in self._entries.items():
            # Determine matching strategy: ASCII → case-insensitive.
            is_ascii = term.isascii()
            search_term = term.lower() if is_ascii else term
            search_text = text_lower if is_ascii else text

            start = 0
            while True:
                pos = search_text.find(search_term, start)
                if pos == -1:
                    break
                end = pos + len(term)
                # Extract the actual span from the original text.
                actual_text = text[pos:end]
                tags.append(
                    NERTag(
                        text=actual_text,
                        tag_type=ner_type,
                        start=pos,
                        end=end,
                        confidence=1.0,
                        source=self.name,
                        normalized="",
                    )
                )
                start = pos + 1  # allow overlapping matches from same term

        return tags

    @property
    def name(self) -> str:
        """Tagger identifier string."""
        return "dictionary"

    @property
    def supported_types(self) -> frozenset[NERTagType]:
        """Set of NERTagType values present in the loaded entries."""
        return frozenset(self._entries.values())
