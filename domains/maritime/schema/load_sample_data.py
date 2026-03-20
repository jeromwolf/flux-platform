"""Load realistic Korean maritime sample data into Neo4j.

Creates a comprehensive set of interconnected entities covering vessels,
ports, sea areas, voyages, KRISO facilities, regulations, weather,
incidents, and sensors.  All mutations use MERGE for idempotency.

Usage::

    python -m kg.schema.load_sample_data
"""

from __future__ import annotations

from kg.config import get_config, get_driver

# =========================================================================
# Helper
# =========================================================================


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# =========================================================================
# 1. Organizations
# =========================================================================


def _create_organizations(tx) -> None:
    _section("Organizations (7)")
    query = """
    UNWIND $orgs AS o
    MERGE (org:Organization {orgId: o.orgId})
      ON CREATE SET
        org.name      = o.name,
        org.nameEn    = o.nameEn,
        org.orgType   = o.orgType,
        org.createdAt = datetime()
      ON MATCH SET
        org.name      = o.name,
        org.nameEn    = o.nameEn,
        org.orgType   = o.orgType,
        org.updatedAt = datetime()
    WITH org, o
    CALL apoc.create.addLabels(org, [o.label]) YIELD node
    RETURN count(node) AS cnt
    """
    # Fallback query without APOC (uses FOREACH trick for conditional label)
    query_no_apoc = """
    UNWIND $orgs AS o
    MERGE (org:Organization {orgId: o.orgId})
      ON CREATE SET
        org.name      = o.name,
        org.nameEn    = o.nameEn,
        org.orgType   = o.orgType,
        org.createdAt = datetime()
      ON MATCH SET
        org.name      = o.name,
        org.nameEn    = o.nameEn,
        org.orgType   = o.orgType,
        org.updatedAt = datetime()
    RETURN count(org) AS cnt
    """

    orgs = [
        {
            "orgId": "ORG-KRISO",
            "name": "한국해양과학기술원 부설 선박해양플랜트연구소",
            "nameEn": "Korea Research Institute of Ships and Ocean Engineering",
            "orgType": "ResearchInstitute",
            "label": "ResearchInstitute",
        },
        {
            "orgId": "ORG-MOF",
            "name": "해양수산부",
            "nameEn": "Ministry of Oceans and Fisheries",
            "orgType": "GovernmentAgency",
            "label": "GovernmentAgency",
        },
        {
            "orgId": "ORG-BPA",
            "name": "부산항만공사",
            "nameEn": "Busan Port Authority",
            "orgType": "GovernmentAgency",
            "label": "GovernmentAgency",
        },
        {
            "orgId": "ORG-KR",
            "name": "한국선급",
            "nameEn": "Korean Register",
            "orgType": "ClassificationSociety",
            "label": "ClassificationSociety",
        },
        {
            "orgId": "ORG-HMM",
            "name": "HMM (현대상선)",
            "nameEn": "HMM Co., Ltd.",
            "orgType": "ShippingCompany",
            "label": "ShippingCompany",
        },
        {
            "orgId": "ORG-PANOCEAN",
            "name": "팬오션",
            "nameEn": "Pan Ocean Co., Ltd.",
            "orgType": "ShippingCompany",
            "label": "ShippingCompany",
        },
        {
            "orgId": "ORG-KCG",
            "name": "해양경찰청",
            "nameEn": "Korea Coast Guard",
            "orgType": "GovernmentAgency",
            "label": "GovernmentAgency",
        },
    ]

    # Try with APOC first, fall back to plain Cypher
    try:
        result = tx.run(query, orgs=orgs)
        cnt = result.single()["cnt"]
    except Exception:
        result = tx.run(query_no_apoc, orgs=orgs)
        cnt = result.single()["cnt"]

    # Add sub-labels individually (works without APOC)
    for o in orgs:
        tx.run(
            f"MATCH (org:Organization {{orgId: $orgId}}) SET org:{o['label']}",
            orgId=o["orgId"],
        )

    print(f"  -> Merged {cnt} organizations")


# =========================================================================
# 2. Ports
# =========================================================================


def _create_ports(tx) -> None:
    _section("Ports (5)")
    query = """
    UNWIND $ports AS p
    MERGE (port:Port {unlocode: p.unlocode})
      ON CREATE SET
        port.name       = p.name,
        port.nameEn     = p.nameEn,
        port.country    = 'KR',
        port.location   = point({latitude: p.lat, longitude: p.lon}),
        port.portType   = p.portType,
        port.maxDraft   = p.maxDraft,
        port.berthCount = p.berthCount,
        port.timezone   = 'Asia/Seoul',
        port.createdAt  = datetime()
      ON MATCH SET
        port.name       = p.name,
        port.nameEn     = p.nameEn,
        port.location   = point({latitude: p.lat, longitude: p.lon}),
        port.portType   = p.portType,
        port.maxDraft   = p.maxDraft,
        port.berthCount = p.berthCount,
        port.updatedAt  = datetime()
    RETURN count(port) AS cnt
    """

    ports = [
        {
            "unlocode": "KRPUS",
            "name": "부산항",
            "nameEn": "Port of Busan",
            "lat": 35.1028,
            "lon": 129.0403,
            "portType": "TradePort",
            "maxDraft": 17.0,
            "berthCount": 169,
        },
        {
            "unlocode": "KRICN",
            "name": "인천항",
            "nameEn": "Port of Incheon",
            "lat": 37.4563,
            "lon": 126.5922,
            "portType": "TradePort",
            "maxDraft": 12.0,
            "berthCount": 73,
        },
        {
            "unlocode": "KRULS",
            "name": "울산항",
            "nameEn": "Port of Ulsan",
            "lat": 35.5007,
            "lon": 129.3855,
            "portType": "TradePort",
            "maxDraft": 15.0,
            "berthCount": 88,
        },
        {
            "unlocode": "KRYOS",
            "name": "여수광양항",
            "nameEn": "Port of Yeosu-Gwangyang",
            "lat": 34.7360,
            "lon": 127.7356,
            "portType": "TradePort",
            "maxDraft": 23.0,
            "berthCount": 95,
        },
        {
            "unlocode": "KRPTK",
            "name": "평택당진항",
            "nameEn": "Port of Pyeongtaek-Dangjin",
            "lat": 36.9640,
            "lon": 126.8180,
            "portType": "TradePort",
            "maxDraft": 14.0,
            "berthCount": 52,
        },
    ]

    # Add TradePort label to all ports
    result = tx.run(query, ports=ports)
    cnt = result.single()["cnt"]
    tx.run("MATCH (p:Port) WHERE p.portType = 'TradePort' SET p:TradePort")
    print(f"  -> Merged {cnt} ports")


