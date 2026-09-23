# Módulo de Logs e Syslog

## Fluxo

1. Dispositivos enviam Syslog para o IP do NetGuard na porta 514 UDP ou TCP.
2. O Docker encaminha a porta externa 514 para a porta interna 5514.
3. O backend interpreta RFC 3164/5424 e persiste os eventos no PostgreSQL.
4. A página **Logs** permite combinar texto, nível, facility, host/IP,
   aplicação, protocolo, período e propriedades.
5. **Criar métrica desta pesquisa** salva a consulta como uma contagem em
   janela móvel.
6. O Celery avalia a métrica a cada minuto e cria um alerta quando o limiar é
   alcançado. Quando a condição normaliza, o alerta é resolvido automaticamente.

## Configuração

```env
SYSLOG_ENABLED=true
SYSLOG_HOST=0.0.0.0
SYSLOG_PORT=5514
SYSLOG_EXTERNAL_PORT=514
SYSLOG_UDP_ENABLED=true
SYSLOG_TCP_ENABLED=true
SYSLOG_RETENTION_DAYS=30
```

No modo Docker, confirme a publicação das duas portas:

```yaml
ports:
  - "514:5514/udp"
  - "514:5514/tcp"
```

Se o backend for executado diretamente e precisar escutar a porta 514, conceda
somente a capability necessária ao binário Python ou use um redirecionamento
de porta. Não é necessário executar Celery como root.

## Testes de ingestão

UDP:

```bash
logger --server IP_DO_NETGUARD --port 514 --udp --tag netguard-test \
  "failed password para usuario de teste"
```

TCP:

```bash
logger --server IP_DO_NETGUARD --port 514 --tcp --tag netguard-test \
  "disk full teste controlado"
```

Saúde do receptor, com autenticação JWT:

```text
GET /api/v1/logs/receiver/health
```

## Pesquisa e propriedades

- Termos entre aspas são tratados como uma expressão: `"failed password"`.
- Vários termos podem usar correspondência **Todos** ou **Qualquer**.
- Campos de structured data RFC 5424 são armazenados em `properties` e podem
  ser consultados por chave e valor.
- A busca textual considera mensagem, mensagem original, hostname e aplicação.

## Métricas e alertas

Uma métrica armazena:

- filtros da pesquisa;
- janela móvel de 1 minuto a 7 dias;
- operador e limiar;
- severidade;
- cooldown;
- opções de e-mail e webhook.

As métricas usam o worker Celery na fila `alerts`. Portanto, mantenha o worker
e o Celery Beat ativos. O intervalo padrão de avaliação é de 60 segundos.
