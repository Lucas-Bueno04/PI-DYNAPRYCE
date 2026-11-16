import { Alert, Button, Stack, Table, Text, Title } from "@mantine/core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../shared/api/cliente";
import { useClaims } from "../../shared/api/sessao";
import { diferencas } from "./diferencas";

export function Politicas() {
  const consultas = useQueryClient();
  const claims = useClaims();
  const { data, isError } = useQuery({
    queryKey: ["politicas"],
    queryFn: async () => {
      const { data: itens } = await api.GET("/api/v1/politicas");
      if (!itens) throw new Error("falha ao listar");
      return itens;
    },
  });
  const publicada = data?.find((p) => p.estado === "publicada");
  const rascunho = data?.find((p) => p.estado === "rascunho");
  const podePublicar = claims?.roles.includes("aprovar") && rascunho?.portao_aceite !== false;

  async function publicar(versao: number) {
    await api.POST("/api/v1/politicas/{versao}/publicar", { params: { path: { versao } } });
    void consultas.invalidateQueries({ queryKey: ["politicas"] });
  }

  return (
    <Stack>
      <Title order={2}>Políticas de preço</Title>
      {isError && <Alert color="red" role="alert">Não foi possível carregar as políticas.</Alert>}
      <Text>Publicada: {publicada ? `v${publicada.versao}` : "nenhuma"}</Text>
      {rascunho && (
        <>
          <Title order={3}>Rascunho v{rascunho.versao}</Title>
          {rascunho.portao_aceite === false && <Alert color="red">Portão de aceite reprovado: as equações novas erram mais que as vigentes.</Alert>}
          <Table>
            <Table.Thead><Table.Tr><Table.Th>Campo</Table.Th><Table.Th>Publicada</Table.Th><Table.Th>Rascunho</Table.Th></Table.Tr></Table.Thead>
            <Table.Tbody>
              {diferencas(publicada?.documento ?? {}, rascunho.documento).map((d) => (
                <Table.Tr key={d.campo}><Table.Td>{d.campo}</Table.Td><Table.Td>{d.antes}</Table.Td><Table.Td>{d.depois}</Table.Td></Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          {podePublicar && <Button onClick={() => void publicar(rascunho.versao)}>Publicar v{rascunho.versao}</Button>}
        </>
      )}
    </Stack>
  );
}
