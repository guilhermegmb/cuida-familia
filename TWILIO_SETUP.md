# 📱 Guia Completo: Configuração do Twilio para CuidaFamília

## 1. 🎯 Visão Geral

O **Twilio** é a plataforma de comunicação que permite que o agente CuidaFamília interaja com os cuidadores através do **WhatsApp**. É o canal principal de conversação onde o agente receberá mensagens de usuários, processará com inteligência artificial (OpenRouter) e responderá automaticamente.

### 📊 Fluxo de Comunicação

```
Cuidador envia msg via WhatsApp
           ↓
    Twilio recebe (Webhook)
           ↓
    CuidaFamília processa (IA)
           ↓
   Resposta armazenada no Supabase
           ↓
    Resposta enviada via Twilio
           ↓
    Cuidador recebe no WhatsApp
```

### 🔄 Twilio Sandbox vs. Número Oficial

| Aspecto | Sandbox (Teste) | Número Oficial (Produção) |
|---------|-----------------|--------------------------|
| **Custo** | Gratuito | Pago (conforme uso) |
| **Remetente** | `whatsapp:+14155238886` | Seu número Twilio próprio |
| **Destinatários** | Apenas números previamente autorizados | Qualquer número |
| **Expiração** | 72h sem atividade | Sem expiração |
| **Ideal para** | Desenvolvimento e testes | Produção |
| **Setup** | 5 minutos | 24-48h (verificação) |

> ⚠️ **Recomendação**: Comece com Sandbox para testes. Quando estiver pronto para produção, migre para um número oficial Twilio.

---

## 2. ✅ Pré-requisitos

Antes de começar, certifique-se de que você possui:

### Conta e Serviços Necessários

