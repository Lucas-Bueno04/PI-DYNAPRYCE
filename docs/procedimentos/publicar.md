# Publicação no piloto

**Situação:** a confirmar. O destino depende da TI do escritório (D9) e do remoto no GitHub (CI). Quem publica é o responsável pelo projeto; o agente não publica.

1. Construir e testar a imagem: `docker build -t dynaprice-backend:<versão> backend`.
2. Fazer o backup do banco antes de migrar (F1.39).
3. Atualizar `DYNAPRICE_VERSAO` e subir: `docker compose -f deploy/compose/compose.yaml up -d`.
4. Conferir a saúde: `GET /api/v1/saude` responde 200.

**Reversão:** voltar `DYNAPRICE_VERSAO` à versão anterior e restaurar o backup se a migração tiver mudado o esquema.
