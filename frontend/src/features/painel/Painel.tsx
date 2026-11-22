import { Badge, Card, Group, SimpleGrid, Stack, Table, Text, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import { Link } from "react-router";
import { rotuloDaCompetencia, useCompetencia } from "../../app/competencia";
import { api } from "../../shared/api/cliente";
import { moeda, percentual } from "../../shared/lib/formato";
import { Carregando, Falha } from "../../shared/ui/Estados";
import { Kpi } from "../../shared/ui/Kpi";

const COR_DOS_ESTADOS: Record<string, string> = {
  pendente: "yellow", aprovada: "teal", exportada: "indigo", rejeitada: "gray", expirada: "gray", falha_exportacao: "red",
};
const ROTULO_DOS_ESTADOS: Record<string, string> = {
  pendente: "Pendentes", aprovada: "Aprovadas", exportada: "Exportadas", rejeitada: "Rejeitadas", expirada: "Expiradas", falha_exportacao: "Falha na exportação",
};

function Grafico({ titulo, opcao }: { titulo: string; opcao: object }) {
  return (
    <Card>
      <Text fw={600} mb="xs">{titulo}</Text>
      <ReactECharts option={opcao} style={{ height: 280 }} notMerge />
    </Card>
  );
}

export function Painel() {
  const { competencia } = useCompetencia();
  const { data, isError, isLoading } = useQuery({
    queryKey: ["painel", competencia],
    queryFn: async () => {
      const { data: corpo } = await api.GET("/api/v1/painel", { params: { query: { competencia } } });
      if (!corpo) throw new Error("falha no painel");
      return corpo;
    },
  });
  if (isLoading) return <Carregando />;
  if (isError || !data) return <Falha>Não foi possível carregar o painel.</Falha>;

  const receita = Number(data.receita_mensal);
  const potencial = Number(data.potencial_de_reajuste);
  const pendentes = data.recomendacoes.pendente ?? 0;

  const serie = {
    tooltip: { trigger: "axis" },
    grid: { left: 60, right: 16, top: 16, bottom: 28 },
    xAxis: { type: "category", data: data.serie_receita.map((p) => rotuloDaCompetencia(p.competencia)) },
    yAxis: { type: "value", axisLabel: { formatter: (v: number) => `${Math.round(v / 1000)} mil` } },
    series: [{ type: "line", smooth: true, areaStyle: { opacity: 0.15 }, data: data.serie_receita.map((p) => Number(p.valor)) }],
  };
  const regimes = {
    tooltip: { trigger: "item", formatter: "{b}: {c} contratos ({d}%)" },
    legend: { bottom: 0 },
    series: [{ type: "pie", radius: ["45%", "70%"], data: data.por_regime.map((r) => ({ name: r.regime, value: r.contratos })) }],
  };
  const faixas = {
    tooltip: { trigger: "axis" },
    grid: { left: 40, right: 16, top: 16, bottom: 70 },
    xAxis: { type: "category", data: data.faixas.map((f) => f.rotulo), axisLabel: { interval: 0, rotate: 20, fontSize: 10 } },
    yAxis: { type: "value" },
    series: [{ type: "bar", data: data.faixas.map((f) => f.contratos) }],
  };
  const receitaPorRegime = {
    tooltip: { trigger: "axis" },
    grid: { left: 60, right: 16, top: 16, bottom: 28 },
    xAxis: { type: "category", data: data.por_regime.map((r) => r.regime) },
    yAxis: { type: "value", axisLabel: { formatter: (v: number) => `${Math.round(v / 1000)} mil` } },
    series: [{ type: "bar", data: data.por_regime.map((r) => Number(r.receita)) }],
  };

  return (
    <Stack gap="lg">
      <div>
        <Title order={2}>Painel</Title>
        <Text c="dimmed">Competência {rotuloDaCompetencia(data.competencia)}</Text>
      </div>
      <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }}>
        <Kpi rotulo="Receita mensal" valor={moeda(receita)} detalhe={`Alvo da política: ${moeda(data.receita_alvo)}`} />
        <Kpi rotulo="Potencial de reajuste" valor={moeda(potencial)} cor={potencial > 0 ? "teal" : undefined}
          detalhe={receita > 0 ? `${percentual(potencial / receita)} da receita` : undefined} />
        <Kpi rotulo="Contratos" valor={data.contratos} detalhe={`${data.empresas} empresas · ${data.provisorios} provisórios`} />
        <Kpi rotulo="Recomendações pendentes" valor={pendentes} cor={pendentes > 0 ? "yellow.7" : undefined}
          detalhe={data.alertas > 0 ? `${data.alertas} alertas abertos` : "Sem alertas"} />
      </SimpleGrid>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Grafico titulo="Receita de honorários (12 meses)" opcao={serie} />
        <Grafico titulo="Contratos por regime" opcao={regimes} />
        <Grafico titulo="Preço vigente frente ao alvo" opcao={faixas} />
        <Grafico titulo="Receita por regime" opcao={receitaPorRegime} />
      </SimpleGrid>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Card>
          <Group justify="space-between" mb="xs"><Text fw={600}>Ciclo de recomendações</Text><Link to="/recomendacoes">Abrir</Link></Group>
          <Group>
            {Object.entries(data.recomendacoes).map(([estado, n]) => (
              <Badge key={estado} size="lg" variant="light" color={COR_DOS_ESTADOS[estado] ?? "gray"}>{ROTULO_DOS_ESTADOS[estado] ?? estado}: {n}</Badge>
            ))}
            {Object.keys(data.recomendacoes).length === 0 && <Text c="dimmed">Nenhuma recomendação gerada.</Text>}
          </Group>
          <Text fw={600} mt="md" mb="xs">Divergências de cobrança</Text>
          <Group>
            {Object.entries(data.divergencias).map(([situacao, n]) => <Badge key={situacao} variant="outline">{situacao}: {n}</Badge>)}
            {Object.keys(data.divergencias).length === 0 && <Text c="dimmed">Nenhuma divergência.</Text>}
          </Group>
        </Card>
        <Card>
          <Group justify="space-between" mb="xs"><Text fw={600}>Maiores defasagens</Text><Link to="/clientes">Ver clientes</Link></Group>
          <Table>
            <Table.Thead><Table.Tr><Table.Th>Contrato</Table.Th><Table.Th>Vigente</Table.Th><Table.Th>Alvo</Table.Th><Table.Th>Defasagem</Table.Th></Table.Tr></Table.Thead>
            <Table.Tbody>
              {data.maiores_defasagens.map((c) => (
                <Table.Tr key={c.contrato_id}>
                  <Table.Td>{c.contrato_id}</Table.Td><Table.Td>{moeda(c.preco_vigente)}</Table.Td><Table.Td>{moeda(c.preco_alvo)}</Table.Td>
                  <Table.Td><Text c="red.6" fw={600}>{c.defasagem_pct}%</Text></Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          {data.maiores_defasagens.length === 0 && <Text c="dimmed">Nenhum contrato abaixo do alvo.</Text>}
        </Card>
      </SimpleGrid>
    </Stack>
  );
}
