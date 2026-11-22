import {
  ActionIcon, AppShell, Avatar, Badge, Burger, Group, Menu, NativeSelect, NavLink, ScrollArea, Stack, Text, Title,
  useComputedColorScheme, useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router";
import { api } from "../shared/api/cliente";
import { limparSessao, useClaims } from "../shared/api/sessao";
import { rotuloDaCompetencia, useCompetencia } from "./competencia";

interface Item { para: string; rotulo: string }
interface Grupo { titulo: string; itens: Item[] }

function grupos(administra: boolean): Grupo[] {
  return [
    { titulo: "Visão geral", itens: [{ para: "/", rotulo: "Painel" }] },
    { titulo: "Carteira", itens: [{ para: "/clientes", rotulo: "Clientes" }] },
    {
      titulo: "Precificação",
      itens: [
        { para: "/recomendacoes", rotulo: "Recomendações" },
        { para: "/cotacao", rotulo: "Cotação" },
        { para: "/politicas", rotulo: "Políticas" },
        { para: "/laboratorio", rotulo: "Laboratório" },
      ],
    },
    {
      titulo: "Acompanhamento",
      itens: [
        { para: "/acompanhamento", rotulo: "Divergências e alertas" },
        { para: "/provisorios", rotulo: "Provisórios" },
        { para: "/diagnostico", rotulo: "Diagnóstico" },
      ],
    },
    ...(administra
      ? [{ titulo: "Administração", itens: [{ para: "/usuarios", rotulo: "Usuários" }, { para: "/administracao", rotulo: "Conectores e vínculos" }] }]
      : []),
  ];
}

/** Se a competência escolhida não tem honorários, vai para a mais recente que tem. */
function useCompetenciaComDados() {
  const { competencia, definir } = useCompetencia();
  const { data } = useQuery({
    queryKey: ["painel", competencia],
    queryFn: async () => (await api.GET("/api/v1/painel", { params: { query: { competencia } } })).data ?? null,
  });
  useEffect(() => {
    if (data && Number(data.receita_mensal) === 0 && data.competencias_com_dados.length > 0) {
      definir(data.competencias_com_dados[0] ?? competencia);
    }
  }, [data, definir, competencia]);
}

export function Moldura() {
  const claims = useClaims();
  const { pathname } = useLocation();
  const navegar = useNavigate();
  const [aberto, { toggle, close }] = useDisclosure();
  const { competencia, definir, opcoes } = useCompetencia();
  const { setColorScheme } = useMantineColorScheme();
  const esquema = useComputedColorScheme("light");
  useCompetenciaComDados();

  const ativo = (para: string) => (para === "/" ? pathname === "/" : pathname.startsWith(para));

  async function sair() {
    await api.POST("/api/v1/auth/sair");
    limparSessao();
    navegar("/entrar");
  }

  return (
    <AppShell header={{ height: 60 }} navbar={{ width: 250, breakpoint: "sm", collapsed: { mobile: !aberto } }} padding="lg">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={aberto} onClick={toggle} hiddenFrom="sm" size="sm" aria-label="Abrir menu" />
            <Title order={3} c="indigo">DynaPrice</Title>
            <Badge variant="light" visibleFrom="sm">Precificação dinâmica</Badge>
          </Group>
          <Group gap="sm" wrap="nowrap">
            <NativeSelect
              aria-label="Competência"
              size="xs"
              value={competencia}
              onChange={(e) => definir(e.target.value)}
              data={opcoes.map((c) => ({ value: c, label: rotuloDaCompetencia(c) }))}
            />
            <ActionIcon
              variant="default" size="lg" aria-label="Alternar tema"
              onClick={() => setColorScheme(esquema === "dark" ? "light" : "dark")}
            >
              {esquema === "dark" ? "☀" : "☾"}
            </ActionIcon>
            <Menu position="bottom-end" width={220}>
              <Menu.Target>
                <ActionIcon variant="subtle" size="lg" radius="xl" aria-label="Conta"><Avatar size="sm" color="indigo" /></ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Label>Papéis: {claims?.roles.join(", ") || "—"}</Menu.Label>
                <Menu.Item onClick={() => void sair()}>Sair</Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="sm">
        <ScrollArea>
          <Stack gap="md">
            {grupos(Boolean(claims?.roles.includes("administrar"))).map((grupo) => (
              <Stack key={grupo.titulo} gap={2}>
                <Text size="xs" fw={700} c="dimmed" tt="uppercase" px="xs">{grupo.titulo}</Text>
                {grupo.itens.map((item) => (
                  <NavLink key={item.para} component={Link} to={item.para} label={item.rotulo} active={ativo(item.para)} onClick={close} />
                ))}
              </Stack>
            ))}
          </Stack>
        </ScrollArea>
      </AppShell.Navbar>
      <AppShell.Main><Outlet /></AppShell.Main>
    </AppShell>
  );
}
