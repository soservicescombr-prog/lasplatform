<!-- lasplatform/docs/RELATORIO_STATUS_PRODUCAO.md -->
# NetGuard (lasplatform): relatório de status e prontidão para produção

**Data da revisão:** 24/09/2026
**Versão analisada:** commit `3a5c3733` (branch `lasplatform`), código declarado como v1.5.3/v1.6.0

---

## 1. Resumo executivo

A parte **funcional** do NetGuard está bem avançada: backend FastAPI com 11 grupos de rotas, workers Celery (scans, SNMP, alertas, disponibilidade, limpeza), receptor Syslog, agente Python e frontend React com 19 páginas. O frontend compila sem erros e 25 dos 26 módulos de teste do backend passam.

Ainda **não está pronto para produção**. Os bloqueios não estão nas funcionalidades, e sim em **segurança, higiene do repositório, banco de dados e pipeline de CI/CD**:

| Área | Status | Observação |
|---|---|---|
| Funcionalidades (backend) | 🟢 Avançado | Discovery, vulnerabilidades, pentest, SNMP, agentes, logs/baseline, relatórios, compliance, threat intel |
| Funcionalidades (frontend) | 🟢 Avançado | Build OK (`tsc && vite build`), `npm audit`: 0 vulnerabilidades |
| Segurança | 🔴 Crítico | Segredos reais versionados, admin padrão `admin/admin123`, segredos fixos no código |
| Repositório | 🔴 Crítico | `node_modules` (18.934 arquivos), `.env`, `__pycache__`, tarballs e arquivos de runtime versionados |
| Banco de dados / migrações | 🟠 Atenção | Alembic configurado, mas **sem nenhuma migração**. O schema depende de `create_all` e `ALTER TABLE` manuais |
| Testes | 🟠 Atenção | 1 módulo de teste quebrado. Nenhum teste de API ou autenticação |
| CI/CD | 🔴 Não funcional | Os dois workflows estão quebrados ou nunca disparam (detalhes na seção 4) |
| Documentação de deploy | 🟡 Parcial | `docs/DEPLOY.md` existe, mas não cobre HTTPS, backup nem o hardening |

---

## 2. Inventário do projeto

```
lasplatform/
├── backend/            FastAPI + SQLAlchemy async + Celery (≈ 7.500 linhas Python)
│   ├── app/api/v1/     auth, users, devices, scans, snmp, alerts, agents, reports, extras, logs, dashboard
│   ├── app/services/   14 serviços (discovery, pentest, snmp, syslog, baseline, threat intel...)
│   ├── app/tasks/      Celery: scan_tasks, snmp_tasks, alert_tasks (+ beat_schedule)
│   ├── alembic/        env.py apenas: SEM pasta versions/ e SEM script.py.mako
│   └── tests/          12 módulos, pytest
├── frontend/           React 18 + Vite 6 + Tailwind + React Query + Zustand, servido via Nginx
├── agent/              Agente Python (heartbeat, métricas, logs), setup.py
├── docker-compose.yml  postgres, redis, backend, celery-worker (network_mode: host), celery-beat, frontend
├── .github/workflows/  deploy.yml e netguard-pipeline.yml
└── docs/               DEPLOY.md, LOGS_SYSLOG.md + ~20 RELEASE_NOTES_*.md na raiz
```

### Resultado das verificações executadas

| Verificação | Resultado |
|---|---|
| `npm ci && npm run build` (frontend) | ✅ OK. Aviso: bundle JS de **835 KB** (sem code-splitting) |
| `npm audit --omit=dev` | ✅ 0 vulnerabilidades |
| `pytest` (backend, Python 3.11) | ⚠️ **25 passed, 1 error**: `tests/test_availability.py` importa `_ports`, que não existe mais em `availability_service.py` |
| Rotas sem autenticação | ✅ Apenas `/auth/login` e `/auth/refresh` (esperado). Todas as outras exigem usuário, operador, admin ou token de agente |

---