# =========================================================================
# 3. Sea Areas & Waterways
# =========================================================================


def _create_sea_areas_and_waterways(tx) -> None:
    _section("Sea Areas (4) & Waterways (2)")

    # --- Sea Areas ---
    sea_query = """
    UNWIND $areas AS a
    MERGE (sa:SeaArea {name: a.name})
      ON CREATE SET
        sa.nameEn      = a.nameEn,
        sa.seaAreaType = a.seaAreaType,
        sa.createdAt   = datetime()
      ON MATCH SET
        sa.nameEn      = a.nameEn,
        sa.seaAreaType = a.seaAreaType,
        sa.updatedAt   = datetime()
    RETURN count(sa) AS cnt
    """
    areas = [
        {"name": "남해", "nameEn": "South Sea", "seaAreaType": "coastal_sea"},
        {"name": "동해", "nameEn": "East Sea", "seaAreaType": "marginal_sea"},
        {"name": "서해", "nameEn": "West Sea (Yellow Sea)", "seaAreaType": "marginal_sea"},
        {"name": "대한해협", "nameEn": "Korea Strait", "seaAreaType": "strait"},
    ]
    result = tx.run(sea_query, areas=areas)
    cnt_sa = result.single()["cnt"]
    print(f"  -> Merged {cnt_sa} sea areas")

    # --- Waterways ---
    ww_query = """
    UNWIND $waterways AS w
    MERGE (ww:Waterway {name: w.name})
      ON CREATE SET
        ww.nameEn        = w.nameEn,
        ww.waterwayType  = w.waterwayType,
        ww.tssApplicable = w.tssApplicable,
        ww.createdAt     = datetime()
      ON MATCH SET
        ww.nameEn        = w.nameEn,
        ww.waterwayType  = w.waterwayType,
        ww.tssApplicable = w.tssApplicable,
        ww.updatedAt     = datetime()
    RETURN count(ww) AS cnt
    """
    waterways = [
        {
            "name": "대한해협",
            "nameEn": "Korea Strait",
            "waterwayType": "strait",
            "tssApplicable": True,
        },
        {
            "name": "제주해협",
            "nameEn": "Jeju Strait",
            "waterwayType": "strait",
            "tssApplicable": True,
        },
    ]
    result = tx.run(ww_query, waterways=waterways)
    cnt_ww = result.single()["cnt"]
    print(f"  -> Merged {cnt_ww} waterways")

    # --- Waterway CONNECTS SeaArea ---
    # Korea Strait connects South Sea <-> East Sea
    tx.run("""
        MATCH (ww:Waterway {name: '대한해협'})
        MATCH (sa1:SeaArea {name: '남해'})
        MATCH (sa2:SeaArea {name: '동해'})
        MERGE (ww)-[:CONNECTS]->(sa1)
        MERGE (ww)-[:CONNECTS]->(sa2)
    """)
    # Jeju Strait connects South Sea <-> West Sea
    tx.run("""
        MATCH (ww:Waterway {name: '제주해협'})
        MATCH (sa1:SeaArea {name: '남해'})
        MATCH (sa2:SeaArea {name: '서해'})
        MERGE (ww)-[:CONNECTS]->(sa1)
        MERGE (ww)-[:CONNECTS]->(sa2)
    """)
    print("  -> Created waterway CONNECTS relationships")


# =========================================================================
# 4. Vessels
# =========================================================================


