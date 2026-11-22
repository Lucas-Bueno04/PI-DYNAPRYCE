import { AppShell, Group, NavLink, Title } from "@mantine/core";
import { Link, Outlet, Route, Routes, useLocation } from "react-router";
import { Administracao } from "../features/admin/Administracao";
import { Entrar } from "../features/auth/Entrar";
import { Guarda } from "../features/auth/Guarda";
import { Redefinir } from "../features/auth/Redefinir";
import { Cotacao } from "../features/cotacao/Cotacao";
import { Diagnostico } from "../features/diagnostico/Diagnostico";
import { Laboratorio } from "../features/laboratorio/Laboratorio";
import { Politicas } from "../features/politicas/Politicas";
import { Provisorios } from "../features/provisorios/Provisorios";
import { Recomendacoes } from "../features/recomendacoes/Recomendacoes";
import { useClaims } from "../shared/api/sessao";

/** Competência fechada de referência: o mês anterior ao atual. */
function competenciaAnterior(): string {
  const hoje = new Date();
  const anterior = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1);
  return `${anterior.getFullYear()}-${String(anterior.getMonth() + 1).padStart(2, "0")}`;
}

function Moldura() {
  const claims = useClaims();
  const { pathname } = useLocation();
  const itens = [
    { para: "/", rotulo: "Recomendações" },
    { para: "/cotacao", rotulo: "Cotação" },
    { para: "/provisorios", rotulo: "Provisórios" },
    { para: "/politicas", rotulo: "Políticas" },
    { para: "/diagnostico", rotulo: "Diagnóstico" },
    { para: "/laboratorio", rotulo: "Laboratório" },
    ...(claims?.roles.includes("administrar") ? [{ para: "/administracao", rotulo: "Administração" }] : []),
  ];
  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 220, breakpoint: "sm" }} padding="md">
      <AppShell.Header><Group h="100%" px="md"><Title order={3}>DynaPrice</Title></Group></AppShell.Header>
      <AppShell.Navbar p="sm">
        {itens.map((item) => <NavLink key={item.para} component={Link} to={item.para} label={item.rotulo} active={pathname === item.para} />)}
      </AppShell.Navbar>
      <AppShell.Main><Outlet /></AppShell.Main>
    </AppShell>
  );
}

export function App() {
  const competencia = competenciaAnterior();
  return (
    <Routes>
      <Route path="/entrar" element={<Entrar />} />
      <Route path="/redefinir" element={<Redefinir />} />
      <Route element={<Guarda><Moldura /></Guarda>}>
        <Route path="/" element={<Recomendacoes />} />
        <Route path="/cotacao" element={<Cotacao />} />
        <Route path="/provisorios" element={<Provisorios referencia={competencia} />} />
        <Route path="/politicas" element={<Politicas />} />
        <Route path="/diagnostico" element={<Diagnostico referencia={competencia} />} />
        <Route path="/laboratorio" element={<Laboratorio referencia={competencia} />} />
        <Route path="/administracao" element={<Guarda papel="administrar"><Administracao competencia={competencia} /></Guarda>} />
      </Route>
    </Routes>
  );
}
