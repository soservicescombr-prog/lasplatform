# NetGuard — Atualização imediata

Data: 22/09/2026

## Entregas

- Corrigida a dependência SNMP (`pysnmp` 7.1.29 e `pyasn1` 0.6.3).
- Frontend voltou a compilar para produção, com ajustes de tipagem e imports.
- Worker Celery voltou a compartilhar a rede Docker de PostgreSQL e Redis.
- Adicionadas capacidades `NET_RAW` e `NET_ADMIN` ao worker para scans.
- Corrigido erro de execução do pentest pela ausência do modelo `Device`.
- Agentes agora autenticam com Bearer JWT, armazenam hash do token e persistem heartbeat e relatórios.
- Receptor syslog UDP inicia e encerra no ciclo de vida da API e compartilha o buffer usado pelos endpoints.
- Porta syslog UDP configurável e exposta pelo Compose.
- Alertas recém-criados agora enfileiram notificações por e-mail/webhook.
- Adicionadas configurações ausentes para OTX e AbuseIPDB.

## Validações executadas

- `python -m compileall -q app`: aprovado.
- Resolução completa de `backend/requirements.txt` com `pip --dry-run`: aprovada.
- Import real de `pysnmp.hlapi.v1arch.asyncio`: aprovado.
- `npm run build` no frontend: aprovado.
- Parse YAML do Docker Compose: aprovado.

## Próximos passos recomendados

1. Criar migrações Alembic versionadas e teste de upgrade/rollback.
2. Substituir credenciais padrão e exigir segredos fortes em produção.
3. Adicionar testes de integração com PostgreSQL, Redis, Celery, Nmap e tráfego syslog real.
4. Oferecer um perfil Docker opcional `host`/macvlan para descoberta L2, mantendo o perfil padrão funcional.
5. Persistir syslog em armazenamento durável; o buffer atual é volátil e limitado.

## Observação operacional

O ambiente desta validação não possui o binário Docker. O arquivo Compose foi validado sintaticamente, mas o stack completo deve passar por um smoke test em um host com Docker antes de produção.
