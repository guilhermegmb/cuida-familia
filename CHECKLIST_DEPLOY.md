### Checklist de Deploy — CuidaFamília (Render Free)

Use este checklist para subir o projeto e iniciar testes com 2-3 pessoas.

---

### 1) Preparação do repositório
- [ ] Código atualizado no GitHub
- [ ] Arquivos presentes: `README.md`, `README_DEPLOY.md`, `schema.sql`, `.env.example`
- [ ] Scripts presentes: `init_db.py`, `test_agent.py`

---

### 2) Configuração de ambiente local
- [ ] Criar `.env` a partir de `.env.example`
- [ ] Preencher `OPENROUTER_API_KEY`
- [ ] Preencher variáveis Twilio (`SID`, `TOKEN`, `PHONE_NUMBER`)
- [ ] Preencher variáveis Supabase (`SUPABASE_URL`, `SUPABASE_KEY`, `DATABASE_URL`)

---

### 3) Banco de dados (Supabase)
- [ ] `DATABASE_URL` válido no formato `postgresql+asyncpg://...`
- [ ] Rodar `python init_db.py` sem erros
- [ ] Confirmar criação das tabelas principais no Supabase
- [ ] Validar acesso de leitura/escrita

---

### 4) Teste local antes do deploy
- [ ] Instalar dependências: `pip install -r requirements.txt`
- [ ] Subir API local: `uvicorn src.main:app --reload --port 8000`
- [ ] Testar health: `GET /health`
- [ ] Rodar `python test_agent.py`
- [ ] Validar fluxo básico de conversa no terminal

---

### 5) Deploy no Render
- [ ] Criar Web Service (Environment: Docker)
- [ ] Selecionar branch `main`
- [ ] Escolher plano `Free`
- [ ] Configurar variáveis de ambiente (todas da `.env.example`)
- [ ] Configurar health check path `/health`
- [ ] Aguardar deploy concluir com sucesso

---

### 6) Configuração Twilio webhook
- [ ] Copiar URL pública do Render
- [ ] Configurar no Twilio: `https://SEU-SERVICO.onrender.com/webhook/twilio/whatsapp`
- [ ] Método `POST`
- [ ] Salvar configuração

---

### 7) Testes pós-deploy
- [ ] Testar `https://SEU-SERVICO.onrender.com/health`
- [ ] Enviar mensagem WhatsApp de teste
- [ ] Confirmar resposta do agente
- [ ] Verificar logs no Render
- [ ] Verificar persistência no Supabase (`interacoes`, `alertas`, `lembretes`)

---

### 8) Go-live controlado (2-3 pessoas)
- [ ] Definir cuidadores piloto
- [ ] Testar cadastro inicial com cada cuidador
- [ ] Testar lembrete de medicação real
- [ ] Testar registro de evento de saúde
- [ ] Coletar feedback (clareza, utilidade, tempo de resposta)

---

### 9) Monitoramento inicial (primeira semana)
- [ ] Revisar logs diariamente
- [ ] Ajustar prompt/modelo se necessário
- [ ] Revisar CRON de check-ins e lembretes
- [ ] Acompanhar custos OpenRouter/Twilio
- [ ] Planejar upgrade se hibernação free atrapalhar