def _create_vessels(tx) -> None:
    _section("Vessels (5)")
    query = """
    UNWIND $vessels AS v
    MERGE (vessel:Vessel {mmsi: v.mmsi})
      ON CREATE SET
        vessel.imo             = v.imo,
        vessel.name            = v.name,
        vessel.nameEn          = v.nameEn,
        vessel.vesselType      = v.vesselType,
        vessel.flag            = v.flag,
        vessel.grossTonnage    = v.grossTonnage,
        vessel.length          = v.length,
        vessel.beam            = v.beam,
        vessel.draft           = v.draft,
        vessel.yearBuilt       = v.yearBuilt,
        vessel.currentStatus   = v.currentStatus,
        vessel.currentLocation = point({latitude: v.lat, longitude: v.lon}),
        vessel.speed           = v.speed,
        vessel.course          = v.course,
        vessel.lastUpdated     = datetime(),
        vessel.createdAt       = datetime()
      ON MATCH SET
        vessel.imo             = v.imo,
        vessel.name            = v.name,
        vessel.nameEn          = v.nameEn,
        vessel.vesselType      = v.vesselType,
        vessel.flag            = v.flag,
        vessel.grossTonnage    = v.grossTonnage,
        vessel.length          = v.length,
        vessel.beam            = v.beam,
        vessel.draft           = v.draft,
        vessel.yearBuilt       = v.yearBuilt,
        vessel.currentStatus   = v.currentStatus,
        vessel.currentLocation = point({latitude: v.lat, longitude: v.lon}),
        vessel.speed           = v.speed,
        vessel.course          = v.course,
        vessel.lastUpdated     = datetime(),
        vessel.updatedAt       = datetime()
    RETURN count(vessel) AS cnt
    """

    vessels = [
        {
            "mmsi": 440123001,
            "imo": 9863297,
            "name": "HMM 알헤시라스",
            "nameEn": "HMM Algeciras",
            "vesselType": "ContainerShip",
            "flag": "KR",
            "grossTonnage": 228283.0,
            "length": 399.9,
            "beam": 61.0,
            "draft": 16.5,
            "yearBuilt": 2020,
            "currentStatus": "UNDERWAY",
            "lat": 35.05,
            "lon": 129.00,
            "speed": 12.5,
            "course": 315.0,
            "ownerOrgId": "ORG-HMM",
            "label": "CargoShip",
        },
        {
            "mmsi": 440234002,
            "imo": 9786543,
            "name": "팬오션 드림",
            "nameEn": "Pan Ocean Dream",
            "vesselType": "BulkCarrier",
            "flag": "KR",
            "grossTonnage": 81000.0,
            "length": 292.0,
            "beam": 45.0,
            "draft": 18.2,
            "yearBuilt": 2018,
            "currentStatus": "UNDERWAY",
            "lat": 35.20,
            "lon": 129.30,
            "speed": 11.0,
            "course": 210.0,
            "ownerOrgId": "ORG-PANOCEAN",
            "label": "CargoShip",
        },
        {
            "mmsi": 440345003,
            "imo": 9654321,
            "name": "한라",
            "nameEn": "Halla",
            "vesselType": "Tanker",
            "flag": "KR",
            "grossTonnage": 160000.0,
            "length": 333.0,
            "beam": 60.0,
            "draft": 22.0,
            "yearBuilt": 2019,
            "currentStatus": "AT_ANCHOR",
            "lat": 34.80,
            "lon": 127.80,
            "speed": 0.0,
            "course": 0.0,
            "ownerOrgId": None,
            "label": "Tanker",
        },
        {
            "mmsi": 440456004,
            "imo": 9512345,
            "name": "새마을호",
            "nameEn": "Saemaeul",
            "vesselType": "PassengerShip",
            "flag": "KR",
            "grossTonnage": 10500.0,
            "length": 145.0,
            "beam": 22.0,
            "draft": 5.5,
            "yearBuilt": 2015,
            "currentStatus": "AT_BERTH",
            "lat": 35.10,
            "lon": 129.04,
            "speed": 0.0,
            "course": 0.0,
            "ownerOrgId": None,
            "label": "PassengerShip",
        },
        {
            "mmsi": 440567005,
            "imo": 9898765,
            "name": "무궁화 10호",
            "nameEn": "Mugunghwa 10",
            "vesselType": "FishingVessel",
            "flag": "KR",
            "grossTonnage": 350.0,
            "length": 45.0,
            "beam": 8.5,
            "draft": 3.2,
            "yearBuilt": 2021,
            "currentStatus": "FISHING",
            "lat": 34.50,
            "lon": 128.50,
            "speed": 3.0,
            "course": 90.0,
            "ownerOrgId": None,
            "label": "FishingVessel",
        },
    ]

    result = tx.run(query, vessels=vessels)
    cnt = result.single()["cnt"]
    print(f"  -> Merged {cnt} vessels")

    # Add sub-labels
    for v in vessels:
        tx.run(
            f"MATCH (vessel:Vessel {{mmsi: $mmsi}}) SET vessel:{v['label']}",
            mmsi=v["mmsi"],
        )

    # OWNED_BY relationships
    for v in vessels:
        if v["ownerOrgId"] is not None:
            tx.run(
                """
                MATCH (vessel:Vessel {mmsi: $mmsi})
                MATCH (org:Organization {orgId: $orgId})
                MERGE (vessel)-[:OWNED_BY]->(org)
                """,
                mmsi=v["mmsi"],
                orgId=v["ownerOrgId"],
            )
    print("  -> Created vessel sub-labels and OWNED_BY relationships")

    # LOCATED_AT relationships (vessel -> sea area)
    vessel_sea_area = [
        (440123001, "대한해협"),  # HMM Algeciras near Korea Strait
        (440234002, "동해"),  # Pan Ocean Dream in East Sea
        (440345003, "남해"),  # Halla at anchor in South Sea
        (440456004, "대한해협"),  # Saemaeul at Busan (Korea Strait)
        (440567005, "남해"),  # Mugunghwa fishing in South Sea
    ]
    for mmsi, sea_name in vessel_sea_area:
        tx.run(
            """
            MATCH (v:Vessel {mmsi: $mmsi})
            MATCH (sa:SeaArea {name: $seaName})
            MERGE (v)-[:LOCATED_AT {timestamp: datetime(), source: 'AIS'}]->(sa)
            """,
            mmsi=mmsi,
            seaName=sea_name,
        )
    print("  -> Created vessel LOCATED_AT sea area relationships")


# =========================================================================
# 5. Voyages
# =========================================================================


