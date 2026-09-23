# NetGuard 1.4.1 — Hotfix do módulo de Logs

Corrige dois problemas observados na implantação da versão 1.4.0:

1. **Inicialização com múltiplos workers:** a criação automática das tabelas
   agora utiliza `pg_advisory_xact_lock`, impedindo que vários processos tentem
   criar `syslog_events` ao mesmo tempo.
2. **Pesquisa por período:** datas ISO 8601 com timezone, como valores terminados
   em `Z`, são convertidas para UTC sem timezone antes da consulta em colunas
   `TIMESTAMP WITHOUT TIME ZONE`.

Não é necessário remover ou recriar as tabelas. A tabela criada com sucesso por
um dos workers pode ser mantida.
