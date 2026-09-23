# NetGuard 1.5.0 — Detalhes, métricas e disponibilidade

## Páginas de detalhes

- Página dedicada de dispositivo, acessível pela lista de dispositivos.
- Gráficos de CPU, memória, disco, tráfego e utilização de interfaces.
- Interfaces SNMP, inventário, agente vinculado, vulnerabilidades e alertas.
- Página dedicada de agente, acessível pela lista de agentes.
- Gráficos de CPU, memória, disco, load e evolução de vulnerabilidades.
- Informações do host, dispositivo vinculado, relatório e alertas de disponibilidade.
- Períodos de 6 horas, 24 horas, 7 dias e 30 dias.

## Disponibilidade e alertas

- Verificação de dispositivos por ICMP e portas TCP conhecidas.
- Três falhas consecutivas por padrão antes de declarar um dispositivo offline.
- Detecção de agente offline após 180 segundos sem heartbeat.
- Alertas `device_offline` e `agent_offline` independentes de regras manuais.
- Resolução automática do alerta quando o dispositivo/agente retorna.
- Contadores separados de dispositivos e agentes offline no painel de alertas.
- Dashboard, agentes e alertas atualizados automaticamente a cada 30 segundos.
- Retenção configurável de métricas, padrão de 30 dias.

## Agente 1.1.0

- Heartbeat com CPU, memória, disco, load, rede e boot time.
- Dependência `psutil` adicionada.
- Correção do entry point `netguard-agent`.

## Banco de dados

As tabelas `device_metrics` e `agent_metrics` são criadas automaticamente pelo
startup da API. Não é necessária migração manual nesta versão.

## Configurações

- `AGENT_OFFLINE_SECONDS=180`
- `DEVICE_OFFLINE_FAILURES=3`
- `METRICS_RETENTION_DAYS=30`
- `AVAILABILITY_CONCURRENCY=50`