def _create_voyages(tx) -> None:
    _section("Voyages (2)")

    # --- Voyage 1: HMM Algeciras, Busan -> Incheon ---
    tx.run("""
        MERGE (v:Voyage {voyageId: 'VOY-HMM-2024-001'})
          ON CREATE SET
            v.status      = 'IN_PROGRESS',
            v.cargoType   = 'container',
            v.cargoDesc   = '컨테이너 화물 (TEU 23,964)',
            v.createdAt   = datetime()
        WITH v
        MATCH (dep:Port {unlocode: 'KRPUS'})
        MATCH (arr:Port {unlocode: 'KRICN'})
        MERGE (v)-[:FROM_PORT {departureTime: datetime('2024-12-01T08:00:00+09:00')}]->(dep)
        MERGE (v)-[:TO_PORT   {eta: datetime('2024-12-02T14:00:00+09:00')}]->(arr)
        WITH v
        MATCH (vessel:Vessel {mmsi: 440123001})
        MERGE (vessel)-[:ON_VOYAGE]->(v)
    """)

    # TrackSegment for voyage 1
    tx.run("""
        MERGE (ts:TrackSegment {segmentId: 'SEG-HMM-001-01'})
          ON CREATE SET
            ts.startTime  = datetime('2024-12-01T08:00:00+09:00'),
            ts.endTime    = datetime('2024-12-01T18:00:00+09:00'),
            ts.startPoint = point({latitude: 35.1028, longitude: 129.0403}),
            ts.endPoint   = point({latitude: 36.00, longitude: 127.50}),
            ts.distance   = 185.0,
            ts.avgSpeed   = 14.5,
            ts.anomaly    = false,
            ts.createdAt  = datetime()
        WITH ts
        MATCH (v:Voyage {voyageId: 'VOY-HMM-2024-001'})
        MERGE (v)-[:CONSISTS_OF {order: 1}]->(ts)
    """)
    print("  -> Created voyage VOY-HMM-2024-001 (Busan -> Incheon)")

    # --- Voyage 2: Pan Ocean Dream, Ulsan -> Yeosu-Gwangyang ---
    tx.run("""
        MERGE (v:Voyage {voyageId: 'VOY-PO-2024-001'})
          ON CREATE SET
            v.status      = 'IN_PROGRESS',
            v.cargoType   = 'bulk',
            v.cargoDesc   = '철광석 (iron ore) 80,000 MT',
            v.createdAt   = datetime()
        WITH v
        MATCH (dep:Port {unlocode: 'KRULS'})
        MATCH (arr:Port {unlocode: 'KRYOS'})
        MERGE (v)-[:FROM_PORT {departureTime: datetime('2024-12-01T06:00:00+09:00')}]->(dep)
        MERGE (v)-[:TO_PORT   {eta: datetime('2024-12-01T18:00:00+09:00')}]->(arr)
        WITH v
        MATCH (vessel:Vessel {mmsi: 440234002})
        MERGE (vessel)-[:ON_VOYAGE]->(v)
    """)

    # TrackSegment for voyage 2
    tx.run("""
        MERGE (ts:TrackSegment {segmentId: 'SEG-PO-001-01'})
          ON CREATE SET
            ts.startTime  = datetime('2024-12-01T06:00:00+09:00'),
            ts.endTime    = datetime('2024-12-01T14:00:00+09:00'),
            ts.startPoint = point({latitude: 35.5007, longitude: 129.3855}),
            ts.endPoint   = point({latitude: 34.7360, longitude: 127.7356}),
            ts.distance   = 145.0,
            ts.avgSpeed   = 12.0,
            ts.anomaly    = false,
            ts.createdAt  = datetime()
        WITH ts
        MATCH (v:Voyage {voyageId: 'VOY-PO-2024-001'})
        MERGE (v)-[:CONSISTS_OF {order: 1}]->(ts)
    """)
    print("  -> Created voyage VOY-PO-2024-001 (Ulsan -> Yeosu-Gwangyang)")


# =========================================================================
# 6. KRISO Test Facilities & Experiment
# =========================================================================


