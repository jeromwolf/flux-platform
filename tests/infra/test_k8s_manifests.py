"""Tests for new K8s manifests: Zipkin deployment and cert-manager issuer.

TC-KM01: zipkin-deployment.yaml loads and has expected structure.
TC-KM02: cert-manager-issuer.yaml loads and has expected ClusterIssuer resources.
TC-KM03: ingress.yaml has TLS configuration.
TC-KM04: kustomization.yaml lists new resources.
TC-KM05: prometheus.yml has Zipkin scrape target.
"""
from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INFRA_DIR = PROJECT_ROOT / "infra"
K8S_BASE = INFRA_DIR / "k8s" / "base"
PROMETHEUS_DIR = INFRA_DIR / "prometheus"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    """Read file as UTF-8 text."""
    return path.read_text(encoding="utf-8")


# ===========================================================================
# TC-KM01: zipkin-deployment.yaml
# ===========================================================================


@pytest.mark.unit
class TestZipkinDeploymentYaml:
    """Validate zipkin-deployment.yaml manifest structure."""

    def test_zipkin_deployment_yaml_valid(self) -> None:
        """TC-KM01: zipkin-deployment.yaml exists and contains Deployment + Service."""
        path = K8S_BASE / "zipkin-deployment.yaml"
        assert path.exists(), f"File missing: {path}"
        content = _read(path)

        # Deployment section
        assert "kind: Deployment" in content, "kind: Deployment not found"
        assert "name: zipkin" in content, "name: zipkin not found"
        assert "openzipkin/zipkin:3.1" in content, "zipkin image tag not found"
        assert "containerPort: 9411" in content, "containerPort 9411 not found"
        assert "STORAGE_TYPE" in content, "STORAGE_TYPE env var not found"

        # Resource limits
        assert "memory:" in content, "memory resource setting missing"
        assert "cpu:" in content, "cpu resource setting missing"
        assert "limits:" in content, "limits block missing"
        assert "requests:" in content, "requests block missing"

        # Liveness probe
        assert "livenessProbe" in content, "livenessProbe missing"
        assert "/health" in content, "health path for probe missing"

    def test_zipkin_service_yaml_valid(self) -> None:
        """TC-KM01b: zipkin-deployment.yaml contains a Service on port 9411."""
        content = _read(K8S_BASE / "zipkin-deployment.yaml")
        assert "kind: Service" in content, "kind: Service not found"
        assert "9411" in content, "port 9411 not found in Service"
        assert "app: zipkin" in content, "selector app: zipkin not found"

    def test_zipkin_namespace_is_imsp(self) -> None:
        """TC-KM01c: Zipkin resources are in the imsp namespace."""
        content = _read(K8S_BASE / "zipkin-deployment.yaml")
        assert "namespace: imsp" in content, "namespace: imsp not found"


# ===========================================================================
# TC-KM02: cert-manager-issuer.yaml
# ===========================================================================


@pytest.mark.unit
class TestCertManagerIssuerYaml:
    """Validate cert-manager-issuer.yaml ClusterIssuer resources."""

    def test_cert_manager_issuer_yaml_valid(self) -> None:
        """TC-KM02: cert-manager-issuer.yaml exists and has ClusterIssuer kind."""
        path = K8S_BASE / "cert-manager-issuer.yaml"
        assert path.exists(), f"File missing: {path}"
        content = _read(path)

        assert "kind: ClusterIssuer" in content, "kind: ClusterIssuer not found"
        assert "cert-manager.io/v1" in content, "cert-manager.io/v1 apiVersion not found"

    def test_cert_manager_has_prod_issuer(self) -> None:
        """TC-KM02b: letsencrypt-prod ClusterIssuer is defined."""
        content = _read(K8S_BASE / "cert-manager-issuer.yaml")
        assert "name: letsencrypt-prod" in content, "letsencrypt-prod issuer missing"
        assert "acme-v02.api.letsencrypt.org" in content, "prod ACME server URL missing"

    def test_cert_manager_has_staging_issuer(self) -> None:
        """TC-KM02c: letsencrypt-staging ClusterIssuer is defined."""
        content = _read(K8S_BASE / "cert-manager-issuer.yaml")
        assert "name: letsencrypt-staging" in content, "letsencrypt-staging issuer missing"
        assert "acme-staging-v02.api.letsencrypt.org" in content, "staging ACME server URL missing"

    def test_cert_manager_has_http01_solver(self) -> None:
        """TC-KM02d: Both issuers use http01 challenge solver."""
        content = _read(K8S_BASE / "cert-manager-issuer.yaml")
        assert "http01:" in content, "http01 solver not found"
        assert "class: nginx" in content, "nginx ingress class for solver not found"

    def test_cert_manager_contact_email(self) -> None:
        """TC-KM02e: KRISO contact email is set for ACME registration."""
        content = _read(K8S_BASE / "cert-manager-issuer.yaml")
        assert "admin@kriso.re.kr" in content, "KRISO contact email missing"