- ✅ **Conta Twilio ativa e paga** ([twilio.com](https://twilio.com))
  - Necessário cartão de crédito válido
  - Saldo para SMS/WhatsApp (valores baixos para testes)

- ✅ **Número Twilio habilitado para WhatsApp**
  - Pode usar Sandbox para testes (sem número específico)
  - Ou um número oficial (adquirido no console Twilio)

- ✅ **Projeto CuidaFamília deployado no Render**
  - URL pública acessível (ex: `https://meu-app.render.com`)
  - Verificar em [dashboard.render.com](https://dashboard.render.com)

- ✅ **Banco de dados Supabase configurado**
  - Schema aplicado (tabelas: `interacoes`, `usuarios`, etc)
  - Credenciais de acesso disponíveis

- ✅ **OpenRouter API Key**
  - Para processamento de IA das mensagens
  - Cadastrada em `.env` do projeto

- ✅ **Git/GitHub conectado**
  - Projeto versionado e pronto para deploy

---

## 3. 🔐 Configuração do .env

O arquivo `.env` armazena as credenciais sensíveis do Twilio. Este arquivo **NUNCA deve ser commitado** no GitHub.

### 3.1 Variáveis de Ambiente Necessárias

```bash
# =============== TWILIO ===============
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here_very_long_string
TWILIO_PHONE_NUMBER=whatsapp:+5511999887766

# =============== API ===============
OPENROUTER_API_KEY=your_openrouter_key_here

# =============== BANCO DE DADOS ===============
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=your_supabase_key_here

# =============== DEPLOY ===============
RENDER_EXTERNAL_URL=https://seu-app.render.com
```

### 3.2 Onde Encontrar Cada Credencial

#### 🔑 TWILIO_ACCOUNT_SID e TWILIO_AUTH_TOKEN

1. Acesse [console.twilio.com](https://console.twilio.com)
2. Login com suas credenciais
3. No **Dashboard** (primeira página), procure a seção **Account**
4. Você verá:
   - **Account SID**: String que começa com `AC` (ex: `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)
   - **Auth Token**: String longa (clique em "eye" para revelar)

```
Exemplo:
TWILIO_ACCOUNT_SID=AC123456789abcdef123456789abcdef
TWILIO_AUTH_TOKEN=abcdef123456789abcdef123456789ab
```

#### 📞 TWILIO_PHONE_NUMBER

A variação depende do modo:

**Para Sandbox (testes)**:
```bash
TWILIO_PHONE_NUMBER=whatsapp:+14155238886
```

**Para Número Oficial** (após adquirir):
```bash
# Substitua 55 por código do país, 11 por DDD, e os dígitos restantes
TWILIO_PHONE_NUMBER=whatsapp:+5511999887766
```

> 📌 **Nota**: O formato `whatsapp:+` é obrigatório. O número deve incluir:
> - Código do país (Brasil = 55)
> - DDD (ex: 11, 21, 85)
> - Número de telefone (8 ou 9 dígitos)

### 3.3 Arquivo .env Completo (Exemplo Real)

```bash
# ========================================
# TWILIO - Webhook WhatsApp
# ========================================
TWILIO_ACCOUNT_SID=AC12345678901234567890123456789a
TWILIO_AUTH_TOKEN=your_very_long_auth_token_string_here
TWILIO_PHONE_NUMBER=whatsapp:+5511987654321

# ========================================
# OPENROUTER - IA/LLM
# ========================================
OPENROUTER_API_KEY=sk-or-v1-1234567890abcdef1234567890abcdef

# ========================================
# SUPABASE - Banco de Dados
# ========================================
SUPABASE_URL=https://abcdefghij.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# ========================================
# RENDER - Deploy
# ========================================
RENDER_EXTERNAL_URL=https://cuidafamilia.render.com

# ========================================
# AMBIENTE
# ========================================
NODE_ENV=production
PORT=3000
```

### 3.4 Carregar no Render

1. Acesse [dashboard.render.com](https://dashboard.render.com)
2. Selecione seu serviço (Web Service)
3. Vá em **Environment** (abas superiores)
4. Cole as variáveis no campo de texto
5. Clique em **Save Changes**
6. O serviço será redeployado automaticamente

---

## 4. ⚙️ Configuração no Console Twilio

Este é o passo mais crítico. Você configurará o **webhook** (URL que recebe mensagens).

### 4.1 Acesso ao Console

1. Acesse [console.twilio.com](https://console.twilio.com)
2. Certifique-se de estar no **Production** (não Trial)
   - Verifique o canto superior direito: "Production Account"

### 4.2 Acessar Messaging (WhatsApp)

1. No menu lateral esquerdo, clique em **Messaging** (ou **Explore**)
2. Selecione **Channels** > **Whatsapp** (ou **Try It Out**)
3. Se for Sandbox: você verá "WhatsApp Sandbox"
4. Se for número oficial: você verá seu número personalizado

### 4.3 Para Sandbox (Testes)

#### Entender o Código de Opt-in

O Sandbox do Twilio funciona com um código de pareamento:

1. No Console, vá em **Messaging** > **Settings** > **WhatsApp Sandbox**
2. Você verá uma mensagem como:
   ```
   Envie a seguinte mensagem de WhatsApp para +14155238886:
   join [código-aleatório-aqui]
   ```

3. **Abra seu WhatsApp** e envie exatamente essa mensagem para o número indicado
4. Você receberá uma confirmação: "Você agora está conectado ao Sandbox Twilio"
5. A partir daí, qualquer mensagem do seu número será recebida pelo webhook

#### Configurar o Webhook no Sandbox

1. Permaneça em **Messaging** > **Settings** > **WhatsApp Sandbox**
2. Procure o campo **"When a message comes in"**
3. Copie a URL do seu app:
   ```
   https://seu-app.render.com/webhook/twilio/whatsapp
   ```
4. Cole no campo "When a message comes in"
5. Certifique-se de que **HTTP POST** está selecionado
6. Clique em **Save**

### 4.4 Para Número Oficial (Produção)

#### Adquirir um Número

1. Vá em **Phone Numbers** > **Manage** > **Active Numbers**
2. Clique em **+ Buy a Number** (ou adquirido previamente)
3. Escolha país (Brasil), DDD (11, 21, 85, etc)
4. Selecione um número disponível
5. Complete o checkout (será cobrado no cartão)

#### Habilitar WhatsApp

1. Com o número adquirido, vá em **Messaging** > **Settings** > **WhatsApp Business Profile**
2. Solicite acesso (pode levar 24-48h)
3. Forneça informações da empresa/projeto
4. Aguarde aprovação do Twilio

#### Configurar Webhook no Número Oficial

1. Assim que aprovado, vá em **Messaging** > **Channels** > **WhatsApp** > seu número
2. Procure a seção **Webhook Settings** ou **When a message comes in**
3. Cole a URL:
   ```
   https://seu-app.render.com/webhook/twilio/whatsapp
   ```
4. Defina **HTTP Method** como **POST**
5. Salve as configurações

### 4.5 Estrutura da URL do Webhook

A URL deve respeitar este formato:

```
https://[DOMINIO_RENDER]/webhook/twilio/whatsapp
```

| Componente | Exemplo | Obrigatório |
|-----------|---------|-----------|
| Protocol | `https://` | ✅ Sempre HTTPS |
| Domínio Render | `seu-app.render.com` | ✅ Do seu serviço |
| Rota | `/webhook/twilio/whatsapp` | ✅ Exato |

> ⚠️ **Erro comum**: Usar `http://` (sem s). O Twilio rejeita URLs HTTP.

### 4.6 Validação da Configuração

Após salvar, você pode fazer um teste rápido:

1. **Via WhatsApp**: Envie uma mensagem simples (ex: "oi")
2. **Via Console Twilio**: 
   - Vá em **Messaging** > **Messages**
   - Você deve ver a mensagem listada com status "received"

---

## 5. 🧪 Teste do Fluxo Completo

### 5.1 Enviar Mensagem de Teste

1. **Abra seu WhatsApp** (no celular que usou para opt-in no Sandbox)
2. Envie uma mensagem para o número Twilio:
   - **Sandbox**: `+1 415 523 8886`
   - **Número Oficial**: Seu número Twilio adquirido
3. Digite a mensagem (ex: "Olá agente, tudo bem?")
4. Envie

### 5.2 Verificar Recebimento no Webhook

#### No Render Dashboard

1. Acesse [dashboard.render.com](https://dashboard.render.com)
2. Selecione seu serviço Web Service
3. Vá em **Logs** (abas superiores)
4. Procure por um log contendo:
   ```
   POST /webhook/twilio/whatsapp 200 OK
   ```
   ou
   ```
   Webhook recebido de Twilio
   ```

Se aparecer **erro 404 ou 405**, verifique:
- ❌ URL do webhook está correta no console Twilio?
- ❌ Rota `/webhook/twilio/whatsapp` existe no código?
- ❌ Método é POST?

#### No Supabase

1. Acesse [supabase.com/dashboard](https://supabase.com/dashboard)
2. Selecione seu projeto
3. Vá em **SQL Editor** ou **Table Editor**
4. Abra a tabela `interacoes`
5. Procure por um registro recente com:
   - `timestamp` = horário que enviou a mensagem
   - `tipo_mensagem` = "entrada"
   - `conteudo` = sua mensagem

Se nada aparecer na tabela:
- ❌ Webhook não foi recebido (verificar Render logs)
- ❌ Rota do webhook não está salvando no banco (verificar código)

### 5.3 Verificar Resposta do Agente

1. **Abra o Supabase** e procure pela resposta na tabela `interacoes`
2. Você deve ver um novo registro com:
   - `tipo_mensagem` = "saida"
   - `conteudo` = resposta gerada pela IA

3. **No WhatsApp**, aguarde alguns segundos a resposta chegar
4. Se nada chegar:
   - ❌ OpenRouter API Key inválida
   - ❌ Plano do Render está em modo "Spinning Down" (sempre ativo custo)
   - ❌ TWILIO_PHONE_NUMBER incorreto no .env

### 5.4 Fluxo de Teste Recomendado

```
PASSO 1: Enviar "teste" via WhatsApp
         ↓ [Esperar 5 seg]
PASSO 2: Verificar Render Logs (POST 200?)
         ↓
PASSO 3: Verificar Supabase > interacoes (registro entrada?)
         ↓
PASSO 4: Verificar Supabase (resposta gerada?)
         ↓
PASSO 5: Verificar WhatsApp (msg chegou?)
```

Se falhar em algum passo, veja o **Troubleshooting** (seção 8).

---

## 6. 🔒 Configuração do Sandbox (Modo Teste)

### 6.1 Como Funciona o Opt-in

O Sandbox do Twilio usa um sistema de **pareamento por código** para evitar spam:

1. **Código gerado**: Twilio cria um código aleatório (ex: `join xyz123`)
2. **Você envia**: Você envia essa mensagem exata para o número Twilio
3. **Pareamento**: Seu número é autorizado a enviar/receber mensagens
4. **Duração**: Válido por **72 horas**. Após isso, precisa fazer novo opt-in

### 6.2 Renovar o Opt-in

Quando faltar 24h ou expirar:

1. Vá ao **Console Twilio** > **Messaging** > **WhatsApp Sandbox**
2. Clique em **Generate New Code** (ou similar)
3. Envie a nova mensagem de pareamento via WhatsApp
4. Reinicie o período de 72h

### 6.3 Limitações do Sandbox

| Limitação | Detalhe |
|----------|---------|
| **Números permitidos** | Apenas os pareados (max ~3-5) |
| **Frequência** | Max ~50 mensagens/dia |
| **Tipo de msg** | Template + text (sem mídia no Sandbox) |
| **Validade** | 72h sem atividade |
| **Ideal para** | MVP, testes, prototipagem |

### 6.4 Migrar do Sandbox para Produção

Quando seu projeto estiver pronto:

1. **Adquira um número oficial** (veja seção 4.4)
2. **Atualize no .env**:
   ```bash
   # De:
   TWILIO_PHONE_NUMBER=whatsapp:+14155238886
   
   # Para:
   TWILIO_PHONE_NUMBER=whatsapp:+5511987654321
   ```
3. **Atualize no Console Twilio**: Configure webhook no novo número
4. **Deploy**: Faça push para Render (redeploy automático)
5. **Teste**: Envie uma mensagem com o novo número

Não é necessário deletar o Sandbox. Você pode manter ambos configurados.

---

## 7. 💼 Considerações Profissionais

### 7.1 Por que Usar Número Oficial em Produção

| Aspecto | Sandbox | Número Oficial |
|--------|---------|----------------|
| **Confiabilidade** | ❌ Pode expirar | ✅ Permanente |
| **Escalabilidade** | ❌ Max 50 msg/dia | ✅ Sem limite |
| **Branding** | ❌ Número aleatório | ✅ Seu número |
| **SLA** | ❌ Nenhum | ✅ 99.9% uptime |
| **Suporte** | ❌ Limitado | ✅ Premium |

> **Recomendação**: Sandbox para desenvolvimento, número oficial para produção.

### 7.2 Configurar URL Fallback (Opcional)

Se a URL principal falhar, Twilio pode tentar uma secundária:

1. No console Twilio, procure por **Fallback URL** ou **Retry Configuration**
2. Configure uma URL alternativa (ex: seu servidor backup)
3. Isso garante que mensagens não sejam perdidas

### 7.3 Rate Limits e Boas Práticas

#### Twilio Rate Limits
- **Sandbox**: ~50 mensagens/dia
- **Produção**: ~1.000 msg/min (depende do plano)

#### Sua Aplicação

```javascript
// Exemplo de throttling recomendado
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

app.post('/webhook/twilio/whatsapp', async (req, res) => {
  // 1. Responder imediatamente (< 1 segundo)
  res.json({ status: 'received' });
  
  // 2. Processar em background (sem bloquear)
  await delay(100);
  processMessage(req.body);
});
```

#### Boas Práticas
1. ✅ Sempre responda ao webhook em < 5 segundos
2. ✅ Processe mensagens de forma assíncrona
3. ✅ Implemente fila (ex: Bull, RabbitMQ) para alta volume
4. ✅ Cache respostas frequentes
5. ✅ Log de todas as mensagens (auditoria)

### 7.4 Segurança: Validar Webhooks Twilio

O Twilio envia um header especial `X-Twilio-Signature` para confirmar que é realmente de Twilio.

#### Validação Recomendada

```javascript
const twilio = require('twilio');

app.post('/webhook/twilio/whatsapp', (req, res) => {
  const signature = req.get('X-Twilio-Signature') || '';
  const url = `https://seu-app.render.com/webhook/twilio/whatsapp`;
  const params = req.body;
  
  // Validar assinatura
  const isValid = twilio.validateRequest(
    process.env.TWILIO_AUTH_TOKEN,
    signature,
    url,
    params
  );
  
  if (!isValid) {
    // Rejeitar se não for válido
    return res.status(403).send('Invalid request');
  }
  
  // Processar normalmente
  res.json({ status: 'ok' });
});
```

> ⚠️ **Segurança crítica**: Sempre valide assinatura de webhooks para evitar mensagens falsificadas.

---

## 8. 🔧 Troubleshooting

### ❌ Problema: Mensagem não chega ao WhatsApp

**Causa provável**: 
- Webhook não está recebendo mensagens
- TWILIO_PHONE_NUMBER incorreto

**Solução**:

1. Verifique URL do webhook no console Twilio:
   ```
   Deve ser: https://seu-app.render.com/webhook/twilio/whatsapp
   (HTTPS, não HTTP)
   ```

2. Teste a URL manualmente:
   ```bash
   curl -X POST https://seu-app.render.com/webhook/twilio/whatsapp \
     -d "Body=teste&From=whatsapp:%2B14155238886&To=whatsapp:%2B55..."
   ```

3. Verifique TWILIO_PHONE_NUMBER no .env:
   ```bash
   # Deve ser assim:
   TWILIO_PHONE_NUMBER=whatsapp:+5511987654321
   # NÃO assim:
   TWILIO_PHONE_NUMBER=+5511987654321 ❌ (faltou whatsapp:)
   ```

4. Redeploy no Render após qualquer mudança no .env:
   - Dashboard > seu serviço > **Manual Deploy**

---

### ❌ Problema: Erro 401 Unauthorized

**Causa provável**: 
- TWILIO_ACCOUNT_SID ou TWILIO_AUTH_TOKEN incorretos

**Solução**:

1. Acesse [console.twilio.com](https://console.twilio.com)
2. Copie novamente as credenciais:
   - Account SID (clique ao lado para copiar)
   - Auth Token (clique em "eye", depois copiar)
3. Atualize .env:
   ```bash
   TWILIO_ACCOUNT_SID=AC123... (copie exato)
   TWILIO_AUTH_TOKEN=abc123... (copie exato)
   ```
4. Deploy no Render

> 📌 **Dica**: Token pode estar expirado ou resetado. Se não funcionar, gere um novo no console.

---

### ❌ Problema: Mensagem chega mas agente não responde

**Causa provável**: 
- OpenRouter API Key inválida ou sem saldo
- Limite de requisições excedido

**Solução**:

1. Verifique OpenRouter:
   - Acesse [openrouter.ai](https://openrouter.ai)
   - Confira sua API Key no perfil
   - Verifique saldo (precisa de crédito)

2. Teste a API manualmente:
   ```bash
   curl -X POST https://openrouter.ai/api/v1/chat/completions \
     -H "Authorization: Bearer sk-or-v1-..." \
     -H "Content-Type: application/json" \
     -d '{
       "model": "openai/gpt-3.5-turbo",
       "messages": [{"role": "user", "content": "Teste"}]
     }'
   ```

3. Se erro: atualize API Key no .env e redeploy

---

### ❌ Problema: Delay grande nas respostas (> 10 segundos)

**Causa provável**: 
- Plano do Render muito fraco
- API (OpenRouter) lenta
- Banco de dados (Supabase) lento

**Solução**:

1. **Upgrade Render**:
   - Dashboard > seu serviço > **Settings**
   - Mude de "Free" para "Paid Plans" (Starter: $7/mês)

2. **Otimize requisições**:
   - Reduza chamadas ao banco
   - Implemente cache

3. **Monitore tempos**:
   ```javascript
   console.time('procurando db');
   await supabase.from('interacoes').select();
   console.timeEnd('procurando db');
   ```

---

### ❌ Problema: Mensagem aparece no banco mas WhatsApp não recebe

**Causa provável**: 
- TWILIO_PHONE_NUMBER incorreto
- Conta Twilio sem saldo
- Número não autorizado em produção

**Solução**:

1. Verifique TWILIO_PHONE_NUMBER:
   ```bash
   # Correto (com whatsapp: e +):
   TWILIO_PHONE_NUMBER=whatsapp:+5511999887766
   
   # Errado:
   TWILIO_PHONE_NUMBER=+5511999887766 ❌
   TWILIO_PHONE_NUMBER=5511999887766 ❌
   TWILIO_PHONE_NUMBER=11999887766 ❌
   ```

2. Verifique saldo da conta Twilio:
   - [console.twilio.com](https://console.twilio.com)
   - Account > Billing > Balance
   - Recarregue crédito se necessário

3. Se número oficial (produção):
   - Verifique se foi aprovado no Twilio
   - Teste primeiramente com Sandbox

---

### ❌ Problema: Render retorna erro 503 (Serviço Indisponível)

**Causa provável**: 
- Plano Free foi "Spinning Down"
- Limite de memória excedido
- Aplicação crashou

**Solução**:

1. **Upgrade para Paid Plan**:
   - Free plans são suspensos após inatividade
   - Vá em **Settings** > mude para **Starter** ($7/mês)

2. **Verifique logs**:
   - Dashboard > **Logs**
   - Procure por `Error` ou `FATAL`

3. **Reinicie o serviço**:
   - Dashboard > seu serviço
   - Botão **Manual Deploy** (reinicia)

---

### ❌ Problema: Webhook recebe mensagem mas retorna erro 500

**Causa provável**: 
- Erro no código da rota `/webhook/twilio/whatsapp`
- Variável de ambiente não encontrada
- Erro ao conectar ao banco

**Solução**:

1. Verifique logs do Render:
   - Dashboard > **Logs**
   - Procure pelo erro específico

2. Exemplo de erro comum:
   ```
   Error: Cannot read property 'env' of undefined
   ```
   Solução: Certifique-se de que `process.env.TWILIO_AUTH_TOKEN` está no .env

3. Faça um teste local:
   ```bash
   NODE_ENV=development npm run dev
   ```
   Simule um webhook do Twilio e verifique o erro

---

## 9. ✔️ Checklist Final

Use este checklist para confirmar que tudo está configurado corretamente:

### Conta Twilio
- [ ] Conta Twilio criada e ativa
- [ ] Cartão de crédito válido cadastrado
- [ ] Saldo disponível (mínimo $5)

### Credenciais
- [ ] `TWILIO_ACCOUNT_SID` copiado corretamente
- [ ] `TWILIO_AUTH_TOKEN` copiado corretamente
- [ ] `TWILIO_PHONE_NUMBER` no formato `whatsapp:+55...`

### Modo Sandbox (se usando testes)
- [ ] Código de opt-in enviado via WhatsApp
- [ ] Confirmação recebida ("Você está conectado...")
- [ ] Número pareado aparece em "Active Senders"

### Modo Produção (se usando número oficial)
- [ ] Número Twilio adquirido
- [ ] WhatsApp habilitado no número
- [ ] Aprovação do Twilio recebida (24-48h)

### Configuração Render
- [ ] Variáveis de ambiente atualizadas no Render
- [ ] Serviço redeployado após mudanças
- [ ] URL pública acessível em `https://seu-app.render.com`

### Webhook
- [ ] Rota `/webhook/twilio/whatsapp` implementada
- [ ] URL exata configurada no console Twilio
- [ ] Método HTTP definido como `POST`
- [ ] Webhook salvo (clique em Save)

### Banco de Dados
- [ ] Supabase conectado e acessível
- [ ] Tabela `interacoes` criada
- [ ] Schema com campos: `id`, `usuario_id`, `conteudo`, `tipo_mensagem`, `timestamp`

### Teste Completo
- [ ] Mensagem de teste enviada via WhatsApp
- [ ] Log `POST 200` aparece em Render Logs
- [ ] Registro de entrada aparece em Supabase
- [ ] Resposta gerada e salva no banco
- [ ] Resposta recebida no WhatsApp

### OpenRouter
- [ ] API Key cadastrada no .env
- [ ] Saldo disponível na conta OpenRouter
- [ ] Modelo selecionado funciona

### Segurança
- [ ] Arquivo `.env` no `.gitignore`
- [ ] Credenciais não estão commitadas no GitHub
- [ ] Validação de assinatura Twilio implementada
- [ ] HTTPS usado em todas as URLs

### Monitoramento
- [ ] Render Logs sendo verificados regularmente
- [ ] Supabase sendo monitorado para erros
- [ ] Alertas configurados (opcional, recomendado)

---

## 📞 Suporte Rápido

| Problema | Onde Verificar | Próximos Passos |
|----------|---|---|
| Webhook não recebe | Render Logs | Verificar URL, HTTP método, HTTPS |
| Mensagem não salva | Supabase > interacoes | Verificar código da rota, conexão BD |
| IA não responde | OpenRouter API | Verificar key, saldo, limites |
| Erro 401 | Console Twilio | Regenerar token |
| Delay grande | Render Dashboard > Stats | Upgrade para Paid Plan |

---

## 📚 Recursos Adicionais

- 📖 [Documentação Twilio WhatsApp](https://www.twilio.com/docs/whatsapp)
- 📖 [Documentação Twilio Webhooks](https://www.twilio.com/docs/usage/webhooks)
- 📖 [Console Twilio](https://console.twilio.com)
- 📖 [OpenRouter Docs](https://openrouter.ai/docs)
- 📖 [Render Deployment](https://render.com/docs)

---

**Versão**: 1.0 | **Atualizado**: 2024 | **Mantenedor**: CuidaFamília Team