def _create_kriso(tx) -> None:
    _section("KRISO Test Facilities (10) & Experiments (3)")

    # --- Test Facilities ---
    facilities_query = """
    UNWIND $facilities AS f
    MERGE (tf:TestFacility {facilityId: f.facilityId})
      ON CREATE SET
        tf.name         = f.name,
        tf.nameEn       = f.nameEn,
        tf.facilityType = f.facilityType,
        tf.length       = f.length,
        tf.width        = f.width,
        tf.depth        = f.depth,
        tf.maxSpeed     = f.maxSpeed,
        tf.location     = '대전 유성구',
        tf.createdAt    = datetime()
      ON MATCH SET
        tf.name         = f.name,
        tf.nameEn       = f.nameEn,
        tf.facilityType = f.facilityType,
        tf.length       = f.length,
        tf.width        = f.width,
        tf.depth        = f.depth,
        tf.maxSpeed     = f.maxSpeed,
        tf.updatedAt    = datetime()
    RETURN count(tf) AS cnt
    """

    facilities = [
        {
            "facilityId": "TF-LTT",
            "name": "대형 예인수조",
            "nameEn": "Large Towing Tank",
            "facilityType": "TowingTank",
            "length": 200.0,
            "width": 16.0,
            "depth": 7.0,
            "maxSpeed": 6.0,
        },
        {
            "facilityId": "TF-OEB",
            "name": "해양공학수조",
            "nameEn": "Ocean Engineering Basin",
            "facilityType": "OceanEngineeringBasin",
            "length": 56.0,
            "width": 30.0,
            "depth": 4.5,
            "maxSpeed": None,
        },
        {
            "facilityId": "TF-ICE",
            "name": "빙해수조",
            "nameEn": "Ice Tank",
            "facilityType": "IceTank",
            "length": 42.0,
            "width": 32.0,
            "depth": 2.5,
            "maxSpeed": None,
        },
        {
            "facilityId": "TF-DOB",
            "name": "심해공학수조",
            "nameEn": "Deep Ocean Basin",
            "facilityType": "DeepOceanBasin",
            "length": 100.0,
            "width": 50.0,
            "depth": 15.0,
            "maxSpeed": None,
        },
        {
            "facilityId": "TF-WET",
            "name": "파력발전 해상실증 시설",
            "nameEn": "Wave Energy Test Site",
            "facilityType": "WaveEnergyTestSite",
            "length": None,
            "width": None,
            "depth": None,
            "maxSpeed": None,
        },
        {
            "facilityId": "TF-HPC",
            "name": "고압챔버",
            "nameEn": "Hyperbaric Chamber",
            "facilityType": "HyperbaricChamber",
            "length": None,
            "width": None,
            "depth": None,
            "maxSpeed": None,
        },
        {
            "facilityId": "TF-LCT",
            "name": "대형 캐비테이션터널",
            "nameEn": "Large Cavitation Tunnel",
            "facilityType": "LargeCavitationTunnel",
            "length": 12.5,
            "width": 2.8,
            "depth": 2.8,
            "maxSpeed": 16.0,
        },
        {
            "facilityId": "TF-MCT",
            "name": "중형 캐비테이션터널",
            "nameEn": "Medium Cavitation Tunnel",
            "facilityType": "MediumCavitationTunnel",
            "length": 6.0,
            "width": 1.2,
            "depth": 1.2,
            "maxSpeed": 12.0,
        },
        {
            "facilityId": "TF-HSCT",
            "name": "고속 캐비테이션터널",
            "nameEn": "High-Speed Cavitation Tunnel",
            "facilityType": "HighSpeedCavitationTunnel",
            "length": 4.5,
            "width": 0.6,
            "depth": 0.6,
            "maxSpeed": 25.0,
        },
        {
            "facilityId": "TF-SIM",
            "name": "선박운항시뮬레이터",
            "nameEn": "Full Mission Bridge Simulator",
            "facilityType": "BridgeSimulator",
            "length": None,
            "width": None,
            "depth": None,
            "maxSpeed": None,
        },
    ]

    result = tx.run(facilities_query, facilities=facilities)
    cnt = result.single()["cnt"]

    # Add sub-labels
    for f in facilities:
        tx.run(
            f"MATCH (tf:TestFacility {{facilityId: $fid}}) SET tf:{f['facilityType']}",
            fid=f["facilityId"],
        )

    # Add CavitationTunnel parent label for cavitation facilities
    for fid in ["TF-LCT", "TF-MCT", "TF-HSCT"]:
        tx.run(
            "MATCH (tf:TestFacility {facilityId: $fid}) SET tf:CavitationTunnel",
            fid=fid,
        )

    # Link facilities to KRISO
    tx.run("""
        MATCH (org:Organization {orgId: 'ORG-KRISO'})
        MATCH (tf:TestFacility)
        MERGE (org)-[:HAS_FACILITY]->(tf)
    """)
    print(f"  -> Merged {cnt} test facilities with sub-labels")

    # --- Experiment ---
    tx.run("""
        MERGE (exp:Experiment {experimentId: 'EXP-2024-001'})
          ON CREATE SET
            exp.title                 = 'KVLCC2 저항성능 시험',
            exp.titleEn               = 'KVLCC2 Resistance Performance Test',
            exp.objective             = 'KVLCC2 선형의 저항 성능 평가 및 CFD 검증 데이터 확보',
            exp.date                  = date('2024-06-15'),
            exp.duration              = 8.0,
            exp.status                = 'COMPLETED',
            exp.principalInvestigator = '김해양',
            exp.projectCode           = 'KRISO-2024-RES-001',
            exp.createdAt             = datetime()
        WITH exp
        MATCH (tf:TestFacility {facilityId: 'TF-LTT'})
        MERGE (exp)-[:CONDUCTED_AT]->(tf)
    """)

    # --- ModelShip ---
    tx.run("""
        MERGE (ms:ModelShip {modelId: 'MODEL-KVLCC2-058'})
          ON CREATE SET
            ms.name         = 'KVLCC2 모형선',
            ms.scale        = 58.0,
            ms.length       = 5.7414,
            ms.beam         = 1.0345,
            ms.draft        = 0.3793,
            ms.displacement = 1.424,
            ms.hullForm     = 'KVLCC2',
            ms.createdAt    = datetime()
        WITH ms
        MATCH (exp:Experiment {experimentId: 'EXP-2024-001'})
        MERGE (exp)-[:TESTED]->(ms)
        WITH ms
        MATCH (vessel:Vessel {mmsi: 440345003})
        MERGE (ms)-[:MODEL_OF {scale: 1.0/58.0}]->(vessel)
    """)
    print("  -> Created experiment EXP-2024-001 with ModelShip")

    # --- Experiment 2: Ocean Engineering Basin seakeeping test ---
    tx.run("""
        MERGE (exp:Experiment {experimentId: 'EXP-2024-002'})
          ON CREATE SET
            exp.title                 = '컨테이너선 내항성능 시험',
            exp.titleEn               = 'Container Ship Seakeeping Performance Test',
            exp.objective             = '대형 컨테이너선의 불규칙파 중 운동 응답 및 갑판 침수 평가',
            exp.date                  = date('2024-07-20'),
            exp.duration              = 12.0,
            exp.status                = 'COMPLETED',
            exp.principalInvestigator = '이파도',
            exp.projectCode           = 'KRISO-2024-SEA-001',
            exp.createdAt             = datetime()
        WITH exp
        MATCH (tf:TestFacility {facilityId: 'TF-OEB'})
        MERGE (exp)-[:CONDUCTED_AT]->(tf)
    """)

    # --- Experiment 3: Ice Tank performance test ---
    tx.run("""
        MERGE (exp:Experiment {experimentId: 'EXP-2024-003'})
          ON CREATE SET
            exp.title                 = '쇄빙 상선 빙해 저항성능 시험',
            exp.titleEn               = 'Icebreaking Cargo Ship Ice Resistance Test',
            exp.objective             = '북극항로 운항 쇄빙 상선의 빙해 저항 및 추진 성능 평가',
            exp.date                  = date('2024-09-10'),
            exp.duration              = 6.0,
            exp.status                = 'COMPLETED',
            exp.principalInvestigator = '박빙해',
            exp.projectCode           = 'KRISO-2024-ICE-001',
            exp.createdAt             = datetime()
        WITH exp
        MATCH (tf:TestFacility {facilityId: 'TF-ICE'})
        MERGE (exp)-[:CONDUCTED_AT]->(tf)
    """)
    print("  -> Created experiments EXP-2024-002 (seakeeping) and EXP-2024-003 (ice)")


# =========================================================================
# 7. Regulations
# =========================================================================


