import { Loader, Text } from "@mantine/core";
import { useEffect, useState, type ReactNode } from "react";
import { Navigate } from "react-router";
import { renovarSessao } from "../../shared/api/cliente";
import { obterAcesso, useClaims } from "../../shared/api/sessao";

interface Propriedades {
  papel?: string;
  children: ReactNode;
}

/** Conveniência de interface: quem autoriza de verdade é o backend. */
export function Guarda({ papel, children }: Propriedades) {
  const claims = useClaims();
  const [verificando, setVerificando] = useState(() => obterAcesso() === null);

  useEffect(() => {
    if (obterAcesso() !== null) return;
    void renovarSessao().finally(() => setVerificando(false));
  }, []);

  if (verificando) return <Loader aria-label="Carregando" />;
  if (claims === null) return <Navigate to="/entrar" replace />;
  if (papel && !claims.roles.includes(papel)) return <Text>Você não tem acesso a esta tela.</Text>;
  return children;
}
