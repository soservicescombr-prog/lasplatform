# NetGuard 1.5.3 — Migração de métricas e diagnóstico do agente

## Correções

- Adiciona migração idempotente das tabelas `device_metrics` e `agent_metrics`.
- Corrige `column device_metrics.details does not exist`.
- Corrige `column agent_metrics.load_15m does not exist` e todas as demais colunas novas da coleta 1.5.x.
- A migração é protegida pelo mesmo advisory lock do startup com múltiplos workers.
- O agente agora imprime o HTTP status e parte da resposta da API quando heartbeat ou relatório forem rejeitados.

## Operação

Reinicie primeiro a API. No startup, a migração será aplicada automaticamente.
Em seguida, reinstale/reinicie o agente para habilitar o diagnóstico detalhado.
