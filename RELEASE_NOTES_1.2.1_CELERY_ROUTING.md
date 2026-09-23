# NetGuard 1.2.1 — Correção de roteamento Celery

## Sintoma corrigido

O discovery era criado e marcado como enviado, mas o worker não registrava
`Task netguard.run_discovery_scan received` e a execução permanecia pendente.

## Causa

`celery.send_task()` publicava sem fila explícita. O padrão nativo do Celery é a
fila `celery`, enquanto o comando operacional do NetGuard consumia somente
`default,scans,snmp,alerts`.

## Alterações

- fila padrão definida como `default`;
- filas `default`, `scans`, `snmp` e `alerts` declaradas centralmente;
- rotas de todas as tasks definidas centralmente;
- publicação de scans explicitamente direcionada à fila `scans`;
- health-check agora valida quais workers realmente consomem `scans`;
- `broker_connection_retry_on_startup=True` elimina o aviso de migração do
  Celery 6 e preserva a reconexão no startup.

## Após atualizar

Reinicie API, worker e beat. Jobs antigos que ficaram na fila incorreta não
devem ser usados como teste; crie um novo discovery após o restart.
