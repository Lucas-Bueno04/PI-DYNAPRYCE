import { Alert, Center, Loader } from "@mantine/core";

export function Carregando() {
  return <Center py="xl"><Loader aria-label="Carregando" /></Center>;
}

export function Falha({ children }: { children: string }) {
  return <Alert color="red" role="alert">{children}</Alert>;
}
