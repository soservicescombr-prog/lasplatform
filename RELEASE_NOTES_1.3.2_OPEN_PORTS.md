# NetGuard 1.3.2 — Hotfix de detalhes dos dispositivos

Corrige o erro React #31 ao expandir um dispositivo cujo campo `open_ports`
contém objetos no formato `{port, service, version}`.

A interface agora aceita portas numéricas, texto e objetos enriquecidos,
apresentando valores como `443 · https · nginx 1.24` sem tentar renderizar o
objeto JavaScript diretamente.

Este hotfix parte exclusivamente da linha 1.3.1 e não incorpora os módulos
SNMP, métricas e alertas das versões posteriores.
