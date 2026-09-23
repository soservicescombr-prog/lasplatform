# NetGuard 1.2.2 — Event loop persistente nos workers

## Sintoma corrigido

O worker recebia o discovery, mas a execução falhava com:

```text
got Future <Future pending ...> attached to a different loop
```

## Causa

As tasks síncronas do Celery criavam e fechavam um event loop para cada acesso
assíncrono. O pool SQLAlchemy/asyncpg podia reutilizar uma conexão criada no
loop anterior, o que não é permitido pelo asyncio.

## Alterações

- runner assíncrono único e persistente por processo filho do Celery;
- proteção para o modelo `prefork`, descartando loops herdados do processo pai;
- Discovery, Vulnerability, Pentest, SNMP e Alerts usam o mesmo runner;
- testes de regressão garantem que chamadas consecutivas reutilizem o loop.

## Operação obrigatória

Após atualizar, encerre e inicie novamente todos os processos Celery. Apenas
recarregar a API não elimina conexões asyncpg vinculadas aos loops antigos.
