# NetGuard 1.3.1 — Serialização defensiva de dispositivos

## Correção

O endpoint `/api/v1/devices` não depende mais da conversão implícita de tipos
do Pydantic. Endereços PostgreSQL `INET` são normalizados explicitamente para
texto antes da criação da resposta, e o schema aceita nativamente IPv4 e IPv6.

Essa normalização também é usada nas respostas de detalhe, edição e fixação de
dispositivos.

## Inventário autocorretivo

Ao consultar `/api/v1/extras/inventory`, a API verifica e cria de forma
idempotente os itens de CMDB ausentes. Assim, dispositivos descobertos antes da
versão 1.3.0 aparecem sem exigir uma nova varredura.

## Diagnóstico operacional

Após atualizar e reiniciar a API, `/health` deve informar a versão `1.3.1`.
Esse teste confirma que o processo ativo carregou efetivamente os arquivos do
hotfix.
