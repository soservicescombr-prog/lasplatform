# NetGuard 1.5.2 — Hotfix de inicialização da API

- Restaura a função pública `agent_is_online` usada pelo dashboard.
- Restaura os helpers públicos de resolução de alertas offline para agentes e dispositivos.
- Mantém compatibilidade com instalações que já receberam o módulo de detalhes/alertas anterior.
- Adiciona teste para heartbeat recente, vencido, ausente e agente desativado.

Este hotfix corrige o `ImportError` que encerrava todos os workers do Uvicorn antes
do startup da API.
