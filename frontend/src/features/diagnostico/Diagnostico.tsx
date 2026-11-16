import { Alert, Loader, Stack, Table, Text, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../shared/api/cliente";

interface Item { rotulo: string; valor: string; fonte: string }
interface Tabela { titulo: string; colunas: string[]; linhas: string[][]; fonte: string }
interface Secao { titulo: string; itens: Item[]; tabelas: Tabela[] }
interface Relatorio { titulo: string; secoes: Secao[] }

export function Diagnostico({ referencia }: { referencia: string }) {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["diagnostico", referencia],
    queryFn: async () => {
      const { data: corpo } = await api.GET("/api/v1/diagnostico", {
        params: { query: { referencia } },
      });
      if (!corpo) throw new Error("falha no diagnóstico");
      return corpo as unknown as Relatorio;
    },
  });
  if (isLoading) return <Loader aria-label="Carregando" />;
  if (isError || !data) return <Alert color="red" role="alert">Não foi possível gerar o diagnóstico.</Alert>;
  return (
    <Stack>
      <Title order={2}>{data.titulo}</Title>
      {data.secoes.map((secao) => (
        <Stack key={secao.titulo}>
          <Title order={3}>{secao.titulo}</Title>
          <Table>
            <Table.Tbody>
              {secao.itens.map((item) => (
                <Table.Tr key={item.rotulo}><Table.Td>{item.rotulo}</Table.Td><Table.Td>{item.valor}</Table.Td><Table.Td>{item.fonte}</Table.Td></Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          {secao.tabelas.map((tabela) => (
            <Stack key={tabela.titulo}>
              <Text fw={600}>{tabela.titulo}</Text>
              <Table>
                <Table.Thead><Table.Tr>{tabela.colunas.map((c) => <Table.Th key={c}>{c}</Table.Th>)}</Table.Tr></Table.Thead>
                <Table.Tbody>
                  {tabela.linhas.map((linha) => (
                    <Table.Tr key={linha.join("|")}>{linha.map((v, i) => <Table.Td key={tabela.colunas[i]}>{v}</Table.Td>)}</Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Stack>
          ))}
        </Stack>
      ))}
    </Stack>
  );
}
