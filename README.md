# CuidaFamília — Agente de IA Concierge de Cuidado 💙

Backend do agente CuidaFamília: WhatsApp + FastAPI + Supabase + OpenRouter.

---

## Estrutura do Projeto

```
cuidafamilia/
├── main.py                        ← Ponto de entrada FastAPI
├── requirements.txt
├── Procfile                       ← Deploy Render
├── .env.example                   ← Modelo de variáveis de ambiente
├── .gitignore
│
├── src/
│   ├── api/
│   │   └── webhook.py             ← Endpoint POST /webhook/whatsapp
│   ├── core/
│   │   ├── agent.py               ← Cérebro do agente (orquestrador)
│   │   ├── prompts.py             ← Todos os prompts do agente
│   │   └── config.py             ← Configurações e variáveis de ambiente
│   ├── services/
│   │   ├── llm_service.py         ← Integração OpenRouter/GPT-4o-mini
│   │   ├── supabase_service.py    ← Todas as operações de banco de dados
│   │   └── twilio_service.py      ← Envio/validação WhatsApp via Twilio
│   └── utils/
│       └── logger.py              ← Logger centralizado
│
├── scripts/
│   └── supabase_schema.sql        ← SQL completo para criar o banco
│
└── tests/
    └── test_semana1.py            ← Testes mínimos obrigatórios
```

---

## PASSO 1 — Criar o Banco de Dados no Supabase

1. Acesse [supabase.com](https://supabase.com) → seu projeto
2. No menu lateral: **SQL Editor** → **New Query**
3. Cole todo o conteúdo de `scripts/supabase_schema.sql`
4. Clique em **Run** (▶)
5. Deve aparecer: `Schema CuidaFamília criado com sucesso!`

**Tabelas criadas:**
- `cuidadores` — quem usa o agente
- `pessoas_cuidadas` — o ente querido
- `interacoes` — histórico de mensagens
- `memoria_agente` — memória persistente
- `logs_sistema` — logs de erros

**Copie suas credenciais do Supabase:**
- Settings → API → `Project URL` (SUPABASE_URL)
- Settings → API → `service_role` secret (SUPABASE_SERVICE_KEY)

---

## PASSO 2 — Configurar o Twilio (WhatsApp Sandbox)

1. Acesse [console.twilio.com](https://console.twilio.com)
2. Menu: **Messaging → Try it out → Send a WhatsApp message**
3. Siga as instruções para ativar o sandbox (enviar mensagem de join)
4. Anote:
   - `Account SID` (começa com AC...)
   - `Auth Token`
   - Número do sandbox (ex: +14155238886)

O webhook será configurado no Passo 5.

---

## PASSO 3 — Obter chave do OpenRouter

1. Acesse [openrouter.ai](https://openrouter.ai)
2. Keys → Create Key
3. Copie a chave (começa com `sk-or-...`)
4. O modelo padrão é `openai/gpt-4o-mini` (custo muito baixo)

---

## PASSO 4 — Configurar e Rodar Localmente

### Clone o repositório
```bash
git clone https://github.com/SEU_USUARIO/cuidafamilia.git
cd cuidafamilia
```

### Crie o ambiente virtual
```bash
python -m venv venv

# Linux/Mac:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### Instale as dependências
```bash
pip install -r requirements.txt
```

### Configure as variáveis de ambiente
```bash
cp .env.example .env
```

Edite o `.env` com seus valores reais:
```env
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENROUTER_MODEL=openai/gpt-4o-mini
APP_ENV=development
SECRET_KEY=uma_chave_aleatoria_longa_aqui
```

### Rode localmente
```bash
uvicorn main:app --reload --port 8000
```

Acesse: http://localhost:8000 — deve aparecer a mensagem de boas-vindas.
Health check: http://localhost:8000/health

---

## PASSO 5 — Expor o localhost para o Twilio (teste local)

Para o Twilio enviar mensagens para sua máquina local, use o **ngrok**:

```bash
# Instale o ngrok: https://ngrok.com/download
ngrok http 8000
```

Copie a URL gerada (ex: `https://abc123.ngrok.io`)

No Twilio Console → Sandbox → **Sandbox Configuration**:
- **WHEN A MESSAGE COMES IN:** `https://abc123.ngrok.io/webhook/whatsapp`
- Método: `HTTP POST`
- Salve.

**Teste:** Envie qualquer mensagem para o número sandbox do Twilio no WhatsApp.
O agente deve responder com o onboarding! 🎉

---

## PASSO 6 — Deploy no Render (produção)

1. Crie conta em [render.com](https://render.com)
2. **New → Web Service → Connect GitHub repo**
3. Configure:
   - **Name:** cuidafamilia
   - **Region:** Oregon (US West)
   - **Branch:** main
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Em **Environment Variables**, adicione TODAS as variáveis do `.env`
5. **Create Web Service**

Após o deploy, a URL será: `https://cuidafamilia.onrender.com`

**Atualize o webhook no Twilio:**
`https://cuidafamilia.onrender.com/webhook/whatsapp`

**⚠️ Importante — Render Free Tier dorme após 15 min de inatividade.**
Configure o [UptimeRobot](https://uptimerobot.com) (gratuito) para fazer ping a cada 10 minutos:
- URL: `https://cuidafamilia.onrender.com/health`
- Tipo: HTTP(S)
- Intervalo: 10 minutos

---

## PASSO 7 — Rodar os Testes

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

Deve aparecer 6 testes passando ✅

---

## Variáveis de Ambiente — Referência Rápida

| Variável | Onde Encontrar |
|---|---|
| SUPABASE_URL | Supabase → Settings → API → Project URL |
| SUPABASE_SERVICE_KEY | Supabase → Settings → API → service_role |
| TWILIO_ACCOUNT_SID | Twilio Console → Dashboard |
| TWILIO_AUTH_TOKEN | Twilio Console → Dashboard |
| TWILIO_WHATSAPP_NUMBER | Twilio → Sandbox → número |
| OPENROUTER_API_KEY | openrouter.ai → Keys |

---

## Fluxo de Dados

```
WhatsApp (usuário)
      ↓
   Twilio
      ↓
POST /webhook/whatsapp  (FastAPI)
      ↓
   agent.py  ←→  supabase_service.py (banco)
      ↓
  llm_service.py  →  OpenRouter (GPT-4o-mini)
      ↓
   Resposta
      ↓
twilio_service.py  →  WhatsApp (usuário)
```

---

## Onboarding do Usuário

```
Usuário: "Oi"
Agente:  "Olá! Sou o CuidaFamília... Como posso te chamar?"

Usuário: "Guilherme"
Agente:  "Que nome bonito! Me conta: quem você cuida?"

Usuário: "Minha mãe, Dona Maria, 78 anos"
Agente:  "Obrigado por compartilhar... Como posso te ajudar hoje?"

[Conversa livre com LLM + contexto]
```

---

## Suporte e Próximos Passos (Semana 2+)

- Integração com Google Calendar para agendamentos
- Lembretes proativos de medicamentos
- Resumo semanal automático para a família
- Busca semântica no histórico

---

*CuidaFamília v0.1.0 — Semana 1 MVP* 💙
