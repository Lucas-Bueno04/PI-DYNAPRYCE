# Princípios de engenharia do DynaPrice

Valem para todo código do repositório (backend e frontend). Foram definidos pelo responsável pelo projeto em 2026-11-09. Em caso de conflito, a ordem é: **artigo → ADRs → este documento → conveniência**.

## 1. Fonte de verdade

- **Cálculo, fórmula e base teórica vêm do artigo** (`Artigo_Precificacao_Dinamica_Lucas_Bueno_v2.pdf`). Todo método do núcleo cita no docstring a equação, proposição ou algoritmo que implementa (ex.: `Eq. (59)`, `Prop. 8`, `Algoritmo 3`).
- Divergência deliberada do artigo só por ADR (ex.: ADR-003 contrato como unidade, ADR-004 piso do regime sem dados).
- Na dúvida, segue-se a decisão recomendada no `plano.md` e se registra em `decisoes.md`.

## 2. Arquitetura (ADR-001)

- Clean Architecture em 4 anéis: `dominio` → `aplicacao` → `adaptadores` → `principal`. Dependências só para dentro, verificadas por import-linter.
- `dominio/` não faz I/O. Só `dominio/estimacao` pode importar numpy, pandas, scikit-learn e statsmodels.
- **A regra de preço tem uma única implementação** (`dominio/precificacao`), usada por cotação, recalibração e simulação.
- Composição em `principal.py` (Composition Root), com injeção de dependência manual e sem framework de DI.

## 3. Orientação a objetos e SOLID

| Princípio | Como se aplica aqui |
|---|---|
| **S**: responsabilidade única | Uma classe por conceito do artigo (`PoliticaDePreco`, `EquacoesDeTempo`, `RegraDeTransicao`, `GatilhoDeRevisao`, `EstimadorDeTarifa`). Caso de uso = uma classe com um método público (`executar`). |
| **O**: aberto/fechado | Variações entram por novas implementações de uma abstração, sem editar as existentes (estratégias de tarifa, conectores, exportadores). |
| **L**: substituição de Liskov | Toda implementação de porta respeita o contrato do `Protocol`, inclusive erros e invariantes, verificados por testes de contrato compartilhados (ex.: os mesmos testes rodam no conector de planilha, no sintético e no Domínio). |
| **I**: segregação de interfaces | Portas pequenas e por necessidade do caso de uso (`RepositorioDeContratos`, `RepositorioDePoliticas`…), nunca um "repositório genérico". |
| **D**: inversão de dependência | Casos de uso dependem de portas (`typing.Protocol`) do anel 2; adaptadores as implementam. |

**Modelagem:**
- **Objetos de valor** imutáveis (`@dataclass(frozen=True, slots=True)`) com validação no construtor: `Dinheiro`, `Horas`, `Competencia`, `Regime`, `Kappa` (1,0 ≤ κ ≤ κ̄, D12), `Tarifa`.
- **Entidades** com identidade e comportamento: `Contrato`, `Empresa`, `PoliticaVersao`, `Recomendacao`. As transições de estado são métodos da entidade (`recomendacao.aprovar(por, justificativa)`), nunca atribuição solta de campo.
- **Dinheiro sempre `Decimal`**, arredondado só em `Dinheiro` (ROUND_HALF_UP, 2 casas, D11). `float` só dentro de `dominio/estimacao`, convertido na fronteira.
- Invariantes do artigo vivem no tipo: um `Kappa` inválido não existe, e um `PoliticaVersao` publicado é imutável.

## 4. Padrões de projeto: só quando o caso pede

Um padrão entra quando existe a variação ou o problema que ele resolve, e o motivo fica num comentário de uma linha. Casos já identificados:

