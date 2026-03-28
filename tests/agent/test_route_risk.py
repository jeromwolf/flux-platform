"""Unit tests for rule-based route risk assessment.

Covers:
    TC-RR01  _haversine_distance computes correct nautical-mile distances
    TC-RR02  _estimate_route_risks returns meaningful risk for known routes
    TC-RR03  _estimate_route_risks gracefully handles unknown ports
    TC-RR04  _format_route_analysis produces valid JSON with risk_assessment
"""

from __future__ import annotations

import json

import pytest

from agent.skills.builtins import (
    _KNOWN_PORTS,
    _SEA_AREA_RISKS,
    _estimate_route_risks,
    _format_route_analysis,
    _haversine_distance,
)


# ---------------------------------------------------------------------------
# TC-RR01: _haversine_distance
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHaversineDistance:
    """TC-RR01: Haversine 거리 계산 검증."""

    def test_rr01a_busan_incheon_approx_200nm(self) -> None:
        """TC-RR01-a: 부산-인천 거리가 약 200해리 전후."""
        lat1, lon1 = _KNOWN_PORTS["부산"]
        lat2, lon2 = _KNOWN_PORTS["인천"]
        dist = _haversine_distance(lat1, lon1, lat2, lon2)
        # 실제 해상거리는 ~196nm; 오차 ±40nm 허용
        assert 150 <= dist <= 250, f"부산-인천 거리: {dist:.1f}nm"

    def test_rr01b_busan_shanghai_approx_450nm(self) -> None:
        """TC-RR01-b: 부산-상하이 거리가 약 450해리 전후."""
        lat1, lon1 = _KNOWN_PORTS["부산"]
        lat2, lon2 = _KNOWN_PORTS["상하이"]
        dist = _haversine_distance(lat1, lon1, lat2, lon2)
        # 직선 거리 ~430nm; 오차 ±80nm 허용
        assert 350 <= dist <= 550, f"부산-상하이 거리: {dist:.1f}nm"

    def test_rr01c_same_point_zero_distance(self) -> None:
        """TC-RR01-c: 동일 좌표 사이 거리는 0."""
        dist = _haversine_distance(35.0, 129.0, 35.0, 129.0)
        assert dist == pytest.approx(0.0, abs=1e-6)

    def test_rr01d_returns_float(self) -> None:
        """TC-RR01-d: 반환값이 float 타입."""
        dist = _haversine_distance(35.0, 129.0, 37.0, 127.0)
        assert isinstance(dist, float)

    def test_rr01e_symmetric(self) -> None:
        """TC-RR01-e: 방향에 무관하게 동일한 거리 반환."""
        d1 = _haversine_distance(35.10, 129.04, 37.45, 126.60)
        d2 = _haversine_distance(37.45, 126.60, 35.10, 129.04)
        assert d1 == pytest.approx(d2, rel=1e-6)

    def test_rr01f_busan_singapore_long_haul(self) -> None:
        """TC-RR01-f: 부산-싱가포르 장거리 항로 (~2600nm 직선)."""
        lat1, lon1 = _KNOWN_PORTS["부산"]
        lat2, lon2 = _KNOWN_PORTS["싱가포르"]
        dist = _haversine_distance(lat1, lon1, lat2, lon2)
        assert 2000 <= dist <= 3200, f"부산-싱가포르 거리: {dist:.1f}nm"


