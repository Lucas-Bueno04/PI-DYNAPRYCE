import { Alert, Badge, Button, Card, Code, Group, MultiSelect, PasswordInput, Stack, Table, Text, TextInput, Title } from "@mantine/core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../shared/api/cliente";
import type { components } from "../../shared/api/esquema";
import { Carregando, Falha } from "../../shared/ui/Estados";

type Papel = components["schemas"]["Papel"];
const PAPEIS = [
  { value: "analisar", label: "Analisar" },
  { value: "aprovar", label: "Aprovar" },
  { value: "administrar", label: "Administrar" },
];

export function Usuarios() {
  const consultas = useQueryClient();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [papeis, setPapeis] = useState<string[]>(["analisar"]);
  const [erro, setErro] = useState<string | null>(null);
  const [link, setLink] = useState<string | null>(null);
  const { data, isError, isLoading } = useQuery({
    queryKey: ["usuarios"],
    queryFn: async () => (await api.GET("/api/v1/usuarios")).data ?? [],
  });
  const atualizar = () => void consultas.invalidateQueries({ queryKey: ["usuarios"] });

  async function criar() {
    setErro(null);
    const { response } = await api.POST("/api/v1/usuarios", { body: { email, senha, papeis: papeis as Papel[] } });
    if (!response.ok) return setErro("Não foi possível criar. Confira o e-mail e a senha (mínimo de 12 caracteres).");
    setEmail(""); setSenha(""); atualizar();
  }
  async function trocarPapeis(id: string, novos: string[]) {
    const { response } = await api.PUT("/api/v1/usuarios/{usuario_id}/papeis", {
      params: { path: { usuario_id: id } }, body: { papeis: novos as Papel[] },
    });
    if (!response.ok) setErro("Não foi possível alterar os papéis.");
    atualizar();
  }
  async function desativar(id: string) {
    await api.DELETE("/api/v1/usuarios/{usuario_id}", { params: { path: { usuario_id: id } } });
    atualizar();
  }
  async function gerarLink(id: string) {
    const { data: corpo } = await api.POST("/api/v1/usuarios/{usuario_id}/redefinicao", { params: { path: { usuario_id: id } } });
    if (corpo) setLink(corpo.token);
  }

  if (isLoading) return <Carregando />;
  if (isError) return <Falha>Não foi possível carregar os usuários.</Falha>;
  return (
    <Stack>
      <div><Title order={2}>Usuários</Title><Text c="dimmed">Quem acessa o escritório e com quais papéis. Aprovar e administrar exigem MFA.</Text></div>
      {erro && <Alert color="red" role="alert">{erro}</Alert>}
      {link && <Alert color="indigo" title="Link de uso único (30 minutos)"><Code>/redefinir?token={link}</Code></Alert>}
      <Card p={0}>
        <Table.ScrollContainer minWidth={720}>
          <Table>
            <Table.Thead><Table.Tr><Table.Th>E-mail</Table.Th><Table.Th>Papéis</Table.Th><Table.Th>MFA</Table.Th><Table.Th>Situação</Table.Th><Table.Th /></Table.Tr></Table.Thead>
            <Table.Tbody>
              {(data ?? []).map((u) => (
                <Table.Tr key={u.id}>
                  <Table.Td fw={600}>{u.email}</Table.Td>
                  <Table.Td>
                    <MultiSelect aria-label={`Papéis de ${u.email}`} data={PAPEIS} value={[...u.papeis]} onChange={(v) => void trocarPapeis(u.id, v)} w={260} />
                  </Table.Td>
                  <Table.Td><Badge variant="light" color={u.mfa_ativo ? "teal" : "yellow"}>{u.mfa_ativo ? "Ativo" : "Pendente"}</Badge></Table.Td>
                  <Table.Td><Badge variant="light" color={u.ativo ? "teal" : "gray"}>{u.ativo ? "Ativo" : "Desativado"}</Badge></Table.Td>
                  <Table.Td>
                    <Group gap="xs" wrap="nowrap">
                      <Button size="xs" variant="default" onClick={() => void gerarLink(u.id)}>Gerar link</Button>
                      {u.ativo && <Button size="xs" variant="light" color="red" onClick={() => void desativar(u.id)}>Desativar</Button>}
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Card>
      <Card>
        <Text fw={600} mb="sm">Novo usuário</Text>
        <Group align="flex-end">
          <TextInput label="E-mail" value={email} onChange={(e) => setEmail(e.target.value)} />
          <PasswordInput label="Senha inicial (mín. 12)" value={senha} onChange={(e) => setSenha(e.target.value)} />
          <MultiSelect label="Papéis" data={PAPEIS} value={papeis} onChange={setPapeis} w={260} />
          <Button onClick={() => void criar()}>Criar usuário</Button>
        </Group>
      </Card>
    </Stack>
  );
}
