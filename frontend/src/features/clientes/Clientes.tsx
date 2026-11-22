import { Badge, Card, Drawer, Group, NativeSelect, Pagination, SimpleGrid, Stack, Table, Text, TextInput, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { rotuloDaCompetencia, useCompetencia } from "../../app/competencia";
import { api } from "../../shared/api/cliente";
import type { components } from "../../shared/api/esquema";
import { moeda } from "../../shared/lib/formato";
import { Carregando, Falha } from "../../shared/ui/Estados";

type Cliente = components["schemas"]["RespostaCliente"];
type Ordem = "contrato" | "vigente" | "defasagem";

const POR_PAGINA = 20;
const MESES = ["", "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

function situacao(c: Cliente): { rotulo: string; cor: string } {
  if (c.defasagem_pct === null) return { rotulo: "Sem alvo", cor: "gray" };
  const d = Number(c.defasagem_pct);
  if (d < -15) return { rotulo: "Muito abaixo", cor: "red" };
  if (d < -5) return { rotulo: "Abaixo", cor: "orange" };
  if (d <= 5) return { rotulo: "No alvo", cor: "teal" };
  return { rotulo: "Acima", cor: "blue" };
}

function filtrar(lista: Cliente[], busca: string, regime: string, faixa: string): Cliente[] {
  return lista.filter((c) => {
    if (busca && !c.contrato_id.toLowerCase().includes(busca.toLowerCase())) return false;
    if (regime && c.regime !== regime) return false;
    if (faixa === "provisorio") return c.provisorio;
    if (faixa && situacao(c).rotulo !== faixa) return false;
    return true;
  });
}

function ordenar(lista: Cliente[], ordem: Ordem): Cliente[] {
  const copia = [...lista];
  if (ordem === "vigente") return copia.sort((a, b) => Number(b.preco_vigente) - Number(a.preco_vigente));
  if (ordem === "defasagem") return copia.sort((a, b) => Number(a.defasagem_pct ?? 1e9) - Number(b.defasagem_pct ?? 1e9));
  return copia.sort((a, b) => a.contrato_id.localeCompare(b.contrato_id));
}

function Campo({ rotulo, valor }: { rotulo: string; valor: string }) {
  return <div><Text size="xs" c="dimmed" tt="uppercase" fw={700}>{rotulo}</Text><Text fw={500}>{valor}</Text></div>;
}

function Detalhe({ cliente, aoFechar }: { cliente: Cliente | null; aoFechar: () => void }) {
  return (
    <Drawer opened={cliente !== null} onClose={aoFechar} position="right" size="md" title={cliente ? `Contrato ${cliente.contrato_id}` : ""}>
      {cliente && (
        <Stack>
          <Group>
            <Badge color={situacao(cliente).cor}>{situacao(cliente).rotulo}</Badge>
            {cliente.provisorio && <Badge variant="outline" color="grape">Provisório</Badge>}
            {cliente.recomendacao && <Badge variant="light">Recomendação {cliente.recomendacao}</Badge>}
          </Group>
          <SimpleGrid cols={2}>
            <Campo rotulo="Preço vigente" valor={moeda(cliente.preco_vigente)} />
            <Campo rotulo="Preço-alvo" valor={moeda(cliente.preco_alvo)} />
            <Campo rotulo="Defasagem" valor={cliente.defasagem_pct === null ? "—" : `${cliente.defasagem_pct}%`} />
            <Campo rotulo="Cobrado no mês" valor={moeda(cliente.cobrado)} />
            <Campo rotulo="Regime" valor={cliente.regime ?? "—"} />
            <Campo rotulo="Empresas no contrato" valor={String(cliente.empresas)} />
            <Campo rotulo="Mês de reajuste" valor={cliente.mes_reajuste ? (MESES[cliente.mes_reajuste] ?? "—") : "—"} />
            <Campo rotulo="κ (ajuste comercial)" valor={cliente.kappa} />
          </SimpleGrid>
          <Text size="sm" c="dimmed">A identificação é um pseudônimo: o sistema não guarda nome nem CNPJ do cliente.</Text>
        </Stack>
      )}
    </Drawer>
  );
}

export function Clientes() {
  const { competencia } = useCompetencia();
  const [busca, setBusca] = useState("");
  const [regime, setRegime] = useState("");
  const [faixa, setFaixa] = useState("");
  const [ordem, setOrdem] = useState<Ordem>("contrato");
  const [pagina, setPagina] = useState(1);
  const [aberto, setAberto] = useState<Cliente | null>(null);

  const { data, isError, isLoading } = useQuery({
    queryKey: ["clientes", competencia],
    queryFn: async () => {
      const { data: itens } = await api.GET("/api/v1/clientes", { params: { query: { competencia } } });
      if (!itens) throw new Error("falha ao listar clientes");
      return itens;
    },
  });
  const visiveis = useMemo(() => ordenar(filtrar(data ?? [], busca, regime, faixa), ordem), [data, busca, regime, faixa, ordem]);
  if (isLoading) return <Carregando />;
  if (isError) return <Falha>Não foi possível carregar os clientes.</Falha>;

  const paginas = Math.max(1, Math.ceil(visiveis.length / POR_PAGINA));
  const atual = Math.min(pagina, paginas);
  const fatia = visiveis.slice((atual - 1) * POR_PAGINA, atual * POR_PAGINA);
  const reiniciar = <T,>(definir: (v: T) => void) => (v: T) => { definir(v); setPagina(1); };

  return (
    <Stack gap="md">
      <div>
        <Title order={2}>Clientes</Title>
        <Text c="dimmed">{visiveis.length} de {data?.length ?? 0} contratos · {rotuloDaCompetencia(competencia)}</Text>
      </div>
      <Card>
        <Group align="flex-end">
          <TextInput label="Buscar contrato" placeholder="Ex.: C0042" value={busca} onChange={(e) => reiniciar(setBusca)(e.target.value)} />
          <NativeSelect label="Regime" value={regime} onChange={(e) => reiniciar(setRegime)(e.target.value)} data={[{ value: "", label: "Todos" }, "MEI", "SN", "LP", "LR"]} />
          <NativeSelect label="Situação" value={faixa} onChange={(e) => reiniciar(setFaixa)(e.target.value)}
            data={[{ value: "", label: "Todas" }, "Muito abaixo", "Abaixo", "No alvo", "Acima", "Sem alvo", { value: "provisorio", label: "Provisórios" }]} />
          <NativeSelect label="Ordenar por" value={ordem} onChange={(e) => setOrdem(e.target.value as Ordem)}
            data={[{ value: "contrato", label: "Contrato" }, { value: "vigente", label: "Maior preço" }, { value: "defasagem", label: "Maior defasagem" }]} />
        </Group>
      </Card>
      <Card p={0}>
        <Table.ScrollContainer minWidth={760}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Contrato</Table.Th><Table.Th>Regime</Table.Th><Table.Th>Empresas</Table.Th><Table.Th>Vigente</Table.Th>
                <Table.Th>Alvo</Table.Th><Table.Th>Defasagem</Table.Th><Table.Th>Situação</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {fatia.map((c) => (
                <Table.Tr key={c.contrato_id} style={{ cursor: "pointer" }} onClick={() => setAberto(c)}>
                  <Table.Td fw={600}>{c.contrato_id}{c.provisorio && <Badge ml="xs" size="xs" variant="outline" color="grape">prov.</Badge>}</Table.Td>
                  <Table.Td>{c.regime ?? "—"}</Table.Td>
                  <Table.Td>{c.empresas}</Table.Td>
                  <Table.Td>{moeda(c.preco_vigente)}</Table.Td>
                  <Table.Td>{moeda(c.preco_alvo)}</Table.Td>
                  <Table.Td>{c.defasagem_pct === null ? "—" : `${c.defasagem_pct}%`}</Table.Td>
                  <Table.Td><Badge variant="light" color={situacao(c).cor}>{situacao(c).rotulo}</Badge></Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
        {fatia.length === 0 && <Text c="dimmed" p="lg">Nenhum contrato com esses filtros.</Text>}
      </Card>
      {paginas > 1 && <Pagination value={atual} onChange={setPagina} total={paginas} />}
      <Detalhe cliente={aberto} aoFechar={() => setAberto(null)} />
    </Stack>
  );
}