def _create_regulations(tx) -> None:
    _section("Regulations (3)")
    query = """
    UNWIND $regs AS r
    MERGE (reg:Regulation {code: r.code})
      ON CREATE SET
        reg.title          = r.title,
        reg.titleEn        = r.titleEn,
        reg.description    = r.description,
        reg.regulationType = r.regulationType,
        reg.scope          = r.scope,
        reg.createdAt      = datetime()
      ON MATCH SET
        reg.title          = r.title,
        reg.titleEn        = r.titleEn,
        reg.description    = r.description,
        reg.updatedAt      = datetime()
    RETURN count(reg) AS cnt
    """

    regs = [
        {
            "code": "COLREG-1972",
            "title": "국제해상충돌예방규칙",
            "titleEn": "Convention on the International Regulations for Preventing Collisions at Sea",
            "description": "해상에서 선박 간 충돌을 예방하기 위한 국제 규칙",
            "regulationType": "InternationalConvention",
            "scope": "ALL_VESSELS",
            "label": "COLREG",
            "enforcedBy": "ORG-MOF",
        },
        {
            "code": "SOLAS-1974",
            "title": "해상에서의 인명안전에 관한 국제협약",
            "titleEn": "International Convention for the Safety of Life at Sea",
            "description": "선박의 건조, 장비, 운항에 관한 최소 안전 기준을 규정",
            "regulationType": "InternationalConvention",
            "scope": "ALL_VESSELS",
            "label": "SOLAS",
            "enforcedBy": "ORG-KR",
        },
        {
            "code": "MARPOL-73/78",
            "title": "선박으로부터의 오염방지에 관한 국제협약",
            "titleEn": "International Convention for the Prevention of Pollution from Ships",
            "description": "선박 운항 및 사고로 인한 해양환경 오염 방지를 위한 국제 협약",
            "regulationType": "InternationalConvention",
            "scope": "ALL_VESSELS",
            "label": "MARPOL",
            "enforcedBy": "ORG-MOF",
        },
    ]

    result = tx.run(query, regs=regs)
    cnt = result.single()["cnt"]

    # Add sub-labels and ENFORCED_BY
    for r in regs:
        tx.run(
            f"MATCH (reg:Regulation {{code: $code}}) SET reg:{r['label']}",
            code=r["code"],
        )
        tx.run(
            """
            MATCH (reg:Regulation {code: $code})
            MATCH (org:Organization {orgId: $orgId})
            MERGE (reg)-[:ENFORCED_BY]->(org)
            """,
            code=r["code"],
            orgId=r["enforcedBy"],
        )

    print(f"  -> Merged {cnt} regulations with ENFORCED_BY relationships")


# =========================================================================
# 8. Weather
# =========================================================================


def _create_weather(tx) -> None:
    _section("Weather Condition (1)")
    tx.run("""
        MERGE (w:WeatherCondition {conditionId: 'WX-SOUTH-SEA-NOW'})
          ON CREATE SET
            w.timestamp     = datetime(),
            w.windSpeed     = 8.5,
            w.windDirection = 225.0,
            w.waveHeight    = 1.2,
            w.wavePeriod    = 6.5,
            w.visibility    = 15.0,
            w.seaState      = 3,
            w.temperature   = 18.5,
            w.humidity      = 72.0,
            w.pressure      = 1015.0,
            w.riskLevel     = 'LOW',
            w.forecast      = false,
            w.createdAt     = datetime()
        WITH w
        MATCH (sa:SeaArea {name: '남해'})
        MERGE (w)-[:AFFECTS {severity: 'LOW'}]->(sa)
    """)
    print("  -> Created weather condition for South Sea (남해)")


# =========================================================================
# 9. Incident
# =========================================================================


def _create_incident(tx) -> None:
    _section("Incident (1) & Accident Report")

    tx.run("""
        MERGE (inc:Incident:Collision {incidentId: 'INC-2024-0042'})
          ON CREATE SET
            inc.incidentType = 'Collision',
            inc.date         = datetime('2024-11-15T14:30:00+09:00'),
            inc.location     = point({latitude: 35.08, longitude: 129.02}),
            inc.severity     = 'MODERATE',
            inc.description  = '부산항 접근 수역에서 컨테이너선과 소형 어선 간 접촉 사고 발생. 어선 선체 일부 파손, 인명 피해 없음.',
            inc.casualties   = 0,
            inc.resolved     = true,
            inc.resolvedDate = datetime('2024-11-15T22:00:00+09:00'),
            inc.createdAt    = datetime()
    """)

    # INVOLVES vessel
    tx.run("""
        MATCH (inc:Incident {incidentId: 'INC-2024-0042'})
        MATCH (v:Vessel {mmsi: 440123001})
        MERGE (inc)-[:INVOLVES {role: 'PRIMARY'}]->(v)
    """)

    # VIOLATED regulation
    tx.run("""
        MATCH (inc:Incident {incidentId: 'INC-2024-0042'})
        MATCH (reg:Regulation {code: 'COLREG-1972'})
        MERGE (inc)-[:VIOLATED {severity: 'MODERATE'}]->(reg)
    """)

    # Accident Report document
    tx.run("""
        MERGE (doc:Document:AccidentReport {docId: 'DOC-ACC-2024-0042'})
          ON CREATE SET
            doc.title     = '부산항 접근수역 충돌사고 보고서',
            doc.titleEn   = 'Busan Port Approach Collision Accident Report',
            doc.content   = '2024년 11월 15일 14:30 부산항 접근 수역에서 HMM 알헤시라스호(컨테이너선, 228,283 GT)와 소형 어선 간 접촉 사고가 발생하였다. 사고 원인은 어선의 횡단 항법 위반으로 추정되며, COLREG Rule 15(횡단 상황) 위반이 확인되었다. 어선 선체 좌현 일부가 파손되었으나 인명 피해는 없었으며, 해양 오염도 발생하지 않았다.',
            doc.summary   = '부산항 접근수역 컨테이너선-어선 접촉사고. COLREG 위반 확인, 인명피해 없음.',
            doc.docType   = 'AccidentReport',
            doc.language  = 'ko',
            doc.issueDate = date('2024-11-20'),
            doc.source    = '해양안전심판원',
            doc.createdAt = datetime()
        WITH doc
        MATCH (inc:Incident {incidentId: 'INC-2024-0042'})
        MERGE (doc)-[:DESCRIBES]->(inc)
        WITH doc
        MATCH (org:Organization {orgId: 'ORG-KCG'})
        MERGE (doc)-[:ISSUED_BY {issueDate: date('2024-11-20')}]->(org)
    """)
    print("  -> Created incident INC-2024-0042 with accident report")


# =========================================================================
# 10. Sensors
# =========================================================================


