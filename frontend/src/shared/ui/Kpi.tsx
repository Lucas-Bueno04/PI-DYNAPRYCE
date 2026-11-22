import { Card, Text } from "@mantine/core";
import type { ReactNode } from "react";

export function Kpi({ rotulo, valor, detalhe, cor }: { rotulo: string; valor: ReactNode; detalhe?: ReactNode; cor?: string }) {
  return (
    <Card>
      <Text size="xs" fw={700} c="dimmed" tt="uppercase">{rotulo}</Text>
      <Text fz={28} fw={700} c={cor} mt={4}>{valor}</Text>
      {detalhe && <Text size="sm" c="dimmed" mt={2}>{detalhe}</Text>}
    </Card>
  );
}
