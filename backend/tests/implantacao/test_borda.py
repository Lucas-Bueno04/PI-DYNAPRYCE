"""F1.37: a borda (nginx + compose) cumpre ADR-001 e fecha M3.

Testes estáticos sobre a configuração versionada; o teste ao vivo é
deploy/compose/verificar-borda.sh, que roda contra o compose em pé.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[3]
FRONT = RAIZ / "frontend"
COMPOSE = RAIZ / "deploy" / "compose" / "compose.yaml"
SEGURANCA_INC = "/etc/nginx/conf.d/seguranca.inc"


def _ler(nome: str) -> str:
    texto = (FRONT / nome).read_text(encoding="utf-8")
    return re.sub(r"#[^\n]*", "", texto)


def _locais(conf: str) -> dict[str, str]:
    """Corpo de cada bloco `location` (os blocos não se aninham neste arquivo)."""
    return dict(re.findall(r"location\s+(\S+)\s*\{([^}]*)\}", conf))


def _diretivas(corpo: str, nome: str) -> list[str]:
    return re.findall(rf'^\s*{nome}\s+((?:"[^"]*"|[^;"])+);', corpo, flags=re.MULTILINE)


# --- nginx ---------------------------------------------------------------


def test_cabecalhos_de_seguranca_ficam_num_unico_include() -> None:
    inc = _ler("seguranca.inc")
    csp = re.search(r'Content-Security-Policy\s+"([^"]+)"', inc)
    assert csp, "CSP ausente"
    politica = csp.group(1)
    assert "default-src 'self'" in politica
    assert "frame-ancestors 'none'" in politica
    assert "unsafe-eval" not in politica
    assert not re.search(r"script-src[^;]*unsafe-inline", politica)
    hsts = re.search(r'Strict-Transport-Security\s+"max-age=(\d+)', inc)
    assert hsts and int(hsts.group(1)) >= 31536000
    for cabecalho in ("X-Content-Type-Options", "Referrer-Policy"):
        assert re.search(rf"add_header\s+{cabecalho}\s+\S+\s+always;", inc), cabecalho
    diretivas = _diretivas(inc, "add_header")
    assert len(diretivas) >= 4
    assert all(d.rstrip().endswith("always") for d in diretivas)


def test_todo_bloco_com_add_header_repete_o_include() -> None:
    """No nginx, um add_header no location descarta os herdados do server."""
    conf = _ler("nginx.conf")
    servidor = re.sub(r"location\s+\S+\s*\{[^}]*\}", "", conf)
    assert f"include {SEGURANCA_INC};" in servidor
    for local, corpo in _locais(conf).items():
        if "add_header" in corpo:
            assert f"include {SEGURANCA_INC};" in corpo, local


def test_limite_de_taxa_no_login_e_tamanho_de_corpo() -> None:
    conf = _ler("nginx.conf")
    assert re.search(r"limit_req_zone\s+\$binary_remote_addr\s+zone=auth:", conf)
    assert _diretivas(conf, "limit_req_status") == ["429"]
    locais = _locais(conf)
    assert _diretivas(locais["/api/v1/auth/"], "limit_req")
    assert _diretivas(locais["/api/v1/importacoes"], "client_max_body_size") == ["11m"]
    assert _diretivas(locais["/api/"], "client_max_body_size") == ["1m"]
    assert "server_tokens off;" in conf


def test_so_tls_moderno() -> None:
    conf = _ler("nginx.conf")
    assert re.search(r"listen\s+8443\s+ssl", conf)
    assert _diretivas(conf, "ssl_protocols") == ["TLSv1.2 TLSv1.3"]


def test_proxy_sobrescreve_x_forwarded_for() -> None:
    """M3: o cliente não injeta IP; o proxy grava só o endereço que viu."""
    inc = _ler("proxy.inc")
    assert re.search(r"proxy_set_header\s+X-Forwarded-For\s+\$remote_addr;", inc)
    assert "proxy_add_x_forwarded_for" not in inc
    for local, corpo in _locais(_ler("nginx.conf")).items():
        if "proxy_pass" in corpo:
            assert "include /etc/nginx/conf.d/proxy.inc;" in corpo, local


def test_imagens_da_borda_fixadas_por_versao_exata() -> None:
    bases = re.findall(r"^FROM\s+(\S+)", _ler("Dockerfile"), flags=re.MULTILINE)
    assert bases
    for base in bases:
        assert re.search(r":\d+\.\d+\.\d+", base), base
    assert f"COPY seguranca.inc {SEGURANCA_INC}" in _ler("Dockerfile")


# --- compose -------------------------------------------------------------


@pytest.fixture(scope="module")
def servicos() -> dict[str, Any]:
    if not shutil.which("docker"):
        pytest.skip("docker ausente")
    saida = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), "config", "--format", "json", "--no-interpolate"],
        capture_output=True,
        text=True,
        check=True,
    )
    servicos: dict[str, Any] = json.loads(saida.stdout)["services"]
    return servicos


def test_so_a_borda_publica_porta_e_so_no_loopback(servicos: dict[str, Any]) -> None:
    publicados = {nome: s["ports"] for nome, s in servicos.items() if s.get("ports")}
    assert list(publicados) == ["web"]
    assert [(p["host_ip"], p["published"]) for p in publicados["web"]] == [("127.0.0.1", "8443")]


def test_api_confia_so_no_ip_fixo_do_proxy(servicos: dict[str, Any]) -> None:
    ip_web = {r["ipv4_address"] for r in servicos["web"]["networks"].values() if r}
    assert servicos["api"]["environment"]["DYNAPRICE_PROXY_CONFIAVEL"] in ip_web


def test_api_alcanca_o_banco_e_a_borda_nao(servicos: dict[str, Any]) -> None:
    redes = {nome: set(s.get("networks") or {"default": None}) for nome, s in servicos.items()}
    assert redes["api"] & redes["pg"], "api sem rota para o banco"
    assert redes["api"] & redes["web"], "api sem rota para o proxy"
    assert not redes["web"] & redes["pg"], "o proxy não deve ver o banco"
