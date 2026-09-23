# NetGuard 1.6.0 — Ingestão verificável e alertas sustentados

## Corrigido

- Rotação segura do token de agente pelo detalhe do agente; o token anterior é revogado imediatamente.
- Diagnóstico do motivo do `401` no log da API sem registrar o token.
- Heartbeat e métricas do agente a cada 15 segundos, inclusive após configuração remota.
- Página do agente com janelas de 5 min, 15 min, 1 h, 6 h, 24 h, 7 d e 30 d.
- Regra de baseline: alerta somente com 10 anomalias em 5 minutos, abrangendo pelo menos 180 segundos.
- Métricas derivadas de logs usam a mesma cobertura temporal mínima de 180 segundos.
- Coleta SNMP periódica alterada de 15 para 5 minutos.
- Falhas e timeouts SNMP passam a ser persistidos em `snmp_collections`.

## Diagnóstico e prova de persistência

- `GET /api/v1/logs/ingestion/health`: totais, última gravação e registros dos últimos 5 minutos para Syslog, métricas de agente, métricas de dispositivo e coletas SNMP.
- `POST /api/v1/logs/receiver/test`: injeta uma mensagem sintética pelo parser real e confirma o ID gravado no PostgreSQL.
- A página de Logs mostra contadores recebidos/persistidos/falhos e os totais reais do banco.

## Banco de dados

Na primeira inicialização da API, a migração idempotente adiciona `log_metrics.minimum_span_seconds` e o `create_all` cria `agent_anomaly_events`. A API precisa iniciar antes do worker Celery.

## Atualização obrigatória

1. Substitua os arquivos do pacote.
2. Reinicie a API e aguarde o startup concluir.
3. Reinicie Celery worker e Celery beat (o nome do agendamento SNMP mudou para `bulk-snmp-collection-5m`).
4. No detalhe do agente, clique em **Novo token**, copie-o para `~/.netguard-agent.json` no host e reinicie o agente.
5. Em Logs, clique em **Testar persistência**. O retorno deve trazer `status: persisted` e um `event_id`.

## Validação da entrega

- Backend: 25 testes aprovados.
- Frontend: TypeScript e build de produção aprovados.
- Bundle: `frontend/dist/assets/index-CYvJTWmi.js`.
