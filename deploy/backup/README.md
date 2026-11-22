# Backup e restauração (F1.39)

**Dump lógico:** `DESTINO=<pasta externa> PGHOST=pg ./backup.sh`, diário. `tests/integracao/test_restauracao.py` prova que esse formato restaura a última recomendação e a cadeia de auditoria.

**WAL (a configurar no piloto, ainda não testado):** `archive_mode=on` e `archive_command` copiando para o destino externo, para reduzir a perda entre dumps.

**Restaurar:**

1. Criar o banco vazio: `createdb -O dynaprice_migrador dynaprice_restaurado`.
2. `pg_restore -d dynaprice_restaurado <arquivo>`.
3. Conferir a cadeia de auditoria antes de apontar a aplicação para o banco restaurado.

**Retenção dos backups (D6):** 35 dias de WAL e mensais por 12 meses. RPO, RTO e cifragem do destino são definidos com o escritório na F1.42.
