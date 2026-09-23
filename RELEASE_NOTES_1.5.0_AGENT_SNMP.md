# NetGuard 1.5.0 — Agentes, baselines e SNMP resiliente

## Entregas

- Coleta do agente: CPU, memória, disco, load average, processos, rede e I/O de disco.
- Séries temporais e páginas de detalhes para agentes e dispositivos.
- Baseline adaptativo por métrica, com fase de aprendizado e alertas de desvio.
- Coleta incremental de arquivos de log configuráveis no painel do agente.
- Logs do agente integrados à pesquisa, métricas e alertas do módulo Logs.
- Alertas automáticos para agente ou dispositivo offline, com resolução automática.
- SNMP em lote convertido em fan-out: uma tarefa curta despacha uma coleta por dispositivo.
- Timeout individual SNMP e suporte preferencial a contadores de interface de 64 bits.
- Métricas SNMP genéricas de CPU/memória/armazenamento e Cisco CPU.
- Painel de dispositivo com interfaces, utilização, erros, logs e alertas.

## Syslog 514

No Docker, mantenha `SYSLOG_PORT=5514` e `SYSLOG_EXTERNAL_PORT=514`: o host publica
514 UDP/TCP para 5514 no container. Em execução direta do Uvicorn, defina
`SYSLOG_PORT=514` e conceda `CAP_NET_BIND_SERVICE` (ou execute atrás de redirecionamento
de porta). Consulte `/api/v1/logs/receiver/health` para confirmar UDP/TCP e a porta real.

## Atualização

Após extrair, reinstale o agente (`pip install -U ./agent`), reinicie API, Celery worker
e Celery Beat. As novas tabelas são criadas no startup protegido pelo advisory lock.
