"""Sprint 12: K8s Manifests and Keycloak Configuration Validation.

TC-K01 ~ TC-K50: infra/k8s/ 및 infra/keycloak/ 디렉토리의 파일 구조,
필수 필드, 보안 설정을 검증한다.

모든 테스트는 외부 의존성 없이 순수 Python으로 동작한다.
- YAML 파일: 원시 텍스트 기반 검증 (의존성 제로)
- Keycloak realm: json (stdlib) 파싱
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# 경로 상수
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INFRA_DIR = PROJECT_ROOT / "infra"
K8S_BASE = INFRA_DIR / "k8s" / "base"
K8S_DEV = INFRA_DIR / "k8s" / "dev"
K8S_PROD = INFRA_DIR / "k8s" / "prod"
KEYCLOAK_DIR = INFRA_DIR / "keycloak"


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    """파일을 UTF-8로 읽어 문자열로 반환한다."""
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def realm_data() -> dict[str, Any]:
    """realm-imsp.json을 파싱해서 반환한다."""
    return json.loads((KEYCLOAK_DIR / "realm-imsp.json").read_text(encoding="utf-8"))


# ===========================================================================
# TC-K01 ~ TC-K16: K8s Base Manifests
# ===========================================================================


@pytest.mark.unit
class TestK8sBaseManifests:
    """K8s base 디렉토리의 YAML 매니페스트 원시 텍스트 검증."""

    # -----------------------------------------------------------------------
    # TC-K01: namespace.yaml
    # -----------------------------------------------------------------------

    def test_namespace_yaml_exists_and_valid(self) -> None:
        """TC-K01: namespace.yaml 존재 및 Namespace kind·name 확인."""
        path = K8S_BASE / "namespace.yaml"
        assert path.exists(), f"파일이 없습니다: {path}"
        content = _read(path)
        assert "kind: Namespace" in content, "kind: Namespace 가 없습니다"
        assert "name: imsp" in content, "name: imsp 가 없습니다"

    # -----------------------------------------------------------------------
    # TC-K02 ~ TC-K03: configmap.yaml / secret.yaml
    # -----------------------------------------------------------------------

    def test_configmap_has_required_keys(self) -> None:
        """TC-K02: configmap.yaml에 필수 환경변수 키가 존재한다."""
        content = _read(K8S_BASE / "configmap.yaml")
        for key in ("NEO4J_URI", "NEO4J_DATABASE", "KEYCLOAK_REALM", "KEYCLOAK_CLIENT_ID"):
            assert key in content, f"configmap.yaml에 {key!r} 가 없습니다"

    def test_secret_has_required_keys(self) -> None:
        """TC-K03: secret.yaml에 필수 시크릿 키와 type: Opaque가 존재한다."""
        content = _read(K8S_BASE / "secret.yaml")
        for key in ("NEO4J_USER", "NEO4J_PASSWORD", "JWT_SECRET_KEY"):
            assert key in content, f"secret.yaml에 {key!r} 가 없습니다"
        assert "type: Opaque" in content, "type: Opaque 가 없습니다"

    def test_secret_uses_placeholder_values(self) -> None:
        """TC-K04: secret.yaml은 실제 비밀값 대신 CHANGE_ME 플레이스홀더를 사용한다."""
        content = _read(K8S_BASE / "secret.yaml")
        assert "CHANGE_ME" in content, (
            "secret.yaml에 CHANGE_ME 플레이스홀더가 없습니다 — 실제 비밀값이 커밋되었을 수 있습니다"
        )

    # -----------------------------------------------------------------------
    # TC-K05 ~ TC-K09: api-deployment.yaml
    # -----------------------------------------------------------------------

    def test_api_deployment_structure(self) -> None:
        """TC-K05: api-deployment.yaml의 기본 구조 및 컨테이너 포트 검증."""
        content = _read(K8S_BASE / "api-deployment.yaml")
        assert "kind: Deployment" in content, "kind: Deployment 가 없습니다"
        assert "name: imsp-api" in content, "name: imsp-api 가 없습니다"
        assert "containerPort: 8000" in content, "containerPort: 8000 이 없습니다"
        assert "runAsNonRoot: true" in content, "runAsNonRoot: true 가 없습니다"

    def test_api_deployment_has_health_probes(self) -> None:
        """TC-K06: api-deployment.yaml에 liveness·readiness 프로브가 정의된다."""
        content = _read(K8S_BASE / "api-deployment.yaml")
        assert "livenessProbe" in content, "livenessProbe 가 없습니다"
        assert "readinessProbe" in content, "readinessProbe 가 없습니다"
        assert "/api/v1/health" in content, "헬스체크 경로 /api/v1/health 가 없습니다"

    def test_api_deployment_has_resource_limits(self) -> None:
        """TC-K07: api-deployment.yaml에 리소스 요청과 제한이 모두 설정된다."""
        content = _read(K8S_BASE / "api-deployment.yaml")
        assert "memory:" in content, "memory 설정이 없습니다"
        assert "cpu:" in content, "cpu 설정이 없습니다"
        assert "limits:" in content, "limits 블록이 없습니다"
        assert "requests:" in content, "requests 블록이 없습니다"

    def test_api_deployment_security_context(self) -> None:
        """TC-K08: api-deployment.yaml에 컨테이너 보안 컨텍스트가 강화된다."""
        content = _read(K8S_BASE / "api-deployment.yaml")
        assert "runAsNonRoot: true" in content, "runAsNonRoot: true 가 없습니다"
        assert "allowPrivilegeEscalation: false" in content, (
            "allowPrivilegeEscalation: false 가 없습니다"
        )
        assert "drop:" in content, "capabilities.drop 이 없습니다"
        assert "ALL" in content, "ALL capability drop 이 없습니다"

    def test_api_service_structure(self) -> None:
        """TC-K09: api-service.yaml의 kind와 포트 설정 검증."""
        content = _read(K8S_BASE / "api-service.yaml")
        assert "kind: Service" in content, "kind: Service 가 없습니다"
        # port 또는 targetPort 중 하나에 8000이 포함돼야 한다
        assert any(
            token in content for token in ("port: 8000", "targetPort: 8000", "containerPort: 8000")
        ), "포트 8000 참조가 없습니다"

    # -----------------------------------------------------------------------
    # TC-K10 ~ TC-K14: neo4j-statefulset.yaml
    # -----------------------------------------------------------------------

    def test_neo4j_statefulset_structure(self) -> None:
        """TC-K10: neo4j-statefulset.yaml의 기본 구조 검증."""
        content = _read(K8S_BASE / "neo4j-statefulset.yaml")
        assert "kind: StatefulSet" in content, "kind: StatefulSet 가 없습니다"
        assert "name: imsp-neo4j" in content, "name: imsp-neo4j 가 없습니다"
        assert "replicas: 1" in content, "replicas: 1 이 없습니다 (Community Edition은 단일 인스턴스)"
        assert "neo4j:5" in content, "Neo4j 5.x 이미지 참조가 없습니다"

    def test_neo4j_statefulset_has_volume_claim(self) -> None:
        """TC-K11: neo4j-statefulset.yaml에 영구 볼륨 클레임이 정의된다."""
        content = _read(K8S_BASE / "neo4j-statefulset.yaml")
        assert "volumeClaimTemplates" in content, "volumeClaimTemplates 가 없습니다"
        assert "10Gi" in content, "10Gi 스토리지 요청이 없습니다"
        assert "ReadWriteOnce" in content, "ReadWriteOnce 액세스 모드가 없습니다"

    def test_neo4j_statefulset_has_plugins(self) -> None:
        """TC-K12: neo4j-statefulset.yaml에 APOC 및 n10s 플러그인이 설정된다."""
        content = _read(K8S_BASE / "neo4j-statefulset.yaml")
        assert "apoc" in content, "APOC 플러그인 설정이 없습니다"
        assert "n10s" in content, "n10s 플러그인 설정이 없습니다"

    def test_neo4j_statefulset_memory_tuning(self) -> None:
        """TC-K13: neo4j-statefulset.yaml에 힙 및 페이지캐시 메모리 튜닝이 있다."""
        content = _read(K8S_BASE / "neo4j-statefulset.yaml")
        assert "heap" in content, "heap 메모리 설정이 없습니다"
        assert "pagecache" in content, "pagecache 설정이 없습니다"

    def test_neo4j_service_ports(self) -> None:
        """TC-K14: neo4j-service.yaml에 Bolt(7687)과 Browser(7474) 포트가 있다."""
        content = _read(K8S_BASE / "neo4j-service.yaml")
        assert "7687" in content, "Bolt 포트 7687이 없습니다"
        assert "7474" in content, "Browser 포트 7474가 없습니다"

    # -----------------------------------------------------------------------
    # TC-K15 ~ TC-K16: ingress.yaml / kustomization.yaml
    # -----------------------------------------------------------------------

    def test_ingress_structure(self) -> None:
        """TC-K15: ingress.yaml의 kind와 호스트 설정 검증."""
        content = _read(K8S_BASE / "ingress.yaml")
        assert "kind: Ingress" in content, "kind: Ingress 가 없습니다"
        assert "api.imsp.local" in content, "호스트 api.imsp.local 이 없습니다"

    def test_kustomization_lists_all_resources(self) -> None:
        """TC-K16: base/kustomization.yaml이 8개 리소스 파일을 모두 나열한다."""
        content = _read(K8S_BASE / "kustomization.yaml")
        expected_resources = [
            "namespace.yaml",
            "configmap.yaml",
            "secret.yaml",
            "api-deployment.yaml",
            "api-service.yaml",
            "neo4j-statefulset.yaml",
            "neo4j-service.yaml",
            "ingress.yaml",
        ]
        for resource in expected_resources:
            assert resource in content, f"kustomization.yaml에 {resource!r} 가 없습니다"


# ===========================================================================
# TC-K17 ~ TC-K24: K8s Overlays (dev / prod)
# ===========================================================================


@pytest.mark.unit
class TestK8sOverlays:
    """K8s dev·prod 오버레이의 kustomization 및 패치 파일 검증."""

    # -----------------------------------------------------------------------
    # TC-K17 ~ TC-K20: dev overlay
    # -----------------------------------------------------------------------

    def test_dev_overlay_exists(self) -> None:
        """TC-K17: dev/kustomization.yaml이 존재하고 ../base를 참조한다."""
        path = K8S_DEV / "kustomization.yaml"
        assert path.exists(), f"파일이 없습니다: {path}"
        assert "../base" in _read(path), "dev kustomization이 ../base를 참조하지 않습니다"

    def test_dev_has_name_prefix(self) -> None:
        """TC-K18: dev/kustomization.yaml에 namePrefix: dev- 가 설정된다."""
        content = _read(K8S_DEV / "kustomization.yaml")
        assert "namePrefix: dev-" in content, "namePrefix: dev- 가 없습니다"

    def test_dev_overlay_has_patches(self) -> None:
        """TC-K24: dev/kustomization.yaml에 patches 섹션이 존재한다."""
        content = _read(K8S_DEV / "kustomization.yaml")
        assert "patches" in content, "dev kustomization에 patches 섹션이 없습니다"

    # -----------------------------------------------------------------------
    # TC-K19 ~ TC-K23: prod overlay
    # -----------------------------------------------------------------------

    def test_prod_overlay_exists(self) -> None:
        """TC-K19: prod/kustomization.yaml이 존재하고 ../base를 참조한다."""
        path = K8S_PROD / "kustomization.yaml"
        assert path.exists(), f"파일이 없습니다: {path}"
        assert "../base" in _read(path), "prod kustomization이 ../base를 참조하지 않습니다"

    def test_prod_has_name_prefix(self) -> None:
        """TC-K20: prod/kustomization.yaml에 namePrefix: prod- 가 설정된다."""
        content = _read(K8S_PROD / "kustomization.yaml")
        assert "namePrefix: prod-" in content, "namePrefix: prod- 가 없습니다"

    def test_prod_has_tls_config(self) -> None:
        """TC-K21: prod/ingress-patch.yaml에 TLS·cert-manager·letsencrypt 설정이 있다."""
        content = _read(K8S_PROD / "ingress-patch.yaml")
        assert "tls" in content, "TLS 설정이 없습니다"
        assert "cert-manager" in content, "cert-manager 참조가 없습니다"
        assert "letsencrypt" in content, "letsencrypt issuer 참조가 없습니다"

    def test_prod_has_production_host(self) -> None:
        """TC-K22: prod/ingress-patch.yaml이 운영 도메인을 사용한다."""
        content = _read(K8S_PROD / "ingress-patch.yaml")
        assert "api.imsp.kriso.re.kr" in content, "운영 도메인 api.imsp.kriso.re.kr 이 없습니다"

    def test_prod_api_has_more_replicas(self) -> None:
        """TC-K23: prod/api-patch.yaml이 replicas: 3 으로 스케일 아웃된다."""
        content = _read(K8S_PROD / "api-patch.yaml")
        assert "replicas: 3" in content, "prod api-patch.yaml에 replicas: 3 이 없습니다"


# ===========================================================================
# TC-K25 ~ TC-K40: Keycloak Realm Configuration
# ===========================================================================


@pytest.mark.unit
class TestKeycloakRealm:
    """realm-imsp.json의 구조·보안·클라이언트·사용자 설정 검증."""

    def test_realm_name_is_imsp(self, realm_data: dict[str, Any]) -> None:
        """TC-K25: realm 이름이 'imsp' 다."""
        assert realm_data["realm"] == "imsp", f"realm 이름 불일치: {realm_data['realm']!r}"

    def test_realm_is_enabled(self, realm_data: dict[str, Any]) -> None:
        """TC-K26: realm이 활성화 상태(enabled=true)다."""
        assert realm_data["enabled"] is True, "realm이 비활성화 상태입니다"

    def test_realm_has_brute_force_protection(self, realm_data: dict[str, Any]) -> None:
        """TC-K27: brute force 보호가 활성화된다."""
        assert realm_data.get("bruteForceProtected") is True, (
            "bruteForceProtected 가 true 가 아닙니다"
        )

    def test_realm_has_four_roles(self, realm_data: dict[str, Any]) -> None:
        """TC-K28: realm 역할이 정확히 4개(admin, researcher, developer, viewer)다."""
        roles = realm_data["roles"]["realm"]
        assert len(roles) == 4, f"realm 역할 수 불일치: 예상 4, 실제 {len(roles)}"

    def test_realm_role_names(self, realm_data: dict[str, Any]) -> None:
        """TC-K29: realm 역할 이름이 admin·researcher·developer·viewer 이다."""
        role_names = {r["name"] for r in realm_data["roles"]["realm"]}
        expected = {"admin", "researcher", "developer", "viewer"}
        assert role_names == expected, f"역할 이름 불일치: {role_names!r}"

    def test_realm_has_two_clients(self, realm_data: dict[str, Any]) -> None:
        """TC-K30: 클라이언트가 정확히 2개(imsp-api, imsp-web)다."""
        clients = realm_data["clients"]
        assert len(clients) == 2, f"클라이언트 수 불일치: 예상 2, 실제 {len(clients)}"

    def _get_client(self, realm_data: dict[str, Any], client_id: str) -> dict[str, Any]:
        """clientId로 클라이언트 딕셔너리를 반환한다."""
        for client in realm_data["clients"]:
            if client["clientId"] == client_id:
                return client
        raise KeyError(f"클라이언트를 찾을 수 없습니다: {client_id!r}")

    def test_api_client_is_bearer_only(self, realm_data: dict[str, Any]) -> None:
        """TC-K31: imsp-api 클라이언트는 bearerOnly=true, publicClient=false 다."""
        client = self._get_client(realm_data, "imsp-api")
        assert client["bearerOnly"] is True, "imsp-api bearerOnly 가 true 가 아닙니다"
        assert client["publicClient"] is False, "imsp-api publicClient 가 false 가 아닙니다"

    def test_web_client_is_public(self, realm_data: dict[str, Any]) -> None:
        """TC-K32: imsp-web 클라이언트는 publicClient=true 다."""
        client = self._get_client(realm_data, "imsp-web")
        assert client["publicClient"] is True, "imsp-web publicClient 가 true 가 아닙니다"

    def test_web_client_has_redirect_uris(self, realm_data: dict[str, Any]) -> None:
        """TC-K33: imsp-web은 localhost와 kriso 도메인 리다이렉트 URI를 가진다."""
        client = self._get_client(realm_data, "imsp-web")
        uris = client.get("redirectUris", [])
        assert any("localhost" in u for u in uris), "localhost 리다이렉트 URI가 없습니다"
        assert any("kriso" in u for u in uris), "kriso 도메인 리다이렉트 URI가 없습니다"

    def test_realm_has_bootstrap_admin(self, realm_data: dict[str, Any]) -> None:
        """TC-K34: 부트스트랩 admin 사용자가 존재하고 admin 역할을 가진다."""
        users = realm_data.get("users", [])
        admin_users = [u for u in users if u.get("username") == "admin"]
        assert len(admin_users) >= 1, "username='admin' 사용자가 없습니다"
        admin = admin_users[0]
        assert "admin" in admin.get("realmRoles", []), "admin 사용자에게 admin 역할이 없습니다"

    def test_admin_password_is_temporary(self, realm_data: dict[str, Any]) -> None:
        """TC-K35: admin 사용자의 초기 비밀번호는 임시(temporary=true)다."""
        admin = next(u for u in realm_data["users"] if u["username"] == "admin")
        creds = admin.get("credentials", [])
        assert len(creds) >= 1, "admin 사용자에게 credentials 가 없습니다"
        assert creds[0].get("temporary") is True, "admin 초기 비밀번호가 임시(temporary)가 아닙니다"

    def test_realm_supports_korean_locale(self, realm_data: dict[str, Any]) -> None:
        """TC-K36: 한국어 로케일(ko)이 지원되고 기본값으로 설정된다."""
        assert "ko" in realm_data.get("supportedLocales", []), (
            "supportedLocales에 'ko' 가 없습니다"
        )
        assert realm_data.get("defaultLocale") == "ko", (
            f"defaultLocale이 'ko' 가 아닙니다: {realm_data.get('defaultLocale')!r}"
        )

    def test_realm_registration_disabled(self, realm_data: dict[str, Any]) -> None:
        """TC-K37: 셀프 등록(registrationAllowed)이 비활성화된다."""
        assert realm_data.get("registrationAllowed") is False, (
            "registrationAllowed 가 false 가 아닙니다 — 무단 등록이 가능합니다"
        )

    def test_access_token_lifespan(self, realm_data: dict[str, Any]) -> None:
        """TC-K38: 액세스 토큰 수명이 300초(5분)다."""
        lifespan = realm_data.get("accessTokenLifespan")
        assert lifespan == 300, f"accessTokenLifespan 불일치: 예상 300, 실제 {lifespan}"

    def test_ssl_required_external(self, realm_data: dict[str, Any]) -> None:
        """TC-K39: sslRequired 가 'external' 이다."""
        ssl = realm_data.get("sslRequired")
        assert ssl == "external", f"sslRequired 불일치: 예상 'external', 실제 {ssl!r}"

    def test_web_client_standard_flow(self, realm_data: dict[str, Any]) -> None:
        """TC-K40: imsp-web 클라이언트는 standardFlowEnabled=true 다."""
        client = self._get_client(realm_data, "imsp-web")
        assert client.get("standardFlowEnabled") is True, (
            "imsp-web standardFlowEnabled 가 true 가 아닙니다"
        )


# ===========================================================================
# TC-K41 ~ TC-K46: Keycloak Docker Compose
# ===========================================================================


@pytest.mark.unit
class TestKeycloakDockerCompose:
    """infra/keycloak/docker-compose.keycloak.yaml 검증."""

    _COMPOSE_PATH = KEYCLOAK_DIR / "docker-compose.keycloak.yaml"

    def test_keycloak_compose_exists(self) -> None:
        """TC-K41: docker-compose.keycloak.yaml 파일이 존재한다."""
        assert self._COMPOSE_PATH.exists(), f"파일이 없습니다: {self._COMPOSE_PATH}"

    def test_keycloak_compose_has_keycloak_service(self) -> None:
        """TC-K42: compose 파일에 keycloak 서비스가 정의된다."""
        content = _read(self._COMPOSE_PATH)
        assert "keycloak" in content, "keycloak 서비스가 없습니다"

    def test_keycloak_compose_has_postgres(self) -> None:
        """TC-K43: compose 파일에 postgres 또는 keycloak-db 서비스가 있다."""
        content = _read(self._COMPOSE_PATH)
        assert ("postgres" in content) or ("keycloak-db" in content), (
            "postgres/keycloak-db 서비스가 없습니다"
        )

    def test_keycloak_compose_has_health_check(self) -> None:
        """TC-K44: compose 파일에 healthcheck 설정이 있다."""
        content = _read(self._COMPOSE_PATH)
        assert "healthcheck" in content, "healthcheck 설정이 없습니다"

    def test_keycloak_compose_has_realm_import(self) -> None:
        """TC-K45: compose 파일이 realm-imsp.json을 마운트해서 자동 import한다."""
        content = _read(self._COMPOSE_PATH)
        assert "realm-imsp.json" in content, "realm-imsp.json 마운트가 없습니다"

    def test_keycloak_compose_port_mapping(self) -> None:
        """TC-K46: Keycloak이 호스트 8180 → 컨테이너 8080으로 포트가 매핑된다."""
        content = _read(self._COMPOSE_PATH)
        assert "8180:8080" in content, "포트 매핑 8180:8080 이 없습니다"


# ===========================================================================
# TC-K47 ~ TC-K50: Infra File Structure
# ===========================================================================


@pytest.mark.unit
class TestInfraFileStructure:
    """infra 디렉토리 전체의 파일 구조 검증."""

    def test_all_base_manifests_exist(self) -> None:
        """TC-K47: infra/k8s/base/ 에 8개 필수 매니페스트가 모두 존재한다."""
        expected = [
            "namespace.yaml",
            "configmap.yaml",
            "secret.yaml",
            "api-deployment.yaml",
            "api-service.yaml",
            "neo4j-statefulset.yaml",
            "neo4j-service.yaml",
            "ingress.yaml",
        ]
        missing = [f for f in expected if not (K8S_BASE / f).exists()]
        assert not missing, f"base 디렉토리에 다음 파일이 없습니다: {missing}"

    def test_all_dev_overlay_files_exist(self) -> None:
        """TC-K48: infra/k8s/dev/ 에 4개 파일이 모두 존재한다."""
        expected = [
            "kustomization.yaml",
            "api-patch.yaml",
            "neo4j-patch.yaml",
            "configmap-patch.yaml",
        ]
        missing = [f for f in expected if not (K8S_DEV / f).exists()]
        assert not missing, f"dev 디렉토리에 다음 파일이 없습니다: {missing}"

    def test_all_prod_overlay_files_exist(self) -> None:
        """TC-K49: infra/k8s/prod/ 에 5개 파일이 모두 존재한다."""
        expected = [
            "kustomization.yaml",
            "api-patch.yaml",
            "neo4j-patch.yaml",
            "configmap-patch.yaml",
            "ingress-patch.yaml",
        ]
        missing = [f for f in expected if not (K8S_PROD / f).exists()]
        assert not missing, f"prod 디렉토리에 다음 파일이 없습니다: {missing}"

    def test_keycloak_files_exist(self) -> None:
        """TC-K50: infra/keycloak/ 에 realm JSON과 compose 파일이 존재한다."""
        expected = [
            "realm-imsp.json",
            "docker-compose.keycloak.yaml",
        ]
        missing = [f for f in expected if not (KEYCLOAK_DIR / f).exists()]
        assert not missing, f"keycloak 디렉토리에 다음 파일이 없습니다: {missing}"
