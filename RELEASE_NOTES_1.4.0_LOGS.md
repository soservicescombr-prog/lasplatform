# NetGuard 1.4.0 — Logs, métricas e alertas

Esta versão parte da linha estável 1.3.2 e transforma o receptor Syslog em um
módulo persistente de observabilidade de logs.

## Entregas

- recepção Syslog RFC 3164/5424 por UDP e TCP;
- porta externa padrão 514, encaminhada para a porta interna 5514 no Docker;
- persistência dos eventos no PostgreSQL;
- busca por termos (todos/qualquer), severidade, facility, host/IP, aplicação,
  protocolo, período, categoria de segurança e propriedades estruturadas;
- métricas de contagem criadas diretamente a partir da pesquisa atual;
- janela móvel, limiar, operador, severidade, cooldown, e-mail e webhook;
- avaliação automática a cada minuto e geração de alertas no painel existente;
- resolução automática do alerta quando a condição deixa de ocorrer;
- retenção configurável (`SYSLOG_RETENTION_DAYS`, padrão 30 dias);
- endpoint de saúde do receptor UDP/TCP.

## Implantação

Em Docker, publique `514/udp` e `514/tcp`. Em execução direta, portas abaixo
de 1024 exigem root ou a capability `CAP_NET_BIND_SERVICE`; alternativamente,
mantenha o processo em 5514 e faça o redirecionamento 514 → 5514 no host.

As tabelas `syslog_events` e `log_metrics` são criadas automaticamente no
startup pelo mecanismo atual de `Base.metadata.create_all`.
