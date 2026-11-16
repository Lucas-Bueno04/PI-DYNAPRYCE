import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Badge, Button, Group, NativeSelect, SimpleGrid, Stack, Text, TextInput, Title } from "@mantine/core";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { api } from "../../shared/api/cliente";
import { moeda, percentual } from "../../shared/lib/formato";

const REGIMES = [
  { value: "MEI", label: "MEI" },
  { value: "SN", label: "Simples Nacional" },
  { value: "LP", label: "Lucro Presumido" },
  { value: "LR", label: "Lucro Real" },
];

const esquema = z
  .object({
    regime: z.enum(["MEI", "SN", "LP", "LR"], { error: "Informe o regime tributário" }),
    meses: z.string().regex(/^\d{1,3}$/, "Informe um número inteiro de meses"),
    horas: z.string(),
    kappa: z.string(),
  })
  .superRefine((v, ctx) => {
    if (Number(v.meses) > 0 && v.horas.trim() === "") {
      ctx.addIssue({ code: "custom", path: ["horas"], message: "Informe as horas-padrão mensais" });
    }
  });
type Campos = z.infer<typeof esquema>;

interface Decomposicao {
  nivel_informacao: number;
  piso: string;
  base_propria: string | null;
  credibilidade_z: string;
  kappa: string;
  motivo: string;
}
interface Resultado {
  preco: string;
  politica_versao: number;
  provisorio: boolean;
  decomposicao: Decomposicao;
}

function corpoDoPedido(v: Campos) {
  const horas = v.horas.trim();
  const kappa = v.kappa.trim();
  return {
    regime: v.regime,
    meses: Number(v.meses),
    ...(horas ? { horas_padrao: horas } : {}),
    ...(kappa ? { kappa } : {}),
  };
}

function mensagemDeErro(status: number): string {
  if (status === 409) return "Não há política publicada. Publique uma política antes de cotar.";
  return "A cotação foi recusada. Confira o regime, os meses, as horas e o κ.";
}

function Painel({ resultado }: { resultado: Resultado }) {
  const d = resultado.decomposicao;
  return (
    <Stack data-testid="cotacao">
      <Group>
        <Title order={3}>{moeda(resultado.preco)}</Title>
        <Badge color={resultado.provisorio ? "yellow" : "green"}>
          {resultado.provisorio ? "Provisório" : "Definitivo"}
        </Badge>
        <Text c="dimmed">política v{resultado.politica_versao}</Text>
      </Group>
      <Text>{d.motivo}</Text>
      <SimpleGrid cols={{ base: 2, md: 4 }}>
        <Text>Piso do regime: {moeda(d.piso)}</Text>
        <Text>Base pelo esforço: {moeda(d.base_propria)}</Text>
        <Text>Credibilidade Z: {percentual(d.credibilidade_z)}</Text>
        <Text>κ: {d.kappa}</Text>
      </SimpleGrid>
    </Stack>
  );
}

export function Cotacao() {
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const { register, handleSubmit, formState } = useForm<Campos>({
    resolver: zodResolver(esquema),
    defaultValues: { meses: "0", horas: "", kappa: "" },
  });
  const erros = formState.errors;

  async function cotar(valores: Campos) {
    setErro(null);
    setResultado(null);
    const { data, response } = await api.POST("/api/v1/cotacoes", { body: corpoDoPedido(valores) });
    if (!data) return setErro(mensagemDeErro(response.status));
    setResultado(data as unknown as Resultado);
  }

  return (
    <Stack>
      <Title order={2}>Cotação</Title>
      <form onSubmit={(e) => void handleSubmit(cotar)(e)} noValidate>
        <Stack maw={420}>
          <NativeSelect
            label="Regime tributário"
            data={[{ value: "", label: "Selecione" }, ...REGIMES]}
            error={erros.regime?.message}
            {...register("regime")}
          />
          <TextInput label="Meses de histórico" inputMode="numeric" error={erros.meses?.message} {...register("meses")} />
          <TextInput label="Horas-padrão mensais" inputMode="decimal" error={erros.horas?.message} {...register("horas")} />
          <TextInput label="κ (opcional)" inputMode="decimal" error={erros.kappa?.message} {...register("kappa")} />
          <Button type="submit">Cotar</Button>
        </Stack>
      </form>
      {erro && <Alert color="red" role="alert">{erro}</Alert>}
      {resultado && <Painel resultado={resultado} />}
    </Stack>
  );
}
