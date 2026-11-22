import { Alert, Button, Group, Modal, Stack, Table, Text, Textarea, TextInput } from "@mantine/core";
import { useState } from "react";
import type { components } from "../../shared/api/esquema";
import { api } from "../../shared/api/cliente";
import { useClaims } from "../../shared/api/sessao";
import { moeda, numero } from "../../shared/lib/formato";

type Recomendacao = components["schemas"]["RespostaRecomendacao"];
interface Decomposicao {
  preco_alvo?: string;
  nivel_informacao?: number;
  horas_padrao?: string | null;
  horas_por_departamento?: Record<string, string>;
  regime?: string;
  tarifa?: string;
  piso?: string;
  kappa?: string;
}
type Decisao = components["schemas"]["CorpoDecisao"];

interface Propriedades {
  item: Recomendacao;
  aoFechar: () => void;
  aoDecidir: () => void;
}

export function Detalhe({ item, aoFechar, aoDecidir }: Propriedades) {
  const claims = useClaims();
  const [erro, setErro] = useState<string | null>(null);
  const [kappa, setKappa] = useState("");
  const [justificativa, setJustificativa] = useState("");
  const [motivo, setMotivo] = useState("");
  const d = item.decomposicao as Decomposicao;

  async function decidir(corpo: Omit<Decisao, "versao">) {
    setErro(null);
    if (!claims?.mfa) {
      setErro("Sua sessão não tem TOTP verificado. Saia e entre de novo com o código.");
      return;
    }
    const { response } = await api.POST("/api/v1/recomendacoes/{recomendacao_id}/decisao", {
      params: { path: { recomendacao_id: item.id } },
      body: { versao: item.versao, ...corpo } as Decisao,
    });
    if (response.ok) return aoDecidir();
    setErro(response.status === 409 ? "A recomendação mudou desde a leitura. Atualize a fila." : "Não foi possível registrar a decisão.");
  }

  function rejeitar() {
    if (!motivo.trim()) return setErro("Informe o motivo da rejeição.");
    void decidir({ acao: "rejeitar", motivo } as Omit<Decisao, "versao">);
  }

  return (
    <Modal opened onClose={aoFechar} title={`Contrato ${item.contrato_id}`} size="lg">
      <Stack>
        {erro && <Alert color="red" role="alert">{erro}</Alert>}
        <Table>
          <Table.Tbody>
            <Table.Tr><Table.Td>Preço-alvo</Table.Td><Table.Td>{moeda(d.preco_alvo)}</Table.Td></Table.Tr>
            <Table.Tr><Table.Td>Informação</Table.Td><Table.Td>Nível {d.nivel_informacao}</Table.Td></Table.Tr>
            <Table.Tr><Table.Td>Regime e piso</Table.Td><Table.Td>{d.regime} · {moeda(d.piso)}</Table.Td></Table.Tr>
            <Table.Tr><Table.Td>Horas-padrão</Table.Td><Table.Td>{numero(d.horas_padrao)}</Table.Td></Table.Tr>
            {Object.entries(d.horas_por_departamento ?? {}).map(([departamento, horas]) => (
              <Table.Tr key={departamento}><Table.Td>{departamento}</Table.Td><Table.Td>{numero(horas)}</Table.Td></Table.Tr>
            ))}
            <Table.Tr><Table.Td>τ</Table.Td><Table.Td>{numero(d.tarifa)}</Table.Td></Table.Tr>
            <Table.Tr><Table.Td>κ</Table.Td><Table.Td>{numero(d.kappa)}</Table.Td></Table.Tr>
          </Table.Tbody>
        </Table>
        <Text>Trajetória: {item.trajetoria.map((p) => moeda(p)).join(" → ")}</Text>
        <Button onClick={() => void decidir({ acao: "aprovar" } as Omit<Decisao, "versao">)}>Aprovar</Button>
        <Group grow align="flex-end">
          <TextInput label="Novo κ" value={kappa} onChange={(e) => setKappa(e.target.value)} />
          <TextInput label="Justificativa" value={justificativa} onChange={(e) => setJustificativa(e.target.value)} />
          <Button variant="default" onClick={() => void decidir({ acao: "ajustar", kappa, justificativa } as Omit<Decisao, "versao">)}>Ajustar κ</Button>
        </Group>
        <Textarea label="Motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
        <Button color="red" variant="light" onClick={rejeitar}>Rejeitar</Button>
      </Stack>
    </Modal>
  );
}
