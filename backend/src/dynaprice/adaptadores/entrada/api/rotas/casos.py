"""Casos de uso que as rotas de negócio chamam; instanciados uma vez no Composition Root."""

from dataclasses import dataclass

from dynaprice.aplicacao.casos_de_uso import (
    BaixarLote,
    ConfigurarConector,
    ConsultarDiagnostico,
    CotarServico,
    CriarRascunhoDePolitica,
    CriarVinculo,
    DecidirRecomendacao,
    ImportarPlanilha,
    ListarAlertas,
    ListarConectores,
    ListarDivergencias,
    ListarPendencias,
    ListarPoliticas,
    ListarRecomendacoes,
    ProvisoriosAbaixoDoEsforco,
    PublicarPolitica,
    ReproduzirCotacao,
    SimularRascunho,
    SolicitarExportacao,
    TentarExportarDeNovo,
    TestarConector,
    TratarDivergencia,
)


@dataclass(frozen=True, slots=True)
class CasosDeUso:
    listar_recomendacoes: ListarRecomendacoes
    decidir: DecidirRecomendacao
    solicitar_exportacao: SolicitarExportacao
    tentar_exportar: TentarExportarDeNovo
    baixar_lote: BaixarLote
    listar_politicas: ListarPoliticas
    criar_rascunho: CriarRascunhoDePolitica
    publicar: PublicarPolitica
    listar_divergencias: ListarDivergencias
    tratar_divergencia: TratarDivergencia
    criar_vinculo: CriarVinculo
    listar_pendencias: ListarPendencias
    importar: ImportarPlanilha
    configurar_conector: ConfigurarConector
    listar_conectores: ListarConectores
    testar_conector: TestarConector
    listar_alertas: ListarAlertas
    diagnostico: ConsultarDiagnostico
    simular: SimularRascunho
    cotar: CotarServico
    reproduzir_cotacao: ReproduzirCotacao
    provisorios: ProvisoriosAbaixoDoEsforco
