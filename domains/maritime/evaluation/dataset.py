"""Evaluation dataset models and built-in maritime evaluation questions.

Defines the data structures for evaluation questions with reasoning type
classification and difficulty levels. Includes a built-in dataset of 30
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
        """Create the built-in maritime evaluation dataset (30 questions).

        Returns:
            EvalDataset with 10 easy, 10 medium, and 10 hard questions
            covering DIRECT, BRIDGE, COMPARISON, INTERSECTION, and
            COMPOSITION reasoning types.
        """
        return cls(questions=_BUILTIN_QUESTIONS[:])


# =========================================================================
# Built-in evaluation dataset (30 questions)
# =========================================================================

_BUILTIN_QUESTIONS: list[EvalQuestion] = [
    # -----------------------------------------------------------------
    # Easy (10 questions, 1-hop, DIRECT)
    # -----------------------------------------------------------------
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

    # -----------------------------------------------------------------
    # Medium (10 questions, 2-hop, BRIDGE)
    # -----------------------------------------------------------------
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

    # -----------------------------------------------------------------
    # Hard (10 questions, multi-hop / comparison / intersection)
    # -----------------------------------------------------------------
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
]