| Padrão | Onde | Por quê |
|---|---|---|
| **Strategy** | Origem da tarifa (`TarifaPorPrecoRevelado`, `TarifaAncoradaEmCusto`, `TarifaPorReceitaAlvo`); regra sem histórico (`PisoDoRegime`, futura `Vizinhanca`); arredondamento comercial | O artigo define alternativas intercambiáveis (seções 6.4, 6.5, 6.9) |
| **Repository + Unit of Work** | Persistência; a UoW fixa o tenant da transação | Isola o domínio do SQL e garante RLS por transação |
| **Adapter** | Conectores (Domínio, Omie, planilha, sintético), exportadores, emissor de JWT | Portas e adaptadores (seção 7.4) |
| **Template Method** | Pipeline do conector: extrair → validar → normalizar → quarentena | Passos fixos, extração variável |
| **State** (métodos de transição + tabela de transições válidas) | `Recomendacao`, `PoliticaVersao`, `Job` | Máquinas de estado do desenho; transição inválida é erro de domínio |
| **Factory** | Montagem de `PoliticaVersao` a partir do documento declarativo | Validação central do documento da política (Quadro 7) |
| **Composition Root** | `principal.py` | Uma única ligação de todas as dependências |

**Evitar:** herança profunda (prefira composição), singletons, service locator, classe "Util/Helper/Manager" genérica, e padrão sem variação real.

## 5. Boas práticas

- **Testes:** pirâmide com domínio (unitário + hypothesis com as proposições do artigo), aplicação (com fakes das portas), integração (testcontainers) e aceite (simulações da Ada). Um teste nomeia a equação ou proposição que verifica.
- **Tipagem:** mypy `strict` em `dominio/` e `aplicacao/`; nada de `Any` sem justificativa.
- **Erros:** exceções de domínio próprias (`ErroDeDominio` e derivadas); nunca `except Exception` silencioso.
- **Nomes:** português do domínio do artigo (`horas_padrao`, `piso`, `tarifa`, `preco_alvo`); siglas do artigo no docstring.
- **Funções pequenas**, sem efeito colateral escondido; comentários dizem o porquê, não o quê.
- **Segurança:** nenhum segredo no código, em log ou em teste; dado pessoal pseudonimizado na entrada (D8).
- **Commits:** pequenos, um por passo da Ada, mensagem com o id do passo.
- **Frontend:** componentes de função com responsabilidade única, hooks por feature, sem regra de preço no cliente (só exibe a decomposição vinda da API).

## 6. Processo de construção (definido pelo responsável em 2026-11-09, segunda sessão)

### 6.1 TDD em todo componente

Ciclo **vermelho → verde → refatorar**: o teste que descreve o comportamento (com a equação/proposição do artigo no nome ou no docstring) é escrito **antes** do código e precisa falhar primeiro. Só então entra o mínimo de código para passar, e por fim a refatoração com os testes verdes.

### 6.2 Portões de qualidade de cada componente

Todo componente implementado passa, antes de o passo fechar, por quatro verificações automáticas (alvo `backend` do perfil):

| Verificação | Ferramenta | Limite |
|---|---|---|
| Testes unitários (e de propriedade) | pytest + hypothesis | todos verdes |
| Complexidade ciclomática | `tests/qualidade/test_complexidade.py` (AST) + ruff `C901` | ≤ 8 por função/método |
| Número de linhas | `tests/qualidade/test_tamanho.py` | função/método ≤ 40 linhas; módulo ≤ 300 linhas; classe ≤ 200 linhas |
| Dependência entre componentes | import-linter (anéis) + `tests/qualidade/test_dependencias.py` (grimp) | sem ciclos entre módulos; acoplamento eferente ≤ 8 módulos internos por módulo (fachadas `__init__` que só reexportam ficam fora da contagem; o teste verifica que são puras) |

Estourou um limite: **refatorar** (extrair método/classe, Strategy, State, Factory, Template Method, conforme a seção 4) em vez de afrouxar o limite. Exceção só com justificativa numa lista explícita do próprio teste.

### 6.3 Fluxo de trabalho

- **Commits e push:** o agente não faz commit nem push; o responsável faz tudo em lote depois.
- **Aprovações:** o responsável delegou (2026-11-09) as aprovações de passo e de portão ao agente, que segue o projeto do início ao fim sem parar para aprovação, registrando cada decisão tomada por delegação em `decisoes.md`.
- **Bloqueios:** o que depender de algo externo (dados reais do escritório, acesso ao Domínio, remoto no GitHub, implantação no escritório) vai para o fim da fila ou segue pelo contorno estatisticamente e estrategicamente mais viável (ex.: carteira sintética calibrada no artigo no lugar dos dados reais), registrado como decisão.
