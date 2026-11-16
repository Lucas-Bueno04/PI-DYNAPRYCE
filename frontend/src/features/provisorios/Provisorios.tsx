import { Stack, Table, Text, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../shared/api/cliente";
import { moeda } from "../../shared/lib/formato";

export function Provisorios({ referencia }: { referencia: string }) {
  const { data } = useQuery({
    queryKey: ["provisorios", referencia],
    queryFn: async () =>
      (await api.GET("/api/v1/relatorios/provisorios", { params: { query: { competencia: referencia } } })).data ?? [],
  });
  const itens = data ?? [];
  const total = itens.reduce((soma, i) => soma + Number(i.diferenca), 0);
  return (
    <Stack>
      <Title order={2}>Provisórios abaixo do esforço medido</Title>
      <Text c="dimmed">
        Contratos provisórios cujo preço vigente está abaixo de κ·max(piso, τ·H) na competência {referencia}.
      </Text>
      {data && itens.length === 0 && <Text>Nenhum provisório abaixo do esforço medido.</Text>}
      {itens.length > 0 && (
        <>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Contrato</Table.Th>
                <Table.Th>Meses</Table.Th>
                <Table.Th>Preço vigente</Table.Th>
                <Table.Th>Esforço medido</Table.Th>
                <Table.Th>Diferença</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {itens.map((i) => (
                <Table.Tr key={i.contrato_id}>
                  <Table.Td>{i.contrato_id}</Table.Td>
                  <Table.Td>{i.meses}</Table.Td>
                  <Table.Td>{moeda(i.preco_vigente)}</Table.Td>
                  <Table.Td>{moeda(i.esforco)}</Table.Td>
                  <Table.Td>{moeda(i.diferenca)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          <Text data-testid="total">Receita mensal não cobrada: {moeda(total)}</Text>
        </>
      )}
    </Stack>
  );
}
