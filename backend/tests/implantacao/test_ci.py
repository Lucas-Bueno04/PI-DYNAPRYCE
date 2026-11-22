"""F1.38: o CI guarda as regras (docs/versoes.md, cadeia de suprimentos)."""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
FLUXOS = RAIZ / ".github" / "workflows"
CI = FLUXOS / "ci.yaml"
RENOVATE = RAIZ / "renovate.json"


def _texto() -> str:
    return CI.read_text(encoding="utf-8")


def test_toda_action_fixada_por_sha_completo() -> None:
    usos = re.findall(r"^\s*-?\s*uses:\s*(\S+)", _texto(), flags=re.MULTILINE)
    assert usos
    for uso in usos:
        assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", uso), uso


def test_nunca_trivy_action_nem_setup_trivy() -> None:
    for arquivo in FLUXOS.glob("*.y*ml"):
        texto = arquivo.read_text(encoding="utf-8").lower()
        assert "trivy-action" not in texto and "setup-trivy" not in texto, arquivo.name


def test_scanners_rodam_por_imagem_fixada_em_digest() -> None:
    texto = _texto()
    for imagem in ("aquasec/trivy", "anchore/syft"):
        assert re.search(rf"{imagem}(?::[\w.-]+)?@sha256:[0-9a-f]{{64}}", texto), imagem


def test_permissoes_minimas_e_sem_checkout_com_credencial() -> None:
    texto = _texto()
    assert re.search(r"^permissions:\s*\n\s+contents:\s*read\s*$", texto, flags=re.MULTILINE)
    assert "pull_request_target" not in texto
    assert texto.count("persist-credentials: false") == texto.count("actions/checkout@")


def test_cobre_os_alvos_do_perfil() -> None:
    texto = _texto()
    for trecho in (
        "ruff check",
        "mypy",
        "lint-imports",
        "pytest",
        "pip-audit",
        "npm audit --omit=dev",
        "npm run lint",
        "npm test",
        "npm run build",
        "npm run verificar:api",
        "trivy",
        "syft",
        "docker/build-push-action",
    ):
        assert trecho in texto, trecho


def test_publicacao_so_na_main_e_nunca_em_pr() -> None:
    texto = _texto()
    assert re.search(
        r"if:\s*github\.ref == 'refs/heads/main' && github\.event_name == 'push'", texto
    )
    assert "packages: write" in texto


def test_renovate_configurado_com_pinagem_de_digest() -> None:
    texto = RENOVATE.read_text(encoding="utf-8")
    assert "helpers:pinGitHubActionDigests" in texto
    assert "docker:pinDigests" in texto
