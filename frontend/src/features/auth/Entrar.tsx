import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Anchor, Button, Code, Container, List, PasswordInput, Stack, Text, TextInput, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useLocation, useNavigate } from "react-router";
import { z } from "zod";
import { api } from "../../shared/api/cliente";
import { definirAcesso } from "../../shared/api/sessao";

const esquema = z.object({ email: z.string().min(1), senha: z.string().min(1) });
type Credenciais = z.infer<typeof esquema>;

type Etapa =
  | { nome: "senha" }
  | { nome: "totp"; desafio: string }
  | { nome: "cadastro"; desafio: string; segredo: string; uri: string }
  | { nome: "codigos"; codigos: string[] };

function mensagemDeErro(status: number): string {
  if (status === 429) return "Muitas tentativas. Aguarde alguns minutos e tente de novo.";
  return "E-mail ou senha inválidos.";
}

/** Retorno do provedor: o desafio de MFA vem no fragmento e o erro, na consulta. */
function retornoDoProvedor(hash: string, consulta: string) {
  const fragmento = new URLSearchParams(hash.replace(/^#/, ""));
  return {
    desafio: fragmento.get("desafio"),
    cadastro: fragmento.get("cadastro_mfa") === "1",
    falhou: new URLSearchParams(consulta).get("erro") === "federacao",
  };
}

export function Entrar() {
  const navegar = useNavigate();
  const { hash, search } = useLocation();
  const disponivel = useQuery({
    queryKey: ["oidc-disponivel"],
    queryFn: async () => (await api.GET("/api/v1/auth/oidc/disponivel")).data?.disponivel ?? false,
  });
  const [etapa, setEtapa] = useState<Etapa>({ nome: "senha" });
  const [erro, setErro] = useState<string | null>(null);
  const [codigo, setCodigo] = useState("");
  const formulario = useForm<Credenciais>({ resolver: zodResolver(esquema) });

  const retornoTratado = useRef(false);
  useEffect(() => {
    if (retornoTratado.current) return;
    retornoTratado.current = true;
    const retorno = retornoDoProvedor(hash, search);
    if (retorno.falhou) setErro("Não foi possível entrar pelo provedor da empresa.");
    if (!retorno.desafio) return;
    if (retorno.cadastro) void iniciarCadastro(retorno.desafio);
    else setEtapa({ nome: "totp", desafio: retorno.desafio });
    window.history.replaceState(null, "", window.location.pathname); // o desafio sai da barra
  }, []);

  function concluir(acesso: string) {
    definirAcesso(acesso);
    void navegar("/");
  }

  async function iniciarCadastro(desafio: string) {
    const { data } = await api.POST("/api/v1/auth/mfa/cadastrar", { body: { desafio } });
    if (data) setEtapa({ nome: "cadastro", desafio, ...data });
  }

  async function enviarSenha(credenciais: Credenciais) {
    setErro(null);
    const { data, response } = await api.POST("/api/v1/auth/entrar", { body: credenciais });
    if (!data) return setErro(mensagemDeErro(response.status));
    if (data.tokens) return concluir(data.tokens.acesso);
    if (data.desafio && data.cadastro_mfa_requerido) return iniciarCadastro(data.desafio);
    if (data.desafio) return setEtapa({ nome: "totp", desafio: data.desafio });
    setErro("Seu usuário não tem acesso a nenhum escritório.");
  }

  async function enviarTotp(desafio: string) {
    setErro(null);
    const { data, response } = await api.POST("/api/v1/auth/mfa", { body: { desafio, codigo } });
    if (data) return concluir(data.acesso);
    setErro(response.status === 429 ? mensagemDeErro(429) : "Código inválido.");
  }

  async function confirmarCadastro(desafio: string) {
    setErro(null);
    const { data } = await api.POST("/api/v1/auth/mfa/confirmar", { body: { desafio, codigo } });
    if (!data) return setErro("Código inválido.");
    definirAcesso(data.tokens.acesso);
    setEtapa({ nome: "codigos", codigos: data.codigos_de_recuperacao });
  }

  const campoDoCodigo = (
    <TextInput label="Código TOTP" value={codigo} onChange={(e) => setCodigo(e.target.value)} autoComplete="one-time-code" />
  );

  return (
    <Container size={420} py="xl">
      <Stack>
        <Title order={2}>DynaPrice</Title>
        {erro && <Alert color="red" role="alert">{erro}</Alert>}
        {etapa.nome === "senha" && (
          <form onSubmit={formulario.handleSubmit(enviarSenha)}>
            <Stack>
              <TextInput label="E-mail" type="email" autoComplete="username" {...formulario.register("email")} />
              <PasswordInput label="Senha" autoComplete="current-password" {...formulario.register("senha")} />
              <Button type="submit">Entrar</Button>
              {disponivel.data && (
                <Anchor href="/api/v1/auth/oidc/entrar">Entrar com o provedor da empresa</Anchor>
              )}
            </Stack>
          </form>
        )}
        {etapa.nome === "totp" && (
          <>
            {campoDoCodigo}
            <Button onClick={() => void enviarTotp(etapa.desafio)}>Confirmar</Button>
          </>
        )}
        {etapa.nome === "cadastro" && (
          <>
            <Text>Cadastre este segredo no seu aplicativo autenticador:</Text>
            <Code block>{etapa.segredo}</Code>
            {campoDoCodigo}
            <Button onClick={() => void confirmarCadastro(etapa.desafio)}>Confirmar</Button>
          </>
        )}
        {etapa.nome === "codigos" && (
          <>
            <Text>Guarde estes códigos de recuperação. Eles não serão mostrados de novo.</Text>
            <List>{etapa.codigos.map((c) => <List.Item key={c}>{c}</List.Item>)}</List>
            <Button onClick={() => void navegar("/")}>Já guardei</Button>
          </>
        )}
      </Stack>
    </Container>
  );
}
