### CuidaFamília — Backend do Agente de Cuidado

Backend em **FastAPI** para um agente conversacional (WhatsApp) focado em apoio a cuidadores familiares.

O projeto integra:
- **Twilio WhatsApp** (entrada/saída de mensagens)
- **OpenRouter** (LLM com function-calling)
- **Supabase Postgres** (persistência)
- **APScheduler** (check-ins e lembretes automáticos)

---

### Visão geral do projeto

O CuidaFamília centraliza interações do cuidador e transforma mensagens em ações práticas, como:
- cadastro/atualização de cuidador e pessoa cuidada;
- criação de lembretes de medicação e consultas;
- registro de eventos de saúde;
- detecção inicial de risco com criação de alertas;
- manutenção de contexto de conversa para respostas mais consistentes.

Arquitetura em camadas:
- **routes**: endpoints HTTP/webhook
- **services**: lógica de negócio e integração externa
- **models/database**: entidades e sessão assíncrona SQLAlchemy
- **tasks**: jobs periódicos

---

### Funcionalidades do agente

Principais capacidades disponíveis no `AgentService`:
- `get_context`
- `upsert_caregiver_profile`
- `upsert_cared_person_profile`
- `create_medication_reminder`
- `list_medication_reminders`
- `confirm_medication_taken`
- `create_appointment`
- `list_upcoming_appointments`
- `create_care_plan`
- `register_health_event`
- `create_alert`
- `list_active_alerts`

Além disso:
- análise básica de palavras-chave de emergência;
- memória de interações recentes para continuidade da conversa;
- respostas em pt-BR com tom empático e foco em cuidado familiar.

---

### Tecnologias utilizadas

- Python 3.11
- FastAPI + Uvicorn
- SQLAlchemy 2 (async) + asyncpg
- PostgreSQL (Supabase)
- Twilio SDK
- OpenRouter API (via httpx)
- APScheduler
- Pydantic Settings / python-dotenv

---

### Estrutura de diretórios

```text
cuidafamilia/
├── src/
│   ├── config/          # Settings e variáveis de ambiente
│   ├── database/        # Engine, session factory, init_db ORM
│   ├── models/          # Enums e entidades SQLAlchemy
│   ├── routes/          # /health e /webhook/twilio/whatsapp
│   ├── services/        # Lógica de agente, alerta, lembretes etc.
│   ├── tasks/           # Jobs agendados (check-ins e lembretes)
│   └── utils/           # Prompt, formatação e helpers
├── schema.sql           # Schema relacional completo (Supabase)
├── init_db.py           # Script para aplicar schema.sql automaticamente
├── test_agent.py        # Teste local via terminal (simula WhatsApp)
├── README.md
├── README_DEPLOY.md
├── FLUXO_CONVERSA.md
├── CHECKLIST_DEPLOY.md
├── requirements.txt
├── Dockerfile
└── .env.example
```

---

### Como rodar localmente (passo a passo)

#### 1) Pré-requisitos
- Python 3.11+
- Supabase (projeto criado)
- Chave OpenRouter com créditos
- Twilio (se for testar webhook real)

#### 2) Clonar e entrar no projeto
```bash
git clone <SEU_REPO_GITHUB_URL>
cd cuidafamilia
```

#### 3) Criar ambiente virtual
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows
```

#### 4) Instalar dependências
```bash
pip install -r requirements.txt
```

#### 5) Configurar variáveis
```bash
cp .env.example .env
# edite o .env com seus valores reais
```

#### 6) Aplicar schema no Supabase
Opção A (recomendado):
```bash
python init_db.py
```

Opção B (manual pelo SQL Editor do Supabase):
1. Abrir SQL Editor
2. Colar conteúdo de `schema.sql`
3. Executar

#### 7) Subir API local
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

#### 8) Testar saúde da API
```bash
curl http://127.0.0.1:8000/health
```

#### 9) Testar agente no terminal (sem Twilio)
```bash
python test_agent.py
```

---

### Variáveis de ambiente necessárias

Definidas em `.env.example`:

- **Aplicação**
  - `APP_NAME`
  - `APP_ENV`
  - `APP_HOST`
  - `APP_PORT`
  - `TIMEZONE`
  - `LOG_LEVEL`

- **OpenRouter**
  - `OPENROUTER_API_KEY`
  - `OPENROUTER_MODEL`
  - `OPENROUTER_BASE_URL`

- **Twilio WhatsApp**
  - `TWILIO_ACCOUNT_SID`
  - `TWILIO_AUTH_TOKEN`
  - `TWILIO_PHONE_NUMBER`

- **Supabase/PostgreSQL**
  - `SUPABASE_URL`
  - `SUPABASE_KEY`
  - `DATABASE_URL` (formato async SQLAlchemy: `postgresql+asyncpg://...`)

- **Agendamentos**
  - `CHECKIN_CRON`
  - `REMINDERS_CRON`

---

### Comandos para aplicar o schema no Supabase

#### Via script automático
```bash
python init_db.py
# com caminho customizado:
python init_db.py --schema /caminho/para/schema.sql
```

#### Via psql
```bash
psql "postgresql://postgres:<SENHA>@db.<PROJECT_REF>.supabase.co:5432/postgres" -f schema.sql
```

#### Via painel Supabase (SQL Editor)
- Executar integralmente o conteúdo de `schema.sql`.

---

### Próximos passos recomendados

1. Rodar `python test_agent.py` para validar lógica conversacional.
2. Fazer deploy no Render seguindo `README_DEPLOY.md`.
3. Configurar webhook Twilio para URL pública do Render.
4. Testar com 2-3 pessoas e acompanhar logs + tabelas de `interacoes`, `alertas` e `lembretes`.
