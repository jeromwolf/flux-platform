# 멀티모달 해사데이터 인벤토리 (Draft)

## REQ-001 산출물 ③

> **Draft v0.2 — 2026-05-20**
> AIS 표준 분석 템플릿(산출물 ④)의 9컬럼 양식으로 멀티모달 해사데이터 10종을 정리한다.
> 근거: 정성제안서 표 II-6 (오재용·김혜진 2024 선행연구), 데이터 제공처별 현황 조사서 v0.2, AIS 표준 분석 템플릿(④)

---

## 1. 개요

### 1.1 목적
멀티모달 해사데이터를 9컬럼 표준 양식으로 정리하여, 향후 온톨로지 설계(DES-001)와 지식그래프 스키마 설계의 기준 산출물로 삼는다.

### 1.2 대상 — 10종
정성제안서 표 II-5 ③·과업지시서가 명시한 인벤토리 대상 10종이다.
- **선행연구 8종** (정성제안서 표 II-6, 오재용·김혜진 2024): AIS · GPS · 항해장비※ · RADAR · VHF · Port-MIS · CCTV · 환경정보
- **그 외 2종** (표 II-5·과업지시서 명시): 전자해도(ENC) · 법령

> ※ "항해장비"는 표 II-6(오재용·김혜진 논문)의 표기다. 과업지시서·정성제안서 표 II-5는 동일 항목을 "항해술"로 표기 — 원문 간 표기가 불일치하므로 데이터 범위를 KRISO에 확인할 예정이다.

### 1.3 9컬럼 양식
A 데이터 자체(데이터구분·형식·세부항목) · B 연결 정보(연계항목·식별자·시공간) · C 그래프 설계(후보노드·후보관계·활용시나리오) — 표 1·2로 분할 제시.

---

## 2. 인벤토리 표 1 — 데이터 기술 (그룹 A·B)

| 데이터 | 형식 | 세부 항목 | 연계 항목 | 주요 식별자 | 시공간 |
|--------|------|----------|----------|-----------|--------|
| **AIS** | NMEA0183·CSV·OpenAPI | 선박 식별·정적·위치·침로·속력·ETA·흘수 | GPS·RADAR·VHF·Port-MIS·CCTV·환경정보 | MMSI·IMO·호출부호 | O |
| **GPS** | 텍스트(NMEA0183) | 시각·위경도·위성정보·침로·속력 | AIS·항해장비 | 선박ID·수신시각 | O |
| **항해장비** | CSV 텍스트 | 자이로컴퍼스·음향측심기·엔진RPM·오토파일럿·ECDIS | GPS·AIS | 장비ID·선박ID | O (시각) |
| **RADAR** | 텍스트 + 이미지 | 표적 추적 정보 (위치·속도·방위) | AIS·환경정보 | 표적ID | O |
| **VHF** | 음성(wav) + 텍스트(STT) | VHF 음성파일·시각·채널·사이트·STT 변환 텍스트 | AIS·Port-MIS | MMSI·호출부호·채널 | O (시각) |
| **Port-MIS** | 텍스트(CSV)·OpenAPI | 항만시설정보·입출항보고·항만시설 이용보고 | AIS·VHF·CCTV | 호출부호·항만코드 | O |
| **CCTV** | 이미지·영상 | 표적정보(MMSI·침로·속력) | AIS·Port-MIS | 표적MMSI·카메라ID | O |
| **환경정보** | 텍스트(CSV)·API | 조류·조위·바람·파고·기상상태·시정거리 | Port-MIS·CCTV·AIS | 관측소코드(ObsCode)·위경도 | O |
| **전자해도(ENC)** | S-57·S-63·SHP | 해안선·수심·항로표지·위험물·항로·수역경계 | 수심·해역 | ENC 셀번호·S-57 피처ID | O (공간) |
| **법령** | 텍스트(PDF·HWP) | 법령 조항·규정·지침 (비정형) | 해역·사고·선박 | 규정ID·법령명 | △ (적용 해역) |

---

## 3. 인벤토리 표 2 — 지식그래프 설계 (그룹 C)