## 3. Problemas encontrados, por severidade

### 🔴 P0: bloqueiam o deploy (corrigir antes de qualquer coisa)

1. **Segredos reais commitados no Git**
   - O arquivo `.env` está versionado e contém `DB_PASSWORD`, `POSTGRES_PASSWORD`, `SECRET_KEY` e chaves reais de **NVD, AlienVault OTX e AbuseIPDB**.
   - `backend/app/config.py` traz como valor padrão a mesma `SECRET_KEY` e a senha do banco (`DB_PASSWORD`).
   - **Ação:** revogar e regenerar **todas** as chaves e senhas (NVD, OTX, AbuseIPDB, DB, SECRET_KEY) e remover `.env` do índice (`git rm --cached .env`). Limpar o histórico com `git filter-repo` ou BFG. Remover os defaults sensíveis do `config.py` e fazer a aplicação **falhar no startup** se `SECRET_KEY` ou `DB_PASSWORD` não estiverem definidos em produção.
   - Obs.: o `.gitignore` já lista `.env` e `.env.*`. O arquivo foi adicionado antes disso ou de forma forçada. Além disso, `.env.*` também ignora o `.env.example` (que hoje só está versionado por ter sido adicionado antes).

2. **Administrador padrão `admin` / `admin123`**
   - `AuthService.create_initial_admin()` cria o superusuário com senha fixa, e a própria senha aparece no log de startup.
   - **Ação:** ler `INITIAL_ADMIN_PASSWORD` do ambiente (ou gerar uma senha aleatória exibida uma única vez) e adicionar o campo `must_change_password`, forçando a troca no primeiro login.

3. **Repositório poluído (≈ 19 mil arquivos indevidos)**
   - `frontend/node_modules/` (18.934 arquivos), `frontend/dist/`, `**/__pycache__/*.pyc`, `backend/celerybeat-schedule*`, `backend/netguard-error.log`, `agent/netguard_agent/.agent.py.swp`, `*.tar.gz` (pacotes de update) e `UPDATE_FILES_*.txt`.
   - **Ação:** `git rm -r --cached` desses caminhos e completar o `.gitignore` (`dist/`, `*.pyc`, `celerybeat-schedule*`, `*.swp`, `*.tar.gz`, `!.env.example`).

4. **Injeção de argumentos no Nmap via campo `target`**
   - `ScanJobCreate.target` só valida `min_length=1`. O valor é repassado ao `nmap` (via `subprocess.Popen` e `python-nmap`). Um alvo começando com `-` (ex.: `-iL /etc/passwd` ou `--script ...`) seria interpretado como opção. O risco é limitado a usuários *operador*, mas ainda assim é execução de opções arbitrárias no worker, que roda com `NET_RAW/NET_ADMIN` e `network_mode: host`.
   - **Ação:** validar `target` com `ipaddress.ip_network`/`ip_address` ou regex de hostname, rejeitar valores iniciados por `-`, e validar `target_ports` (regex `^[0-9,\-]+$`).

### 🟠 P1: necessários para produção estável

5. **Migrações de banco inexistentes.** Alembic está configurado, mas não existe `alembic/versions/` nem `script.py.mako`. O schema é criado com `Base.metadata.create_all()` no startup, junto com uma lista manual de `ALTER TABLE ... IF NOT EXISTS` em `database.py`. Isso não suporta renomeação, remoção, índices nem rollback.
   **Ação:** gerar a migração *baseline* (`alembic revision --autogenerate -m "baseline 1.6.0"`), usar `alembic stamp head` nas instalações existentes e trocar o `create_all` do startup por `alembic upgrade head` num passo de deploy.

6. **Credenciais SNMP em texto puro e expostas pela API.** `community_string`, `auth_password` e `priv_password` são gravados em claro, e `SNMPCommunityResponse` devolve `community_string` para qualquer usuário autenticado (inclusive *viewer*).
   **Ação:** mascarar na resposta (ex.: `pub***`) e criptografar em repouso (Fernet, com chave vinda do ambiente).

