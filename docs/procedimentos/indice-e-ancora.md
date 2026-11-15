# Índice de inflação (BCB) e âncora externa da auditoria (F3.5)

Comandos da `cli` (mesma imagem da API). Agendar no ambiente (cron/systemd timer ou job do orquestrador); a agenda fica para a F1.42/F4.

## Índice de inflação (IPCA, série 433 do SGS)

`dynaprice indice atualizar --inicio AAAA-MM --fim AAAA-MM` — **rodar com a credencial do migrador** (`DYNAPRICE_DB_URL_FILE` apontando para `db_url_migrador`): a aplicação não tem permissão de gravar `core.indice_inflacao` (decisão de segurança da F1.5; testada). O índice é global (vale para todos os inquilinos).

- Mensal, depois da divulgação do IPCA (por volta do dia 10), por exemplo `--inicio <mês anterior> --fim <mês anterior>`.
- Nunca sobrescreve: valor já gravado e igual conta como "já existia"; **valor diferente (revisão da fonte ou digitação manual) sai como divergente, com código de saída 1**, e o gestor decide (fica a origem em `registrado_por`: `bcb:sgs433` ou `manual:...`).
- BCB fora do ar ou resposta ilegível: falha transitória (`ConectorIndisponivel`); repetir depois. A recalibração já avisa (`indice_ausente`) quando falta mês.

## Âncora externa da auditoria

A cadeia de hash por inquilino detecta edição isolada, mas quem reescreve da edição em diante refaz todos os hashes e a cadeia continua consistente. A âncora guarda **fora do banco** o par (seq, hash) e denuncia isso.

- `dynaprice auditoria ancorar` — grava a cabeça da cadeia de cada inquilino que tenha evento novo. Diário (ou a cada hora).
- `dynaprice auditoria verificar` — confere a cadeia e todas as âncoras; **sai com 1 e diz inquilino e evento** se algo não conferir. Semanal e depois de qualquer restauração de backup.
- Variável: `DYNAPRICE_ANCORA_ARQUIVO` (caminho do arquivo). O arquivo é só de acréscimo e cada linha leva o elo (hash) da anterior: editar ou remover uma linha do meio é detectado.

**O que faz a âncora ser externa é onde o arquivo mora:** outro host, montagem só de acréscimo (`chattr +a`/NFS exportado só para acréscimo) ou armazenamento com retenção imutável (object lock). No mesmo disco e com as mesmas permissões do banco, ela só detecta erro, não má-fé. Definir o destino na F4.1. Limite honesto: quem apaga o arquivo inteiro e a cadeia ao mesmo tempo não é detectado pela âncora em arquivo; aí vale um carimbo de tempo de terceiros (RFC 3161), que cabe no mesmo porto `AncoraExterna` sem mudar o resto.

Testes: `tests/adaptadores/test_ancora.py`, `tests/aplicacao/test_ancora.py` (inclui o caso da cadeia reescrita de forma consistente, que só a âncora denuncia).
