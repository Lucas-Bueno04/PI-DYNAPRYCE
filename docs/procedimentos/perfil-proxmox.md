# Perfil Proxmox (F4.1) — RASCUNHO para aprovação

Estado: **desenho sem inventário**. O Proxmox (192.168.90.240:8006) não respondeu à consulta de leitura em 2026-11-14 (timeout), então nós, armazenamento, pontes e modelos ainda não foram conferidos. Nada foi criado nem alterado no ambiente.

## Mapa de nós do desenho de implantação → Proxmox

| Nó do desenho | Proposta | Observação |
|---|---|---|
| `dp_proxy` + `dp_web` | contêiner `web` (nginx 1.30 sem root, TLS) | mesma imagem do compose (`frontend/Dockerfile`) |
| `dp_worker` (api + worker) | contêineres `api` e `worker` | mesma imagem `dynaprice-backend` (diff vazio em `dominio/` e `aplicacao/`, critério F4.2) |
| `dp_pg` | PostgreSQL 18.6 em VM ou LXC dedicado, disco próprio | sem TLS no compose local: **ligar TLS e `verify-full` aqui** (dívida) |
| `dp_bkp` | destino de backup em outro armazenamento/host | `deploy/backup/backup.sh` (pg_dump + WAL) |
| `dp_src` | acesso de rede ao Domínio/Omie | depende de F0.21 (ODBC/licença) e de D9 |

Recomendação: uma VM Linux com Docker/Compose reproduz o ambiente validado (menor risco) antes de pensar em LXC por serviço; isolar rede: só o `web` publica porta, `api` e `pg` em rede interna (como no compose).

## RPO/RTO propostos (a aprovar)

RPO 15 min (arquivamento de WAL) e RTO 4 h (restauração ensaiada em F4.3). Conferir se o armazenamento de backup cobre 35 dias de WAL e dumps diários.

## Destino da âncora da auditoria

Arquivo só de acréscimo **fora** do host do banco (ver `indice-e-ancora.md`).

## O que preciso de você para seguir (F4.2 em diante)

1. Restabelecer o acesso de leitura ao Proxmox (rede/VPN/credencial do MCP) para o inventário.
2. Aprovar RPO/RTO, o nó/armazenamento e a faixa de rede.
3. Aprovar cada mudança no ambiente (criação de VM/contêiner, firewall, backup). Todo passo segue o procedimento de reversão: parar contêineres e restaurar backup.
4. F4.4 (um mês de disponibilidade medida) só começa depois da implantação e não se antecipa.
