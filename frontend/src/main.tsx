import "@mantine/core/styles.css";
import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { App } from "./app/App";
import { ProvedorDeCompetencia } from "./app/competencia";
import { tema } from "./app/tema";

const consultas = new QueryClient();
const raiz = document.getElementById("raiz");
if (raiz) {
  createRoot(raiz).render(
    <StrictMode>
      <MantineProvider theme={tema} defaultColorScheme="auto">
        <QueryClientProvider client={consultas}>
          <BrowserRouter>
            <ProvedorDeCompetencia>
              <App />
            </ProvedorDeCompetencia>
          </BrowserRouter>
        </QueryClientProvider>
      </MantineProvider>
    </StrictMode>,
  );
}
