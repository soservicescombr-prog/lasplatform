# NetGuard 1.5.1 — Hotfix das páginas de detalhes

- Corrige `Cannot read properties of undefined (reading 'map')`.
- Normaliza respostas parciais da API para agentes e dispositivos.
- Mantém compatibilidade durante atualização/reinício desencontrado entre frontend e backend.
- Exibe estados vazios para métricas, baselines, interfaces, logs e alertas.
- Adiciona tratamento de falha ao carregar detalhes de dispositivos.

As mensagens `packages.extensions.recorder... message port closed` são geradas
por uma extensão do navegador e não fazem parte do NetGuard.
