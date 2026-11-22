import { Badge, Button, Card, Group, Modal, Stack, Table, Tabs, Text, Textarea, Title } from "@mantine/core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { rotuloDaCompetencia, useCompetencia } from "../../app/competencia";
import { api } from "../../shared/api/cliente";
import { useClaims } from "../../shared/api/sessao";
import type { components } from "../../shared/api/esquema";
import { moeda } from "../../shared/lib/formato";
import { Carregando, Falha } from "../../shared/ui/Estados";

type Divergencia = components["schemas"]["RespostaDivergencia"];

const COR: Record<string, string> = { aberta: "red", justificada: "yellow", resolvida: "teal" };
const TEXTO_DO_ALERTA: Record<string, string> = {
  indice_ausente: "Índice de inflação ausente na janela",
  recomendacao_nao_exportada: "Recomendação aprovada ainda não exportada",
};

function Divergencias() {
  const consultas = useQueryClient();
  const podeTratar = useClaims()?.roles.includes("aprovar") ?? false;
  const [alvo, setAlvo] = useState<Divergencia | null>(null);
  const [texto, setTexto] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const { data, isError, isLoading } = useQuery({
    queryKey: ["divergencias"],
    queryFn: async () => (await api.GET("/api/v1/divergencias")).data ?? [],
  });
  const atualizar = () => void consultas.invalidateQueries({ queryKey: ["divergencias"] });

  async function justificar() {
    if (!alvo) return;
    const { response } = await api.POST("/api/v1/divergencias/{divergencia_id}/justificativa", {
      params: { path: { divergencia_id: alvo.id } }, body: { texto },
    });
    if (!response.ok) return setErro("Não foi possível registrar a justificativa.");
    setAlvo(null); setTexto(""); setErro(null); atualizar();
  }
  async function resolver(d: Divergencia) {
    await api.POST("/api/v1/divergencias/{divergencia_id}/resolucao", { params: { path: { divergencia_id: d.id } } });
    atualizar();
  }

  if (isLoading) return <Carregando />;
  if (isError) return <Falha>Não foi possível carregar as divergências.</Falha>;
  return (
    <Stack>
      <Text c="dimmed">Diferença entre o preço aprovado e o honorário efetivamente cobrado.</Text>
      <Card p={0}>
        <Table.ScrollContainer minWidth={700}>
          <Table>
            <Table.Thead><Table.Tr><Table.Th>Contrato</Table.Th><Table.Th>Competência</Table.Th><Table.Th>Aprovado</Table.Th><Table.Th>Cobrado</Table.Th><Table.Th>Situação</Table.Th><Table.Th /></Table.Tr></Table.Thead>
            <Table.Tbody>
              {(data ?? []).map((d) => (
                <Table.Tr key={d.id}>
                  <Table.Td fw={600}>{d.contrato_id}</Table.Td><Table.Td>{d.competencia}</Table.Td>
                  <Table.Td>{moeda(d.aprovado)}</Table.Td><Table.Td>{moeda(d.cobrado)}</Table.Td>
                  <Table.Td><Badge variant="light" color={COR[d.situacao] ?? "gray"}>{d.situacao}</Badge></Table.Td>
                  <Table.Td>
                    {podeTratar && d.situacao === "aberta" && <Button size="xs" variant="default" onClick={() => setAlvo(d)}>Justificar</Button>}
                    {podeTratar && d.situacao !== "resolvida" && <Button size="xs" ml="xs" onClick={() => void resolver(d)}>Resolver</Button>}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
        {(data ?? []).length === 0 && <Text c="dimmed" p="lg">Nenhuma divergência registrada.</Text>}
      </Card>
      <Modal opened={alvo !== null} onClose={() => setAlvo(null)} title={`Justificar ${alvo?.contrato_id ?? ""}`}>
        <Stack>
          {erro && <Falha>{erro}</Falha>}
          <Textarea label="Justificativa" autosize minRows={3} value={texto} onChange={(e) => setTexto(e.target.value)} />
          <Button onClick={() => void justificar()}>Registrar</Button>
        </Stack>
      </Modal>
    </Stack>
  );
}

function Alertas() {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["alertas"],
    queryFn: async () => (await api.GET("/api/v1/alertas")).data ?? [],
  });
  if (isLoading) return <Carregando />;
  if (isError) return <Falha>Não foi possível carregar os alertas.</Falha>;
  return (
    <Card p={0}>
      <Table>
        <Table.Thead><Table.Tr><Table.Th>Alerta</Table.Th><Table.Th>Referência</Table.Th><Table.Th>Quando</Table.Th></Table.Tr></Table.Thead>
        <Table.Tbody>
          {(data ?? []).map((a) => (
            <Table.Tr key={`${a.tipo}${a.referencia}${a.criado_em}`}>
              <Table.Td>{TEXTO_DO_ALERTA[a.tipo] ?? a.tipo}</Table.Td><Table.Td>{a.referencia}</Table.Td>
              <Table.Td>{new Date(a.criado_em).toLocaleString("pt-BR")}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {(data ?? []).length === 0 && <Text c="dimmed" p="lg">Sem alertas abertos.</Text>}
    </Card>
  );
}

function Pendencias() {
  const { competencia } = useCompetencia();
  const { data, isError, isLoading } = useQuery({
    queryKey: ["pendencias", competencia],
    queryFn: async () => (await api.GET("/api/v1/vinculos/pendencias", { params: { query: { competencia } } })).data ?? [],
  });
  if (isLoading) return <Carregando />;
  if (isError) return <Falha>Não foi possível carregar as pendências.</Falha>;
  return (
    <Card>
      <Text fw={600} mb="xs">Empresas sem vínculo a contrato em {rotuloDaCompetencia(competencia)}</Text>
      {(data ?? []).length === 0 ? <Text c="dimmed">Nenhuma pendência.</Text> : (
        <Group gap="xs">{(data ?? []).map((p) => <Badge key={p} variant="outline">{p}</Badge>)}</Group>
      )}
    </Card>
  );
}

export function Acompanhamento() {
  return (
    <Stack>
      <Title order={2}>Acompanhamento</Title>
      <Tabs defaultValue="divergencias" keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="divergencias">Divergências</Tabs.Tab>
          <Tabs.Tab value="alertas">Alertas</Tabs.Tab>
          <Tabs.Tab value="pendencias">Vínculos pendentes</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="divergencias" pt="md"><Divergencias /></Tabs.Panel>
        <Tabs.Panel value="alertas" pt="md"><Alertas /></Tabs.Panel>
        <Tabs.Panel value="pendencias" pt="md"><Pendencias /></Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