def _create_sensors(tx) -> None:
    _section("Sensors (2)")
    query = """
    UNWIND $sensors AS s
    MERGE (sensor:Sensor {sensorId: s.sensorId})
      ON CREATE SET
        sensor.name       = s.name,
        sensor.nameEn     = s.nameEn,
        sensor.sensorType = s.sensorType,
        sensor.location   = point({latitude: s.lat, longitude: s.lon}),
        sensor.status     = 'ACTIVE',
        sensor.createdAt  = datetime()
      ON MATCH SET
        sensor.name       = s.name,
        sensor.sensorType = s.sensorType,
        sensor.updatedAt  = datetime()
    RETURN count(sensor) AS cnt
    """
    sensors = [
        {
            "sensorId": "SENSOR-AIS-BUSAN",
            "name": "AIS 기지국 부산",
            "nameEn": "AIS Base Station Busan",
            "sensorType": "AISTransceiver",
            "lat": 35.1028,
            "lon": 129.0403,
            "label": "AISTransceiver",
        },
        {
            "sensorId": "SENSOR-CCTV-BUSAN",
            "name": "CCTV 부산항",
            "nameEn": "CCTV Busan Port",
            "sensorType": "CCTVCamera",
            "lat": 35.1000,
            "lon": 129.0380,
            "label": "CCTVCamera",
        },
    ]
    result = tx.run(query, sensors=sensors)
    cnt = result.single()["cnt"]

    # Add sub-labels
    for s in sensors:
        tx.run(
            f"MATCH (sensor:Sensor {{sensorId: $sid}}) SET sensor:{s['label']}",
            sid=s["sensorId"],
        )

    # Link sensors to Busan port
    tx.run("""
        MATCH (sensor:Sensor) WHERE sensor.sensorId IN ['SENSOR-AIS-BUSAN', 'SENSOR-CCTV-BUSAN']
        MATCH (port:Port {unlocode: 'KRPUS'})
        MERGE (port)-[:HAS_FACILITY]->(sensor)
    """)
    print(f"  -> Merged {cnt} sensors linked to Busan port")


# =========================================================================
# 11. Cross-entity relationships
# =========================================================================


def _create_relationships(tx) -> None:
    _section("Port <-> SeaArea relationships")

    # Port CONNECTED_VIA waterway / sea area
    port_sea = [
        ("KRPUS", "대한해협"),  # Busan -> Korea Strait
        ("KRICN", "서해"),  # Incheon -> West Sea
        ("KRPTK", "서해"),  # Pyeongtaek -> West Sea
        ("KRULS", "동해"),  # Ulsan -> East Sea
        ("KRYOS", "남해"),  # Yeosu-Gwangyang -> South Sea
    ]

    for unlocode, sea_name in port_sea:
        # Use a generic ACCESSIBLE_FROM to connect port to sea area
        tx.run(
            """
            MATCH (p:Port {unlocode: $unlocode})
            MATCH (sa:SeaArea {name: $seaName})
            MERGE (p)-[:ACCESSIBLE_FROM]->(sa)
            """,
            unlocode=unlocode,
            seaName=sea_name,
        )

    # Busan specifically via Korea Strait waterway
    tx.run("""
        MATCH (p:Port {unlocode: 'KRPUS'})
        MATCH (ww:Waterway {name: '대한해협'})
        MERGE (p)-[:CONNECTED_VIA]->(ww)
    """)

    print("  -> Created port <-> sea area / waterway relationships")


# =========================================================================
# 12. Experimental Data (TestCondition, ExperimentalDataset, Measurement)
# =========================================================================


