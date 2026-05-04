# Modelo de Dados - CuidaFamília

Este documento descreve o **modelo relacional em 3FN** do projeto CuidaFamília.

## Visão Geral

- SGBD: PostgreSQL (Supabase)
- Chaves primárias: UUID (`gen_random_uuid()`)
- Datas e horas: `TIMESTAMPTZ`
- Rastreabilidade: `created_at` e `updated_at` em todas as tabelas
- Domínios controlados: enums para status/tipos

## Diagrama textual das relações

```text
cuidadores (1) ────< (N) pessoas_cuidadas
cuidadores (1) ────< (N) planos_cuidado
cuidadores (1) ────< (N) interacoes
cuidadores (1) ────< (N) alertas
cuidadores (1) ────< (N) lembretes
cuidadores (1) ────< (N) consultas

pessoas_cuidadas (1) ────< (N) planos_cuidado
pessoas_cuidadas (1) ────< (N) rotinas
pessoas_cuidadas (1) ────< (N) medicamentos
pessoas_cuidadas (1) ────< (N) eventos_saude
pessoas_cuidadas (1) ────< (N) alertas
pessoas_cuidadas (1) ────< (N) lembretes
pessoas_cuidadas (1) ────< (N) consultas
pessoas_cuidadas (1) ────< (N) interacoes (opcional)

planos_cuidado (1) ────< (N) rotinas
planos_cuidado (1) ────< (N) medicamentos (opcional)

medicamentos (1) ────< (N) rotinas (opcional por rotina)
medicamentos (1) ────< (N) lembretes (opcional)

rotinas (1) ────< (N) eventos_saude (opcional)
rotinas (1) ────< (N) alertas (opcional)
rotinas (1) ────< (N) lembretes (opcional)

eventos_saude (1) ────< (N) alertas (opcional)

alertas (1) ────< (N) interacoes (opcional)

consultas (1) ────< (N) lembretes (opcional)
```

## Tabelas e propósito

1. **cuidadores**: perfil dos cuidadores e preferências de notificação.
2. **pessoas_cuidadas**: perfil clínico e dados essenciais de idosos/pacientes.
3. **planos_cuidado**: plano personalizado por pessoa cuidada, com versionamento.
4. **rotinas**: rotinas recorrentes (medicação, monitoramento, atividades etc.).
5. **eventos_saude**: registros de sintomas, crises e medições.
6. **interacoes**: histórico de conversas com agente/sistema/cuidador.
7. **alertas**: alertas de risco e notificações operacionais.
8. **lembretes**: lembretes programados para execução e confirmação.
9. **consultas**: agendamentos médicos e exames.
10. **medicamentos**: cadastro farmacológico e orientações de uso.

## Notas de normalização (3FN)

- Cada tabela representa **uma entidade de negócio** específica.
- Atributos não-chave dependem da chave primária da própria tabela.
- Campos categóricos com valores controlados foram modelados via **ENUM**.
- Relacionamentos entre entidades foram implementados com **chaves estrangeiras**.
- Índices foram adicionados para chaves estrangeiras e filtros frequentes (status, data/hora).
