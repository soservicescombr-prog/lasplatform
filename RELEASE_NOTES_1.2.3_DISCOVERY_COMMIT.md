# NetGuard 1.2.3 — Confirmação do Discovery antes da fila

## Sintoma corrigido

O worker recebia `netguard.run_discovery_scan`, mas finalizava em poucos
milissegundos com `status: cancelled`. Não havia execução do Nmap, dispositivos
descobertos nem atualização percentual.

## Causa

A API publicava a mensagem no Redis antes de confirmar no PostgreSQL a
transação que criava o `scan_job`. O worker podia receber a mensagem antes de o
registro ficar visível e falhava ao realizar a transição `pending -> running`.

## Alterações

- o job é confirmado no PostgreSQL antes da publicação no Celery;
- a atualização posterior grava somente o ID da task, sem sobrescrever o
  progresso que o worker já possa ter registrado;
- cancelamento real, job ausente e entrega duplicada agora têm mensagens
  distintas;
- cada atualização de progresso também aparece no log do worker;
- teste de regressão garante que o commit ocorre antes do `send_task()`.
