# NetGuard v1.1.2 — Hotfix de autenticação e timestamps

Data: 22/09/2026

## Problema corrigido

O login retornava HTTP 500 após validar corretamente usuário e senha. A falha ocorria ao atualizar `users.last_login`: o PostgreSQL utiliza `TIMESTAMP WITHOUT TIME ZONE`, mas o backend enviava um `datetime` com timezone UTC.

Erro original:

```text
asyncpg.exceptions.DataError: can't subtract offset-naive and offset-aware datetimes
```

## Alterações

- `last_login` agora é gravado como UTC sem `tzinfo`, compatível com o schema existente.
- Aplicada a mesma correção preventiva aos timestamps persistidos por scans, discovery, SNMP e alertas.
- `bcrypt` fixado em `4.0.1`, compatível com `passlib 1.7.4`, removendo o aviso `module 'bcrypt' has no attribute '__about__'`.
- Versão da API atualizada para `1.1.2`.

## Aplicação do hotfix

Substitua os arquivos do pacote incremental preservando a estrutura de diretórios e execute:

```bash
cd backend
source .venv/bin/activate
pip install --upgrade --force-reinstall bcrypt==4.0.1
pip install -r requirements.txt
```

Depois, reinicie o backend e teste:

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
```

Resposta esperada: HTTP 200 com `access_token` e `refresh_token`.

Não é necessária alteração no banco de dados para este hotfix.