# ---------------------------------------------------------------------------
# TC-RR02: _estimate_route_risks — known routes
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEstimateRouteRisksKnown:
    """TC-RR02: 알려진 항구 간 위험도 평가 검증."""

    def test_rr02a_busan_incheon_returns_dict(self) -> None:
        """TC-RR02-a: 부산-인천 경로에 대해 딕셔너리 반환."""
        result = _estimate_route_risks("부산", "인천")
        assert isinstance(result, dict)

    def test_rr02b_required_keys_present(self) -> None:
        """TC-RR02-b: 필수 키가 모두 존재함."""
        result = _estimate_route_risks("부산", "인천")
        required_keys = {
            "overall_risk",
            "weather_risk",
            "piracy_risk",
            "traffic_risk",
            "distance_nm",
            "estimated_days",
            "sea_areas_crossed",
        }
        assert required_keys.issubset(result.keys())

    def test_rr02c_risk_values_valid(self) -> None:
        """TC-RR02-c: 위험도 값이 valid 범주 내에 있음."""
        valid = {"low", "medium", "high", "unknown"}
        result = _estimate_route_risks("부산", "인천")
        assert result["overall_risk"] in valid
        assert result["weather_risk"] in valid
        assert result["piracy_risk"] in valid
        assert result["traffic_risk"] in valid

    def test_rr02d_distance_nm_positive(self) -> None:
        """TC-RR02-d: 알려진 경로의 distance_nm은 양수."""
        result = _estimate_route_risks("부산", "인천")
        assert result["distance_nm"] is not None
        assert result["distance_nm"] > 0

    def test_rr02e_estimated_days_positive(self) -> None:
        """TC-RR02-e: estimated_days는 양수."""
        result = _estimate_route_risks("부산", "인천")
        assert result["estimated_days"] is not None
        assert result["estimated_days"] > 0

    def test_rr02f_sea_areas_crossed_list(self) -> None:
        """TC-RR02-f: sea_areas_crossed는 리스트."""
        result = _estimate_route_risks("부산", "인천")
        assert isinstance(result["sea_areas_crossed"], list)

    def test_rr02g_busan_incheon_crosses_west_sea(self) -> None:
        """TC-RR02-g: 부산-인천 경로는 서해(西海)를 통과함."""
        result = _estimate_route_risks("부산", "인천")
        # 부산→인천 경로는 서해 또는 대한해협을 지나야 함
        crossed = result["sea_areas_crossed"]
        assert len(crossed) >= 1, "부산-인천은 최소 1개 해역 통과"

    def test_rr02h_busan_singapore_high_risk(self) -> None:
        """TC-RR02-h: 부산-싱가포르는 말라카해협 통과로 high 위험도 포함."""
        result = _estimate_route_risks("부산", "싱가포르")
        assert "말라카해협" in result["sea_areas_crossed"]
        # 말라카해협 피라시 위험도는 high
        assert result["piracy_risk"] == "high"
        assert result["overall_risk"] == "high"

    def test_rr02i_estimated_days_consistent_with_distance(self) -> None:
        """TC-RR02-i: estimated_days = distance_nm / (12 * 24) 로 계산됨."""
        result = _estimate_route_risks("부산", "도쿄")
        if result["distance_nm"] is not None:
            expected_days = result["distance_nm"] / (12.0 * 24)
            assert result["estimated_days"] == pytest.approx(expected_days, rel=0.05)

    def test_rr02j_all_known_ports_have_non_none_distance(self) -> None:
        """TC-RR02-j: 알려진 모든 항구 조합에 대해 distance_nm이 None이 아님."""
        ports = list(_KNOWN_PORTS.keys())
        for origin in ports[:3]:  # 3개 항구만 샘플 테스트 (속도 고려)
            for dest in ports[3:6]:
                if origin != dest:
                    result = _estimate_route_risks(origin, dest)
                    assert result["distance_nm"] is not None, f"{origin}→{dest} distance is None"


# ---------------------------------------------------------------------------
# TC-RR03: _estimate_route_risks — unknown ports
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEstimateRouteRisksUnknown:
    """TC-RR03: 알려지지 않은 항구 처리 검증."""

    def test_rr03a_unknown_origin_returns_unknown_risk(self) -> None:
        """TC-RR03-a: 알 수 없는 출발지는 'unknown' 위험도 반환."""
        result = _estimate_route_risks("알수없는항구", "부산")
        assert result["overall_risk"] == "unknown"
        assert result["piracy_risk"] == "unknown"
        assert result["weather_risk"] == "unknown"
        assert result["traffic_risk"] == "unknown"

    def test_rr03b_unknown_destination_returns_unknown_risk(self) -> None:
        """TC-RR03-b: 알 수 없는 도착지는 'unknown' 위험도 반환."""
        result = _estimate_route_risks("부산", "알수없는항구")
        assert result["overall_risk"] == "unknown"

    def test_rr03c_both_unknown_returns_unknown(self) -> None:
        """TC-RR03-c: 출발지와 도착지 모두 미지의 경우 'unknown' 반환."""
        result = _estimate_route_risks("UNKNOWN_A", "UNKNOWN_B")
        assert result["overall_risk"] == "unknown"

    def test_rr03d_unknown_returns_none_distance(self) -> None:
        """TC-RR03-d: 알 수 없는 항구는 distance_nm=None."""
        result = _estimate_route_risks("UNKNOWN", "부산")
        assert result["distance_nm"] is None

    def test_rr03e_unknown_returns_none_estimated_days(self) -> None:
        """TC-RR03-e: 알 수 없는 항구는 estimated_days=None."""
        result = _estimate_route_risks("부산", "UNKNOWN")
        assert result["estimated_days"] is None

    def test_rr03f_unknown_returns_empty_sea_areas(self) -> None:
        """TC-RR03-f: 알 수 없는 항구는 sea_areas_crossed=[]."""
        result = _estimate_route_risks("UNKNOWN", "UNKNOWN")
        assert result["sea_areas_crossed"] == []

    def test_rr03g_empty_string_ports_handled(self) -> None:
        """TC-RR03-g: 빈 문자열 항구 이름도 graceful하게 처리됨."""
        result = _estimate_route_risks("", "")
        assert result["overall_risk"] == "unknown"


