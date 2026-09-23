# NetGuard v1.2.0 — Network Discovery operacional

Data: 22/09/2026

## Escopo concluído

- Execução do Nmap com progresso real obtido por `--stats-every`.
- Etapas persistidas: fila, inicialização, scan, processamento, gravação e conclusão.
- Heartbeat da execução armazenado no próprio `ScanJob`.
- Resultado com quantidade de dispositivos novos, atualizados e total descoberto.
- Falhas do Nmap persistidas e apresentadas na interface.
- Timeout global do scan elevado para 600 segundos e configurável por ambiente.
- Cancelamento cooperativo: o Nmap é interrompido sem converter a task em falha.
- Validação segura de IP, CIDR e ranges antes de chamar o Nmap.
- Diagnóstico de worker Celery online/offline na tela de Discovery.
- Três perfis: rápido, detalhado e sem ping.
- Tela Discovery com barra de progresso, etapa atual e detalhe clicável.
- Nova opção **Tasks**, com histórico e detalhe de todas as execuções assíncronas.
- Identificador Celery visível no detalhe para correlação com logs.

## Rede Docker

O worker de scans usa `network_mode: host` para enxergar a LAN, ARP e MAC addresses. Para manter o acesso aos serviços:

- PostgreSQL e Redis são publicados apenas em `127.0.0.1`.
- No worker, `DB_HOST` e `REDIS_HOST` apontam para `127.0.0.1`.
- Backend e demais containers continuam na rede `netguard-net` usando DNS de serviços.

## Execução sem Docker

Além do backend FastAPI, é obrigatório manter um worker Celery ativo:

```bash
cd backend
source .venv/bin/activate
celery -A app.tasks worker -l info -c 4 -Q default,scans,snmp,alerts
```

Para permitir scans detalhados sem executar o Celery como root:

```bash
sudo setcap cap_net_raw,cap_net_admin+eip /usr/bin/nmap
```

Confirme também que Redis e PostgreSQL estão acessíveis pelas configurações do `.env`.

## Validações executadas

- Compilação Python: aprovada.
- Build de produção React/Vite: aprovado.
- Registro das rotas FastAPI/OpenAPI: aprovado.
- Testes automatizados do Discovery: 5 aprovados.
- Parse e verificações estruturais do Docker Compose: aprovados.
- Resolução das dependências Python: aprovada.

## Teste operacional sugerido

1. Abra Discovery e confirme `Executor de scans: online`.
2. Execute perfil rápido contra uma rede pequena, por exemplo `/29`.
3. Observe progresso, etapa e heartbeat.
4. Confirme conclusão, total de dispositivos e atualização da tela Dispositivos.
5. Em seguida, teste uma `/24` e compare o perfil `sem ping` se houver hosts que bloqueiam ICMP.

Não há migração de banco nesta versão; os campos existentes de `scan_jobs` foram reutilizados.