def _create_experimental_data(tx) -> None:
    _section("Experimental Data (TestCondition, Dataset, Measurement)")

    # --- TestConditions for EXP-2024-001 ---
    tx.run("""
        MERGE (tc:TestCondition {conditionId: 'TC-2024-001-01'})
          ON CREATE SET
            tc.description    = '정수 중 저항시험 조건',
            tc.waterTemp      = 15.5,
            tc.waterDensity   = 999.0,
            tc.waveHeight     = 0.0,
            tc.wavePeriod     = 0.0,
            tc.windSpeed      = 0.0,
            tc.currentSpeed   = 0.0,
            tc.testSpeed      = 1.5,
            tc.testSpeedUnit  = 'm/s',
            tc.createdAt      = datetime()
        WITH tc
        MATCH (exp:Experiment {experimentId: 'EXP-2024-001'})
        MERGE (exp)-[:HAS_CONDITION]->(tc)
    """)

    tx.run("""
        MERGE (tc:TestCondition {conditionId: 'TC-2024-001-02'})
          ON CREATE SET
            tc.description    = '파랑 중 저항시험 조건',
            tc.waterTemp      = 15.5,
            tc.waterDensity   = 999.0,
            tc.waveHeight     = 0.05,
            tc.wavePeriod     = 1.2,
            tc.windSpeed      = 0.0,
            tc.currentSpeed   = 0.0,
            tc.testSpeed      = 1.5,
            tc.testSpeedUnit  = 'm/s',
            tc.createdAt      = datetime()
        WITH tc
        MATCH (exp:Experiment {experimentId: 'EXP-2024-001'})
        MERGE (exp)-[:HAS_CONDITION]->(tc)
    """)

    # --- TestCondition for EXP-2024-002 (seakeeping) ---
    tx.run("""
        MERGE (tc:TestCondition {conditionId: 'TC-2024-002-01'})
          ON CREATE SET
            tc.description    = '불규칙파 내항성능 시험 조건 (Sea State 5)',
            tc.waterTemp      = 18.0,
            tc.waterDensity   = 999.0,
            tc.waveHeight     = 0.12,
            tc.wavePeriod     = 1.4,
            tc.windSpeed      = 2.0,
            tc.currentSpeed   = 0.0,
            tc.testSpeed      = 1.2,
            tc.testSpeedUnit  = 'm/s',
            tc.createdAt      = datetime()
        WITH tc
        MATCH (exp:Experiment {experimentId: 'EXP-2024-002'})
        MERGE (exp)-[:HAS_CONDITION]->(tc)
    """)

    # --- TestCondition for EXP-2024-003 (ice) ---
    tx.run("""
        MERGE (tc:TestCondition {conditionId: 'TC-2024-003-01'})
          ON CREATE SET
            tc.description    = '평탄빙 저항시험 조건 (빙두께 40mm)',
            tc.waterTemp      = -1.5,
            tc.waterDensity   = 999.0,
            tc.iceThickness   = 0.04,
            tc.iceStrength    = 30.0,
            tc.testSpeed      = 0.8,
            tc.testSpeedUnit  = 'm/s',
            tc.createdAt      = datetime()
        WITH tc
        MATCH (exp:Experiment {experimentId: 'EXP-2024-003'})
        MERGE (exp)-[:HAS_CONDITION]->(tc)
    """)
    print("  -> Created 4 test conditions")

    # --- ExperimentalDatasets ---
    tx.run("""
        MERGE (ds:ExperimentalDataset {datasetId: 'DS-2024-001-RES'})
          ON CREATE SET
            ds.title       = 'KVLCC2 저항시험 데이터셋',
            ds.description = 'KVLCC2 모형선 정수 중 및 파랑 중 저항시험 결과 (6개 속도 조건)',
            ds.dataType    = 'resistance_test',
            ds.format      = 'CSV',
            ds.fileSize    = 2400000,
            ds.recordCount = 12000,
            ds.createdAt   = datetime()
        WITH ds
        MATCH (exp:Experiment {experimentId: 'EXP-2024-001'})
        MERGE (exp)-[:PRODUCED]->(ds)
    """)

    tx.run("""
        MERGE (ds:ExperimentalDataset {datasetId: 'DS-2024-002-SEA'})
          ON CREATE SET
            ds.title       = '컨테이너선 내항성능 데이터셋',
            ds.description = '대형 컨테이너선 불규칙파 중 운동응답 및 상대수위 데이터',
            ds.dataType    = 'seakeeping_test',
            ds.format      = 'CSV',
            ds.fileSize    = 5600000,
            ds.recordCount = 36000,
            ds.createdAt   = datetime()
        WITH ds
        MATCH (exp:Experiment {experimentId: 'EXP-2024-002'})
        MERGE (exp)-[:PRODUCED]->(ds)
    """)

    tx.run("""
        MERGE (ds:ExperimentalDataset {datasetId: 'DS-2024-003-ICE'})
          ON CREATE SET
            ds.title       = '쇄빙 상선 빙해저항 데이터셋',
            ds.description = '빙두께/빙강도 변화에 따른 빙해 저항 및 추진 성능 데이터',
            ds.dataType    = 'ice_resistance_test',
            ds.format      = 'CSV',
            ds.fileSize    = 1800000,
            ds.recordCount = 8000,
            ds.createdAt   = datetime()
        WITH ds
        MATCH (exp:Experiment {experimentId: 'EXP-2024-003'})
        MERGE (exp)-[:PRODUCED]->(ds)
    """)
    print("  -> Created 3 experimental datasets")

    # --- Measurements (sample for EXP-2024-001) ---
    tx.run("""
        UNWIND [
            {id: 'MEAS-2024-001-R01', type: 'Resistance', value: 12.45, unit: 'N', speed: 1.0, desc: '정수 중 저항 (Fn=0.142)'},
            {id: 'MEAS-2024-001-R02', type: 'Resistance', value: 28.73, unit: 'N', speed: 1.5, desc: '정수 중 저항 (Fn=0.213)'},
            {id: 'MEAS-2024-001-R03', type: 'Resistance', value: 52.18, unit: 'N', speed: 2.0, desc: '정수 중 저항 (Fn=0.284)'},
            {id: 'MEAS-2024-001-P01', type: 'Propulsion', value: 0.72, unit: '-', speed: 1.5, desc: '추진효율 (Fn=0.213)'},
            {id: 'MEAS-2024-001-P02', type: 'Propulsion', value: 0.68, unit: '-', speed: 2.0, desc: '추진효율 (Fn=0.284)'}
        ] AS m
        MERGE (meas:Measurement {measurementId: m.id})
          ON CREATE SET
            meas.measurementType = m.type,
            meas.value           = m.value,
            meas.unit            = m.unit,
            meas.testSpeed       = m.speed,
            meas.description     = m.desc,
            meas.createdAt       = datetime()
        WITH meas, m
        MATCH (ds:ExperimentalDataset {datasetId: 'DS-2024-001-RES'})
        MERGE (ds)-[:CONTAINS]->(meas)
    """)

    # Add measurement sub-labels
    tx.run("MATCH (m:Measurement) WHERE m.measurementType = 'Resistance' SET m:Resistance")
    tx.run("MATCH (m:Measurement) WHERE m.measurementType = 'Propulsion' SET m:Propulsion")

    print("  -> Created 5 measurements (3 resistance + 2 propulsion)")

    # --- Link datasets to KRISO via DataSource ---
    tx.run("""
        MERGE (src:DataSource {sourceId: 'SRC-KRISO-TOWING'})
          ON CREATE SET
            src.name       = 'KRISO 예인수조 데이터 시스템',
            src.nameEn     = 'KRISO Towing Tank Data System',
            src.sourceType = 'FileSource',
            src.format     = 'CSV',
            src.createdAt  = datetime()
        WITH src
        MATCH (ds:ExperimentalDataset)
        WHERE ds.datasetId STARTS WITH 'DS-2024'
        MERGE (ds)-[:STORED_AT]->(src)
    """)
    print("  -> Linked datasets to KRISO data source")


# =========================================================================
# Verification
# =========================================================================


def _verify(session) -> None:
    _section("Verification")
    from kg.utils.verification import verify_graph_summary

    verify_graph_summary(session)


# =========================================================================
# Main
# =========================================================================


def load_sample_data() -> None:
    """Connect to Neo4j and load all sample data."""
    print("=" * 60)
    print("  Maritime Knowledge Graph - Sample Data Loader")
    print("=" * 60)

    driver = get_driver()
    try:
        with driver.session(database=get_config().neo4j.database) as session:
            session.execute_write(_create_organizations)
            session.execute_write(_create_ports)
            session.execute_write(_create_sea_areas_and_waterways)
            session.execute_write(_create_vessels)
            session.execute_write(_create_voyages)
            session.execute_write(_create_kriso)
            session.execute_write(_create_regulations)
            session.execute_write(_create_weather)
            session.execute_write(_create_incident)
            session.execute_write(_create_sensors)
            session.execute_write(_create_relationships)
            session.execute_write(_create_experimental_data)

            # Verification (read-only, no transaction wrapper needed)
            _verify(session)
    finally:
        driver.close()


if __name__ == "__main__":
    load_sample_data()
