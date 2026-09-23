# NetGuard 1.2.4 — Compatibilidade PostgreSQL INET

## Sintoma corrigido

Após o Nmap descobrir hosts, a persistência falhava com:

```text
operator does not exist: inet = character varying
```

## Causa

O campo `devices.ip_address` usa o tipo nativo PostgreSQL `INET`, mas algumas
consultas enviavam endereços IP como parâmetros `VARCHAR`. O PostgreSQL não
realiza implicitamente essa comparação em todas as combinações de driver e
versão.

## Alterações

- conversão SQL explícita de texto para `INET`;
- correção aplicada em Discovery, Vulnerability, Pentest e correlação Syslog;
- teste de regressão verifica que a consulta contém `CAST(... AS INET)` e não
  envia o parâmetro como comparação direta `VARCHAR`.