7. **Autenticação sem proteção contra força bruta.** Não há rate limit nem bloqueio em `/auth/login`.
   **Ação:** usar `slowapi` (ou `limit_req` no Nginx) e bloquear temporariamente após N falhas (a auditoria de `login_failed` já existe).

8. **Tokens no `localStorage`.** O `authStore` usa `zustand/persist`, então access e refresh tokens ficam no `localStorage` (vulnerável a XSS). Os refresh tokens também não são revogáveis (não há lista de revogação, e o logout não invalida no servidor).
   **Ação mínima:** adicionar CSP no Nginx e reduzir a validade do refresh token. **Ideal:** mover o refresh token para cookie `HttpOnly; Secure; SameSite=Strict`, com rotação e revogação.

9. **Backend com um único processo.** O `Dockerfile` roda `uvicorn` sem `--workers`, e a variável `WORKERS=4` do `.env` é ignorada. **Ação:** `uvicorn ... --workers ${WORKERS}` ou `gunicorn -k uvicorn.workers.UvicornWorker`. O `init_db` já usa advisory lock para vários workers.
   - Atenção: com vários workers, cada processo tenta subir o receptor Syslog na mesma porta. O Syslog deve ir para um **serviço/container dedicado** (ou só o primeiro worker deve iniciá-lo).

10. **Sem HTTPS / proxy reverso de borda.** O `docker-compose.yml` expõe `8000` (API) e `3000` (frontend) diretamente, e a documentação não trata TLS.
    **Ação:** criar `docker-compose.prod.yml` com Nginx/Traefik/Caddy + Let's Encrypt, publicando só 80/443 (e 514 para Syslog). Não expor a porta 8000. Em produção, desabilitar `/docs` e `/redoc`, ou protegê-los.

11. **Teste quebrado e cobertura baixa.** Corrigir `tests/test_availability.py` (`_ports` foi removido). Adicionar testes de API com `httpx.AsyncClient` para auth, RBAC (viewer/operator/admin), registro de agente e criação de scan.

12. **`python-jose` e `passlib` sem manutenção.** O `python-jose 3.3.0` tem CVEs conhecidas (ex.: CVE-2024-33663/33664), e o `passlib` está abandonado (aviso de `crypt` no Python 3.13).
    **Ação:** migrar para `PyJWT` e usar `bcrypt` diretamente (ou `pwdlib`). Separar as dependências de teste (`pytest`, `httpx` duplicado) em `requirements-dev.txt`.

### 🟡 P2: melhorias recomendadas

