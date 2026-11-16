import { Alert, Button, Container, PasswordInput, Stack, Title } from "@mantine/core";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { api } from "../../shared/api/cliente";

export function Redefinir() {
  const [parametros] = useSearchParams();
  const navegar = useNavigate();
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  async function enviar() {
    const token = parametros.get("token") ?? "";
    const { response } = await api.POST("/api/v1/auth/redefinir", {
      body: { token, nova_senha: senha },
    });
    if (response.ok) return void navegar("/entrar");
    setErro("Não foi possível redefinir. O link pode ter expirado ou a senha é curta.");
  }

  return (
    <Container size={420} py="xl">
      <Stack>
        <Title order={2}>Nova senha</Title>
        {erro && <Alert color="red" role="alert">{erro}</Alert>}
        <PasswordInput label="Nova senha" value={senha} onChange={(e) => setSenha(e.target.value)} />
        <Button onClick={() => void enviar()}>Redefinir</Button>
      </Stack>
    </Container>
  );
}
