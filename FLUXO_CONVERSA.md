### Fluxo de Conversa — CuidaFamília

Este documento mostra exemplos práticos de interação entre **cuidador** e **agente**, cobrindo os fluxos principais do projeto.

---

### 1) Princípios de interação

O agente foi desenhado para:
- responder em pt-BR com linguagem acolhedora;
- coletar dados mínimos para começar;
- transformar pedidos em ações no sistema (cadastros, lembretes, alertas);
- orientar o cuidador com clareza e segurança.

---

### 2) Fluxo de cadastro inicial

Objetivo: registrar cuidador e primeira pessoa cuidada.

#### Exemplo de conversa
**Cuidador:** Oi, quero começar a usar o CuidaFamília.  
**Agente:** Que bom te ter aqui 💙 Para começarmos, qual seu nome completo?  
**Cuidador:** Ana Paula Souza.  
**Agente:** Obrigada, Ana. Você cuida de quem?  
**Cuidador:** Da minha mãe, Maria Souza.  
**Agente:** Entendi. Você pode me dizer o nível de dependência dela de 1 a 5 (1 = pouca ajuda, 5 = dependência alta)?  
**Cuidador:** 4.  
**Agente:** Perfeito. Existe alguma condição clínica importante que devo considerar?  
**Cuidador:** Alzheimer e hipertensão.  
**Agente:** Cadastro inicial concluído ✅ Sempre que quiser, posso te ajudar com lembretes, consultas e monitoramento diário.

#### Resultado esperado no sistema
- cuidador criado/atualizado;
- pessoa cuidada criada;
- contexto inicial pronto para próximos fluxos.

---

### 3) Fluxo de check-in diário

Objetivo: acompanhar rapidamente como foi o dia da pessoa cuidada.

#### Exemplo de conversa
**Agente (mensagem automática):** Bom dia! Como a pessoa que você cuida está hoje? Teve algum sintoma novo, alteração de humor ou dificuldade com medicação?  
**Cuidador:** Hoje ela acordou um pouco confusa e recusou café.  
**Agente:** Obrigada por avisar. Vou registrar esse evento. Quer que eu te lembre de observar novamente em 2 horas?  
**Cuidador:** Sim, por favor.  
**Agente:** Combinado. Também sugiro monitorar hidratação e, se a confusão piorar, buscar orientação médica.

#### Resultado esperado no sistema
- interação salva em `interacoes`;
- eventual evento de saúde registrado;
- possível lembrete de acompanhamento criado.

---

### 4) Fluxo de lembrete de medicamento

Objetivo: criar e confirmar lembretes de medicação.

#### Exemplo de criação
**Cuidador:** Me lembre de dar losartana 50mg hoje às 20h.  
**Agente:** Perfeito. Vou criar o lembrete: losartana 50mg às 20h de hoje. Deseja uma mensagem personalizada?  
**Cuidador:** Pode ser “Hora da pressão”.  
**Agente:** Pronto ✅ Lembrete cadastrado com sucesso.

#### Exemplo de confirmação
**Agente (horário do lembrete):** Lembrete: Hora da pressão (losartana 50mg).  
**Cuidador:** Já tomou.  
**Agente:** Ótimo! Vou marcar esse lembrete como confirmado.

#### Resultado esperado no sistema
- `medicamentos` e `lembretes` preenchidos;
- após confirmação, status atualizado.

---

### 5) Fluxo de alerta de risco

Objetivo: detectar sinais de risco e orientar ação rápida.

#### Exemplo de conversa
**Cuidador:** Minha mãe caiu agora e está com dor forte no quadril.  
**Agente:** Sinto muito por isso. Esse quadro pode indicar risco importante. Recomendo procurar atendimento de urgência imediatamente. Enquanto isso, evite movimentar bruscamente a perna/quadril.  
**Agente:** Vou registrar um alerta para acompanhamento.

#### Resultado esperado no sistema
- alerta criado em `alertas` (prioridade elevada);
- interação registrada;
- orientação de segurança enviada ao cuidador.

> Observação: o agente **não substitui atendimento médico de emergência**.

---

### 6) Dicas para interagir melhor com o agente

- Dê contexto objetivo: “quem”, “o quê”, “quando”.
- Para lembretes, informe horário e dosagem.
- Para consultas, informe data/hora e especialidade.
- Em sintomas, descreva intensidade e duração.
- Confirme ações concluídas (“já tomou”, “consulta realizada”).
- Em situações graves (queda, falta de ar, dor intensa), priorize urgência médica.

---

### 7) Exemplos rápidos de comandos úteis

- “Atualize meu nome para …”
- “Cadastre meu pai João, dependência 3, diabético.”
- “Me lembre de dar remédio às 08:00 e 20:00.”
- “Marque consulta de cardiologia dia 15 às 14h.”
- “Liste meus alertas ativos.”
- “O que está pendente hoje?”
