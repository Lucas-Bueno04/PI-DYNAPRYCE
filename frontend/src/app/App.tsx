import { Route, Routes } from "react-router";
import { Acompanhamento } from "../features/acompanhamento/Acompanhamento";
import { Administracao } from "../features/admin/Administracao";
import { Entrar } from "../features/auth/Entrar";
import { Guarda } from "../features/auth/Guarda";
import { Redefinir } from "../features/auth/Redefinir";
import { Clientes } from "../features/clientes/Clientes";
import { Cotacao } from "../features/cotacao/Cotacao";
import { Diagnostico } from "../features/diagnostico/Diagnostico";
import { Laboratorio } from "../features/laboratorio/Laboratorio";
import { Painel } from "../features/painel/Painel";
import { Politicas } from "../features/politicas/Politicas";
import { Provisorios } from "../features/provisorios/Provisorios";
import { Recomendacoes } from "../features/recomendacoes/Recomendacoes";
import { Usuarios } from "../features/usuarios/Usuarios";
import { useCompetencia } from "./competencia";
import { Moldura } from "./Moldura";

/** Telas que pedem a competência por propriedade recebem a escolhida no cabeçalho. */
function ComCompetencia({ tela: Tela }: { tela: (props: { referencia: string }) => React.ReactNode }) {
  const { competencia } = useCompetencia();
  return <Tela referencia={competencia} />;
}

function AdministracaoDaCompetencia() {
  const { competencia } = useCompetencia();
  return <Administracao competencia={competencia} />;
}

export function App() {
  return (
    <Routes>
      <Route path="/entrar" element={<Entrar />} />
      <Route path="/redefinir" element={<Redefinir />} />
      <Route element={<Guarda><Moldura /></Guarda>}>
        <Route path="/" element={<Painel />} />
        <Route path="/clientes" element={<Clientes />} />
        <Route path="/recomendacoes" element={<Recomendacoes />} />
        <Route path="/cotacao" element={<Cotacao />} />
        <Route path="/politicas" element={<Politicas />} />
        <Route path="/laboratorio" element={<ComCompetencia tela={Laboratorio} />} />
        <Route path="/acompanhamento" element={<Acompanhamento />} />
        <Route path="/provisorios" element={<ComCompetencia tela={Provisorios} />} />
        <Route path="/diagnostico" element={<ComCompetencia tela={Diagnostico} />} />
        <Route path="/usuarios" element={<Guarda papel="administrar"><Usuarios /></Guarda>} />
        <Route path="/administracao" element={<Guarda papel="administrar"><AdministracaoDaCompetencia /></Guarda>} />
      </Route>
    </Routes>
  );
}