# ===========================================================================
# TC-KM03: ingress.yaml has TLS
# ===========================================================================


@pytest.mark.unit
class TestIngressHasTLS:
    """Validate that ingress.yaml has TLS and cert-manager annotation."""

    def test_ingress_has_tls(self) -> None:
        """TC-KM03: ingress.yaml contains a tls: block."""
        content = _read(K8S_BASE / "ingress.yaml")
        assert "tls:" in content, "tls: block not found in ingress.yaml"

    def test_ingress_tls_host(self) -> None:
        """TC-KM03b: TLS block references imsp.kriso.re.kr host."""
        content = _read(K8S_BASE / "ingress.yaml")
        assert "imsp.kriso.re.kr" in content, "imsp.kriso.re.kr host not found in TLS block"

    def test_ingress_tls_secret(self) -> None:
        """TC-KM03c: TLS block references imsp-tls secretName."""
        content = _read(K8S_BASE / "ingress.yaml")
        assert "secretName: imsp-tls" in content, "secretName: imsp-tls not found"

    def test_ingress_cert_manager_annotation(self) -> None:
        """TC-KM03d: ingress.yaml has cert-manager.io/cluster-issuer annotation."""
        content = _read(K8S_BASE / "ingress.yaml")
        assert "cert-manager.io/cluster-issuer" in content, (
            "cert-manager.io/cluster-issuer annotation missing"
        )
        assert "letsencrypt-prod" in content, "letsencrypt-prod issuer reference missing"


# ===========================================================================
# TC-KM04: kustomization.yaml lists new resources
# ===========================================================================


@pytest.mark.unit
class TestKustomizationListsNewResources:
    """Validate that kustomization.yaml includes the two new manifest files."""

    def test_kustomization_has_cert_manager_issuer(self) -> None:
        """TC-KM04a: kustomization.yaml lists cert-manager-issuer.yaml."""
        content = _read(K8S_BASE / "kustomization.yaml")
        assert "cert-manager-issuer.yaml" in content, (
            "cert-manager-issuer.yaml not in kustomization resources"
        )

    def test_kustomization_has_zipkin_deployment(self) -> None:
        """TC-KM04b: kustomization.yaml lists zipkin-deployment.yaml."""
        content = _read(K8S_BASE / "kustomization.yaml")
        assert "zipkin-deployment.yaml" in content, (
            "zipkin-deployment.yaml not in kustomization resources"
        )


# ===========================================================================
# TC-KM05: prometheus.yml has Zipkin scrape target
# ===========================================================================


@pytest.mark.unit
class TestPrometheusHasZipkinTarget:
    """Validate that prometheus.yml has a zipkin scrape job."""

    def test_prometheus_has_zipkin_scrape_job(self) -> None:
        """TC-KM05: prometheus.yml contains a job_name: 'zipkin' scrape config."""
        content = _read(PROMETHEUS_DIR / "prometheus.yml")
        assert "job_name: 'zipkin'" in content or 'job_name: "zipkin"' in content, (
            "zipkin scrape job not found in prometheus.yml"
        )

    def test_prometheus_zipkin_target_port(self) -> None:
        """TC-KM05b: prometheus.yml targets zipkin on port 9411."""
        content = _read(PROMETHEUS_DIR / "prometheus.yml")
        assert "zipkin:9411" in content, "zipkin:9411 target not found in prometheus.yml"