13. **Agente:** o `server_url` padrão é `http://`. Exigir HTTPS e permitir CA customizada (`verify=<ca.pem>`). Documentar a instalação como serviço systemd/Windows. `agent.tar.gz` versionado deve virar um *release* do GitHub.
14. **Frontend:** o `Dockerfile` usa `npm install` sem lockfile (build não reprodutível), e deveria copiar o `package-lock.json` e usar `npm ci`. Também faltam code-splitting (`React.lazy` por rota, bundle atual de 835 KB), headers de segurança no `nginx.conf` (CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`) e ESLint configurado (o script `lint` existe, mas não há `eslint.config.js`).
15. **Versão inconsistente:** `config.py` diz `1.5.0`, `.env.example` diz `1.6.0` e o commit diz `1.5.3`. Centralizar a versão num único lugar.
16. **Observabilidade:** logs estruturados (JSON) do loguru para arquivo/stdout; um healthcheck que verifique DB e Redis (hoje `/health` só retorna estático); métricas Prometheus opcionais; e Flower para o Celery.
17. **Backup:** não há rotina de backup do PostgreSQL. Adicionar um `pg_dump` agendado com retenção e documentar o restore.
18. **Organização:** mover os ~20 `RELEASE_NOTES_*.md` da raiz para `docs/releases/` e consolidar num `CHANGELOG.md`. Criar um `README.md` na raiz, que hoje não existe.
19. **Celery beat:** o arquivo `celerybeat-schedule` é gravado no diretório da aplicação. Apontar para um volume (`-s /data/celerybeat-schedule`).
20. **Timestamps:** os modelos usam `datetime.utcnow` e `DateTime` sem timezone (depreciado no Python 3.12). Planejar a migração para `DateTime(timezone=True)`.

---

## 4. Pipeline CI/CD: situação atual

A branch padrão do repositório é **`lasplatform`**. Não existe branch `main`.

| Workflow | Dispara em | Problema |
|---|---|---|
| `deploy.yml` ("Python application") | push/PR em `lasplatform` | Roda na raiz: não há `requirements.txt` ali, então as dependências não são instaladas. O `pytest` não encontra o pacote `app`, e o `flake8 .` varre o `node_modules`. **Falha sempre.** O nome também engana (não faz deploy) |
| `netguard-pipeline.yml` | push/PR em `main` | **Nunca dispara**, porque a branch `main` não existe. Além disso, referencia arquivos inexistentes: `docker-compose.prod.yml`, `scripts/generate_secrets.sh` e `deploy/ansible/*`. Tem a sub-rede `192.168.1.0/24` fixa |

**Recomendação:** um único workflow `ci.yml` (lint + testes backend com serviço Postgres/Redis + build do frontend + build das imagens Docker), disparando na branch `lasplatform`. Depois, um `deploy.yml` separado, via runner *self-hosted* ou SSH, acionado por tag `v*`. Guardar os segredos em **GitHub Secrets / Environments**, nunca em arquivo.

---

## 5. Plano sugerido para ir a produção

| Fase | Itens | Esforço estimado |
|---|---|---|
| **Fase 1: Segurança e higiene** (bloqueante) | P0 1 a 4: rotação de segredos, limpeza do repo e do histórico, admin inicial seguro, validação do `target` | 1 a 2 dias |
| **Fase 2: Banco e testes** | P1 5 e 11: migração baseline do Alembic, corrigir o teste quebrado, testes de API/RBAC | 2 a 3 dias |
| **Fase 3: Hardening** | P1 6 a 8 e 12: SNMP criptografado/mascarado, rate limit, tokens, troca de jose/passlib | 2 a 3 dias |
| **Fase 4: Infra de produção** | P1 9 e 10 + P2 14, 17 e 19: `docker-compose.prod.yml`, proxy TLS, Syslog dedicado, workers, backup, Nginx com headers | 2 a 3 dias |
| **Fase 5: CI/CD e documentação** | Seção 4 + P2 16 e 18: workflows novos, README, DEPLOY.md atualizado (tecnologias, variáveis, passo a passo, rollback) | 1 a 2 dias |
| **Fase 6: Homologação** | Deploy em staging, teste de scan real na LAN, SNMP, agentes e Syslog, teste de restore do backup | 1 a 2 dias |

**Total estimado:** 9 a 15 dias de trabalho técnico.

---

## 6. Checklist de go-live

- [ ] Todas as chaves e senhas expostas foram **revogadas e regeneradas**
- [ ] `.env` fora do Git e histórico limpo; segredos no servidor ou em GitHub Secrets
- [ ] Nenhum default sensível em `config.py`; startup falha sem `SECRET_KEY`
- [ ] Admin inicial com senha forte e troca obrigatória
- [ ] `alembic upgrade head` executado; `create_all` removido do startup
- [ ] HTTPS ativo; portas 8000, 5432 e 6379 não expostas publicamente
- [ ] `/docs` desabilitado ou protegido
- [ ] Rate limit no login
- [ ] CI verde (backend + frontend + imagens)
- [ ] Backup diário do PostgreSQL testado com restore
- [ ] Firewall: 443/TCP (UI/API), 514/UDP+TCP (Syslog) só das redes de origem, 161/UDP de saída (SNMP)
- [ ] Worker com `network_mode: host` validado na rede-alvo
- [ ] Agentes configurados com `https://` e token rotacionado