| 데이터 | KG 후보 노드 | KG 후보 관계 | 활용 시나리오 |
|--------|-------------|-------------|--------------|
| **AIS** | Vessel·Voyage·Position·Event | ON_VOYAGE·HAS_POSITION·LOCATED_IN·COMMUNICATE_WITH | 특정 선박·시점·해역 탐색의 기준축 |
| **GPS** | Position·Vessel | HAS_POSITION | 위치 정밀도 교차 검증 |
| **항해장비** | Equipment·SensorReading·Vessel | EQUIPPED_ON·MEASURED_BY | 선박 운항 상태·기관 모니터링 |
| **RADAR** | RadarTarget·Position | DETECTED·MATCHED_WITH(→Vessel) | 표적-선박 매칭, 미식별 표적 탐지 |
| **VHF** | VHFMessage·Vessel·VTSCenter | TRANSMITTED_BY·COMMUNICATE_WITH·PROVIDED_BY | 교신 이력 ↔ 위치 연계, 충돌위험 교신 분석 |
| **Port-MIS** | PortCall·Port·Berth·Vessel | ARRIVES_AT·DEPARTS_FROM·BERTH_TO | 입출항 이력, 항만 이용 분석 |
| **CCTV** | CCTVDetection·Vessel·Camera | LOCATED_IN·DETECTED·BERTH_TO | 영상 표적 검증, 접·이안 모니터링 |
| **환경정보** | WeatherObservation·Area·ObservationStation | OBSERVED·AFFECTS(→Voyage) | 기상-항행 영향, 사고 원인 분석 |
| **전자해도(ENC)** | NavigationArea·Route·NavAid·Depth | CONTAINS·NEAR·OVERLAPS | 항로 안전, S-100 표준 매핑(REQ-004) |
| **법령** | Regulation·LegalReference | APPLIES_TO·REGULATED_BY | 사고 시 적용 법령 탐색 |

> **KG 후보 노드·관계명은 잠정(provisional)이다.** 정성제안서 표 II-7(오재용·김혜진 2024)·표 II-8에 근거한 관계(TRANSMITTED_BY·BERTH_TO·ARRIVES_AT·DEPARTS_FROM·COMMUNICATE_WITH·PROVIDED_BY·LOCATED_IN 등)와, 본 분석에서 도출한 제안 관계(HAS_POSITION·ON_VOYAGE·OBSERVED·AFFECTS·EQUIPPED_ON·MEASURED_BY·DETECTED 등)를 함께 제시한다. 영문 명칭·방향의 최종 확정은 DES-001 온톨로지 설계 단계에서 수행하며, 산출물 ④·⑤와 동일 명칭 체계를 사용한다.

---

## 4. 종합 — 지식그래프 후보 노드·관계 집계

### 4.1 후보 노드군 (중복 제거)
- **선박 중심**: Vessel · Voyage · Position · Event
- **항만 중심**: Port · Berth · PortCall
- **관측·장비**: SensorReading · Equipment · RadarTarget · CCTVDetection · WeatherObservation · ObservationStation · Camera
- **공간**: Area · Route · NavigationArea · NavAid · Depth
- **통신·문서**: VHFMessage · VTSCenter · Regulation · LegalReference

### 4.2 후보 관계군
- **항행**: ON_VOYAGE · HAS_POSITION · LOCATED_IN
- **입출항**: ARRIVES_AT · DEPARTS_FROM · BERTH_TO
- **탐지·관측**: DETECTED · MATCHED_WITH · OBSERVED · MEASURED_BY
- **통신**: TRANSMITTED_BY · COMMUNICATE_WITH · PROVIDED_BY
- **공간**: CONTAINS · NEAR · OVERLAPS
- **규정·영향**: APPLIES_TO · REGULATED_BY · AFFECTS · EQUIPPED_ON

### 4.3 핵심 발견
- **Vessel·Position·Voyage**가 AIS·GPS·RADAR·CCTV·Port-MIS에 공통 등장 → 지식그래프의 허브 노드
- **MMSI·호출부호·IMO**가 선박 관련 데이터 6종을 연결 → 식별자 체계(산출물 ⑤)의 핵심
- 환경정보·전자해도는 위경도·해역으로 공간 연계 → Area 노드 중심
- 법령은 비정형이라 NER/RE 필요 (DES-003 ETL) — 후속 검토 자원

---

## 5. 다음 단계
1. 본 인벤토리의 식별자(MMSI·호출부호·IMO·ObsCode 등) → 산출물 ⑤ 연계 규칙·식별자 체계 정의서로 정리
2. 후보 노드·관계군 → DES-001 온톨로지 엔티티·관계 설계의 입력
3. 데이터별 활용도·연계밀도 평가 → 산출물 ⑥ 우선순위 선정표

---

> REQ-001 산출물 ③ draft · AIS 표준 분석 템플릿(④) 양식 적용 · M+2 「해사 데이터 현황 분석 보고서」에 취합.