# ===========================================================================
# TC-NP: NetworkPolicy tests
# ===========================================================================


@pytest.mark.unit
class TestNetworkPolicies:
    """Validate network-policies.yaml manifest structure."""

    def test_network_policy_default_deny_exists(self) -> None:
        """TC-NP01: default-deny-ingress NetworkPolicy exists."""
        path = K8S_BASE / "network-policies.yaml"
        assert path.exists(), f"File missing: {path}"
        content = _read(path)
        assert "name: default-deny-ingress" in content, "default-deny-ingress policy not found"
        assert "kind: NetworkPolicy" in content, "kind: NetworkPolicy not found"

    def test_network_policy_gateway_ingress(self) -> None:
        """TC-NP02: allow-gateway-ingress NetworkPolicy allows port 8080."""
        content = _read(K8S_BASE / "network-policies.yaml")
        assert "name: allow-gateway-ingress" in content, "allow-gateway-ingress policy not found"
        assert "app: imsp-gateway" in content, "gateway pod selector not found"
        assert "port: 8080" in content, "port 8080 not found in gateway ingress policy"

    def test_network_policy_count(self) -> None:
        """TC-NP03: network-policies.yaml contains ingress + egress NetworkPolicy resources."""
        content = _read(K8S_BASE / "network-policies.yaml")
        count = content.count("kind: NetworkPolicy")
        assert count == 14, f"Expected 14 NetworkPolicy resources, found {count}"

    def test_kustomization_has_network_policies(self) -> None:
        """TC-NP04: kustomization.yaml lists network-policies.yaml."""
        content = _read(K8S_BASE / "kustomization.yaml")
        assert "network-policies.yaml" in content, (
            "network-policies.yaml not in kustomization resources"
        )


# ===========================================================================
# TC-BK: Neo4j Backup CronJob tests
# ===========================================================================


@pytest.mark.unit
class TestNeo4jBackupCronJob:
    """Validate neo4j-backup-cronjob.yaml manifest structure."""

    def test_neo4j_backup_cronjob_schedule(self) -> None:
        """TC-BK01: neo4j-backup-cronjob.yaml has correct daily schedule."""
        path = K8S_BASE / "neo4j-backup-cronjob.yaml"
        assert path.exists(), f"File missing: {path}"
        content = _read(path)
        assert "kind: CronJob" in content, "kind: CronJob not found"
        assert "name: neo4j-backup" in content, "name: neo4j-backup not found"
        assert '0 2 * * *' in content, "Daily 2 AM schedule not found"

    def test_neo4j_backup_pvc_exists(self) -> None:
        """TC-BK02: neo4j-backup-cronjob.yaml contains PersistentVolumeClaim."""
        content = _read(K8S_BASE / "neo4j-backup-cronjob.yaml")
        assert "kind: PersistentVolumeClaim" in content, "PersistentVolumeClaim not found"
        assert "name: neo4j-backup-pvc" in content, "neo4j-backup-pvc not found"
        assert "storage: 10Gi" in content, "10Gi storage request not found"

    def test_neo4j_backup_uses_imsp_secrets(self) -> None:
        """TC-BK03: backup job reads credentials from imsp-secrets."""
        content = _read(K8S_BASE / "neo4j-backup-cronjob.yaml")
        assert "imsp-secrets" in content, "imsp-secrets secretKeyRef not found"
        assert "neo4j-user" in content, "neo4j-user key not found"
        assert "neo4j-password" in content, "neo4j-password key not found"

    def test_neo4j_backup_concurrency_forbid(self) -> None:
        """TC-BK04: concurrencyPolicy is Forbid to prevent overlapping backups."""
        content = _read(K8S_BASE / "neo4j-backup-cronjob.yaml")
        assert "concurrencyPolicy: Forbid" in content, "concurrencyPolicy: Forbid not found"

    def test_kustomization_has_neo4j_backup_cronjob(self) -> None:
        """TC-BK05: kustomization.yaml lists neo4j-backup-cronjob.yaml."""
        content = _read(K8S_BASE / "kustomization.yaml")
        assert "neo4j-backup-cronjob.yaml" in content, (
            "neo4j-backup-cronjob.yaml not in kustomization resources"
        )
