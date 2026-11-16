import { Alert, Button, Group, Stack, Table, Title } from "@mantine/core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { components } from "../../shared/api/esquema";
import { api } from "../../shared/api/cliente";
import { useClaims } from "../../shared/api/sessao";
import { moeda } from "../../shared/lib/formato";
import { Detalhe } from "./Detalhe";

type Recomendacao = components["schemas"]["RespostaRecomendacao"];

export function Recomendacoes() {
  const consultas = useQueryClient();
  const claims = useClaims();
  const [aberto, setAberto] = useState<Recomendacao | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const { data, isError } = useQuery({
    queryKey: ["recomendacoes"],
    queryFn: async () => {
      const { data: itens } = await api.GET("/api/v1/recomendacoes", {
        params: { query: { estado: "pendente" } },
      });
      if (!itens) throw new Error("falha ao listar");
      return itens;
    },
  });

  function atualizar() {
    setAberto(null);
    void consultas.invalidateQueries({ queryKey: ["recomendacoes"] });
  }

  async function exportar() {
    const { data: lote } = await api.POST("/api/v1/exportacoes");
    setAviso(lote?.lote_id ? "Exportação solicitada." : "Não há recomendações aprovadas.");
  }

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Recomendações pendentes</Title>
        {claims?.roles.includes("aprovar") && <Button variant="default" onClick={() => void exportar()}>Exportar aprovadas</Button>}
      </Group>
      {aviso && <Alert>{aviso}</Alert>}
      {isError && <Alert color="red" role="alert">Não foi possível carregar a fila.</Alert>}
      <Table>
        <Table.Thead>
          <Table.Tr><Table.Th>Contrato</Table.Th><Table.Th>Efeito</Table.Th><Table.Th>Vigente</Table.Th><Table.Th>Proposto</Table.Th><Table.Th /></Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {data?.map((item) => (
            <Table.Tr key={item.id}>
              <Table.Td>{item.contrato_id}</Table.Td>
              <Table.Td>{item.efeito}</Table.Td>
              <Table.Td>{moeda(item.preco_vigente)}</Table.Td>
              <Table.Td>{moeda(item.preco_proposto)}</Table.Td>
              <Table.Td><Button size="xs" aria-label={`Ver ${item.contrato_id}`} onClick={() => setAberto(item)}>Ver</Button></Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {aberto && <Detalhe item={aberto} aoFechar={() => setAberto(null)} aoDecidir={atualizar} />}
    </Stack>
  );
}
