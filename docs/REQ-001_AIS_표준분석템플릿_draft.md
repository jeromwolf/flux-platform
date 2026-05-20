# AIS 데이터 중심 표준 분석 템플릿 (Draft)

## REQ-001 산출물 ④

> **Draft v0.2 — 2026-05-20**
> AIS를 대표 사례로 분석하고, 타 멀티모달 데이터셋 분석의 **표준 양식**을 제시한다.
> 근거: 정성제안서 II.2 마), 데이터 제공처별 현황 조사서 v0.2

---

## 1. 개요

### 1.1 AIS란
AIS(Automatic Identification System, 선박자동식별시스템)는 선박이 자신의 식별·위치·항행 정보를 VHF 대역으로 주기 송신하는 국제 표준 시스템이다(AIS 메시지 표준 ITU-R M.1371). 해사서비스 플랫폼에서 **가장 대표적이며 선박 중심 지식그래프의 핵심 연결축**이 되는 데이터다.

### 1.2 본 템플릿의 목적
1. **AIS 데이터 자체의 표준 분석** — 세부 항목·연계 대상·식별자·KG 매핑을 정리
2. **타 데이터셋 분석의 기준 양식** — GPS·RADAR·VHF·Port-MIS·CCTV·환경정보 등을 동일한 틀로 확장 분석

→ AIS 분석은 단순 예시가 아니라, **모든 멀티모달 데이터에 동일 적용 가능한 분석 기준 사례**다.

---

## 2. AIS 데이터 세부 분석 — 5개 범주

| 범주 | 항목 | 설명 |
|------|------|------|
| 선박 식별정보 | MMSI · IMO 번호 · 호출부호(Call Sign) · 선박명 | 선박을 유일하게 식별하는 키 |
| 선박 정적정보 | 선종 · 선박 크기(길이·폭) · 국적 · 장비 정보 | 변하지 않는 선박 속성 |
| 위치정보 | 위도 · 경도 · 수신 시각 | 시공간 좌표 |
| 항행정보 | 침로(COG) · 속력(SOG) · 선수방향(HEADING) · 회전율(ROT) · 항행상태 | 실시간 운항 상태 |
| 운항정보 | 목적지 · ETA(예상도착시간) · 흘수(Draught) | 항차 계획 정보 |

---

## 3. AIS 데이터 소스·형식

데이터 현황 조사서 v0.2에서 확인된 공개 AIS 데이터셋(해양수산부 GICOMS 계열).

| 데이터셋 | 형식 | 갱신 | 식별자 | 비고 |
|----------|------|------|--------|------|
| 선박 AIS 동적정보 | CSV · OpenAPI | 샘플(2018~2023) | MMSI(공개 시 비식별) | 위경도·SOG·COG·HEADING |
| 선박 AIS 정적정보 | CSV · OpenAPI | 스냅샷 | 국적별 집계 | — |
| 선박위치정보(연안AIS) 통계 | WMS/WFS API | 1시간 | 해구번호 | 해역별 선박 척수 |
| 지능형해양수산재난체계 AIS | CSV · OpenAPI | 수시 | **IMO번호 포함** | 식별 가능 |
| SSAS(선박보안경보장치) | CSV · OpenAPI | 수시 | — | 위치·시각·헤딩 |

> ※ 원천 형식은 NMEA0183 바이너리 텍스트. 공개 파일은 CSV로 변환 제공. 실시간 전체 AIS 스트림은 GICOMS API 별도 신청.

---

## 4. AIS 주요 연계 대상

AIS는 다른 해사데이터와 연계성이 매우 높다. 연계 키와 활용 방식은 다음과 같다.

| 연계 데이터 | 연계 키 | 연계 방식 · 활용 |
|------------|---------|------------------|
| GPS | 시각 · 위치 | 위치·속도 정보 교차 검증 |
| RADAR | 표적 정보 · 시공간 | 표적 추적 정보와 선박 식별 결합 |
| VHF | MMSI · 위치 | 선박 위치 ↔ 채널/교신 정보 연계 |
| Port-MIS | 호출부호 | 입·출항 정보, 항만시설 이용 연계 |
| CCTV | 표적 MMSI · 위치 | 영상 내 표적 식별·운항 상황 검증 |
| 환경정보 | 위치 · 시각 | 조류·파고·풍향풍속·시정과 상황 연계 |

---

## 5. AIS 지식그래프 매핑

### 5.1 후보 노드

| 노드 | 핵심 속성 | AIS 항목 출처 |
|------|----------|--------------|
| Vessel (선박) | mmsi · imoNumber · callSign · vesselName · vesselType · flag | 선박 식별·정적정보 |
| Voyage (항차) | departure · destination · eta | 운항정보 |
| Position (위치) | latitude · longitude · timestamp · sog · cog · heading | 위치·항행정보 |
| Event (이벤트) | eventType(입항·출항·교신) · time | 이벤트성 정보 |
| Port · Route · Area | name · 좌표·범위 | AIS 운항정보(목적지) 참조 — Port-MIS·ENC 연계 시 구체화 |

