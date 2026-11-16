import { Alert, Button, Group, SimpleGrid, Stack, Text, Textarea, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import { useEffect, useState } from "react";
import { api } from "../../shared/api/cliente";
import { moeda, numero, percentual } from "../../shared/lib/formato";

interface Resultado {
  contratos: number;
  receita_vigente: string;
  receita_alvo: string;
  receita_ciclo_1: string;
  fracao_no_piso: string;
  fracao_no_teto: string;
  fracao_congelados: string;
  fracao_gatilho: string;
  ciclos_mediana: number;
  ciclos_maximo: number;
}
type Documento = Record<string, unknown>;

function lerDocumento(texto: string): Documento | null {
  try {
    return JSON.parse(texto) as Documento;
  } catch {
    return null;
  }
}

function tarifaDo(documento: Documento | null): unknown {
  return (documento?.tarifa_hora_padrao as { valor?: unknown } | undefined)?.valor;
}

export function Laboratorio({ referencia }: { referencia: string }) {
  const [texto, setTexto] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const { data } = useQuery({
    queryKey: ["politicas"],
    queryFn: async () => (await api.GET("/api/v1/politicas")).data ?? [],
  });

  // Preenche uma vez: política que chega depois não pode apagar o que a pessoa já editou.
  useEffect(() => {
    const inicial = data?.[0];
    if (inicial) setTexto((atual) => atual || JSON.stringify(inicial.documento, null, 2));
  }, [data]);

  function documentoValido(): Documento | null {
    setErro(null);
    const documento = lerDocumento(texto);
    if (documento === null) setErro("O documento não é um JSON válido.");
    return documento;
  }

  async function simular() {
    const documento = documentoValido();
    if (documento === null) return;
    const { data: corpo } = await api.POST("/api/v1/laboratorio/simulacoes", {
      body: { documento, referencia },
    });
    if (!corpo) return setErro("A simulação falhou. Confira o documento.");
    setResultado(corpo as unknown as Resultado);
  }

  async function guardar() {
    const documento = documentoValido();
    if (documento === null) return;
    const { data: corpo } = await api.POST("/api/v1/politicas", { body: { documento } });
    if (!corpo) return setErro("O rascunho foi recusado. Confira o documento.");
    setAviso(`Rascunho v${corpo.versao} guardado`);
  }

  return (
    <Stack>
      <Title order={2}>Laboratório</Title>
      {erro && <Alert color="red" role="alert">{erro}</Alert>}
      {aviso && <Text>{aviso}</Text>}
      <Textarea label="Documento da política" rows={14} value={texto} onChange={(e) => setTexto(e.target.value)} />
      <Group>
        <Button onClick={() => void simular()}>Simular</Button>
        <Button variant="default" onClick={() => void guardar()}>Guardar rascunho</Button>
      </Group>
      {resultado && (
        <Stack data-testid="resultado">
          <SimpleGrid cols={{ base: 2, md: 4 }}>
            <Text>Contratos: {resultado.contratos}</Text>
            <Text>τ da política: {numero(tarifaDo(lerDocumento(texto)) as string)}</Text>
            <Text>Receita vigente: {moeda(resultado.receita_vigente)}</Text>
            <Text>Receita no alvo: {moeda(resultado.receita_alvo)}</Text>
            <Text>Receita no ciclo 1: {moeda(resultado.receita_ciclo_1)}</Text>
            <Text>No piso: {percentual(resultado.fracao_no_piso)}</Text>
            <Text>No teto: {percentual(resultado.fracao_no_teto)}</Text>
            <Text>Congelados: {percentual(resultado.fracao_congelados)}</Text>
            <Text>Com gatilho: {percentual(resultado.fracao_gatilho)}</Text>
            <Text>Ciclos até o alvo (mediana): {numero(resultado.ciclos_mediana)}</Text>
            <Text>Ciclos até o alvo (máximo): {resultado.ciclos_maximo}</Text>
          </SimpleGrid>
          <ReactECharts
            option={{
              xAxis: { type: "category", data: ["Vigente", "Ciclo 1", "Alvo"] },
              yAxis: { type: "value" },
              series: [{ type: "bar", data: [resultado.receita_vigente, resultado.receita_ciclo_1, resultado.receita_alvo].map(Number) }],
            }}
          />
        </Stack>
      )}
    </Stack>
  );
}
