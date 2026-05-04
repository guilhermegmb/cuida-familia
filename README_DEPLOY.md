### Deploy do CuidaFamília no Render (Free Tier)

Guia completo para colocar o backend no ar com:
- Render (web service Docker)
- Supabase (Postgres)
- Twilio WhatsApp (webhook)
- OpenRouter (modelo de linguagem)

---

### 1) Pré-requisitos

Você precisa ter:
- Repositório no GitHub com este projeto
- Conta no Render (free)
- Projeto no Supabase (free)
- Conta Twilio com WhatsApp Sandbox ou número habilitado
- Conta OpenRouter com chave e créditos

---

### 2) Preparar o banco no Supabase

#### 2.1 Obter URL de conexão
No Supabase:
1. Project Settings → Database
2. Copie a connection string
3. Ajuste para formato SQLAlchemy async:

```text
postgresql+asyncpg://postgres:<SENHA>@db.<PROJECT_REF>.supabase.co:5432/postgres
```

#### 2.2 Aplicar `schema.sql`
No seu ambiente local (ou CI):

```bash
python init_db.py
```

Alternativa: SQL Editor do Supabase → execute `schema.sql` completo.

#### 2.3 Validar tabelas
Confirme no Supabase que as tabelas foram criadas:
- `cuidadores`
- `pessoas_cuidadas`
- `interacoes`
- `alertas`
- `lembretes`
- demais tabelas do domínio

---

### 3) Deploy no Render (plano gratuito)

#### 3.1 Criar Web Service
1. Render Dashboard → **New +** → **Web Service**
2. Conecte o repositório GitHub
3. Configure:
   - **Environment**: `Docker`
   - **Branch**: `main`
   - **Plan**: `Free`
   - **Region**: mais próxima (ex.: Oregon ou Virginia)

#### 3.2 Variáveis de ambiente no Render
Em **Environment**, adicione:

- `APP_NAME=CuidaFamília - Agente Backend`
- `APP_ENV=production`
- `APP_HOST=0.0.0.0`
- `APP_PORT=8000`
- `TIMEZONE=America/Sao_Paulo`
- `LOG_LEVEL=INFO`

- `OPENROUTER_API_KEY=...`
- `OPENROUTER_MODEL=openai/gpt-4o-mini`
- `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`

- `TWILIO_ACCOUNT_SID=...`
- `TWILIO_AUTH_TOKEN=...`
- `TWILIO_PHONE_NUMBER=+14155238886` (ou seu número WhatsApp Twilio)

- `SUPABASE_URL=https://<seu-projeto>.supabase.co`
- `SUPABASE_KEY=<service_role_key>`
- `DATABASE_URL=postgresql+asyncpg://postgres:<SENHA>@db.<PROJECT_REF>.supabase.co:5432/postgres`

- `CHECKIN_CRON=0 9 * * *`
- `REMINDERS_CRON=*/5 * * * *`

> Dica: use exatamente os nomes da `.env.example`.

#### 3.3 Health check
Configure no Render:
- **Health Check Path**: `/health`

#### 3.4 Criar deploy
1. Clique em **Create Web Service**
2. Aguarde build + start
3. Guarde a URL pública, por exemplo:
   - `https://cuidafamilia-api.onrender.com`

---

### 4) Configurar webhook do Twilio para URL do Render

No Twilio Console:
1. Entre em **Messaging** → WhatsApp Sandbox (ou sender oficial)
2. Em **When a message comes in**, configure:

```text
https://SEU-SERVICO.onrender.com/webhook/twilio/whatsapp
```

3. Método HTTP: `POST`
4. Salve.

Exemplo real:
```text
https://cuidafamilia-api.onrender.com/webhook/twilio/whatsapp
```

---

### 5) Como conectar corretamente ao Supabase

Checklist rápido:
- [ ] `DATABASE_URL` com `postgresql+asyncpg://`
- [ ] senha correta do banco
- [ ] IP restrictions (se houver) permitindo Render
- [ ] schema aplicado (`schema.sql`)
- [ ] extensão `pgcrypto` habilitada (já prevista no schema)

Se houver erro de conexão:
- revise `DATABASE_URL`
- teste credenciais no SQL Editor
- verifique logs do Render (timeout/auth)

---

### 6) Testes pós-deploy (obrigatórios)

#### 6.1 Teste de saúde
Abra no navegador:

```text
https://SEU-SERVICO.onrender.com/health
```

Resposta esperada:
```json
{"status":"ok"}
```

#### 6.2 Teste do webhook Twilio
1. Envie mensagem para o WhatsApp Twilio
2. Verifique se o agente responde
3. Logs Render: deve mostrar requisição `POST /webhook/twilio/whatsapp`

#### 6.3 Teste de persistência
No Supabase, confira inserções em:
- `interacoes`
- `cuidadores`
- `pessoas_cuidadas` (após cadastro inicial)
- `lembretes`/`alertas` conforme conversa

#### 6.4 Teste de criação de lembrete
Envie algo como:
- “Me lembre de dar losartana 50mg hoje às 20h.”

Valide no banco:
- `medicamentos`
- `lembretes`

#### 6.5 Teste de alerta de risco
Envie uma mensagem com situação crítica (ex.: “queda com dor forte”).
Valide criação em `alertas`.

---

### 7) Limitações do Render Free (importante)

- O serviço pode “hibernar” após inatividade.
- Primeira resposta após hibernação pode demorar (cold start).
- Jobs do APScheduler só rodam enquanto o container estiver ativo.

Para uso contínuo/produção:
- considerar plano pago ou arquitetura com worker dedicado.

---

### 8) Comandos úteis locais

```bash
# subir API localmente
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# aplicar schema no banco configurado em DATABASE_URL
python init_db.py

# simular conversa local (sem Twilio)
python test_agent.py
```
