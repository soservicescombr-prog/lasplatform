# netguard/docs/DEPLOY.md
# NetGuard — Guia de Deploy em Produção

## 1. Visão Geral

O NetGuard é composto por 5 componentes:

| Componente | Tecnologia | Porta padrão |
|---|---|---|
| **Backend API** | Python 3.12 + FastAPI | 8000 |
| **Frontend** | React + Nginx | 3000 (→ 80) |
| **Banco de Dados** | PostgreSQL 16 | 5432 |
| **Cache/Broker** | Redis 7 | 6379 |
| **Workers** | Celery (Python) | — |

## 2. Pré-requisitos

### Software necessário no host:
- Docker Engine 24+ e Docker Compose v2+
- Ou instalação nativa: Python 3.12+, Node.js 20+, PostgreSQL 16+, Redis 7+, Nmap 7+
- Git

### Requisitos de rede:
- O container/host que roda os Workers precisa ter acesso à rede que será escaneada
- Para scans de rede, o worker Celery roda com `network_mode: host`
- Portas de saída: 161/UDP (SNMP), ICMP (ping), TCP variáveis (scans)
- Nmap requer privilégios root para SYN scan (`-sS`)

### Hardware recomendado:
- CPU: 4 cores mínimo (8 recomendado para scans paralelos)
- RAM: 4 GB mínimo (8 GB recomendado)
- Disco: 20 GB mínimo (100 GB para histórico longo)

## 3. Deploy com Docker Compose (Recomendado)

### 3.1 Clonar e configurar

```bash
git clone <repo> netguard
cd netguard

# Copiar e editar variáveis de ambiente
cp .env.example .env
nano .env
```

### 3.2 Variáveis de ambiente obrigatórias

```env
# SEGURANÇA — altere obrigatoriamente:
SECRET_KEY=<gere com: openssl rand -hex 32>
DB_PASSWORD=<senha_forte_para_postgres>
POSTGRES_PASSWORD=<mesma_senha_acima>

# Rede:
CORS_ORIGINS=https://seudominio.com

# SMTP (para alertas por email):
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu-email@gmail.com
SMTP_PASSWORD=app-password

# NVD API (opcional, melhora correlação de CVEs):
# Obtenha em: https://nvd.nist.gov/developers/request-an-api-key
NVD_API_KEY=sua-chave-api
```

### 3.3 Build e start

```bash
# Build de todos os serviços
docker compose build

# Start em background
docker compose up -d

# Verificar status
docker compose ps

# Ver logs
docker compose logs -f backend
```

### 3.4 Verificar funcionamento

```bash
# Health check da API
curl http://localhost:8000/health

# Swagger da API
# Acesse: http://localhost:8000/docs

# Frontend
# Acesse: http://localhost:3000

# Login padrão: admin / admin123
# ⚠️ TROQUE A SENHA IMEDIATAMENTE!
```

## 4. Deploy Nativo (sem Docker)

### 4.1 PostgreSQL

```bash
sudo apt install postgresql-16
sudo -u postgres createuser --createdb netguard
sudo -u postgres createdb -O netguard netguard
sudo -u postgres psql -c "ALTER USER netguard PASSWORD 'SUA_SENHA';"
```

### 4.2 Redis

```bash
sudo apt install redis-server
sudo systemctl enable redis-server
```

### 4.3 Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Instalar nmap no sistema
sudo apt install nmap snmp snmp-mibs-downloader

# Configurar .env na raiz do projeto
# Rodar API:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Rodar Celery Worker (em outro terminal):
celery -A app.tasks worker -l info -c 4 -Q default,scans,snmp,alerts

# Rodar Celery Beat (scheduler, em outro terminal):
celery -A app.tasks beat -l info
```

### 4.4 Frontend

```bash
cd frontend
npm install
npm run build

# Servir com Nginx:
sudo cp nginx.conf /etc/nginx/sites-available/netguard
sudo ln -s /etc/nginx/sites-available/netguard /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## 5. Configuração do Agente (Módulo 5)

### Instalação no host alvo:

```bash
# Linux:
pip install ./agent/
# ou:
cd agent && pip install -r requirements.txt

# Configurar:
cat > ~/.netguard-agent.json << 'EOF'
{
  "server_url": "https://seu-netguard-server:8000",
  "agent_token": "TOKEN_GERADO_NO_SERVIDOR",
  "scan_interval_minutes": 60,
  "heartbeat_interval_seconds": 60
}
EOF

# Rodar:
python -m netguard_agent.agent

# Ou como serviço systemd:
sudo cat > /etc/systemd/system/netguard-agent.service << 'EOF'
[Unit]
Description=NetGuard Security Agent
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 -m netguard_agent.agent
Restart=always
RestartSec=10
Environment=NETGUARD_AGENT_CONFIG=/etc/netguard-agent.json

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now netguard-agent
```

### Windows:

```powershell
pip install .\agent\
# Configurar C:\ProgramData\netguard-agent.json
# Instalar como serviço Windows com NSSM:
nssm install NetGuardAgent python -m netguard_agent.agent
nssm start NetGuardAgent
```

## 6. Produção — Checklist de Segurança

- [ ] Alterar senha do admin padrão
- [ ] Gerar SECRET_KEY seguro (`openssl rand -hex 32`)
- [ ] Configurar HTTPS (Nginx + Let's Encrypt ou certificado próprio)
- [ ] Restringir CORS_ORIGINS ao domínio real
- [ ] PostgreSQL: escutar apenas em localhost ou rede interna
- [ ] Redis: configurar senha (`requirepass`)
- [ ] Firewall: liberar apenas portas 80/443 externamente
- [ ] Backups automáticos do PostgreSQL
- [ ] Monitorar logs de erro
- [ ] Configurar rate limiting no Nginx
- [ ] Rotacionar logs com logrotate

## 7. Backup e Restauração

```bash
# Backup do banco
docker compose exec postgres pg_dump -U netguard netguard > backup_$(date +%Y%m%d).sql

# Restauração
docker compose exec -T postgres psql -U netguard netguard < backup_20240101.sql
```

## 8. Atualização

```bash
cd netguard
git pull
docker compose build
docker compose up -d

# Rodar migrations (se houver):
docker compose exec backend alembic upgrade head
```

## 9. Troubleshooting

| Problema | Solução |
|---|---|
| Scan não encontra dispositivos | Worker precisa de `network_mode: host` ou estar na mesma rede |
| SNMP timeout | Verificar se porta 161/UDP está acessível e community correta |
| Erro de permissão no nmap | Worker precisa rodar como root para SYN scan |
| Frontend não conecta na API | Verificar CORS_ORIGINS e proxy no nginx.conf |
| Celery tasks não executam | Verificar conexão com Redis: `redis-cli ping` |
