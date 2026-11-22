# Layout da planilha pedida ao escritório (F0.20)

Plano B do conector do Domínio (F0.21) e carga do laboratório (F0.22). Seis arquivos CSV em **UTF-8**, separador **`;`**, decimal com **vírgula**, sem separador de milhar, competência no formato **AAAA-MM**. Salvar fora do repositório, numa pasta `dados/` (listada no `.gitignore`).

**Minimização (RNF05, D8).** Pedimos só o necessário para medir o esforço:
- o CPF/CNPJ da empresa vira pseudônimo (HMAC-SHA256) **na leitura**; o documento não entra em nenhuma estrutura do sistema;
- razão social, nomes de colaboradores e qualquer coluna fora da lista abaixo são **ignorados**;
- da folha, só **contagens** por empresa e mês. Arquivo com linhas de empregado ou coluna com CPF/salário é **recusado** pelo leitor.

| Arquivo | Colunas | Observação |
|---|---|---|
| `empresas.csv` | `documento`; `regime` (MEI, SN, LP, LR); `departamentos` (`fiscal`, `contabil`, `folha` separados por `\|`) | um CNPJ/CPF por linha; departamentos atendidos pelo escritório |
| `contratos.csv` | `contrato`; `honorario_vigente`; `mes_reajuste` (1–12, vazio se não houver); `provisorio` (S/N); `kappa` (opcional, 1,0 a 1,2) | código interno do contrato (não pessoal) |
| `vinculos.csv` | `documento`; `contrato`; `desde`; `ate` (vazio se vigente); `principal` (S/N) | uma empresa em um contrato por competência; uma principal por contrato |
| `movimento.csv` | `documento`; `competencia`; `notas_entrada`; `notas_saida`; `lancamentos_manuais`; `lancamentos_automaticos`; `empregados`; `admissoes`; `rescisoes` | contagens mensais (Tabela 4 do artigo) |
| `horas.csv` | `documento`; `competencia`; `departamento`; `horas` | horas registradas somadas por empresa, mês e departamento, sem identificar o colaborador |
| `honorarios.csv` | `contrato`; `competencia`; `valor` | honorário cobrado no mês (Omie) |

Execução: `DYNAPRICE_CHAVE_PSEUDONIMO=<chave com 16+ caracteres> dynaprice lab relatorio --fonte planilha --entrada dados/escritorio --saida dados/relatorio`. A chave fica com o escritório (cofre de senhas), nunca no repositório; trocar a chave muda todos os pseudônimos.