### 5.2 후보 관계

| 관계 | 의미 | 근거 |
|------|------|------|
| (Vessel)-[:ON_VOYAGE]->(Voyage) | 선박의 항차 | AIS 운항정보 |
| (Voyage)-[:HAS_POSITION]->(Position) | 항차의 위치 기록 | AIS 동적정보 |
| (Vessel)-[:LOCATED_IN]->(Area) | 선박이 위치한 해역 | 위치 + 해역 |
| (Voyage)-[:DEPARTS_FROM / ARRIVES_AT]->(Port) | 출발·도착 항만 | 운항정보 + Port-MIS |
| (Vessel)-[:COMMUNICATE_WITH]->(Vessel) | 선박 간 교신 | VHF 연계 |
| (Vessel)-[:TRANSMITTED_BY]->(VHFMessage) | 교신 발신 | 정성제안서 표 II-7 (오재용·김혜진 2024) |

> **후보 노드·관계명은 잠정(provisional)이다.** 정성제안서 표 II-7(오재용·김혜진 2024)이 정의한 해사 특화 관계(TRANSMITTED_BY·PORT_ENTRY·PORT_DEPARTURE·ANCHOR_AT·BERTH_TO·UNBERTH_FROM·COMMUNICATE_WITH·PROVIDED_BY·LOCATED_IN)와 본 분석에서 도출한 제안 관계(ON_VOYAGE·HAS_POSITION)를 구분하며, 영문 명칭·방향의 최종 확정은 DES-001 온톨로지 설계 단계에서 수행한다. §5.1 노드 표의 Vessel·Voyage·Position·Event는 AIS에서 직접 도출되는 핵심 노드이고, Port·Route·Area는 타 데이터 연계 시 구체화되는 공간 노드다 — 인벤토리 ③의 AIS 행은 직접 도출 노드 4종만 싣는다. 또한 TRANSMITTED_BY·COMMUNICATE_WITH는 AIS 단독이 아닌 VHF 교신 데이터와 연계될 때 생성되는 관계다.

---

## 6. AIS 9컬럼 인벤토리 행

REQ-001 멀티모달 데이터 인벤토리(산출물 ③)의 9컬럼 표준 양식에 AIS를 채운 기준 행.

| 컬럼 | AIS 값 |
|------|--------|
| 데이터 구분 | AIS (선박자동식별시스템) |
| 형식 | 바이너리 텍스트(NMEA0183), CSV·OpenAPI(공개 파일) |
| 세부 항목 | 선박 식별·정적정보, 위치, 항행정보(침로·속력·선수방향·회전율·항행상태), 운항정보(목적지·ETA·흘수) |
| 연계 항목 | GPS · RADAR · VHF · Port-MIS · CCTV · 환경정보 |
| 주요 식별자 | MMSI · IMO 번호 · 호출부호 |
| 시공간 정보 | O — 위경도 + 수신시각 |
| KG 후보 노드 | Vessel · Voyage · Position · Event |
| KG 후보 관계 | ON_VOYAGE · HAS_POSITION · LOCATED_IN · COMMUNICATE_WITH |
| 활용 시나리오 | 특정 선박·시점·해역 탐색의 기준축, 사고 대응·경로 분석 |

> ※ "KG 후보 관계"는 §5.2의 6종 중 대표 4종이다 (DEPARTS_FROM/ARRIVES_AT·TRANSMITTED_BY 포함 전체는 §5.2 참조). 9컬럼 인벤토리 양식에는 대표 관계를 싣는다.

---

## 7. 표준 분석 절차 — 타 데이터셋 적용

AIS에 적용한 위 분석 틀을 다른 멀티모달 데이터(GPS·RADAR·VHF·Port-MIS·CCTV·환경정보·전자해도)에 동일하게 적용한다.

| 단계 | 작업 |
|------|------|
| 1 | 데이터 세부 항목을 범주별로 분류 (§2 형식) |
| 2 | 데이터 소스·형식·갱신주기 정리 (§3 형식) |
| 3 | 다른 데이터셋과의 연계 키·방식 식별 (§4 형식) |
| 4 | KG 후보 노드·관계 도출 (§5 형식) |
| 5 | 9컬럼 인벤토리 행 작성 (§6 형식) → 산출물 ③에 누적 |

→ 7종 데이터를 이 절차로 분석하면 멀티모달 데이터 인벤토리(산출물 ③)가 완성된다.

---

## 8. 다음 단계
1. 본 템플릿을 기준으로 GPS·RADAR·VHF·Port-MIS·CCTV·환경정보·전자해도 분석 → 멀티모달 데이터 인벤토리(③)
2. 식별자(MMSI·IMO·호출부호 등) 연계 규칙을 산출물 ⑤(연계 규칙·식별자 체계 정의서)로 정리
3. KRISO 선행연구(오재용·김혜진 2024) 관계 유형을 DES-001 온톨로지 관계 설계에 반영

---

> REQ-001 산출물 ④ draft · M+2 「해사 데이터 현황 분석 보고서」에 취합.
