# CuidaFamília - Backend

Agente de IA via WhatsApp para apoio a cuidadores familiares.

## 🏗️ Stack

- **NestJS** (TypeScript) - framework backend
- **Twilio** - integração WhatsApp
- **Supabase** (PostgreSQL) - persistência
- **OpenRouter** (gpt-4o-mini) - LLM
- **Winston** - logs estruturados

## 🚀 Como rodar localmente

```bash
cd nodejs_space
cp .env.example .env   # preencha as credenciais
yarn install
yarn start:dev
```

O serviço sobe em `http://localhost:3000`.

## 📡 Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Health check |
| POST | `/webhook/twilio` | Webhook do Twilio WhatsApp |
| GET | `/api-docs` | Documentação Swagger |

## 🔐 Variáveis de ambiente

Veja `nodejs_space/.env.example`.

## 🗂️ Estrutura

```
nodejs_space/
├── src/
│   ├── agent/         # Lógica do agente CuidaFamília + onboarding
│   ├── common/        # Serviços: Supabase, OpenRouter, Twilio, Logger
│   ├── health/        # Health check
│   ├── webhook/       # Endpoint Twilio
│   └── main.ts
└── migrations/        # SQL de referência
```

## 🧪 Configurar Twilio Sandbox

No console Twilio (Messaging → Try WhatsApp), aponte o webhook **WHEN A MESSAGE COMES IN** para:

```
https://seu-dominio/webhook/twilio
```

## 📝 Licença

Proprietary.