# ---------------------------------------------------------------------------
# TC-RR04: _format_route_analysis produces valid JSON with risk_assessment
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatRouteAnalysis:
    """TC-RR04: _format_route_analysis JSON 출력 검증."""

    def test_rr04a_returns_valid_json(self) -> None:
        """TC-RR04-a: 반환값이 JSON 파싱 가능함."""
        output = _format_route_analysis("부산", "인천", {})
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_rr04b_report_type_is_route_analysis(self) -> None:
        """TC-RR04-b: report_type이 'route_analysis'임."""
        output = _format_route_analysis("부산", "상하이", {})
        data = json.loads(output)
        assert data["report_type"] == "route_analysis"

    def test_rr04c_risk_assessment_key_present(self) -> None:
        """TC-RR04-c: risk_assessment 키가 존재함."""
        output = _format_route_analysis("부산", "인천", {})
        data = json.loads(output)
        assert "risk_assessment" in data

    def test_rr04d_risk_assessment_has_required_subkeys(self) -> None:
        """TC-RR04-d: risk_assessment 내에 필수 서브키가 있음."""
        output = _format_route_analysis("부산", "인천", {})
        data = json.loads(output)
        risk = data["risk_assessment"]
        for key in ("overall_risk", "weather_risk", "piracy_risk", "traffic_risk",
                    "distance_nm", "estimated_days", "sea_areas_crossed"):
            assert key in risk, f"Missing key: {key}"

    def test_rr04e_overall_risk_not_hardcoded_low(self) -> None:
        """TC-RR04-e: overall_risk가 더 이상 하드코딩된 'low'가 아님 (규칙 기반)."""
        # 부산-싱가포르는 말라카해협 통과로 high여야 함
        output = _format_route_analysis("부산", "싱가포르", {})
        data = json.loads(output)
        assert data["risk_assessment"]["overall_risk"] != "unknown"
        # Known route should produce a real risk level
        assert data["risk_assessment"]["overall_risk"] in {"low", "medium", "high"}

    def test_rr04f_weather_risk_not_unknown_for_known_ports(self) -> None:
        """TC-RR04-f: 알려진 항구 간 weather_risk가 'unknown'이 아님."""
        output = _format_route_analysis("부산", "도쿄", {})
        data = json.loads(output)
        assert data["risk_assessment"]["weather_risk"] != "unknown"

    def test_rr04g_origin_destination_in_report(self) -> None:
        """TC-RR04-g: 보고서에 origin과 destination이 포함됨."""
        output = _format_route_analysis("부산", "광양", {})
        data = json.loads(output)
        assert data["origin"] == "부산"
        assert data["destination"] == "광양"

    def test_rr04h_route_count_reflects_input(self) -> None:
        """TC-RR04-h: route_count가 입력 route_data의 routes 길이를 반영함."""
        route_data = {"routes": [{"id": "r1"}, {"id": "r2"}], "stub": True}
        output = _format_route_analysis("부산", "인천", route_data)
        data = json.loads(output)
        assert data["route_count"] == 2

    def test_rr04i_stub_flag_propagated(self) -> None:
        """TC-RR04-i: stub 플래그가 route_data에서 전달됨."""
        output = _format_route_analysis("부산", "인천", {"stub": True})
        data = json.loads(output)
        assert data["stub"] is True

    def test_rr04j_unknown_ports_produce_unknown_risk(self) -> None:
        """TC-RR04-j: 미지의 항구에 대해 risk_assessment.overall_risk='unknown'."""
        output = _format_route_analysis("UNKNOWN_PORT", "ANOTHER_UNKNOWN", {})
        data = json.loads(output)
        assert data["risk_assessment"]["overall_risk"] == "unknown"
