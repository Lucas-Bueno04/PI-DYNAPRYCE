"""F0.6: estrutura da carteira sintética (ADR-003; docs/lab/calibracao_sintetica.md)."""

from collections import Counter

from dynaprice.adaptadores.saida.sintetico import GeradorDeCarteiraSintetica, ParametrosSinteticos
from dynaprice.dominio.modelos import Carteira, Competencia, Regime
from tests.sintetico.conftest import FIM, INICIO


def test_mesma_semente_mesma_carteira() -> None:
    a = GeradorDeCarteiraSintetica(ParametrosSinteticos(semente=7, contratos=60))
    b = GeradorDeCarteiraSintetica(ParametrosSinteticos(semente=7, contratos=60))
    assert a.extrair(INICIO, FIM) == b.extrair(INICIO, FIM)


def test_sementes_diferentes_carteiras_diferentes() -> None:
    a = GeradorDeCarteiraSintetica(ParametrosSinteticos(semente=1, contratos=60))
    b = GeradorDeCarteiraSintetica(ParametrosSinteticos(semente=2, contratos=60))
    assert a.extrair(INICIO, FIM) != b.extrair(INICIO, FIM)


def test_tamanho_e_ids_unicos(carteira: Carteira) -> None:
    assert len(carteira.contratos) == 500
    assert len({e.id for e in carteira.empresas}) == len(carteira.empresas)


def test_todo_contrato_tem_uma_principal_vigente(carteira: Carteira) -> None:
    principais = Counter(v.contrato_id for v in carteira.vinculos if v.principal)
    assert set(principais) == {c.id for c in carteira.contratos}
    assert set(principais.values()) == {1}


def test_cerca_de_dez_por_cento_sem_vinculo(carteira: Carteira) -> None:
    vinculadas = {v.empresa_id for v in carteira.vinculos}
    sem = [e for e in carteira.empresas if e.id not in vinculadas]
    assert 0.07 <= len(sem) / len(carteira.empresas) <= 0.13
    com_horas = {h.empresa_id for h in carteira.horas}
    assert all(e.id in com_horas for e in sem)


def test_cerca_de_um_terco_sem_honorario_proprio(carteira: Carteira) -> None:
    vinculadas = {v.empresa_id for v in carteira.vinculos}
    nao_principais = vinculadas - {v.empresa_id for v in carteira.vinculos if v.principal}
    assert 0.25 <= len(nao_principais) / len(carteira.empresas) <= 0.40


def test_contratos_mistos_cerca_de_cinco_por_cento(carteira: Carteira) -> None:
    regime = {e.id: e.regime for e in carteira.empresas}
    por_contrato: dict[str, set[Regime]] = {}
    for v in carteira.vinculos:
        por_contrato.setdefault(v.contrato_id, set()).add(regime[v.empresa_id])
    mistos = sum(len(r) > 1 for r in por_contrato.values())
    assert 0.02 <= mistos / len(carteira.contratos) <= 0.09


def test_maioria_simples_nacional_e_todos_os_regimes(carteira: Carteira) -> None:
    contagem = Counter(e.regime for e in carteira.empresas)
    assert set(contagem) == set(Regime)
    assert contagem.most_common(1)[0][0] is Regime.SN


def test_doze_meses_e_historico_parcial(carteira: Carteira) -> None:
    meses: dict[str, set[Competencia]] = {}
    for d in carteira.direcionadores:
        meses.setdefault(d.empresa_id, set()).add(d.competencia)
    completos = sum(len(m) == 12 for m in meses.values())
    parciais = [len(m) for m in meses.values() if len(m) < 12]
    assert completos / len(meses) >= 0.9
    assert parciais and all(1 <= n <= 11 for n in parciais)
    assert all(INICIO <= c <= FIM for m in meses.values() for c in m)


def test_honorario_so_de_contrato_e_mes_de_reajuste(carteira: Carteira) -> None:
    contratos = {c.id for c in carteira.contratos}
    assert {h.contrato_id for h in carteira.honorarios} <= contratos
    assert all(c.mes_reajuste is not None for c in carteira.contratos)
