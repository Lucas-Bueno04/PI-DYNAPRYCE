import { Alert, Badge, Button, Code, Group, List, NativeSelect, PasswordInput, Stack, Table, Text, TextInput, Title } from "@mantine/core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { components } from "../../shared/api/esquema";
import { api } from "../../shared/api/cliente";

type Papel = components["schemas"]["Papel"];
type Conector = components["schemas"]["RespostaConector"];

const TEXTO_DO_TESTE: Record<string, string> = {
  ok: "Conexão ok",
  indisponivel: "Fonte indisponível",
  credencial_invalida: "Credencial recusada",
  falhou: "Conector não disponível",
};

function LinhaDoConector({ conector }: { conector: Conector }) {
  const [resultado, setResultado] = useState<string | null>(null);

  async function testar() {
    const { data } = await api.POST("/api/v1/conectores/{tipo}/teste", {
      params: { path: { tipo: conector.tipo } },
    });
    setResultado(TEXTO_DO_TESTE[data?.situacao ?? "falhou"] ?? "Falhou");
  }

  return (
    <Table.Tr>
      <Table.Td>{conector.tipo}</Table.Td>
      <Table.Td>{conector.credencial_configurada ? "Credencial configurada" : "Sem credencial"}</Table.Td>
      <Table.Td><Button size="xs" onClick={() => void testar()}>Testar conexão</Button></Table.Td>
      <Table.Td>{resultado}</Table.Td>
    </Table.Tr>
  );
}

function useLista<T>(chave: string, buscar: () => Promise<T[] | undefined>) {
  return useQuery({ queryKey: [chave], queryFn: async () => (await buscar()) ?? [] }).data ?? [];
}

export function Administracao({ competencia }: { competencia: string }) {
  const consultas = useQueryClient();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [papel, setPapel] = useState<Papel>("analisar");
  const [erro, setErro] = useState<string | null>(null);
  const [link, setLink] = useState<string | null>(null);

  const usuarios = useLista("usuarios", async () => (await api.GET("/api/v1/usuarios")).data);
  const conectores = useLista("conectores", async () => (await api.GET("/api/v1/conectores")).data);
  const alertas = useLista("alertas", async () => (await api.GET("/api/v1/alertas")).data);
  const pendencias = useLista("pendencias", async () =>
    (await api.GET("/api/v1/vinculos/pendencias", { params: { query: { competencia } } })).data,
  );

  async function criar() {
    setErro(null);
    const { response } = await api.POST("/api/v1/usuarios", {
      body: { email, senha, papeis: [papel] },
    });
    if (!response.ok) return setErro("Não foi possível criar. Confira o e-mail e a senha (mínimo de 12 caracteres).");
    void consultas.invalidateQueries({ queryKey: ["usuarios"] });
  }

  async function gerarLink(usuarioId: string) {
    const { data } = await api.POST("/api/v1/usuarios/{usuario_id}/redefinicao", {
      params: { path: { usuario_id: usuarioId } },
    });
    if (data) setLink(data.token);
  }

  return (
    <Stack>
      <Title order={2}>Administração</Title>
      {erro && <Alert color="red" role="alert">{erro}</Alert>}
      {alertas.length > 0 && (
        <Alert color="orange" title="Alertas">
          <List>{alertas.map((a) => <List.Item key={`${a.tipo}${a.referencia}${a.criado_em}`}>{a.tipo} · {a.referencia}</List.Item>)}</List>
        </Alert>
      )}
      <Title order={3}>Usuários</Title>
      <Table>
        <Table.Tbody>
          {usuarios.map((u) => (
            <Table.Tr key={u.id}>
              <Table.Td>{u.email}</Table.Td>
              <Table.Td>{u.papeis.join(", ")}</Table.Td>
              <Table.Td><Badge color={u.mfa_ativo ? "green" : "yellow"}>{u.mfa_ativo ? "MFA ativo" : "MFA pendente"}</Badge></Table.Td>
              <Table.Td><Button size="xs" variant="default" onClick={() => void gerarLink(u.id)}>Gerar link</Button></Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {link && <Text>Link de uso único, válido por 30 minutos: <Code>/redefinir?token={link}</Code></Text>}
      <Group align="flex-end">
        <TextInput label="E-mail do novo usuário" value={email} onChange={(e) => setEmail(e.target.value)} />
        <PasswordInput label="Senha inicial" value={senha} onChange={(e) => setSenha(e.target.value)} />
        <NativeSelect label="Papel" data={["analisar", "aprovar", "administrar"]} value={papel} onChange={(e) => setPapel(e.target.value as Papel)} />
        <Button onClick={() => void criar()}>Criar usuário</Button>
      </Group>
      <Title order={3}>Conectores</Title>
      <Table><Table.Tbody>{conectores.map((c) => <LinhaDoConector key={c.tipo} conector={c} />)}</Table.Tbody></Table>
      <Title order={3}>Empresas sem vínculo em {competencia}</Title>
      {pendencias.length === 0 ? <Text>Nenhuma pendência.</Text> : <List>{pendencias.map((p) => <List.Item key={p}>{p}</List.Item>)}</List>}
    </Stack>
  );
}
