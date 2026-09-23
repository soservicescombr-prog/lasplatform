# NetGuard 1.3.0 — Dispositivos, Inventário e Discovery agendado

## Dispositivos

- corrige HTTP 500 na listagem quando o PostgreSQL/asyncpg devolve um campo
  `INET` como `IPv4Address` ou `IPv6Address`;
- a API converte o endereço para string antes da validação Pydantic;
- os dispositivos já descobertos passam a aparecer normalmente no frontend.

## Inventário / CMDB

- cada dispositivo novo ou atualizado pelo Discovery recebe uma entrada básica
  no inventário quando ainda não possuir uma;
- ao iniciar a API, dispositivos antigos sem item correspondente são
  adicionados automaticamente à CMDB;
- a tabela do inventário passa a exibir IP, hostname ou fabricante do
  dispositivo vinculado.

## Agendamento de Discovery

- frequências diária, semanal, quinzenal, mensal e dias personalizados;
- seleção de horário, dia da semana ou dia do mês;
- timezone configurável por `SCHEDULE_TIMEZONE`, com padrão
  `America/Sao_Paulo`;
- primeira execução imediata e cálculo persistente da próxima execução;
- Celery Beat verifica agendamentos vencidos a cada minuto;
- cada disparo gera um novo ScanJob rastreável na página Tasks;
- opção para desativar futuras execuções sem cancelar a execução atual.

## Operação

Reinicie API, worker e beat após atualizar. O frontend também deve ser
recompilado. Não há migração de banco, pois os campos de agendamento já
existiam no modelo.
