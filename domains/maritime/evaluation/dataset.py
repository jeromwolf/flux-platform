"""Evaluation dataset models and built-in maritime evaluation questions.

Defines the data structures for evaluation questions with reasoning type
classification and difficulty levels. Includes a built-in dataset of 300
Korean maritime domain questions spanning 5 reasoning types and 3 difficulty
levels.

Usage::

    from kg.evaluation.dataset import EvalDataset, Difficulty, ReasoningType

    dataset = EvalDataset.builtin()
    easy = dataset.get_by_difficulty(Difficulty.EASY)
    bridges = dataset.get_by_reasoning_type(ReasoningType.BRIDGE)
    print(dataset.summary())
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReasoningType(str, Enum):
    """Classification of the reasoning pattern required for a query.

    Based on GraphRAG Part 7 multi-hop reasoning taxonomy:
    - DIRECT: Single-hop entity lookup (1 node)
    - BRIDGE: Multi-hop traversal (A -> B -> C)
    - COMPARISON: Side-by-side comparison (A vs B)
    - INTERSECTION: Shared entities across paths (A intersect B)
    - COMPOSITION: Aggregation + ordering + limit
    """

    DIRECT = "DIRECT"
    BRIDGE = "BRIDGE"
    COMPARISON = "COMPARISON"
    INTERSECTION = "INTERSECTION"
    COMPOSITION = "COMPOSITION"


class Difficulty(str, Enum):
    """Difficulty level for evaluation questions.

    - EASY: 1-hop direct lookups, single node/label
    - MEDIUM: 2-hop relationship traversals
    - HARD: Multi-hop, aggregation, comparison, intersection
    """

    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


@dataclass
class EvalQuestion:
    """A single evaluation question with ground truth Cypher.

    Attributes:
        question: Korean natural language question.
        ground_truth_cypher: Reference Cypher query (gold standard).
        expected_labels: Node labels expected in the generated Cypher.
        reasoning_type: Multi-hop reasoning pattern classification.
        difficulty: Question difficulty level.
        description: Short description of what the question tests.
    """

    question: str
    ground_truth_cypher: str
    expected_labels: list[str]
    reasoning_type: ReasoningType
    difficulty: Difficulty
    description: str = ""


class EvalDataset:
    """Collection of evaluation questions with filtering and summary.

    Attributes:
        questions: List of EvalQuestion instances.
    """

    def __init__(self, questions: list[EvalQuestion] | None = None) -> None:
        self.questions: list[EvalQuestion] = questions or []

    def add_question(self, question: EvalQuestion) -> None:
        """Add a question to the dataset.

        Args:
            question: EvalQuestion instance to add.
        """
        self.questions.append(question)

    def get_by_difficulty(self, difficulty: Difficulty) -> list[EvalQuestion]:
        """Filter questions by difficulty level.

        Args:
            difficulty: Difficulty enum value.

        Returns:
            List of matching EvalQuestion instances.
        """
        return [q for q in self.questions if q.difficulty == difficulty]

    def get_by_reasoning_type(
        self, reasoning_type: ReasoningType
    ) -> list[EvalQuestion]:
        """Filter questions by reasoning type.

        Args:
            reasoning_type: ReasoningType enum value.

        Returns:
            List of matching EvalQuestion instances.
        """
        return [q for q in self.questions if q.reasoning_type == reasoning_type]

    def summary(self) -> str:
        """Generate a human-readable summary of the dataset.

        Returns:
            Formatted string with counts by difficulty and reasoning type.
        """
        total = len(self.questions)
        lines = [
            f"EvalDataset: {total} questions",
            "",
            "By Difficulty:",
        ]
        for diff in Difficulty:
            count = len(self.get_by_difficulty(diff))
            lines.append(f"  {diff.value}: {count}")

        lines.append("")
        lines.append("By Reasoning Type:")
        for rt in ReasoningType:
            count = len(self.get_by_reasoning_type(rt))
            if count > 0:
                lines.append(f"  {rt.value}: {count}")

        return "\n".join(lines)

    @classmethod
    def builtin(cls) -> EvalDataset:
        """Create the built-in maritime evaluation dataset (300 questions).

        Returns:
            EvalDataset with 60 easy, 100 medium, and 140 hard questions
            covering DIRECT, BRIDGE, COMPARISON, INTERSECTION, and
            COMPOSITION reasoning types.
        """
        return cls(questions=_BUILTIN_QUESTIONS[:])


# =========================================================================
# Built-in evaluation dataset (300 questions)
# =========================================================================

_BUILTIN_QUESTIONS: list[EvalQuestion] = [
    # -----------------------------------------------------------------
    # Easy (30 questions, 1-hop, DIRECT)
    # -----------------------------------------------------------------
    # --- Original 10 ---
    EvalQuestion(
        question="부산항 정보 알려줘",
        ground_truth_cypher="MATCH (p:Port {name: '부산항'}) RETURN p",
        expected_labels=["Port"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="단일 항만 엔티티 조회",
    ),
    EvalQuestion(
        question="HMM 알헤시라스 선박 정보",
        ground_truth_cypher="MATCH (v:Vessel {name: 'HMM 알헤시라스'}) RETURN v",
        expected_labels=["Vessel"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="단일 선박 엔티티 조회",
    ),
    EvalQuestion(
        question="KRISO 시설 목록",
        ground_truth_cypher="MATCH (f:TestFacility) RETURN f",
        expected_labels=["TestFacility"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="시험시설 전체 조회",
    ),
    EvalQuestion(
        question="컨테이너선 조회",
        ground_truth_cypher=(
            "MATCH (v:Vessel {vesselType: 'ContainerShip'}) RETURN v"
        ),
        expected_labels=["Vessel"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="선종별 선박 조회",
    ),
    EvalQuestion(
        question="해양수산부 정보",
        ground_truth_cypher=(
            "MATCH (o:Organization {name: '해양수산부'}) RETURN o"
        ),
        expected_labels=["Organization"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="단일 기관 엔티티 조회",
    ),
    EvalQuestion(
        question="예인수조 시험시설",
        ground_truth_cypher=(
            "MATCH (f:TestFacility {name: '대형예인수조'}) RETURN f"
        ),
        expected_labels=["TestFacility"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="특정 시험시설 조회",
    ),
    EvalQuestion(
        question="인천항 정보",
        ground_truth_cypher="MATCH (p:Port {name: '인천항'}) RETURN p",
        expected_labels=["Port"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="단일 항만 엔티티 조회",
    ),
    EvalQuestion(
        question="저항시험 실험",
        ground_truth_cypher="MATCH (e:Experiment {name: '저항시험'}) RETURN e",
        expected_labels=["Experiment"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="단일 실험 엔티티 조회",
    ),
    EvalQuestion(
        question="관리자 역할 권한",
        ground_truth_cypher="MATCH (r:Role {name: '관리자'}) RETURN r",
        expected_labels=["Role"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="RBAC 역할 조회",
    ),
    EvalQuestion(
        question="팬오션 드림 선박",
        ground_truth_cypher=(
            "MATCH (v:Vessel {name: '팬오션 드림'}) RETURN v"
        ),
        expected_labels=["Vessel"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="단일 선박 엔티티 조회",
    ),
    # --- New EASY 11-30 ---
    EvalQuestion(
        question="화물선 목록 조회",
        ground_truth_cypher="MATCH (v:CargoShip) RETURN v",
        expected_labels=["CargoShip"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="화물선 엔티티 전체 조회",
    ),
    EvalQuestion(
        question="유조선 현황",
        ground_truth_cypher="MATCH (v:Tanker) RETURN v",
        expected_labels=["Tanker"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="유조선 엔티티 전체 조회",
    ),
    EvalQuestion(
        question="등록된 어선 목록",
        ground_truth_cypher="MATCH (v:FishingVessel) RETURN v",
        expected_labels=["FishingVessel"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="어선 엔티티 전체 조회",
    ),
    EvalQuestion(
        question="여객선 정보 보여줘",
        ground_truth_cypher="MATCH (v:PassengerShip) RETURN v",
        expected_labels=["PassengerShip"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="여객선 엔티티 전체 조회",
    ),
    EvalQuestion(
        question="자율운항선박 현황",
        ground_truth_cypher="MATCH (v:AutonomousVessel) RETURN v",
        expected_labels=["AutonomousVessel"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="자율운항선박 전체 조회",
    ),
    EvalQuestion(
        question="부산항 선석 정보",
        ground_truth_cypher="MATCH (b:Berth) RETURN b",
        expected_labels=["Berth"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="선석 엔티티 전체 조회",
    ),
    EvalQuestion(
        question="묘박지 목록 알려줘",
        ground_truth_cypher="MATCH (a:Anchorage) RETURN a",
        expected_labels=["Anchorage"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="묘박지 전체 조회",
    ),
    EvalQuestion(
        question="컨테이너 터미널 현황",
        ground_truth_cypher="MATCH (t:Terminal) RETURN t",
        expected_labels=["Terminal"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="터미널 전체 조회",
    ),
    EvalQuestion(
        question="주요 항로 목록",
        ground_truth_cypher="MATCH (w:Waterway) RETURN w",
        expected_labels=["Waterway"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="항로(수로) 전체 조회",
    ),
    EvalQuestion(
        question="통항분리방식 해역 정보",
        ground_truth_cypher="MATCH (t:TSS) RETURN t",
        expected_labels=["TSS"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="TSS 전체 조회",
    ),
    EvalQuestion(
        question="항로표지 채널 목록",
        ground_truth_cypher="MATCH (c:Channel) RETURN c",
        expected_labels=["Channel"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="채널 전체 조회",
    ),
    EvalQuestion(
        question="한국 배타적 경제수역 정보",
        ground_truth_cypher="MATCH (e:EEZ {country: '대한민국'}) RETURN e",
        expected_labels=["EEZ"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="특정 EEZ 조회",
    ),
    EvalQuestion(
        question="영해 구역 목록",
        ground_truth_cypher="MATCH (t:TerritorialSea) RETURN t",
        expected_labels=["TerritorialSea"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="영해 전체 조회",
    ),
    EvalQuestion(
        question="해상 충돌사고 목록",
        ground_truth_cypher="MATCH (c:Collision) RETURN c",
        expected_labels=["Collision"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="충돌사고 전체 조회",
    ),
    EvalQuestion(
        question="좌초 사고 현황",
        ground_truth_cypher="MATCH (g:Grounding) RETURN g",
        expected_labels=["Grounding"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="좌초사고 전체 조회",
    ),
    EvalQuestion(
        question="COLREG 규정 내용",
        ground_truth_cypher="MATCH (c:COLREG) RETURN c",
        expected_labels=["COLREG"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="COLREG 규정 조회",
    ),
    EvalQuestion(
        question="SOLAS 협약 정보",
        ground_truth_cypher="MATCH (s:SOLAS) RETURN s",
        expected_labels=["SOLAS"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="SOLAS 협약 조회",
    ),
    EvalQuestion(
        question="캐비테이션터널 시설 정보",
        ground_truth_cypher="MATCH (c:CavitationTunnel) RETURN c",
        expected_labels=["CavitationTunnel"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="캐비테이션터널 전체 조회",
    ),
    EvalQuestion(
        question="선박운항시뮬레이터 정보",
        ground_truth_cypher="MATCH (b:BridgeSimulator) RETURN b",
        expected_labels=["BridgeSimulator"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="선박운항시뮬레이터 조회",
    ),
    EvalQuestion(
        question="해양공학수조 시설 현황",
        ground_truth_cypher="MATCH (o:OceanEngineeringBasin) RETURN o",
        expected_labels=["OceanEngineeringBasin"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="해양공학수조 전체 조회",
    ),

    # -----------------------------------------------------------------
    # Medium (30 questions, 2-hop, BRIDGE)
    # -----------------------------------------------------------------
    # --- Original 10 ---
    EvalQuestion(
        question="부산항에 정박중인 선박은?",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port {name: '부산항'}) RETURN v"
        ),
        expected_labels=["Vessel", "Port"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="항만-선박 관계 탐색 (2-hop)",
    ),
    EvalQuestion(
        question="KRISO가 보유한 시험시설은?",
        ground_truth_cypher=(
            "MATCH (o:Organization {name: 'KRISO'})"
            "-[:OPERATES]->(f:TestFacility) RETURN f"
        ),
        expected_labels=["Organization", "TestFacility"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="기관-시설 관계 탐색 (2-hop)",
    ),
    EvalQuestion(
        question="HMM 소속 선박 목록",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:OWNED_BY]->"
            "(o:Organization {orgId: 'ORG-HMM'}) RETURN v"
        ),
        expected_labels=["Vessel", "Organization"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="선박-기관 소유 관계 (2-hop)",
    ),
    EvalQuestion(
        question="예인수조에서 수행한 실험은?",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:CONDUCTED_AT]->"
            "(f:TestFacility {name: '대형예인수조'}) RETURN e"
        ),
        expected_labels=["Experiment", "TestFacility"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="실험-시설 관계 탐색 (2-hop)",
    ),
    EvalQuestion(
        question="내부연구원이 접근 가능한 데이터 등급",
        ground_truth_cypher=(
            "MATCH (r:Role {name: '내부연구원'})"
            "-[:CAN_ACCESS]->(dc:DataClass) RETURN dc"
        ),
        expected_labels=["Role", "DataClass"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="RBAC 역할-데이터등급 관계 (2-hop)",
    ),
    EvalQuestion(
        question="부산항 근처 사고 이력",
        ground_truth_cypher=(
            "MATCH (i:Incident)-[:OCCURRED_NEAR]->"
            "(p:Port {name: '부산항'}) RETURN i"
        ),
        expected_labels=["Incident", "Port"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="사고-항만 공간 관계 (2-hop)",
    ),
    EvalQuestion(
        question="컨테이너선의 항해 정보",
        ground_truth_cypher=(
            "MATCH (v:Vessel {vesselType: 'ContainerShip'})"
            "-[:ON_VOYAGE]->(voy:Voyage) RETURN v, voy"
        ),
        expected_labels=["Vessel", "Voyage"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="선박-항해 관계 탐색 (2-hop)",
    ),
    EvalQuestion(
        question="빙해수조 시험 장비",
        ground_truth_cypher=(
            "MATCH (f:TestFacility {name: '빙해수조'})"
            "-[:HAS_EQUIPMENT]->(eq) RETURN eq"
        ),
        expected_labels=["TestFacility"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="시설-장비 관계 탐색 (2-hop)",
    ),
    EvalQuestion(
        question="해양수산부 관할 항만",
        ground_truth_cypher=(
            "MATCH (o:Organization {name: '해양수산부'})"
            "-[:REGULATES]->(p:Port) RETURN p"
        ),
        expected_labels=["Organization", "Port"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="기관-항만 규제 관계 (2-hop)",
    ),
    EvalQuestion(
        question="저항시험에 사용된 모형선",
        ground_truth_cypher=(
            "MATCH (e:Experiment {name: '저항시험'})"
            "-[:USES_MODEL]->(m:ModelShip) RETURN m"
        ),
        expected_labels=["Experiment", "ModelShip"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="실험-모형선 관계 탐색 (2-hop)",
    ),
    # --- New MEDIUM 11-30 ---
    EvalQuestion(
        question="남해 해역에 위치한 선박은?",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:LOCATED_AT]->"
            "(s:SeaArea {name: '남해'}) RETURN v"
        ),
        expected_labels=["Vessel", "SeaArea"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="선박-해역 위치 관계 (LOCATED_AT)",
    ),
    EvalQuestion(
        question="부산 묘박지에 정박 중인 선박",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:ANCHORED_AT]->"
            "(a:Anchorage {name: '부산 외항 묘박지'}) RETURN v"
        ),
        expected_labels=["Vessel", "Anchorage"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="선박-묘박지 정박 관계 (ANCHORED_AT)",
    ),
    EvalQuestion(
        question="부산항과 연결된 항로는?",
        ground_truth_cypher=(
            "MATCH (p:Port {name: '부산항'})-[:CONNECTED_VIA]->"
            "(w:Waterway) RETURN w"
        ),
        expected_labels=["Port", "Waterway"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="항만-항로 연결 관계 (CONNECTED_VIA)",
    ),
    EvalQuestion(
        question="부산발 항해의 목적항은?",
        ground_truth_cypher=(
            "MATCH (voy:Voyage)-[:FROM_PORT]->(p1:Port {name: '부산항'}) "
            "MATCH (voy)-[:TO_PORT]->(p2:Port) RETURN p2"
        ),
        expected_labels=["Voyage", "Port"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="항해-출발항-도착항 관계 (FROM_PORT, TO_PORT)",
    ),
    EvalQuestion(
        question="위험물을 운송 중인 선박은?",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:CARRIES]->"
            "(c:DangerousGoods) RETURN v, c"
        ),
        expected_labels=["Vessel", "DangerousGoods"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="선박-위험화물 운송 관계 (CARRIES)",
    ),
    EvalQuestion(
        question="AIS 센서가 생성한 관측 데이터",
        ground_truth_cypher=(
            "MATCH (s:AISTransceiver)-[:PRODUCES]->"
            "(o:Observation) RETURN o"
        ),
        expected_labels=["AISTransceiver", "Observation"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="센서-관측 생산 관계 (PRODUCES)",
    ),
    EvalQuestion(
        question="위성영상에서 탐지된 선박 목록",
        ground_truth_cypher=(
            "MATCH (si:SatelliteImage)-[:SAT_DETECTED]->"
            "(v:Vessel) RETURN v, si.imageId"
        ),
        expected_labels=["SatelliteImage", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="위성영상-선박 탐지 관계 (SAT_DETECTED)",
    ),
    EvalQuestion(
        question="특정 선박의 AIS 추적 데이터",
        ground_truth_cypher=(
            "MATCH (a:AISData)-[:AIS_TRACK_OF]->"
            "(v:Vessel {name: 'HMM 알헤시라스'}) RETURN a"
        ),
        expected_labels=["AISData", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="AIS 데이터-선박 추적 관계 (AIS_TRACK_OF)",
    ),
    EvalQuestion(
        question="충돌사고에 관련된 선박은?",
        ground_truth_cypher=(
            "MATCH (i:Collision)-[:INVOLVES]->"
            "(v:Vessel) RETURN v, i.incidentId"
        ),
        expected_labels=["Collision", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="충돌사고-선박 관련 관계 (INVOLVES)",
    ),
    EvalQuestion(
        question="COLREG 규정이 적용되는 선박 유형",
        ground_truth_cypher=(
            "MATCH (r:COLREG)-[:APPLIES_TO]->"
            "(v:Vessel) RETURN v"
        ),
        expected_labels=["COLREG", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="규정-선박 적용 관계 (APPLIES_TO)",
    ),
    EvalQuestion(
        question="MARPOL 협약을 시행하는 기관은?",
        ground_truth_cypher=(
            "MATCH (r:MARPOL)-[:ENFORCED_BY]->"
            "(o:Organization) RETURN o"
        ),
        expected_labels=["MARPOL", "Organization"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="규정-기관 시행 관계 (ENFORCED_BY)",
    ),
    EvalQuestion(
        question="캐비테이션터널에서 수행한 실험",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:CONDUCTED_AT]->"
            "(f:CavitationTunnel) RETURN e"
        ),
        expected_labels=["Experiment", "CavitationTunnel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="실험-캐비테이션터널 관계 (CONDUCTED_AT)",
    ),
    EvalQuestion(
        question="추진시험에서 테스트한 모형선",
        ground_truth_cypher=(
            "MATCH (e:Experiment {name: '추진시험'})"
            "-[:TESTED]->(m:ModelShip) RETURN m"
        ),
        expected_labels=["Experiment", "ModelShip"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="실험-모형선 테스트 관계 (TESTED)",
    ),
    EvalQuestion(
        question="저항시험이 생성한 실험 데이터셋",
        ground_truth_cypher=(
            "MATCH (e:Experiment {name: '저항시험'})"
            "-[:PRODUCED]->(d:ExperimentalDataset) RETURN d"
        ),
        expected_labels=["Experiment", "ExperimentalDataset"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="실험-데이터셋 생성 관계 (PRODUCED)",
    ),
    EvalQuestion(
        question="내파성시험의 시험 조건",
        ground_truth_cypher=(
            "MATCH (e:Experiment {name: '내파성시험'})"
            "-[:UNDER_CONDITION]->(tc:TestCondition) RETURN tc"
        ),
        expected_labels=["Experiment", "TestCondition"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="실험-시험조건 관계 (UNDER_CONDITION)",
    ),
    EvalQuestion(
        question="AIS 데이터 처리 파이프라인이 읽는 데이터 소스",
        ground_truth_cypher=(
            "MATCH (dp:DataPipeline {name: 'AIS 수집 파이프라인'})"
            "-[:PIPELINE_READS]->(ds:DataSource) RETURN ds"
        ),
        expected_labels=["DataPipeline", "DataSource"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="파이프라인-데이터소스 읽기 관계 (PIPELINE_READS)",
    ),
    EvalQuestion(
        question="워크플로우에 포함된 노드 목록",
        ground_truth_cypher=(
            "MATCH (w:Workflow {name: 'AIS 분석 워크플로우'})"
            "-[:CONTAINS_NODE]->(n:WorkflowNode) RETURN n"
        ),
        expected_labels=["Workflow", "WorkflowNode"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="워크플로우-노드 포함 관계 (CONTAINS_NODE)",
    ),
    EvalQuestion(
        question="AI 에이전트가 호출하는 MCP 도구",
        ground_truth_cypher=(
            "MATCH (a:AIAgent)-[:INVOKES]->"
            "(t:MCPTool) RETURN a.name, t.name"
        ),
        expected_labels=["AIAgent", "MCPTool"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="에이전트-MCP 도구 호출 관계 (INVOKES)",
    ),
    EvalQuestion(
        question="사고 보고서가 기술하는 사고 목록",
        ground_truth_cypher=(
            "MATCH (d:AccidentReport)-[:DESCRIBES]->"
            "(i:Incident) RETURN d.title, i"
        ),
        expected_labels=["AccidentReport", "Incident"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="사고보고서-사고 기술 관계 (DESCRIBES)",
    ),
    EvalQuestion(
        question="레이더 영상이 커버하는 해역",
        ground_truth_cypher=(
            "MATCH (r:RadarImage)-[:RADAR_COVERS]->"
            "(s:SeaArea) RETURN r.imageId, s.name"
        ),
        expected_labels=["RadarImage", "SeaArea"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="레이더영상-해역 커버 관계 (RADAR_COVERS)",
    ),

    # -----------------------------------------------------------------
    # Hard (40 questions, multi-hop / comparison / intersection)
    # -----------------------------------------------------------------
    # --- Original 10 ---
    EvalQuestion(
        question="부산항 정박 선박의 소유 기관은?",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port {name: '부산항'}) "
            "MATCH (v)-[:OWNED_BY]->(o:Organization) RETURN o"
        ),
        expected_labels=["Vessel", "Port", "Organization"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop 관계 탐색 (항만->선박->기관)",
    ),
    EvalQuestion(
        question="KRISO 시설에서 수행한 실험의 계측 데이터",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:CONDUCTED_AT]->"
            "(f:TestFacility)<-[:OPERATES]-"
            "(o:Organization {name: 'KRISO'}) "
            "MATCH (e)-[:HAS_MEASUREMENT]->(m:Measurement) RETURN m"
        ),
        expected_labels=["Experiment", "TestFacility", "Organization", "Measurement"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop 관계 탐색 (기관->시설->실험->계측)",
    ),
    EvalQuestion(
        question="예인수조와 빙해수조 모두에서 실험한 모형선",
        ground_truth_cypher=(
            "MATCH (m:ModelShip)<-[:USES_MODEL]-(e1:Experiment)"
            "-[:CONDUCTED_AT]->(f1:TestFacility {name: '대형예인수조'}) "
            "MATCH (m)<-[:USES_MODEL]-(e2:Experiment)"
            "-[:CONDUCTED_AT]->(f2:TestFacility {name: '빙해수조'}) "
            "RETURN m"
        ),
        expected_labels=["ModelShip", "Experiment", "TestFacility"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 쿼리 (두 시설 공통 모형선)",
    ),
    EvalQuestion(
        question="가장 많은 실험을 수행한 시험시설은?",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:CONDUCTED_AT]->(f:TestFacility) "
            "RETURN f.name, count(e) AS cnt ORDER BY cnt DESC LIMIT 1"
        ),
        expected_labels=["Experiment", "TestFacility"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="집계 + 정렬 + 제한",
    ),
    EvalQuestion(
        question="내부연구원과 외부연구자의 데이터 접근 등급 차이",
        ground_truth_cypher=(
            "MATCH (r1:Role {name: '내부연구원'})-[:CAN_ACCESS]->(dc1:DataClass) "
            "MATCH (r2:Role {name: '외부연구자'})-[:CAN_ACCESS]->(dc2:DataClass) "
            "RETURN r1.name, collect(DISTINCT dc1.name), "
            "r2.name, collect(DISTINCT dc2.name)"
        ),
        expected_labels=["Role", "DataClass"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="두 역할의 접근 등급 비교",
    ),
    EvalQuestion(
        question="컨테이너선 소유 기관이 운영하는 다른 선종",
        ground_truth_cypher=(
            "MATCH (v:Vessel {vesselType: 'ContainerShip'})"
            "-[:OWNED_BY]->(o:Organization)"
            "<-[:OWNED_BY]-(v2:Vessel) "
            "WHERE v2.vesselType <> 'ContainerShip' "
            "RETURN o.name, v2.name, v2.vesselType"
        ),
        expected_labels=["Vessel", "Organization"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop 역방향 탐색 (선박->기관->다른선박)",
    ),
    EvalQuestion(
        question="KRISO 저항시험 결과를 볼 수 있는 역할은?",
        ground_truth_cypher=(
            "MATCH (e:Experiment {name: '저항시험'})"
            "-[:HAS_CLASSIFICATION]->(dc:DataClass)"
            "<-[:CAN_ACCESS]-(r:Role) RETURN r.name"
        ),
        expected_labels=["Experiment", "DataClass", "Role"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop 관계 탐색 (실험->등급->역할)",
    ),
    EvalQuestion(
        question="사고 발생 항만의 기상 조건",
        ground_truth_cypher=(
            "MATCH (i:Incident)-[:OCCURRED_NEAR]->(p:Port) "
            "MATCH (w:WeatherCondition)-[:OBSERVED_AT]->(p) "
            "RETURN i, p.name, w"
        ),
        expected_labels=["Incident", "Port", "WeatherCondition"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="사고-항만-기상 다중 관계 탐색",
    ),
    EvalQuestion(
        question="부산항과 인천항에 공통으로 입항한 선박",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:DOCKED_AT]->(p1:Port {name: '부산항'}) "
            "MATCH (v)-[:DOCKED_AT]->(p2:Port {name: '인천항'}) RETURN v"
        ),
        expected_labels=["Vessel", "Port"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 쿼리 (두 항만 공통 선박)",
    ),
    EvalQuestion(
        question="Top 3 실험 수행 시설과 각 실험 목록",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:CONDUCTED_AT]->(f:TestFacility) "
            "WITH f, collect(e.name) AS experiments, count(e) AS cnt "
            "ORDER BY cnt DESC LIMIT 3 "
            "RETURN f.name, experiments, cnt"
        ),
        expected_labels=["Experiment", "TestFacility"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="집계 + 수집 + 정렬 + 제한",
    ),
    # --- New HARD 11-40 ---
    # HARD: 3-hop+ BRIDGE (항해-항만-사고-기상 체인)
    EvalQuestion(
        question="부산항 출발 항해에서 기상 악화로 발생한 사고",
        ground_truth_cypher=(
            "MATCH (voy:Voyage)-[:FROM_PORT]->(p:Port {name: '부산항'}) "
            "MATCH (i:Incident)-[:INVOLVES]->(v:Vessel)-[:ON_VOYAGE]->(voy) "
            "MATCH (i)-[:CAUSED_BY]->(w:WeatherCondition) "
            "RETURN i, v.name, w"
        ),
        expected_labels=["Voyage", "Port", "Incident", "Vessel", "WeatherCondition"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop 체인 (항해->항만->사고->기상)",
    ),
    # HARD: 실험-시설-계측-모형선 체인
    EvalQuestion(
        question="캐비테이션터널에서 테스트한 모형선의 실물 선박 정보",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:CONDUCTED_AT]->(f:CavitationTunnel) "
            "MATCH (e)-[:TESTED]->(m:ModelShip)-[:MODEL_OF]->(v:Vessel) "
            "RETURN m, v"
        ),
        expected_labels=["Experiment", "CavitationTunnel", "ModelShip", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop 체인 (시설->실험->모형선->실선)",
    ),
    # HARD: 시간 조건부 질의
    EvalQuestion(
        question="2025년에 수행된 실험과 해당 시험 조건",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:UNDER_CONDITION]->(tc:TestCondition) "
            "WHERE e.date >= date('2025-01-01') AND e.date < date('2026-01-01') "
            "RETURN e.title, tc"
        ),
        expected_labels=["Experiment", "TestCondition"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="시간 조건부 실험-시험조건 조회",
    ),
    # HARD: COMPARISON - 선종별
    EvalQuestion(
        question="유조선과 컨테이너선의 평균 총톤수 비교",
        ground_truth_cypher=(
            "MATCH (v1:Vessel {vesselType: 'Tanker'}) "
            "WITH avg(v1.grossTonnage) AS tankerAvg "
            "MATCH (v2:Vessel {vesselType: 'ContainerShip'}) "
            "RETURN tankerAvg, avg(v2.grossTonnage) AS containerAvg"
        ),
        expected_labels=["Vessel"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="유조선 vs 컨테이너선 톤수 비교",
    ),
    # HARD: COMPARISON - 시설별 실험 수
    EvalQuestion(
        question="예인수조와 캐비테이션터널의 실험 수 비교",
        ground_truth_cypher=(
            "MATCH (e1:Experiment)-[:CONDUCTED_AT]->"
            "(f1:TestFacility {name: '대형예인수조'}) "
            "WITH count(e1) AS towingCnt "
            "MATCH (e2:Experiment)-[:CONDUCTED_AT]->(f2:CavitationTunnel) "
            "RETURN towingCnt, count(e2) AS cavitationCnt"
        ),
        expected_labels=["Experiment", "TestFacility", "CavitationTunnel"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="두 시설의 실험 수 비교",
    ),
    # HARD: INTERSECTION - 두 규정 공통 적용 선박
    EvalQuestion(
        question="SOLAS와 MARPOL이 동시에 적용되는 선박",
        ground_truth_cypher=(
            "MATCH (v:Vessel)<-[:APPLIES_TO]-(r1:SOLAS) "
            "MATCH (v)<-[:APPLIES_TO]-(r2:MARPOL) "
            "RETURN v"
        ),
        expected_labels=["Vessel", "SOLAS", "MARPOL"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 쿼리 (두 규정 공통 적용 선박)",
    ),
    # HARD: COMPOSITION - 기관별 선박 수
    EvalQuestion(
        question="기관별 소유 선박 수 순위",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:OWNED_BY]->(o:Organization) "
            "RETURN o.name, count(v) AS cnt "
            "ORDER BY cnt DESC"
        ),
        expected_labels=["Vessel", "Organization"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="기관별 선박 수 집계 + 정렬",
    ),
    # HARD: COMPOSITION - 항만별 사고 건수
    EvalQuestion(
        question="항만별 사고 발생 건수 Top 5",
        ground_truth_cypher=(
            "MATCH (i:Incident)-[:OCCURRED_NEAR]->(p:Port) "
            "RETURN p.name, count(i) AS cnt "
            "ORDER BY cnt DESC LIMIT 5"
        ),
        expected_labels=["Incident", "Port"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="항만별 사고 건수 집계 Top 5",
    ),
    # HARD: RBAC 권한 경로 (User -> Role -> Permission)
    EvalQuestion(
        question="사용자 '홍길동'에게 부여된 권한 목록",
        ground_truth_cypher=(
            "MATCH (u:User {name: '홍길동'})-[:HAS_ROLE]->(r:Role) "
            "MATCH (r)-[:GRANTS]->(p:Permission) "
            "RETURN r.name, collect(p.name) AS permissions"
        ),
        expected_labels=["User", "Role", "Permission"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="RBAC 3-hop 권한 경로 (사용자->역할->권한)",
    ),
    # HARD: RBAC - 사용자 -> 기관 -> 데이터 접근
    EvalQuestion(
        question="KRISO 소속 사용자가 접근 가능한 데이터 등급",
        ground_truth_cypher=(
            "MATCH (u:User)-[:BELONGS_TO]->"
            "(o:Organization {name: 'KRISO'}) "
            "MATCH (u)-[:HAS_ROLE]->(r:Role)-[:CAN_ACCESS]->(dc:DataClass) "
            "RETURN u.name, r.name, collect(DISTINCT dc.name) AS classes"
        ),
        expected_labels=["User", "Organization", "Role", "DataClass"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="RBAC 4-hop (사용자->기관+역할->데이터등급)",
    ),
    # HARD: 규정 준수 체크 - 사고와 위반 규정
    EvalQuestion(
        question="규정 위반이 포함된 사고와 해당 규정 정보",
        ground_truth_cypher=(
            "MATCH (i:Incident)-[:VIOLATED]->(r:Regulation) "
            "MATCH (i)-[:INVOLVES]->(v:Vessel) "
            "RETURN i.incidentId, v.name, r.title"
        ),
        expected_labels=["Incident", "Regulation", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="사고-규정위반-선박 다중 관계",
    ),
    # HARD: 다중 모달 데이터 연계 (AIS + 위성)
    EvalQuestion(
        question="특정 해역의 AIS 데이터와 위성영상을 모두 보유한 경우",
        ground_truth_cypher=(
            "MATCH (a:AISData)-[:OBSERVED_IN_AREA]->(s:SeaArea) "
            "MATCH (si:SatelliteImage)-[:CAPTURED_OVER]->(s) "
            "RETURN s.name, count(a) AS aisCnt, count(si) AS satCnt"
        ),
        expected_labels=["AISData", "SeaArea", "SatelliteImage"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="다중 모달 교집합 (AIS + 위성 동일 해역)",
    ),
    # HARD: 다중 모달 - 레이더 + 해도
    EvalQuestion(
        question="동일 해역을 커버하는 레이더 영상과 해도 목록",
        ground_truth_cypher=(
            "MATCH (r:RadarImage)-[:RADAR_COVERS]->(s:SeaArea) "
            "MATCH (c:MaritimeChart)-[:CHART_COVERS]->(s) "
            "RETURN s.name, collect(DISTINCT r.imageId) AS radars, "
            "collect(DISTINCT c.chartId) AS charts"
        ),
        expected_labels=["RadarImage", "SeaArea", "MaritimeChart"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="다중 모달 교집합 (레이더 + 해도 동일 해역)",
    ),
    # HARD: 실험-시설-계측-모형선 체인 (4-hop)
    EvalQuestion(
        question="해양공학수조에서 수행된 실험의 계측 데이터와 시험 조건",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:CONDUCTED_AT]->(f:OceanEngineeringBasin) "
            "MATCH (e)-[:HAS_MEASUREMENT]->(m:Measurement) "
            "MATCH (e)-[:UNDER_CONDITION]->(tc:TestCondition) "
            "RETURN e.title, m, tc"
        ),
        expected_labels=[
            "Experiment", "OceanEngineeringBasin", "Measurement", "TestCondition",
        ],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop 체인 (시설->실험->계측+시험조건)",
    ),
    # HARD: 실험 데이터 보안 등급 경로
    EvalQuestion(
        question="기밀 등급 실험 데이터셋을 열람 가능한 역할",
        ground_truth_cypher=(
            "MATCH (ed:ExperimentalDataset)-[:CLASSIFIED_AS]->"
            "(dc:DataClass {name: '기밀'}) "
            "MATCH (r:Role)-[:CAN_ACCESS]->(dc) "
            "RETURN ed, r.name"
        ),
        expected_labels=["ExperimentalDataset", "DataClass", "Role"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="데이터셋-보안등급-역할 접근 경로",
    ),
    # HARD: 워크플로우 → 노드 → AI모델 체인
    EvalQuestion(
        question="AIS 분석 워크플로우에서 사용하는 AI 모델 목록",
        ground_truth_cypher=(
            "MATCH (w:Workflow {name: 'AIS 분석 워크플로우'})"
            "-[:CONTAINS_NODE]->(n:WorkflowNode) "
            "MATCH (n)-[:USES_MODEL]->(m:AIModel) "
            "RETURN n.name, m.name, m.version"
        ),
        expected_labels=["Workflow", "WorkflowNode", "AIModel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop 체인 (워크플로우->노드->AI모델)",
    ),
    # HARD: 워크플로우 실행 이력
    EvalQuestion(
        question="실패한 워크플로우 실행의 원본 워크플로우와 노드 정보",
        ground_truth_cypher=(
            "MATCH (we:WorkflowExecution {status: 'FAILED'})"
            "-[:EXECUTION_OF]->(w:Workflow) "
            "MATCH (w)-[:CONTAINS_NODE]->(n:WorkflowNode) "
            "RETURN we, w.name, collect(n.name) AS nodes"
        ),
        expected_labels=["WorkflowExecution", "Workflow", "WorkflowNode"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop (실행->워크플로우->노드)",
    ),
    # HARD: AI 에이전트 → 워크플로우 → 데이터소스 체인
    EvalQuestion(
        question="AI 에이전트가 관리하는 데이터 소스와 해당 파이프라인",
        ground_truth_cypher=(
            "MATCH (a:AIAgent)-[:MANAGES]->(ds:DataSource) "
            "MATCH (dp:DataPipeline)-[:PIPELINE_FEEDS]->(ds) "
            "RETURN a.name, ds, dp.name"
        ),
        expected_labels=["AIAgent", "DataSource", "DataPipeline"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop (에이전트->데이터소스->파이프라인)",
    ),
    # HARD: COMPARISON - 관리자 vs 개발자 권한
    EvalQuestion(
        question="관리자와 개발자 역할의 부여 권한 비교",
        ground_truth_cypher=(
            "MATCH (r1:Role {name: '관리자'})-[:GRANTS]->(p1:Permission) "
            "MATCH (r2:Role {name: '개발자'})-[:GRANTS]->(p2:Permission) "
            "RETURN r1.name, collect(DISTINCT p1.name) AS adminPerms, "
            "r2.name, collect(DISTINCT p2.name) AS devPerms"
        ),
        expected_labels=["Role", "Permission"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="관리자 vs 개발자 권한 비교",
    ),
    # HARD: COMPOSITION - 선종별 선박 수 통계
    EvalQuestion(
        question="선종별 등록 선박 수 통계",
        ground_truth_cypher=(
            "MATCH (v:Vessel) "
            "RETURN v.vesselType, count(v) AS cnt "
            "ORDER BY cnt DESC"
        ),
        expected_labels=["Vessel"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="선종별 선박 수 집계 통계",
    ),
    # HARD: COMPOSITION - 해역별 위성영상 수
    EvalQuestion(
        question="해역별 촬영된 위성영상 수 Top 3",
        ground_truth_cypher=(
            "MATCH (si:SatelliteImage)-[:CAPTURED_OVER]->(s:SeaArea) "
            "RETURN s.name, count(si) AS cnt "
            "ORDER BY cnt DESC LIMIT 3"
        ),
        expected_labels=["SatelliteImage", "SeaArea"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="해역별 위성영상 수 Top 3",
    ),
    # HARD: 사고-보고서-발행기관 체인
    EvalQuestion(
        question="충돌사고 보고서를 발행한 기관과 사고 상세",
        ground_truth_cypher=(
            "MATCH (d:AccidentReport)-[:DESCRIBES]->(i:Collision) "
            "MATCH (d)-[:ISSUED_BY]->(o:Organization) "
            "RETURN d.title, i, o.name"
        ),
        expected_labels=["AccidentReport", "Collision", "Organization"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop (보고서->사고->발행기관)",
    ),
    # HARD: 항해-화물-위험물 체인
    EvalQuestion(
        question="위험물을 운송 중인 선박의 현재 항해 경로와 도착항",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:CARRIES]->(c:DangerousGoods) "
            "MATCH (v)-[:ON_VOYAGE]->(voy:Voyage)-[:TO_PORT]->(p:Port) "
            "RETURN v.name, c.description, p.name"
        ),
        expected_labels=["Vessel", "DangerousGoods", "Voyage", "Port"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (선박->위험물+항해->도착항)",
    ),
    # HARD: 시뮬레이터 기반 실험 결과
    EvalQuestion(
        question="선박운항시뮬레이터에서 수행된 실험의 모형선과 계측 결과",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:CONDUCTED_AT]->(f:BridgeSimulator) "
            "MATCH (e)-[:TESTED]->(m:ModelShip) "
            "MATCH (e)-[:HAS_MEASUREMENT]->(meas:Measurement) "
            "RETURN e.title, m, meas"
        ),
        expected_labels=["Experiment", "BridgeSimulator", "ModelShip", "Measurement"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="시뮬레이터-실험-모형선-계측 체인",
    ),
    # HARD: 서비스-MCP 도구 노출
    EvalQuestion(
        question="쿼리 서비스가 MCP로 노출하는 도구와 이를 호출하는 에이전트",
        ground_truth_cypher=(
            "MATCH (svc:QueryService)-[:EXPOSES_TOOL]->(t:MCPTool) "
            "MATCH (a:AIAgent)-[:INVOKES]->(t) "
            "RETURN svc, t.name, a.name"
        ),
        expected_labels=["QueryService", "MCPTool", "AIAgent"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop (서비스->MCP도구->에이전트)",
    ),
    # HARD: COMPOSITION - 실험별 측정 건수 + 유형
    EvalQuestion(
        question="실험별 측정 건수와 측정 유형 분포",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:HAS_MEASUREMENT]->(m:Measurement) "
            "RETURN e.title, labels(m) AS measureType, count(m) AS cnt "
            "ORDER BY cnt DESC"
        ),
        expected_labels=["Experiment", "Measurement"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="실험별 측정 유형 분포 집계",
    ),
    # HARD: INTERSECTION - 동일 모형선 다중 시설 실험
    EvalQuestion(
        question="캐비테이션터널과 해양공학수조 모두에서 시험된 모형선",
        ground_truth_cypher=(
            "MATCH (m:ModelShip)<-[:TESTED]-(e1:Experiment)"
            "-[:CONDUCTED_AT]->(f1:CavitationTunnel) "
            "MATCH (m)<-[:TESTED]-(e2:Experiment)"
            "-[:CONDUCTED_AT]->(f2:OceanEngineeringBasin) "
            "RETURN m"
        ),
        expected_labels=["ModelShip", "Experiment", "CavitationTunnel", "OceanEngineeringBasin"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 (두 시설 공통 모형선 테스트)",
    ),
    # HARD: 항해경고-해역-선박 체인
    EvalQuestion(
        question="항행경고가 발효된 해역을 운항 중인 선박 목록",
        ground_truth_cypher=(
            "MATCH (nw:NavigationalWarning)-[:APPLIES_TO_AREA]->"
            "(s:SeaArea) "
            "MATCH (v:Vessel)-[:LOCATED_AT]->(s) "
            "RETURN nw.title, s.name, collect(v.name) AS vessels"
        ),
        expected_labels=["NavigationalWarning", "SeaArea", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="항행경고-해역-선박 3-hop 체인",
    ),
    # HARD: 센서-관측-임베딩 다중모달 체인
    EvalQuestion(
        question="레이더 센서 관측에서 생성된 임베딩 벡터와 탐지된 선박",
        ground_truth_cypher=(
            "MATCH (s:Radar)-[:PRODUCES]->(o:RadarObservation) "
            "MATCH (o)-[:HAS_EMBEDDING]->(e:VisualEmbedding) "
            "MATCH (o)-[:DETECTED]->(v:Vessel) "
            "RETURN s, o, e, v.name"
        ),
        expected_labels=["Radar", "RadarObservation", "VisualEmbedding", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="센서->관측->임베딩+선박 다중모달 체인",
    ),
    # HARD: COMPARISON - 검사 보고서 vs 사고 보고서 발행 기관
    EvalQuestion(
        question="검사보고서와 사고보고서를 각각 발행한 기관 비교",
        ground_truth_cypher=(
            "MATCH (d1:InspectionReport)-[:ISSUED_BY]->(o1:Organization) "
            "WITH collect(DISTINCT o1.name) AS inspOrgs "
            "MATCH (d2:AccidentReport)-[:ISSUED_BY]->(o2:Organization) "
            "RETURN inspOrgs, collect(DISTINCT o2.name) AS accOrgs"
        ),
        expected_labels=["InspectionReport", "AccidentReport", "Organization"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="두 보고서 유형의 발행 기관 비교",
    ),

    # =================================================================
    # NEW 200 questions (EASY 30 + MEDIUM 70 + HARD 100)
    # =================================================================

    # -----------------------------------------------------------------
    # EASY 31-60 (30 questions, 1-hop, DIRECT)
    # -----------------------------------------------------------------
    EvalQuestion(
        question="해군 함정 현황 조회",
        ground_truth_cypher="MATCH (v:NavalVessel) RETURN v",
        expected_labels=["NavalVessel"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="해군 함정 전체 조회",
    ),
    EvalQuestion(
        question="해양오염 사고 목록",
        ground_truth_cypher="MATCH (p:Pollution) RETURN p",
        expected_labels=["Pollution"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="오염사고 전체 조회",
    ),
    EvalQuestion(
        question="조난 사고 이력",
        ground_truth_cypher="MATCH (d:Distress) RETURN d",
        expected_labels=["Distress"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="조난사고 전체 조회",
    ),
    EvalQuestion(
        question="불법조업 적발 현황",
        ground_truth_cypher="MATCH (f:IllegalFishing) RETURN f",
        expected_labels=["IllegalFishing"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="불법조업 전체 조회",
    ),
    EvalQuestion(
        question="위험물 화물 목록",
        ground_truth_cypher="MATCH (d:DangerousGoods) RETURN d",
        expected_labels=["DangerousGoods"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="위험물 화물 전체 조회",
    ),
    EvalQuestion(
        question="벌크 화물 현황",
        ground_truth_cypher="MATCH (b:BulkCargo) RETURN b",
        expected_labels=["BulkCargo"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="벌크 화물 전체 조회",
    ),
    EvalQuestion(
        question="컨테이너 화물 목록 보여줘",
        ground_truth_cypher="MATCH (c:ContainerCargo) RETURN c",
        expected_labels=["ContainerCargo"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="컨테이너 화물 전체 조회",
    ),
    EvalQuestion(
        question="정부기관 목록 조회",
        ground_truth_cypher="MATCH (g:GovernmentAgency) RETURN g",
        expected_labels=["GovernmentAgency"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="정부기관 전체 조회",
    ),
    EvalQuestion(
        question="선급 협회 현황",
        ground_truth_cypher="MATCH (c:ClassificationSociety) RETURN c",
        expected_labels=["ClassificationSociety"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="선급 협회 전체 조회",
    ),
    EvalQuestion(
        question="해운사 목록",
        ground_truth_cypher="MATCH (s:ShippingCompany) RETURN s",
        expected_labels=["ShippingCompany"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="해운사 전체 조회",
    ),
    EvalQuestion(
        question="연구기관 정보 조회",
        ground_truth_cypher="MATCH (r:ResearchInstitute) RETURN r",
        expected_labels=["ResearchInstitute"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="연구기관 전체 조회",
    ),
    EvalQuestion(
        question="항만 시설 목록",
        ground_truth_cypher="MATCH (pf:PortFacility) RETURN pf",
        expected_labels=["PortFacility"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="항만 시설 전체 조회",
    ),
    EvalQuestion(
        question="연안항 정보 보여줘",
        ground_truth_cypher="MATCH (cp:CoastalPort) RETURN cp",
        expected_labels=["CoastalPort"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="연안항 전체 조회",
    ),
    EvalQuestion(
        question="무역항 현황",
        ground_truth_cypher="MATCH (tp:TradePort) RETURN tp",
        expected_labels=["TradePort"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="무역항 전체 조회",
    ),
    EvalQuestion(
        question="어항 목록 알려줘",
        ground_truth_cypher="MATCH (fp:FishingPort) RETURN fp",
        expected_labels=["FishingPort"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="어항 전체 조회",
    ),
    EvalQuestion(
        question="선원 명부 조회",
        ground_truth_cypher="MATCH (c:CrewMember) RETURN c",
        expected_labels=["CrewMember"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="선원 전체 조회",
    ),
    EvalQuestion(
        question="검사관 목록",
        ground_truth_cypher="MATCH (i:Inspector) RETURN i",
        expected_labels=["Inspector"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="검사관 전체 조회",
    ),
    EvalQuestion(
        question="기상관측소 현황",
        ground_truth_cypher="MATCH (ws:WeatherStation) RETURN ws",
        expected_labels=["WeatherStation"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="기상관측소 전체 조회",
    ),
    EvalQuestion(
        question="CCTV 카메라 설치 현황",
        ground_truth_cypher="MATCH (c:CCTVCamera) RETURN c",
        expected_labels=["CCTVCamera"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="CCTV 카메라 전체 조회",
    ),
    EvalQuestion(
        question="레이더 센서 목록",
        ground_truth_cypher="MATCH (r:Radar) RETURN r",
        expected_labels=["Radar"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="레이더 센서 전체 조회",
    ),
    EvalQuestion(
        question="AIS 송수신기 현황",
        ground_truth_cypher="MATCH (a:AISTransceiver) RETURN a",
        expected_labels=["AISTransceiver"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="AIS 송수신기 전체 조회",
    ),
    EvalQuestion(
        question="모형선 목록 보여줘",
        ground_truth_cypher="MATCH (m:ModelShip) RETURN m",
        expected_labels=["ModelShip"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="모형선 전체 조회",
    ),
    EvalQuestion(
        question="계측 데이터 전체 조회",
        ground_truth_cypher="MATCH (m:Measurement) RETURN m",
        expected_labels=["Measurement"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="계측 데이터 전체 조회",
    ),
    EvalQuestion(
        question="실험 데이터셋 목록",
        ground_truth_cypher="MATCH (ed:ExperimentalDataset) RETURN ed",
        expected_labels=["ExperimentalDataset"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="실험 데이터셋 전체 조회",
    ),
    EvalQuestion(
        question="AI 모델 현황 조회",
        ground_truth_cypher="MATCH (m:AIModel) RETURN m",
        expected_labels=["AIModel"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="AI 모델 전체 조회",
    ),
    EvalQuestion(
        question="MCP 도구 목록",
        ground_truth_cypher="MATCH (t:MCPTool) RETURN t",
        expected_labels=["MCPTool"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="MCP 도구 전체 조회",
    ),
    EvalQuestion(
        question="MCP 리소스 현황",
        ground_truth_cypher="MATCH (r:MCPResource) RETURN r",
        expected_labels=["MCPResource"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="MCP 리소스 전체 조회",
    ),
    EvalQuestion(
        question="데이터 파이프라인 목록",
        ground_truth_cypher="MATCH (dp:DataPipeline) RETURN dp",
        expected_labels=["DataPipeline"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="데이터 파이프라인 전체 조회",
    ),
    EvalQuestion(
        question="AI 에이전트 현황",
        ground_truth_cypher="MATCH (a:AIAgent) RETURN a",
        expected_labels=["AIAgent"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="AI 에이전트 전체 조회",
    ),
    EvalQuestion(
        question="워크플로우 목록 조회",
        ground_truth_cypher="MATCH (w:Workflow) RETURN w",
        expected_labels=["Workflow"],
        reasoning_type=ReasoningType.DIRECT,
        difficulty=Difficulty.EASY,
        description="워크플로우 전체 조회",
    ),

    # -----------------------------------------------------------------
    # MEDIUM 31-100 (70 questions, 2-hop, BRIDGE)
    # -----------------------------------------------------------------
    # -- 시간조건 15개 --
    EvalQuestion(
        question="2025년 이후 발생한 충돌사고는?",
        ground_truth_cypher=(
            "MATCH (c:Collision) "
            "WHERE c.date >= date('2025-01-01') "
            "RETURN c"
        ),
        expected_labels=["Collision"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="시간조건부 충돌사고 조회",
    ),
    EvalQuestion(
        question="2024년 부산항 입항 선박",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[d:DOCKED_AT]->(p:Port {name: '부산항'}) "
            "WHERE d.since >= date('2024-01-01') AND d.since < date('2025-01-01') "
            "RETURN v"
        ),
        expected_labels=["Vessel", "Port"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="시간조건부 항만 입항 선박",
    ),
    EvalQuestion(
        question="최근 1년간 좌초 사고 건수",
        ground_truth_cypher=(
            "MATCH (g:Grounding) "
            "WHERE g.date >= date('2025-01-01') "
            "RETURN count(g) AS cnt"
        ),
        expected_labels=["Grounding"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="시간조건부 좌초사고 집계",
    ),
    EvalQuestion(
        question="2025년 상반기 수행된 실험 목록",
        ground_truth_cypher=(
            "MATCH (e:Experiment) "
            "WHERE e.date >= date('2025-01-01') AND e.date < date('2025-07-01') "
            "RETURN e"
        ),
        expected_labels=["Experiment"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="시간조건부 상반기 실험 조회",
    ),
    EvalQuestion(
        question="올해 발효된 항행경고 목록",
        ground_truth_cypher=(
            "MATCH (nw:NavigationalWarning) "
            "WHERE nw.issueDate >= date('2026-01-01') "
            "RETURN nw"
        ),
        expected_labels=["NavigationalWarning"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="시간조건부 항행경고 조회",
    ),
    EvalQuestion(
        question="최근 6개월간 AIS 데이터 수집 현황",
        ground_truth_cypher=(
            "MATCH (a:AISData) "
            "WHERE a.timestamp >= datetime('2025-10-01T00:00:00Z') "
            "RETURN a"
        ),
        expected_labels=["AISData"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="시간조건부 AIS 데이터 조회",
    ),
    EvalQuestion(
        question="2024년에 촬영된 위성영상 목록",
        ground_truth_cypher=(
            "MATCH (si:SatelliteImage) "
            "WHERE si.capturedAt >= datetime('2024-01-01T00:00:00Z') "
            "AND si.capturedAt < datetime('2025-01-01T00:00:00Z') "
            "RETURN si"
        ),
        expected_labels=["SatelliteImage"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="시간조건부 위성영상 조회",
    ),
    EvalQuestion(
        question="올해 실패한 워크플로우 실행 이력",
        ground_truth_cypher=(
            "MATCH (we:WorkflowExecution {status: 'FAILED'}) "
            "WHERE we.startTime >= datetime('2026-01-01T00:00:00Z') "
            "RETURN we"
        ),
        expected_labels=["WorkflowExecution"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="시간조건부 워크플로우 실패 조회",
    ),
    EvalQuestion(
        question="지난 달 발행된 사고 보고서",
        ground_truth_cypher=(
            "MATCH (ar:AccidentReport) "
            "WHERE ar.issueDate >= date('2026-02-01') "
            "AND ar.issueDate < date('2026-03-01') "
            "RETURN ar"
        ),
        expected_labels=["AccidentReport"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="시간조건부 사고보고서 조회",
    ),
    EvalQuestion(
        question="2025년 해양오염 사고 현황",
        ground_truth_cypher=(
            "MATCH (p:Pollution) "
            "WHERE p.date >= date('2025-01-01') AND p.date < date('2026-01-01') "
            "RETURN p"
        ),
        expected_labels=["Pollution"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="시간조건부 오염사고 조회",
    ),
    EvalQuestion(
        question="최근 3개월 레이더 영상 수집 건수",
        ground_truth_cypher=(
            "MATCH (ri:RadarImage) "
            "WHERE ri.capturedAt >= datetime('2026-01-01T00:00:00Z') "
            "RETURN count(ri) AS cnt"
        ),
        expected_labels=["RadarImage"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="시간조건부 레이더영상 집계",
    ),
    EvalQuestion(
        question="올해 신규 등록된 선박 목록",
        ground_truth_cypher=(
            "MATCH (v:Vessel) "
            "WHERE v.yearBuilt >= 2026 "
            "RETURN v"
        ),
        expected_labels=["Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="시간조건부 신규 선박 조회",
    ),
    EvalQuestion(
        question="2025년 이후 발효된 규정 목록",
        ground_truth_cypher=(
            "MATCH (r:Regulation) "
            "WHERE r.effectiveDate >= date('2025-01-01') "
            "RETURN r"
        ),
        expected_labels=["Regulation"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="시간조건부 규정 조회",
    ),
    EvalQuestion(
        question="최근 1년 기상관측 기록 조회",
        ground_truth_cypher=(
            "MATCH (wo:WeatherObservation) "
            "WHERE wo.timestamp >= datetime('2025-03-01T00:00:00Z') "
            "RETURN wo"
        ),
        expected_labels=["WeatherObservation"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="시간조건부 기상관측 조회",
    ),
    EvalQuestion(
        question="2025년에 완료된 항해 정보",
        ground_truth_cypher=(
            "MATCH (voy:Voyage) "
            "WHERE voy.endDate >= date('2025-01-01') "
            "AND voy.endDate < date('2026-01-01') "
            "RETURN voy"
        ),
        expected_labels=["Voyage"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="시간조건부 항해 조회",
    ),
    # -- 공간조건 10개 --
    EvalQuestion(
        question="항로가 연결하는 해역은?",
        ground_truth_cypher=(
            "MATCH (w:Waterway)-[:CONNECTS]->(s:SeaArea) "
            "RETURN w.name, s.name"
        ),
        expected_labels=["Waterway", "SeaArea"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="항로-해역 연결 관계 (CONNECTS)",
    ),
    EvalQuestion(
        question="부산항이 보유한 항만 시설은?",
        ground_truth_cypher=(
            "MATCH (p:Port {name: '부산항'})-[:HAS_FACILITY]->"
            "(pf:PortFacility) RETURN pf"
        ),
        expected_labels=["Port", "PortFacility"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="항만-시설 보유 관계 (HAS_FACILITY)",
    ),
    EvalQuestion(
        question="대한해협 통항분리방식 해역에 위치한 선박",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:LOCATED_AT]->"
            "(s:SeaArea)<-[:CONNECTS]-(w:TSS {name: '대한해협 TSS'}) "
            "RETURN v"
        ),
        expected_labels=["Vessel", "SeaArea", "TSS"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="TSS-해역-선박 공간 관계",
    ),
    EvalQuestion(
        question="동해 EEZ 내 기상관측소 목록",
        ground_truth_cypher=(
            "MATCH (ws:WeatherStation)-[:LOCATED_AT]->"
            "(e:EEZ {name: '동해 EEZ'}) RETURN ws"
        ),
        expected_labels=["WeatherStation", "EEZ"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="기상관측소-EEZ 위치 관계",
    ),
    EvalQuestion(
        question="서해 영해 내 어선 위치",
        ground_truth_cypher=(
            "MATCH (fv:FishingVessel)-[:LOCATED_AT]->"
            "(ts:TerritorialSea {name: '서해 영해'}) RETURN fv"
        ),
        expected_labels=["FishingVessel", "TerritorialSea"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="어선-영해 위치 관계",
    ),
    EvalQuestion(
        question="제주 연안 해역의 기상 조건",
        ground_truth_cypher=(
            "MATCH (wc:WeatherCondition)-[:AFFECTS]->"
            "(s:SeaArea {name: '제주 연안'}) RETURN wc"
        ),
        expected_labels=["WeatherCondition", "SeaArea"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="기상조건-해역 영향 관계 (AFFECTS)",
    ),
    EvalQuestion(
        question="남해 해역을 커버하는 해도 목록",
        ground_truth_cypher=(
            "MATCH (mc:MaritimeChart)-[:CHART_COVERS]->"
            "(s:SeaArea {name: '남해'}) RETURN mc"
        ),
        expected_labels=["MaritimeChart", "SeaArea"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="해도-해역 커버 관계 (CHART_COVERS)",
    ),
    EvalQuestion(
        question="인천항과 연결된 항로 목록",
        ground_truth_cypher=(
            "MATCH (p:Port {name: '인천항'})-[:CONNECTED_VIA]->"
            "(w:Waterway) RETURN w"
        ),
        expected_labels=["Port", "Waterway"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="인천항-항로 연결 관계",
    ),
    EvalQuestion(
        question="위성영상이 촬영한 항만 목록",
        ground_truth_cypher=(
            "MATCH (si:SatelliteImage)-[:SAT_DEPICTS]->"
            "(p:Port) RETURN si.imageId, p.name"
        ),
        expected_labels=["SatelliteImage", "Port"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="위성영상-항만 촬영 관계 (SAT_DEPICTS)",
    ),
    EvalQuestion(
        question="사고 발생 지점 좌표 목록",
        ground_truth_cypher=(
            "MATCH (i:Incident)-[:OCCURRED_AT]->"
            "(g:GeoPoint) RETURN i.incidentId, g"
        ),
        expected_labels=["Incident", "GeoPoint"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="사고-좌표 위치 관계 (OCCURRED_AT)",
    ),
    # -- 미커버 관계 45개 --
    EvalQuestion(
        question="항해의 구성 트랙 세그먼트 조회",
        ground_truth_cypher=(
            "MATCH (voy:Voyage)-[:CONSISTS_OF]->"
            "(ts:TrackSegment) RETURN voy, ts ORDER BY ts.order"
        ),
        expected_labels=["Voyage", "TrackSegment"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="항해-트랙세그먼트 구성 관계 (CONSISTS_OF)",
    ),
    EvalQuestion(
        question="선박이 수행한 활동 이력",
        ground_truth_cypher=(
            "MATCH (v:Vessel {name: 'HMM 알헤시라스'})-[:PERFORMS]->"
            "(a:Activity) RETURN a"
        ),
        expected_labels=["Vessel", "Activity"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="선박-활동 수행 관계 (PERFORMS)",
    ),
    EvalQuestion(
        question="관측 데이터에 포착된 선박 목록",
        ground_truth_cypher=(
            "MATCH (o:Observation)-[:DEPICTS]->"
            "(v:Vessel) RETURN o, v.name"
        ),
        expected_labels=["Observation", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="관측-선박 포착 관계 (DEPICTS)",
    ),
    EvalQuestion(
        question="관측 데이터가 저장된 데이터소스",
        ground_truth_cypher=(
            "MATCH (o:Observation)-[:STORED_AT]->"
            "(ds:DataSource) RETURN o.observationId, ds"
        ),
        expected_labels=["Observation", "DataSource"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="관측-저장소 관계 (STORED_AT)",
    ),
    EvalQuestion(
        question="두 관측 데이터 간 크로스모달 매칭 결과",
        ground_truth_cypher=(
            "MATCH (o1:Observation)-[:MATCHED_WITH]->"
            "(o2:Observation) RETURN o1, o2"
        ),
        expected_labels=["Observation"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="관측 크로스모달 매칭 관계 (MATCHED_WITH)",
    ),
    EvalQuestion(
        question="동일 개체로 확인된 관측 쌍",
        ground_truth_cypher=(
            "MATCH (o1:Observation)-[:SAME_ENTITY]->"
            "(o2:Observation) RETURN o1, o2"
        ),
        expected_labels=["Observation"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="동일 개체 확인 관계 (SAME_ENTITY)",
    ),
    EvalQuestion(
        question="데이터소스를 제공하는 기관",
        ground_truth_cypher=(
            "MATCH (ds:DataSource)-[:PROVIDED_BY]->"
            "(o:Organization) RETURN ds, o.name"
        ),
        expected_labels=["DataSource", "Organization"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="데이터소스-기관 제공 관계 (PROVIDED_BY)",
    ),
    EvalQuestion(
        question="서비스 간 데이터 연계 흐름",
        ground_truth_cypher=(
            "MATCH (s1:Service)-[:FEEDS]->"
            "(s2:Service) RETURN s1.name, s2.name"
        ),
        expected_labels=["Service"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="서비스-서비스 연계 관계 (FEEDS)",
    ),
    EvalQuestion(
        question="서비스가 생성하는 문서 목록",
        ground_truth_cypher=(
            "MATCH (s:Service)-[:GENERATES]->"
            "(d:Document) RETURN s.name, d.title"
        ),
        expected_labels=["Service", "Document"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="서비스-문서 생성 관계 (GENERATES)",
    ),
    EvalQuestion(
        question="파생 데이터소스의 원본 소스",
        ground_truth_cypher=(
            "MATCH (ds1:DataSource)-[:DERIVED_FROM]->"
            "(ds2:DataSource) RETURN ds1, ds2"
        ),
        expected_labels=["DataSource"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="데이터소스 파생 관계 (DERIVED_FROM)",
    ),
    EvalQuestion(
        question="워크플로우 노드가 읽는 데이터소스",
        ground_truth_cypher=(
            "MATCH (wn:WorkflowNode)-[:READS_FROM]->"
            "(ds:DataSource) RETURN wn.name, ds"
        ),
        expected_labels=["WorkflowNode", "DataSource"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="워크플로우노드-데이터소스 읽기 관계 (READS_FROM)",
    ),
    EvalQuestion(
        question="워크플로우 노드가 쓰는 데이터소스",
        ground_truth_cypher=(
            "MATCH (wn:WorkflowNode)-[:WRITES_TO]->"
            "(ds:DataSource) RETURN wn.name, ds"
        ),
        expected_labels=["WorkflowNode", "DataSource"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="워크플로우노드-데이터소스 쓰기 관계 (WRITES_TO)",
    ),
    EvalQuestion(
        question="서비스가 MCP로 노출하는 리소스",
        ground_truth_cypher=(
            "MATCH (s:Service)-[:EXPOSES_RESOURCE]->"
            "(r:MCPResource) RETURN s.name, r"
        ),
        expected_labels=["Service", "MCPResource"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="서비스-MCP 리소스 노출 관계 (EXPOSES_RESOURCE)",
    ),
    EvalQuestion(
        question="AI 에이전트가 접근하는 MCP 리소스",
        ground_truth_cypher=(
            "MATCH (a:AIAgent)-[:ACCESSES]->"
            "(r:MCPResource) RETURN a.name, r"
        ),
        expected_labels=["AIAgent", "MCPResource"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="에이전트-MCP 리소스 접근 관계 (ACCESSES)",
    ),
    EvalQuestion(
        question="실험에서 촬영된 비디오 클립",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:RECORDED_VIDEO]->"
            "(vc:VideoClip) RETURN e.title, vc"
        ),
        expected_labels=["Experiment", "VideoClip"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="실험-비디오 촬영 관계 (RECORDED_VIDEO)",
    ),
    EvalQuestion(
        question="실험의 센서 측정 데이터",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:MEASURED_DATA]->"
            "(sr:SensorReading) RETURN e.title, sr"
        ),
        expected_labels=["Experiment", "SensorReading"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="실험-센서리딩 측정 관계 (MEASURED_DATA)",
    ),
    EvalQuestion(
        question="실험이 참조한 해도 정보",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:BASED_ON_CHART]->"
            "(mc:MaritimeChart) RETURN e.title, mc"
        ),
        expected_labels=["Experiment", "MaritimeChart"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="실험-해도 참조 관계 (BASED_ON_CHART)",
    ),
    EvalQuestion(
        question="실험이 준수하는 규정 목록",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:COMPLIES_WITH]->"
            "(r:Regulation) RETURN e.title, r.title"
        ),
        expected_labels=["Experiment", "Regulation"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="실험-규정 준수 관계 (COMPLIES_WITH)",
    ),
    EvalQuestion(
        question="융합 임베딩의 원본 AIS 데이터",
        ground_truth_cypher=(
            "MATCH (fe:FusedEmbedding)-[:FUSED_FROM]->"
            "(a:AISData) RETURN fe, a"
        ),
        expected_labels=["FusedEmbedding", "AISData"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="융합임베딩-AIS 원본 관계 (FUSED_FROM)",
    ),
    EvalQuestion(
        question="비디오 클립을 촬영한 센서",
        ground_truth_cypher=(
            "MATCH (vc:VideoClip)-[:VIDEO_FROM]->"
            "(s:Sensor) RETURN vc, s"
        ),
        expected_labels=["VideoClip", "Sensor"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="비디오-센서 촬영 관계 (VIDEO_FROM)",
    ),
    EvalQuestion(
        question="비디오 클립에 찍힌 선박",
        ground_truth_cypher=(
            "MATCH (vc:VideoClip)-[:VIDEO_DEPICTS]->"
            "(v:Vessel) RETURN vc, v.name"
        ),
        expected_labels=["VideoClip", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="비디오-선박 포착 관계 (VIDEO_DEPICTS)",
    ),
    EvalQuestion(
        question="센서 리딩의 출처 센서 정보",
        ground_truth_cypher=(
            "MATCH (sr:SensorReading)-[:READING_FROM_SENSOR]->"
            "(s:Sensor) RETURN sr, s"
        ),
        expected_labels=["SensorReading", "Sensor"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="센서리딩-센서 출처 관계 (READING_FROM_SENSOR)",
    ),
    EvalQuestion(
        question="워크플로우 노드 간 연결 관계",
        ground_truth_cypher=(
            "MATCH (n1:WorkflowNode)-[:CONNECTS_TO]->"
            "(n2:WorkflowNode) RETURN n1.name, n2.name"
        ),
        expected_labels=["WorkflowNode"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="워크플로우노드 연결 관계 (CONNECTS_TO)",
    ),
    EvalQuestion(
        question="AI 에이전트가 실행하는 워크플로우",
        ground_truth_cypher=(
            "MATCH (a:AIAgent)-[:EXECUTES]->"
            "(w:Workflow) RETURN a.name, w.name"
        ),
        expected_labels=["AIAgent", "Workflow"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="에이전트-워크플로우 실행 관계 (EXECUTES)",
    ),
    EvalQuestion(
        question="실험 데이터셋의 원시 계측 데이터",
        ground_truth_cypher=(
            "MATCH (ed:ExperimentalDataset)-[:HAS_RAW_DATA]->"
            "(m:Measurement) RETURN ed, m"
        ),
        expected_labels=["ExperimentalDataset", "Measurement"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="데이터셋-계측 원시데이터 관계 (HAS_RAW_DATA)",
    ),
    EvalQuestion(
        question="실험에서 사용한 AIS 데이터",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:HAS_AIS_DATA]->"
            "(a:AISData) RETURN e.title, a"
        ),
        expected_labels=["Experiment", "AISData"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="실험-AIS 데이터 활용 관계 (HAS_AIS_DATA)",
    ),
    EvalQuestion(
        question="실험에서 비교 검증에 사용한 위성영상",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:USES_SATELLITE]->"
            "(si:SatelliteImage) RETURN e.title, si"
        ),
        expected_labels=["Experiment", "SatelliteImage"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="실험-위성영상 활용 관계 (USES_SATELLITE)",
    ),
    EvalQuestion(
        question="실험 데이터셋의 보안 등급",
        ground_truth_cypher=(
            "MATCH (ed:ExperimentalDataset)-[:CLASSIFIED_AS]->"
            "(dc:DataClass) RETURN ed, dc.name"
        ),
        expected_labels=["ExperimentalDataset", "DataClass"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="데이터셋-보안등급 분류 관계 (CLASSIFIED_AS)",
    ),
    EvalQuestion(
        question="모형선의 실물 선박 정보",
        ground_truth_cypher=(
            "MATCH (m:ModelShip)-[:MODEL_OF]->"
            "(v:Vessel) RETURN m, v.name"
        ),
        expected_labels=["ModelShip", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="모형선-실선 대응 관계 (MODEL_OF)",
    ),
    EvalQuestion(
        question="사용자에게 부여된 역할 목록",
        ground_truth_cypher=(
            "MATCH (u:User)-[:HAS_ROLE]->"
            "(r:Role) RETURN u.name, r.name"
        ),
        expected_labels=["User", "Role"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="사용자-역할 부여 관계 (HAS_ROLE)",
    ),
    EvalQuestion(
        question="역할이 부여하는 권한 목록",
        ground_truth_cypher=(
            "MATCH (r:Role)-[:GRANTS]->"
            "(p:Permission) RETURN r.name, p.name"
        ),
        expected_labels=["Role", "Permission"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="역할-권한 부여 관계 (GRANTS)",
    ),
    EvalQuestion(
        question="사용자의 소속 기관 정보",
        ground_truth_cypher=(
            "MATCH (u:User)-[:BELONGS_TO]->"
            "(o:Organization) RETURN u.name, o.name"
        ),
        expected_labels=["User", "Organization"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="사용자-기관 소속 관계 (BELONGS_TO)",
    ),
    EvalQuestion(
        question="파이프라인이 데이터를 적재하는 대상",
        ground_truth_cypher=(
            "MATCH (dp:DataPipeline)-[:PIPELINE_FEEDS]->"
            "(ds:DataSource) RETURN dp.name, ds"
        ),
        expected_labels=["DataPipeline", "DataSource"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="파이프라인-적재 대상 관계 (PIPELINE_FEEDS)",
    ),
    EvalQuestion(
        question="서비스가 MCP로 노출하는 도구 목록",
        ground_truth_cypher=(
            "MATCH (s:Service)-[:EXPOSES_TOOL]->"
            "(t:MCPTool) RETURN s.name, t.name"
        ),
        expected_labels=["Service", "MCPTool"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="서비스-MCP 도구 노출 관계 (EXPOSES_TOOL)",
    ),
    EvalQuestion(
        question="관측 데이터의 좌표 정보",
        ground_truth_cypher=(
            "MATCH (o:Observation)-[:OBSERVED_AT]->"
            "(g:GeoPoint) RETURN o.observationId, g"
        ),
        expected_labels=["Observation", "GeoPoint"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="관측-좌표 위치 관계 (OBSERVED_AT)",
    ),
    EvalQuestion(
        question="관측 데이터에서 자동 탐지된 선박",
        ground_truth_cypher=(
            "MATCH (o:Observation)-[:DETECTED]->"
            "(v:Vessel) RETURN o, v.name"
        ),
        expected_labels=["Observation", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="관측-선박 자동탐지 관계 (DETECTED)",
    ),
    EvalQuestion(
        question="관측 데이터에서 식별된 선박",
        ground_truth_cypher=(
            "MATCH (o:Observation)-[:IDENTIFIED]->"
            "(v:Vessel) RETURN o, v.name"
        ),
        expected_labels=["Observation", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="관측-선박 식별 관계 (IDENTIFIED)",
    ),
    EvalQuestion(
        question="관측 데이터가 기여한 트랙 세그먼트",
        ground_truth_cypher=(
            "MATCH (o:Observation)-[:TRACKED]->"
            "(ts:TrackSegment) RETURN o, ts"
        ),
        expected_labels=["Observation", "TrackSegment"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="관측-트랙세그먼트 추적 관계 (TRACKED)",
    ),
    EvalQuestion(
        question="관측 데이터의 임베딩 벡터",
        ground_truth_cypher=(
            "MATCH (o:Observation)-[:HAS_EMBEDDING]->"
            "(ve:VisualEmbedding) RETURN o, ve"
        ),
        expected_labels=["Observation", "VisualEmbedding"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="관측-임베딩 관계 (HAS_EMBEDDING)",
    ),
    EvalQuestion(
        question="서비스가 사용하는 데이터소스",
        ground_truth_cypher=(
            "MATCH (s:Service)-[:USES_DATA]->"
            "(ds:DataSource) RETURN s.name, ds"
        ),
        expected_labels=["Service", "DataSource"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="서비스-데이터소스 사용 관계 (USES_DATA)",
    ),
    EvalQuestion(
        question="센서 리딩의 측정 위치 좌표",
        ground_truth_cypher=(
            "MATCH (sr:SensorReading)-[:READING_AT]->"
            "(g:GeoPoint) RETURN sr, g"
        ),
        expected_labels=["SensorReading", "GeoPoint"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="센서리딩-좌표 위치 관계 (READING_AT)",
    ),
    EvalQuestion(
        question="융합 임베딩의 원본 위성영상",
        ground_truth_cypher=(
            "MATCH (fe:FusedEmbedding)-[:FUSED_FROM_IMAGE]->"
            "(si:SatelliteImage) RETURN fe, si"
        ),
        expected_labels=["FusedEmbedding", "SatelliteImage"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="융합임베딩-위성영상 원본 관계 (FUSED_FROM_IMAGE)",
    ),
    EvalQuestion(
        question="화물 적재 목록을 가진 선박",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:CARRIES]->"
            "(c:Cargo) RETURN v.name, c"
        ),
        expected_labels=["Vessel", "Cargo"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="선박-화물 적재 관계 (CARRIES)",
    ),
    EvalQuestion(
        question="IMO 위험물코드가 적용되는 화물 목록",
        ground_truth_cypher=(
            "MATCH (r:IMDGCode)-[:APPLIES_TO]->"
            "(c:DangerousGoods) RETURN r, c"
        ),
        expected_labels=["IMDGCode", "DangerousGoods"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="IMDG-위험물 적용 관계 (APPLIES_TO)",
    ),

    # -----------------------------------------------------------------
    # HARD 41-140 (100 questions)
    # -----------------------------------------------------------------
    # -- 3-hop+ BRIDGE 40개 --
    EvalQuestion(
        question="부산항 시설을 이용하는 선박의 소유 기관",
        ground_truth_cypher=(
            "MATCH (p:Port {name: '부산항'})-[:HAS_FACILITY]->(pf:PortFacility) "
            "MATCH (v:Vessel)-[:DOCKED_AT]->(p) "
            "MATCH (v)-[:OWNED_BY]->(o:Organization) "
            "RETURN pf.name, v.name, o.name"
        ),
        expected_labels=["Port", "PortFacility", "Vessel", "Organization"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (항만->시설+선박->기관)",
    ),
    EvalQuestion(
        question="예인수조 실험에서 생성된 계측 데이터의 보안 등급",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:CONDUCTED_AT]->"
            "(f:TestFacility {name: '대형예인수조'}) "
            "MATCH (e)-[:PRODUCED]->(ed:ExperimentalDataset) "
            "MATCH (ed)-[:CLASSIFIED_AS]->(dc:DataClass) "
            "RETURN e.title, ed, dc.name"
        ),
        expected_labels=["Experiment", "TestFacility", "ExperimentalDataset", "DataClass"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (시설->실험->데이터셋->보안등급)",
    ),
    EvalQuestion(
        question="AIS 수집 파이프라인이 읽는 소스의 제공 기관",
        ground_truth_cypher=(
            "MATCH (dp:DataPipeline {name: 'AIS 수집 파이프라인'})"
            "-[:PIPELINE_READS]->(ds:DataSource) "
            "MATCH (ds)-[:PROVIDED_BY]->(o:Organization) "
            "RETURN dp.name, ds, o.name"
        ),
        expected_labels=["DataPipeline", "DataSource", "Organization"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop (파이프라인->소스->기관)",
    ),
    EvalQuestion(
        question="워크플로우 노드가 사용하는 AI 모델의 학습 데이터소스",
        ground_truth_cypher=(
            "MATCH (w:Workflow)-[:CONTAINS_NODE]->(wn:WorkflowNode) "
            "MATCH (wn)-[:USES_MODEL]->(m:AIModel) "
            "MATCH (wn)-[:READS_FROM]->(ds:DataSource) "
            "RETURN w.name, wn.name, m.name, ds"
        ),
        expected_labels=["Workflow", "WorkflowNode", "AIModel", "DataSource"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (워크플로우->노드->모델+데이터소스)",
    ),
    EvalQuestion(
        question="비디오 클립에 찍힌 선박의 항해 경로와 도착항",
        ground_truth_cypher=(
            "MATCH (vc:VideoClip)-[:VIDEO_DEPICTS]->(v:Vessel) "
            "MATCH (v)-[:ON_VOYAGE]->(voy:Voyage)-[:TO_PORT]->(p:Port) "
            "RETURN vc, v.name, voy, p.name"
        ),
        expected_labels=["VideoClip", "Vessel", "Voyage", "Port"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (비디오->선박->항해->도착항)",
    ),
    EvalQuestion(
        question="센서 리딩이 발생한 지점 근처 사고 이력",
        ground_truth_cypher=(
            "MATCH (sr:SensorReading)-[:READING_FROM_SENSOR]->(s:Sensor) "
            "MATCH (sr)-[:READING_AT]->(g:GeoPoint) "
            "MATCH (i:Incident)-[:OCCURRED_AT]->(g) "
            "RETURN sr, s, i"
        ),
        expected_labels=["SensorReading", "Sensor", "GeoPoint", "Incident"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (센서리딩->센서+좌표->사고)",
    ),
    EvalQuestion(
        question="융합 임베딩의 AIS 원본 데이터가 추적하는 선박",
        ground_truth_cypher=(
            "MATCH (fe:FusedEmbedding)-[:FUSED_FROM]->(a:AISData) "
            "MATCH (a)-[:AIS_TRACK_OF]->(v:Vessel) "
            "RETURN fe, a, v.name"
        ),
        expected_labels=["FusedEmbedding", "AISData", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop (융합임베딩->AIS->선박)",
    ),
    EvalQuestion(
        question="AI 에이전트가 실행하는 워크플로우의 노드가 사용하는 모델",
        ground_truth_cypher=(
            "MATCH (a:AIAgent)-[:EXECUTES]->(w:Workflow) "
            "MATCH (w)-[:CONTAINS_NODE]->(n:WorkflowNode) "
            "MATCH (n)-[:USES_MODEL]->(m:AIModel) "
            "RETURN a.name, w.name, n.name, m.name"
        ),
        expected_labels=["AIAgent", "Workflow", "WorkflowNode", "AIModel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (에이전트->워크플로우->노드->모델)",
    ),
    EvalQuestion(
        question="항행경고 해역의 기상 조건과 사고 현황",
        ground_truth_cypher=(
            "MATCH (nw:NavigationalWarning)-[:APPLIES_TO_AREA]->(s:SeaArea) "
            "MATCH (wc:WeatherCondition)-[:AFFECTS]->(s) "
            "MATCH (i:Incident)-[:OCCURRED_NEAR]->(s) "
            "RETURN nw.title, s.name, wc, count(i) AS incidents"
        ),
        expected_labels=["NavigationalWarning", "SeaArea", "WeatherCondition", "Incident"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (항행경고->해역->기상+사고)",
    ),
    EvalQuestion(
        question="데이터 파이프라인이 적재하는 소스에서 파생된 다른 소스",
        ground_truth_cypher=(
            "MATCH (dp:DataPipeline)-[:PIPELINE_FEEDS]->(ds1:DataSource) "
            "MATCH (ds2:DataSource)-[:DERIVED_FROM]->(ds1) "
            "RETURN dp.name, ds1, ds2"
        ),
        expected_labels=["DataPipeline", "DataSource"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop (파이프라인->소스->파생소스)",
    ),
    EvalQuestion(
        question="실험 비디오가 촬영된 센서의 관측 데이터",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:RECORDED_VIDEO]->(vc:VideoClip) "
            "MATCH (vc)-[:VIDEO_FROM]->(s:Sensor) "
            "MATCH (s)-[:PRODUCES]->(o:Observation) "
            "RETURN e.title, vc, s, o"
        ),
        expected_labels=["Experiment", "VideoClip", "Sensor", "Observation"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (실험->비디오->센서->관측)",
    ),
    EvalQuestion(
        question="관측에서 탐지된 선박의 소유사와 운항 항해",
        ground_truth_cypher=(
            "MATCH (o:Observation)-[:DETECTED]->(v:Vessel) "
            "MATCH (v)-[:OWNED_BY]->(org:Organization) "
            "MATCH (v)-[:ON_VOYAGE]->(voy:Voyage) "
            "RETURN o, v.name, org.name, voy"
        ),
        expected_labels=["Observation", "Vessel", "Organization", "Voyage"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (관측->선박->기관+항해)",
    ),
    EvalQuestion(
        question="CCTV 관측에서 식별된 선박의 화물 정보",
        ground_truth_cypher=(
            "MATCH (o:CCTVObservation)-[:IDENTIFIED]->(v:Vessel) "
            "MATCH (v)-[:CARRIES]->(c:Cargo) "
            "RETURN o, v.name, c"
        ),
        expected_labels=["CCTVObservation", "Vessel", "Cargo"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop (CCTV관측->선박->화물)",
    ),
    EvalQuestion(
        question="서비스 체인: 분석서비스가 연계하는 예측서비스의 데이터소스",
        ground_truth_cypher=(
            "MATCH (s1:AnalysisService)-[:FEEDS]->(s2:PredictionService) "
            "MATCH (s2)-[:USES_DATA]->(ds:DataSource) "
            "RETURN s1.name, s2.name, ds"
        ),
        expected_labels=["AnalysisService", "PredictionService", "DataSource"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop (분석->예측서비스->데이터소스)",
    ),
    EvalQuestion(
        question="항해 트랙 세그먼트에 기여한 관측의 원본 센서",
        ground_truth_cypher=(
            "MATCH (voy:Voyage)-[:CONSISTS_OF]->(ts:TrackSegment) "
            "MATCH (o:Observation)-[:TRACKED]->(ts) "
            "MATCH (s:Sensor)-[:PRODUCES]->(o) "
            "RETURN voy, ts, o, s"
        ),
        expected_labels=["Voyage", "TrackSegment", "Observation", "Sensor"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (항해->트랙->관측->센서)",
    ),
    EvalQuestion(
        question="선박의 적재 위험물에 적용되는 IMDG 규정",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:CARRIES]->(dg:DangerousGoods) "
            "MATCH (r:IMDGCode)-[:APPLIES_TO]->(dg) "
            "RETURN v.name, dg, r"
        ),
        expected_labels=["Vessel", "DangerousGoods", "IMDGCode"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop (선박->위험물->IMDG)",
    ),
    EvalQuestion(
        question="워크플로우 노드가 쓰는 소스를 제공하는 기관",
        ground_truth_cypher=(
            "MATCH (wn:WorkflowNode)-[:WRITES_TO]->(ds:DataSource) "
            "MATCH (ds)-[:PROVIDED_BY]->(o:Organization) "
            "RETURN wn.name, ds, o.name"
        ),
        expected_labels=["WorkflowNode", "DataSource", "Organization"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop (노드->데이터소스->기관)",
    ),
    EvalQuestion(
        question="크로스모달 매칭된 관측의 원본 센서와 탐지된 선박",
        ground_truth_cypher=(
            "MATCH (o1:Observation)-[:MATCHED_WITH]->(o2:Observation) "
            "MATCH (s1:Sensor)-[:PRODUCES]->(o1) "
            "MATCH (o2)-[:DETECTED]->(v:Vessel) "
            "RETURN s1, o1, o2, v.name"
        ),
        expected_labels=["Observation", "Sensor", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (센서->관측->매칭관측->선박)",
    ),
    EvalQuestion(
        question="실험 센서 측정이 발생한 좌표와 인근 기상 조건",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:MEASURED_DATA]->(sr:SensorReading) "
            "MATCH (sr)-[:READING_AT]->(g:GeoPoint) "
            "MATCH (wc:WeatherCondition)-[:OBSERVED_AT]->(g) "
            "RETURN e.title, sr, g, wc"
        ),
        expected_labels=["Experiment", "SensorReading", "GeoPoint", "WeatherCondition"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (실험->센서리딩->좌표->기상)",
    ),
    EvalQuestion(
        question="MCP 도구를 노출하는 서비스와 도구를 호출하는 에이전트의 워크플로우",
        ground_truth_cypher=(
            "MATCH (svc:Service)-[:EXPOSES_TOOL]->(t:MCPTool) "
            "MATCH (a:AIAgent)-[:INVOKES]->(t) "
            "MATCH (a)-[:EXECUTES]->(w:Workflow) "
            "RETURN svc.name, t.name, a.name, w.name"
        ),
        expected_labels=["Service", "MCPTool", "AIAgent", "Workflow"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (서비스->도구->에이전트->워크플로우)",
    ),
    EvalQuestion(
        question="알림서비스가 생성한 보고서를 발행한 기관",
        ground_truth_cypher=(
            "MATCH (s:AlertService)-[:GENERATES]->(d:Document) "
            "MATCH (d)-[:ISSUED_BY]->(o:Organization) "
            "RETURN s.name, d.title, o.name"
        ),
        expected_labels=["AlertService", "Document", "Organization"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop (알림서비스->문서->기관)",
    ),
    EvalQuestion(
        question="위성영상에서 탐지된 선박의 화물과 출발항",
        ground_truth_cypher=(
            "MATCH (si:SatelliteImage)-[:SAT_DETECTED]->(v:Vessel) "
            "MATCH (v)-[:CARRIES]->(c:Cargo) "
            "MATCH (v)-[:ON_VOYAGE]->(voy:Voyage)-[:FROM_PORT]->(p:Port) "
            "RETURN si, v.name, c, p.name"
        ),
        expected_labels=["SatelliteImage", "Vessel", "Cargo", "Voyage", "Port"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="5-hop (위성->선박->화물+항해->출발항)",
    ),
    EvalQuestion(
        question="사고에 연루된 선박의 검사 보고서 발행 기관",
        ground_truth_cypher=(
            "MATCH (i:Incident)-[:INVOLVES]->(v:Vessel) "
            "MATCH (d:InspectionReport)-[:DESCRIBES]->(i) "
            "MATCH (d)-[:ISSUED_BY]->(o:Organization) "
            "RETURN i.incidentId, v.name, d.title, o.name"
        ),
        expected_labels=["Incident", "Vessel", "InspectionReport", "Organization"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (사고->선박+보고서->기관)",
    ),
    EvalQuestion(
        question="AIS 데이터의 해역별 위성영상 교차 검증",
        ground_truth_cypher=(
            "MATCH (a:AISData)-[:OBSERVED_IN_AREA]->(s:SeaArea) "
            "MATCH (si:SatelliteImage)-[:CAPTURED_OVER]->(s) "
            "MATCH (a)-[:AIS_TRACK_OF]->(v:Vessel) "
            "RETURN s.name, v.name, count(a) AS aisCnt, count(si) AS satCnt"
        ),
        expected_labels=["AISData", "SeaArea", "SatelliteImage", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (AIS->해역<-위성+선박)",
    ),
    EvalQuestion(
        question="실험이 준수하는 규정을 시행하는 기관",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:COMPLIES_WITH]->(r:Regulation) "
            "MATCH (r)-[:ENFORCED_BY]->(o:Organization) "
            "RETURN e.title, r.title, o.name"
        ),
        expected_labels=["Experiment", "Regulation", "Organization"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop (실험->규정->기관)",
    ),
    EvalQuestion(
        question="해도 기반 실험의 모형선과 실물 선박",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:BASED_ON_CHART]->(mc:MaritimeChart) "
            "MATCH (e)-[:TESTED]->(m:ModelShip)-[:MODEL_OF]->(v:Vessel) "
            "RETURN e.title, mc, m, v.name"
        ),
        expected_labels=["Experiment", "MaritimeChart", "ModelShip", "Vessel"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (실험->해도+모형선->실선)",
    ),
    EvalQuestion(
        question="선박 활동 이력과 해당 활동 중 기상 조건",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:PERFORMS]->(a:Activity) "
            "MATCH (v)-[:LOCATED_AT]->(s:SeaArea) "
            "MATCH (wc:WeatherCondition)-[:AFFECTS]->(s) "
            "RETURN v.name, a, s.name, wc"
        ),
        expected_labels=["Vessel", "Activity", "SeaArea", "WeatherCondition"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (선박->활동+해역->기상)",
    ),
    EvalQuestion(
        question="MCP 리소스를 노출하는 서비스의 입력 데이터소스 제공 기관",
        ground_truth_cypher=(
            "MATCH (svc:Service)-[:EXPOSES_RESOURCE]->(r:MCPResource) "
            "MATCH (svc)-[:REQUIRES_INPUT]->(ds:DataSource) "
            "MATCH (ds)-[:PROVIDED_BY]->(o:Organization) "
            "RETURN svc.name, r, ds, o.name"
        ),
        expected_labels=["Service", "MCPResource", "DataSource", "Organization"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (서비스->리소스+입력소스->기관)",
    ),
    EvalQuestion(
        question="선박 정박 선석의 항만과 해당 항만의 시설 목록",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:DOCKED_AT]->(b:Berth) "
            "MATCH (p:Port)-[:HAS_FACILITY]->(pf:PortFacility) "
            "MATCH (v)-[:DOCKED_AT]->(p) "
            "RETURN v.name, b, p.name, collect(pf.name) AS facilities"
        ),
        expected_labels=["Vessel", "Berth", "Port", "PortFacility"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (선박->선석+항만->시설)",
    ),
    EvalQuestion(
        question="어선의 불법조업 이력과 위반 규정",
        ground_truth_cypher=(
            "MATCH (fv:FishingVessel)<-[:INVOLVES]-(ilf:IllegalFishing) "
            "MATCH (ilf)-[:VIOLATED]->(r:Regulation) "
            "RETURN fv.name, ilf, r.title"
        ),
        expected_labels=["FishingVessel", "IllegalFishing", "Regulation"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop (어선->불법조업->규정위반)",
    ),
    EvalQuestion(
        question="조난사고 발생 해역의 레이더 영상과 기상 관측",
        ground_truth_cypher=(
            "MATCH (d:Distress)-[:OCCURRED_NEAR]->(s:SeaArea) "
            "MATCH (ri:RadarImage)-[:RADAR_COVERS]->(s) "
            "MATCH (wc:WeatherCondition)-[:AFFECTS]->(s) "
            "RETURN d, s.name, ri, wc"
        ),
        expected_labels=["Distress", "SeaArea", "RadarImage", "WeatherCondition"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (조난->해역->레이더+기상)",
    ),
    EvalQuestion(
        question="오염사고 선박의 소유사와 적재 위험물",
        ground_truth_cypher=(
            "MATCH (p:Pollution)-[:INVOLVES]->(v:Vessel) "
            "MATCH (v)-[:OWNED_BY]->(o:Organization) "
            "MATCH (v)-[:CARRIES]->(dg:DangerousGoods) "
            "RETURN p, v.name, o.name, dg"
        ),
        expected_labels=["Pollution", "Vessel", "Organization", "DangerousGoods"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (오염->선박->소유사+위험물)",
    ),
    EvalQuestion(
        question="실험 데이터셋의 원시 데이터 중 저항 측정 결과",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:PRODUCED]->(ed:ExperimentalDataset) "
            "MATCH (ed)-[:HAS_RAW_DATA]->(m:Resistance) "
            "RETURN e.title, ed, m"
        ),
        expected_labels=["Experiment", "ExperimentalDataset", "Resistance"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop (실험->데이터셋->저항측정)",
    ),
    EvalQuestion(
        question="빙해수조 실험의 빙해 성능 측정과 시험 조건",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:CONDUCTED_AT]->(f:IceTank) "
            "MATCH (e)-[:HAS_MEASUREMENT]->(m:IcePerformance) "
            "MATCH (e)-[:UNDER_CONDITION]->(tc:TestCondition) "
            "RETURN e.title, f, m, tc"
        ),
        expected_labels=["Experiment", "IceTank", "IcePerformance", "TestCondition"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (빙해수조->실험->빙해성능+조건)",
    ),
    EvalQuestion(
        question="심해수조 실험의 내항성능 측정 데이터",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:CONDUCTED_AT]->(f:DeepOceanBasin) "
            "MATCH (e)-[:HAS_MEASUREMENT]->(m:Seakeeping) "
            "RETURN e.title, f, m"
        ),
        expected_labels=["Experiment", "DeepOceanBasin", "Seakeeping"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="3-hop (심해수조->실험->내항성능)",
    ),
    EvalQuestion(
        question="대형 캐비테이션터널 추진 성능 실험의 모형선",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:CONDUCTED_AT]->(f:LargeCavitationTunnel) "
            "MATCH (e)-[:HAS_MEASUREMENT]->(m:Propulsion) "
            "MATCH (e)-[:TESTED]->(ms:ModelShip) "
            "RETURN e.title, f, m, ms"
        ),
        expected_labels=["Experiment", "LargeCavitationTunnel", "Propulsion", "ModelShip"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (대형캐비테이션->실험->추진+모형선)",
    ),
    EvalQuestion(
        question="고속 캐비테이션터널 조종 실험 결과와 시험 조건",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:CONDUCTED_AT]->(f:HighSpeedCavitationTunnel) "
            "MATCH (e)-[:HAS_MEASUREMENT]->(m:Maneuvering) "
            "MATCH (e)-[:UNDER_CONDITION]->(tc:TestCondition) "
            "RETURN e.title, m, tc"
        ),
        expected_labels=["Experiment", "HighSpeedCavitationTunnel", "Maneuvering", "TestCondition"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (고속캐비테이션->실험->조종+조건)",
    ),
    # -- COMPARISON 15개 --
    EvalQuestion(
        question="무역항과 어항의 시설 수 비교",
        ground_truth_cypher=(
            "MATCH (tp:TradePort)-[:HAS_FACILITY]->(pf1:PortFacility) "
            "WITH count(pf1) AS tradeFacilities "
            "MATCH (fp:FishingPort)-[:HAS_FACILITY]->(pf2:PortFacility) "
            "RETURN tradeFacilities, count(pf2) AS fishFacilities"
        ),
        expected_labels=["TradePort", "FishingPort", "PortFacility"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="무역항 vs 어항 시설 수 비교",
    ),
    EvalQuestion(
        question="AIS와 레이더 관측의 선박 탐지 수 비교",
        ground_truth_cypher=(
            "MATCH (o1:AISObservation)-[:DETECTED]->(v1:Vessel) "
            "WITH count(DISTINCT v1) AS aisCnt "
            "MATCH (o2:RadarObservation)-[:DETECTED]->(v2:Vessel) "
            "RETURN aisCnt, count(DISTINCT v2) AS radarCnt"
        ),
        expected_labels=["AISObservation", "RadarObservation", "Vessel"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="AIS vs 레이더 탐지 선박 수 비교",
    ),
    EvalQuestion(
        question="화물선과 여객선의 평균 속력 비교",
        ground_truth_cypher=(
            "MATCH (v1:CargoShip) "
            "WITH avg(v1.speed) AS cargoAvg "
            "MATCH (v2:PassengerShip) "
            "RETURN cargoAvg, avg(v2.speed) AS passengerAvg"
        ),
        expected_labels=["CargoShip", "PassengerShip"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="화물선 vs 여객선 속력 비교",
    ),
    EvalQuestion(
        question="부산항과 인천항의 선석 수 비교",
        ground_truth_cypher=(
            "MATCH (p1:Port {name: '부산항'})-[:HAS_FACILITY]->(b1:Berth) "
            "WITH count(b1) AS busanBerths "
            "MATCH (p2:Port {name: '인천항'})-[:HAS_FACILITY]->(b2:Berth) "
            "RETURN busanBerths, count(b2) AS incheonBerths"
        ),
        expected_labels=["Port", "Berth"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="부산항 vs 인천항 선석 수 비교",
    ),
    EvalQuestion(
        question="자율운항선과 일반선박의 사고 건수 비교",
        ground_truth_cypher=(
            "MATCH (i1:Incident)-[:INVOLVES]->(v1:AutonomousVessel) "
            "WITH count(i1) AS autoCnt "
            "MATCH (i2:Incident)-[:INVOLVES]->(v2:Vessel) "
            "WHERE NOT v2:AutonomousVessel "
            "RETURN autoCnt, count(i2) AS normalCnt"
        ),
        expected_labels=["Incident", "AutonomousVessel", "Vessel"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="자율운항선 vs 일반선박 사고 비교",
    ),
    EvalQuestion(
        question="내부연구원과 공개 역할의 권한 수 비교",
        ground_truth_cypher=(
            "MATCH (r1:Role {name: '내부연구원'})-[:GRANTS]->(p1:Permission) "
            "WITH count(p1) AS researchPerms "
            "MATCH (r2:Role {name: '공개'})-[:GRANTS]->(p2:Permission) "
            "RETURN researchPerms, count(p2) AS publicPerms"
        ),
        expected_labels=["Role", "Permission"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="내부연구원 vs 공개 역할 권한 비교",
    ),
    EvalQuestion(
        question="동해와 서해의 사고 건수 비교",
        ground_truth_cypher=(
            "MATCH (i1:Incident)-[:OCCURRED_NEAR]->(s1:SeaArea {name: '동해'}) "
            "WITH count(i1) AS eastCnt "
            "MATCH (i2:Incident)-[:OCCURRED_NEAR]->(s2:SeaArea {name: '서해'}) "
            "RETURN eastCnt, count(i2) AS westCnt"
        ),
        expected_labels=["Incident", "SeaArea"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="동해 vs 서해 사고 건수 비교",
    ),
    EvalQuestion(
        question="충돌사고와 좌초사고의 연간 발생 추이 비교",
        ground_truth_cypher=(
            "MATCH (c:Collision) "
            "WITH c.date.year AS year, count(c) AS collisions "
            "MATCH (g:Grounding) "
            "WHERE g.date.year = year "
            "RETURN year, collisions, count(g) AS groundings "
            "ORDER BY year"
        ),
        expected_labels=["Collision", "Grounding"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="충돌 vs 좌초 연간 추이 비교",
    ),
    EvalQuestion(
        question="분석서비스와 예측서비스의 데이터소스 수 비교",
        ground_truth_cypher=(
            "MATCH (s1:AnalysisService)-[:USES_DATA]->(ds1:DataSource) "
            "WITH count(ds1) AS analysisCnt "
            "MATCH (s2:PredictionService)-[:USES_DATA]->(ds2:DataSource) "
            "RETURN analysisCnt, count(ds2) AS predictionCnt"
        ),
        expected_labels=["AnalysisService", "PredictionService", "DataSource"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="분석 vs 예측서비스 데이터소스 비교",
    ),
    EvalQuestion(
        question="예인수조와 빙해수조의 평균 실험 기간 비교",
        ground_truth_cypher=(
            "MATCH (e1:Experiment)-[:CONDUCTED_AT]->"
            "(f1:TowingTank) "
            "WITH avg(e1.duration) AS towingAvg "
            "MATCH (e2:Experiment)-[:CONDUCTED_AT]->(f2:IceTank) "
            "RETURN towingAvg, avg(e2.duration) AS iceAvg"
        ),
        expected_labels=["Experiment", "TowingTank", "IceTank"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="예인수조 vs 빙해수조 실험 기간 비교",
    ),
    EvalQuestion(
        question="한국선급과 DNV의 인증 선박 수 비교",
        ground_truth_cypher=(
            "MATCH (cs1:ClassificationSociety {name: 'KR'})"
            "<-[:CERTIFIED_BY]-(v1:Vessel) "
            "WITH count(v1) AS krCnt "
            "MATCH (cs2:ClassificationSociety {name: 'DNV'})"
            "<-[:CERTIFIED_BY]-(v2:Vessel) "
            "RETURN krCnt, count(v2) AS dnvCnt"
        ),
        expected_labels=["ClassificationSociety", "Vessel"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="KR vs DNV 인증 선박 수 비교",
    ),
    EvalQuestion(
        question="CCTV와 위성 관측의 선박 식별 정확도 비교",
        ground_truth_cypher=(
            "MATCH (o1:CCTVObservation)-[:IDENTIFIED]->(v1:Vessel) "
            "WITH avg(o1.confidence) AS cctvConf "
            "MATCH (o2:SARObservation)-[:IDENTIFIED]->(v2:Vessel) "
            "RETURN cctvConf, avg(o2.confidence) AS sarConf"
        ),
        expected_labels=["CCTVObservation", "SARObservation", "Vessel"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="CCTV vs SAR 식별 정확도 비교",
    ),
    EvalQuestion(
        question="API와 스트림 데이터소스의 수 비교",
        ground_truth_cypher=(
            "MATCH (a:APIEndpoint) "
            "WITH count(a) AS apiCnt "
            "MATCH (s:StreamSource) "
            "RETURN apiCnt, count(s) AS streamCnt"
        ),
        expected_labels=["APIEndpoint", "StreamSource"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="API vs 스트림 데이터소스 수 비교",
    ),
    EvalQuestion(
        question="파일소스와 스트림소스 기반 파이프라인 수 비교",
        ground_truth_cypher=(
            "MATCH (dp1:DataPipeline)-[:PIPELINE_READS]->(fs:FileSource) "
            "WITH count(dp1) AS fileCnt "
            "MATCH (dp2:DataPipeline)-[:PIPELINE_READS]->(ss:StreamSource) "
            "RETURN fileCnt, count(dp2) AS streamCnt"
        ),
        expected_labels=["DataPipeline", "FileSource", "StreamSource"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="파일 vs 스트림소스 파이프라인 비교",
    ),
    EvalQuestion(
        question="구조응답과 추진 측정의 데이터 건수 비교",
        ground_truth_cypher=(
            "MATCH (m1:StructuralResponse) "
            "WITH count(m1) AS structCnt "
            "MATCH (m2:Propulsion) "
            "RETURN structCnt, count(m2) AS propCnt"
        ),
        expected_labels=["StructuralResponse", "Propulsion"],
        reasoning_type=ReasoningType.COMPARISON,
        difficulty=Difficulty.HARD,
        description="구조응답 vs 추진 측정 건수 비교",
    ),
    # -- INTERSECTION 15개 --
    EvalQuestion(
        question="부산항과 인천항 모두에 시설을 보유한 기관",
        ground_truth_cypher=(
            "MATCH (o:Organization)-[:OPERATES]->"
            "(pf1:PortFacility)<-[:HAS_FACILITY]-(p1:Port {name: '부산항'}) "
            "MATCH (o)-[:OPERATES]->"
            "(pf2:PortFacility)<-[:HAS_FACILITY]-(p2:Port {name: '인천항'}) "
            "RETURN o.name"
        ),
        expected_labels=["Organization", "PortFacility", "Port"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 (두 항만 공통 운영 기관)",
    ),
    EvalQuestion(
        question="AIS와 위성 모두에서 탐지된 선박",
        ground_truth_cypher=(
            "MATCH (v:Vessel)<-[:DETECTED]-(o1:AISObservation) "
            "MATCH (v)<-[:SAT_DETECTED]-(si:SatelliteImage) "
            "RETURN DISTINCT v.name"
        ),
        expected_labels=["Vessel", "AISObservation", "SatelliteImage"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 (AIS + 위성 동시 탐지 선박)",
    ),
    EvalQuestion(
        question="COLREG와 SOLAS 모두를 위반한 사고",
        ground_truth_cypher=(
            "MATCH (i:Incident)-[:VIOLATED]->(r1:COLREG) "
            "MATCH (i)-[:VIOLATED]->(r2:SOLAS) "
            "RETURN i"
        ),
        expected_labels=["Incident", "COLREG", "SOLAS"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 (두 규정 동시 위반 사고)",
    ),
    EvalQuestion(
        question="분석서비스와 알림서비스 모두에 데이터를 공급하는 소스",
        ground_truth_cypher=(
            "MATCH (s1:AnalysisService)-[:USES_DATA]->(ds:DataSource) "
            "MATCH (s2:AlertService)-[:USES_DATA]->(ds) "
            "RETURN ds"
        ),
        expected_labels=["AnalysisService", "AlertService", "DataSource"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 (두 서비스 공통 데이터소스)",
    ),
    EvalQuestion(
        question="동해와 남해 모두에서 관측된 AIS 데이터",
        ground_truth_cypher=(
            "MATCH (a:AISData)-[:OBSERVED_IN_AREA]->"
            "(s1:SeaArea {name: '동해'}) "
            "MATCH (a)-[:OBSERVED_IN_AREA]->"
            "(s2:SeaArea {name: '남해'}) "
            "RETURN a"
        ),
        expected_labels=["AISData", "SeaArea"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 (두 해역 공통 AIS 데이터)",
    ),
    EvalQuestion(
        question="저항시험과 추진시험 모두를 수행한 시설",
        ground_truth_cypher=(
            "MATCH (e1:Experiment {name: '저항시험'})-[:CONDUCTED_AT]->(f:TestFacility) "
            "MATCH (e2:Experiment {name: '추진시험'})-[:CONDUCTED_AT]->(f) "
            "RETURN f.name"
        ),
        expected_labels=["Experiment", "TestFacility"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 (두 실험 공통 시설)",
    ),
    EvalQuestion(
        question="두 개 이상의 워크플로우에 포함된 공통 노드",
        ground_truth_cypher=(
            "MATCH (w1:Workflow)-[:CONTAINS_NODE]->(n:WorkflowNode) "
            "MATCH (w2:Workflow)-[:CONTAINS_NODE]->(n) "
            "WHERE w1 <> w2 "
            "RETURN n.name, collect(DISTINCT w1.name) AS workflows"
        ),
        expected_labels=["Workflow", "WorkflowNode"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 (다중 워크플로우 공통 노드)",
    ),
    EvalQuestion(
        question="CCTV와 레이더 모두에 포착된 선박",
        ground_truth_cypher=(
            "MATCH (v:Vessel)<-[:DETECTED]-(o1:CCTVObservation) "
            "MATCH (v)<-[:DETECTED]-(o2:RadarObservation) "
            "RETURN DISTINCT v.name"
        ),
        expected_labels=["Vessel", "CCTVObservation", "RadarObservation"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 (CCTV + 레이더 동시 포착 선박)",
    ),
    EvalQuestion(
        question="두 해운사가 공통으로 소유한 선박",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:OWNED_BY]->"
            "(o1:ShippingCompany {name: 'HMM'}) "
            "MATCH (v)-[:OWNED_BY]->"
            "(o2:ShippingCompany {name: 'Pan Ocean'}) "
            "RETURN v.name"
        ),
        expected_labels=["Vessel", "ShippingCompany"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 (두 해운사 공동 소유 선박)",
    ),
    EvalQuestion(
        question="두 개 이상의 에이전트가 호출하는 공통 MCP 도구",
        ground_truth_cypher=(
            "MATCH (a1:AIAgent)-[:INVOKES]->(t:MCPTool) "
            "MATCH (a2:AIAgent)-[:INVOKES]->(t) "
            "WHERE a1 <> a2 "
            "RETURN t.name, collect(DISTINCT a1.name) AS agents"
        ),
        expected_labels=["AIAgent", "MCPTool"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 (다중 에이전트 공통 도구)",
    ),
    EvalQuestion(
        question="레이더와 해도 모두 커버하는 해역",
        ground_truth_cypher=(
            "MATCH (ri:RadarImage)-[:RADAR_COVERS]->(s:SeaArea) "
            "MATCH (mc:MaritimeChart)-[:CHART_COVERS]->(s) "
            "RETURN DISTINCT s.name"
        ),
        expected_labels=["RadarImage", "MaritimeChart", "SeaArea"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 (레이더 + 해도 공통 해역)",
    ),
    EvalQuestion(
        question="내부연구원과 외부연구자 모두 접근 가능한 데이터 등급",
        ground_truth_cypher=(
            "MATCH (r1:Role {name: '내부연구원'})-[:CAN_ACCESS]->(dc:DataClass) "
            "MATCH (r2:Role {name: '외부연구자'})-[:CAN_ACCESS]->(dc) "
            "RETURN dc.name"
        ),
        expected_labels=["Role", "DataClass"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 (두 역할 공통 데이터 등급)",
    ),
    EvalQuestion(
        question="저항측정과 추진측정 모두 포함하는 실험",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:HAS_MEASUREMENT]->(m1:Resistance) "
            "MATCH (e)-[:HAS_MEASUREMENT]->(m2:Propulsion) "
            "RETURN e.title"
        ),
        expected_labels=["Experiment", "Resistance", "Propulsion"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 (저항+추진 공통 실험)",
    ),
    EvalQuestion(
        question="동일 선박을 추적하는 AIS와 위성 데이터",
        ground_truth_cypher=(
            "MATCH (a:AISData)-[:AIS_TRACK_OF]->(v:Vessel) "
            "MATCH (si:SatelliteImage)-[:SAT_DETECTED]->(v) "
            "RETURN v.name, collect(DISTINCT a) AS aisData, "
            "collect(DISTINCT si) AS satImages"
        ),
        expected_labels=["AISData", "Vessel", "SatelliteImage"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 (AIS + 위성 동일 선박 추적)",
    ),
    EvalQuestion(
        question="두 파이프라인이 공통으로 읽는 데이터소스",
        ground_truth_cypher=(
            "MATCH (dp1:DataPipeline)-[:PIPELINE_READS]->(ds:DataSource) "
            "MATCH (dp2:DataPipeline)-[:PIPELINE_READS]->(ds) "
            "WHERE dp1 <> dp2 "
            "RETURN ds, collect(DISTINCT dp1.name) AS pipelines"
        ),
        expected_labels=["DataPipeline", "DataSource"],
        reasoning_type=ReasoningType.INTERSECTION,
        difficulty=Difficulty.HARD,
        description="교집합 (다중 파이프라인 공통 소스)",
    ),
    # -- COMPOSITION 30개 --
    EvalQuestion(
        question="해역별 AIS 관측 건수 Top 5",
        ground_truth_cypher=(
            "MATCH (a:AISData)-[:OBSERVED_IN_AREA]->(s:SeaArea) "
            "RETURN s.name, count(a) AS cnt "
            "ORDER BY cnt DESC LIMIT 5"
        ),
        expected_labels=["AISData", "SeaArea"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="해역별 AIS 관측 Top 5",
    ),
    EvalQuestion(
        question="센서 유형별 관측 데이터 수 통계",
        ground_truth_cypher=(
            "MATCH (s:Sensor)-[:PRODUCES]->(o:Observation) "
            "RETURN labels(s) AS sensorType, count(o) AS cnt "
            "ORDER BY cnt DESC"
        ),
        expected_labels=["Sensor", "Observation"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="센서 유형별 관측 수 집계",
    ),
    EvalQuestion(
        question="규정별 위반 사고 건수 통계",
        ground_truth_cypher=(
            "MATCH (i:Incident)-[:VIOLATED]->(r:Regulation) "
            "RETURN r.title, count(i) AS violations "
            "ORDER BY violations DESC"
        ),
        expected_labels=["Incident", "Regulation"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="규정별 위반 건수 집계",
    ),
    EvalQuestion(
        question="데이터소스 제공 기관별 소스 수",
        ground_truth_cypher=(
            "MATCH (ds:DataSource)-[:PROVIDED_BY]->(o:Organization) "
            "RETURN o.name, count(ds) AS cnt "
            "ORDER BY cnt DESC"
        ),
        expected_labels=["DataSource", "Organization"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="기관별 데이터소스 수 집계",
    ),
    EvalQuestion(
        question="서비스별 MCP 도구 노출 수",
        ground_truth_cypher=(
            "MATCH (s:Service)-[:EXPOSES_TOOL]->(t:MCPTool) "
            "RETURN s.name, count(t) AS tools "
            "ORDER BY tools DESC"
        ),
        expected_labels=["Service", "MCPTool"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="서비스별 MCP 도구 수 집계",
    ),
    EvalQuestion(
        question="워크플로우별 노드 수 순위",
        ground_truth_cypher=(
            "MATCH (w:Workflow)-[:CONTAINS_NODE]->(n:WorkflowNode) "
            "RETURN w.name, count(n) AS nodes "
            "ORDER BY nodes DESC"
        ),
        expected_labels=["Workflow", "WorkflowNode"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="워크플로우별 노드 수 집계",
    ),
    EvalQuestion(
        question="에이전트별 MCP 도구 호출 횟수 Top 3",
        ground_truth_cypher=(
            "MATCH (a:AIAgent)-[:INVOKES]->(t:MCPTool) "
            "RETURN a.name, count(t) AS invocations "
            "ORDER BY invocations DESC LIMIT 3"
        ),
        expected_labels=["AIAgent", "MCPTool"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="에이전트별 도구 호출 횟수 Top 3",
    ),
    EvalQuestion(
        question="역할별 부여 권한 수와 데이터 등급 수",
        ground_truth_cypher=(
            "MATCH (r:Role)-[:GRANTS]->(p:Permission) "
            "WITH r, count(p) AS perms "
            "MATCH (r)-[:CAN_ACCESS]->(dc:DataClass) "
            "RETURN r.name, perms, count(dc) AS classes "
            "ORDER BY perms DESC"
        ),
        expected_labels=["Role", "Permission", "DataClass"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="역할별 권한+데이터등급 집계",
    ),
    EvalQuestion(
        question="시설별 모형선 테스트 수 통계",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:CONDUCTED_AT]->(f:TestFacility) "
            "MATCH (e)-[:TESTED]->(m:ModelShip) "
            "RETURN f.name, count(DISTINCT m) AS models "
            "ORDER BY models DESC"
        ),
        expected_labels=["Experiment", "TestFacility", "ModelShip"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="시설별 모형선 테스트 수 집계",
    ),
    EvalQuestion(
        question="월별 사고 발생 건수 추이",
        ground_truth_cypher=(
            "MATCH (i:Incident) "
            "RETURN i.date.year AS year, i.date.month AS month, "
            "count(i) AS cnt ORDER BY year, month"
        ),
        expected_labels=["Incident"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="월별 사고 건수 시계열 집계",
    ),
    EvalQuestion(
        question="파이프라인별 읽기 소스와 적재 소스 수",
        ground_truth_cypher=(
            "MATCH (dp:DataPipeline)-[:PIPELINE_READS]->(dr:DataSource) "
            "WITH dp, count(dr) AS reads "
            "MATCH (dp)-[:PIPELINE_FEEDS]->(dw:DataSource) "
            "RETURN dp.name, reads, count(dw) AS writes"
        ),
        expected_labels=["DataPipeline", "DataSource"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="파이프라인별 읽기/쓰기 소스 수 집계",
    ),
    EvalQuestion(
        question="해역별 기상 악화 빈도 Top 3",
        ground_truth_cypher=(
            "MATCH (wc:WeatherCondition)-[:AFFECTS]->(s:SeaArea) "
            "WHERE wc.riskLevel = 'HIGH' "
            "RETURN s.name, count(wc) AS cnt "
            "ORDER BY cnt DESC LIMIT 3"
        ),
        expected_labels=["WeatherCondition", "SeaArea"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="해역별 기상 악화 빈도 Top 3",
    ),
    EvalQuestion(
        question="문서 유형별 발행 건수 통계",
        ground_truth_cypher=(
            "MATCH (d:Document) "
            "RETURN d.docType, count(d) AS cnt "
            "ORDER BY cnt DESC"
        ),
        expected_labels=["Document"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="문서 유형별 발행 건수 집계",
    ),
    EvalQuestion(
        question="선박 국적별 등록 척수 Top 10",
        ground_truth_cypher=(
            "MATCH (v:Vessel) "
            "RETURN v.flag, count(v) AS cnt "
            "ORDER BY cnt DESC LIMIT 10"
        ),
        expected_labels=["Vessel"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="국적별 선박 수 Top 10",
    ),
    EvalQuestion(
        question="기관별 발행 문서 수 순위",
        ground_truth_cypher=(
            "MATCH (d:Document)-[:ISSUED_BY]->(o:Organization) "
            "RETURN o.name, count(d) AS docs "
            "ORDER BY docs DESC"
        ),
        expected_labels=["Document", "Organization"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="기관별 문서 발행 수 집계",
    ),
    EvalQuestion(
        question="사고 유형별 평균 심각도 분석",
        ground_truth_cypher=(
            "MATCH (i:Incident) "
            "RETURN i.incidentType, count(i) AS cnt, "
            "collect(DISTINCT i.severity) AS severities "
            "ORDER BY cnt DESC"
        ),
        expected_labels=["Incident"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="사고 유형별 심각도 분포 집계",
    ),
    EvalQuestion(
        question="워크플로우 실행 상태별 건수 통계",
        ground_truth_cypher=(
            "MATCH (we:WorkflowExecution) "
            "RETURN we.status, count(we) AS cnt "
            "ORDER BY cnt DESC"
        ),
        expected_labels=["WorkflowExecution"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="워크플로우 실행 상태별 집계",
    ),
    EvalQuestion(
        question="AI 모델별 사용 노드 수 통계",
        ground_truth_cypher=(
            "MATCH (wn:WorkflowNode)-[:USES_MODEL]->(m:AIModel) "
            "RETURN m.name, count(wn) AS nodes "
            "ORDER BY nodes DESC"
        ),
        expected_labels=["WorkflowNode", "AIModel"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="AI 모델별 사용 노드 수 집계",
    ),
    EvalQuestion(
        question="해역별 선박 밀집도 Top 5",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:LOCATED_AT]->(s:SeaArea) "
            "RETURN s.name, count(v) AS vessels "
            "ORDER BY vessels DESC LIMIT 5"
        ),
        expected_labels=["Vessel", "SeaArea"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="해역별 선박 밀집도 Top 5",
    ),
    EvalQuestion(
        question="항만별 정박 선박의 총톤수 합계",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port) "
            "RETURN p.name, sum(v.grossTonnage) AS totalGT, count(v) AS cnt "
            "ORDER BY totalGT DESC"
        ),
        expected_labels=["Vessel", "Port"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="항만별 정박 선박 총톤수 집계",
    ),
    EvalQuestion(
        question="선종별 평균 선령 통계",
        ground_truth_cypher=(
            "MATCH (v:Vessel) "
            "RETURN v.vesselType, avg(2026 - v.yearBuilt) AS avgAge, "
            "count(v) AS cnt ORDER BY avgAge DESC"
        ),
        expected_labels=["Vessel"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="선종별 평균 선령 집계",
    ),
    EvalQuestion(
        question="보안 등급별 실험 데이터셋 수",
        ground_truth_cypher=(
            "MATCH (ed:ExperimentalDataset)-[:CLASSIFIED_AS]->(dc:DataClass) "
            "RETURN dc.name, count(ed) AS datasets "
            "ORDER BY datasets DESC"
        ),
        expected_labels=["ExperimentalDataset", "DataClass"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="보안등급별 데이터셋 수 집계",
    ),
    EvalQuestion(
        question="항해 출발항별 항해 건수 Top 5",
        ground_truth_cypher=(
            "MATCH (voy:Voyage)-[:FROM_PORT]->(p:Port) "
            "RETURN p.name, count(voy) AS voyages "
            "ORDER BY voyages DESC LIMIT 5"
        ),
        expected_labels=["Voyage", "Port"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="출발항별 항해 건수 Top 5",
    ),
    EvalQuestion(
        question="화물 유형별 적재 선박 수 통계",
        ground_truth_cypher=(
            "MATCH (v:Vessel)-[:CARRIES]->(c:Cargo) "
            "RETURN c.cargoType, count(DISTINCT v) AS vessels "
            "ORDER BY vessels DESC"
        ),
        expected_labels=["Vessel", "Cargo"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="화물 유형별 선박 수 집계",
    ),
    EvalQuestion(
        question="연도별 선박 건조 추이",
        ground_truth_cypher=(
            "MATCH (v:Vessel) "
            "RETURN v.yearBuilt AS year, count(v) AS cnt "
            "ORDER BY year"
        ),
        expected_labels=["Vessel"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="연도별 선박 건조 수 시계열",
    ),
    EvalQuestion(
        question="사용자별 소속 기관과 역할 수",
        ground_truth_cypher=(
            "MATCH (u:User)-[:BELONGS_TO]->(o:Organization) "
            "MATCH (u)-[:HAS_ROLE]->(r:Role) "
            "RETURN u.name, o.name, count(r) AS roles "
            "ORDER BY roles DESC"
        ),
        expected_labels=["User", "Organization", "Role"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="사용자별 기관+역할 수 집계",
    ),
    EvalQuestion(
        question="측정 유형별 평균 값과 건수",
        ground_truth_cypher=(
            "MATCH (m:Measurement) "
            "RETURN labels(m) AS mType, count(m) AS cnt, "
            "avg(m.value) AS avgVal ORDER BY cnt DESC"
        ),
        expected_labels=["Measurement"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="측정 유형별 평균값 집계",
    ),
    EvalQuestion(
        question="MCP 리소스를 가장 많이 노출하는 서비스 Top 3",
        ground_truth_cypher=(
            "MATCH (s:Service)-[:EXPOSES_RESOURCE]->(r:MCPResource) "
            "RETURN s.name, count(r) AS resources "
            "ORDER BY resources DESC LIMIT 3"
        ),
        expected_labels=["Service", "MCPResource"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="서비스별 MCP 리소스 수 Top 3",
    ),
    EvalQuestion(
        question="데이터 파생 체인의 깊이별 소스 수",
        ground_truth_cypher=(
            "MATCH path=(ds1:DataSource)-[:DERIVED_FROM*1..3]->(ds2:DataSource) "
            "RETURN length(path) AS depth, count(DISTINCT ds1) AS sources "
            "ORDER BY depth"
        ),
        expected_labels=["DataSource"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="파생 체인 깊이별 소스 수 집계",
    ),
    EvalQuestion(
        question="시설 유형별 실험 수행 건수와 평균 기간",
        ground_truth_cypher=(
            "MATCH (e:Experiment)-[:CONDUCTED_AT]->(f:TestFacility) "
            "RETURN f.facilityType, count(e) AS experiments, "
            "avg(e.duration) AS avgDuration "
            "ORDER BY experiments DESC"
        ),
        expected_labels=["Experiment", "TestFacility"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="시설 유형별 실험 수+평균 기간 집계",
    ),
    # -- 보충 MEDIUM 1개 --
    EvalQuestion(
        question="서비스가 필요로 하는 입력 데이터소스",
        ground_truth_cypher=(
            "MATCH (s:Service)-[:REQUIRES_INPUT]->"
            "(ds:DataSource) RETURN s.name, ds"
        ),
        expected_labels=["Service", "DataSource"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.MEDIUM,
        description="서비스-입력 데이터소스 관계 (REQUIRES_INPUT)",
    ),
    # -- 보충 HARD 3개 --
    EvalQuestion(
        question="파이프라인이 적재하는 소스를 사용하는 서비스의 문서 생성 현황",
        ground_truth_cypher=(
            "MATCH (dp:DataPipeline)-[:PIPELINE_FEEDS]->(ds:DataSource) "
            "MATCH (svc:Service)-[:USES_DATA]->(ds) "
            "MATCH (svc)-[:GENERATES]->(d:Document) "
            "RETURN dp.name, ds, svc.name, d.title"
        ),
        expected_labels=["DataPipeline", "DataSource", "Service", "Document"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (파이프라인->소스->서비스->문서)",
    ),
    EvalQuestion(
        question="서비스가 출력하는 데이터소스에서 파생된 소스를 읽는 노드",
        ground_truth_cypher=(
            "MATCH (svc:Service)-[:PRODUCES_OUTPUT]->(ds1:DataSource) "
            "MATCH (ds2:DataSource)-[:DERIVED_FROM]->(ds1) "
            "MATCH (wn:WorkflowNode)-[:READS_FROM]->(ds2) "
            "RETURN svc.name, ds1, ds2, wn.name"
        ),
        expected_labels=["Service", "DataSource", "WorkflowNode"],
        reasoning_type=ReasoningType.BRIDGE,
        difficulty=Difficulty.HARD,
        description="4-hop (서비스->출력소스->파생소스->노드)",
    ),
    EvalQuestion(
        question="해역별 위성영상 수와 AIS 데이터 수 현황",
        ground_truth_cypher=(
            "MATCH (si:SatelliteImage)-[:CAPTURED_OVER]->(s:SeaArea) "
            "WITH s, count(si) AS satCnt "
            "MATCH (a:AISData)-[:OBSERVED_IN_AREA]->(s) "
            "RETURN s.name, satCnt, count(a) AS aisCnt "
            "ORDER BY satCnt + count(a) DESC"
        ),
        expected_labels=["SatelliteImage", "SeaArea", "AISData"],
        reasoning_type=ReasoningType.COMPOSITION,
        difficulty=Difficulty.HARD,
        description="해역별 위성+AIS 복합 집계",
    ),
]
