-- Projeto: CuidaFamília
-- Banco: PostgreSQL (Supabase)
-- Objetivo: Schema relacional em 3FN para gestão de cuidadores, pessoas cuidadas,
-- planos de cuidado, rotinas, eventos de saúde, interações, alertas, lembretes,
-- consultas e medicamentos.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =====================================================
-- ENUMS DE DOMÍNIO
-- =====================================================

CREATE TYPE genero_enum AS ENUM ('feminino', 'masculino', 'nao_binario', 'prefiro_nao_informar');

CREATE TYPE parentesco_enum AS ENUM (
  'filho', 'filha', 'conjuge', 'irmao', 'irma', 'neto', 'neta', 'sobrinho', 'sobrinha',
  'amigo', 'vizinho', 'cuidador_profissional', 'outro'
);

CREATE TYPE status_plano_enum AS ENUM ('rascunho', 'ativo', 'pausado', 'encerrado', 'arquivado');

CREATE TYPE tipo_rotina_enum AS ENUM (
  'medicamento', 'atividade_fisica', 'alimentacao', 'hidratacao', 'sono',
  'monitoramento', 'consulta', 'exame', 'outro'
);

CREATE TYPE frequencia_rotina_enum AS ENUM ('diaria', 'semanal', 'mensal', 'personalizada');
CREATE TYPE status_rotina_enum AS ENUM ('ativa', 'pausada', 'concluida', 'cancelada');

CREATE TYPE tipo_evento_saude_enum AS ENUM ('sintoma', 'crise', 'medicao', 'queda', 'comportamento', 'sono', 'outro');
CREATE TYPE gravidade_enum AS ENUM ('baixa', 'moderada', 'alta', 'critica');

CREATE TYPE papel_interacao_enum AS ENUM ('cuidador', 'agente', 'sistema');
CREATE TYPE canal_interacao_enum AS ENUM ('whatsapp', 'aplicativo', 'telefone', 'outro');
CREATE TYPE tipo_interacao_enum AS ENUM ('mensagem', 'checkin', 'resposta_alerta', 'resumo', 'outro');

CREATE TYPE tipo_alerta_enum AS ENUM (
  'risco_saude', 'atraso_medicacao', 'consulta_proxima', 'rotina_nao_cumprida',
  'anomalia_medicao', 'emergencia', 'outro'
);
CREATE TYPE prioridade_alerta_enum AS ENUM ('baixa', 'media', 'alta', 'critica');
CREATE TYPE status_alerta_enum AS ENUM ('novo', 'em_analise', 'resolvido', 'descartado');

CREATE TYPE tipo_lembrete_enum AS ENUM ('medicamento', 'consulta', 'exame', 'atividade', 'hidratacao', 'checkin', 'outro');
CREATE TYPE status_lembrete_enum AS ENUM ('agendado', 'enviado', 'confirmado', 'adiado', 'cancelado', 'expirado');

CREATE TYPE tipo_consulta_enum AS ENUM ('presencial', 'telemedicina', 'retorno', 'exame');
CREATE TYPE status_consulta_enum AS ENUM ('agendada', 'confirmada', 'realizada', 'cancelada', 'nao_compareceu', 'reagendada');
CREATE TYPE via_agendamento_enum AS ENUM ('manual', 'agente_ia', 'integracao_externa');

CREATE TYPE status_medicamento_enum AS ENUM ('ativo', 'suspenso', 'concluido');
CREATE TYPE via_administracao_enum AS ENUM (
  'oral', 'sublingual', 'inalatoria', 'topica', 'oftalmica', 'otologica', 'nasal',
  'subcutanea', 'intramuscular', 'intravenosa', 'retal', 'vaginal', 'outra'
);

-- =====================================================
-- FUNÇÃO/TRIGGER PADRÃO PARA updated_at
-- =====================================================

CREATE OR REPLACE FUNCTION atualizar_timestamp_modificacao()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 1) CUIDADORES
-- =====================================================

CREATE TABLE cuidadores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome_completo VARCHAR(150) NOT NULL,
  telefone_whatsapp VARCHAR(20) NOT NULL,
  email VARCHAR(255),
  data_nascimento DATE,
  genero genero_enum,
  parentesco parentesco_enum NOT NULL,
  idioma_preferido VARCHAR(10) NOT NULL DEFAULT 'pt-BR',
  fuso_horario VARCHAR(60) NOT NULL DEFAULT 'America/Sao_Paulo',
  ativo BOOLEAN NOT NULL DEFAULT TRUE,
  preferencias_notificacao JSONB NOT NULL DEFAULT '{}'::jsonb,
  observacoes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_cuidadores_telefone_whatsapp UNIQUE (telefone_whatsapp),
  CONSTRAINT uq_cuidadores_email UNIQUE (email)
);

CREATE INDEX idx_cuidadores_ativo ON cuidadores (ativo);

CREATE TRIGGER trg_cuidadores_updated_at
BEFORE UPDATE ON cuidadores
FOR EACH ROW EXECUTE FUNCTION atualizar_timestamp_modificacao();

COMMENT ON TABLE cuidadores IS 'Perfis dos cuidadores responsáveis pelo acompanhamento das pessoas cuidadas.';
COMMENT ON COLUMN cuidadores.telefone_whatsapp IS 'Telefone principal de contato, usado no canal WhatsApp/Twilio.';
COMMENT ON COLUMN cuidadores.parentesco IS 'Relação principal do cuidador com a pessoa cuidada.';
COMMENT ON COLUMN cuidadores.preferencias_notificacao IS 'Preferências de horário, canal e tipo de notificação.';

-- =====================================================
-- 2) PESSOAS_CUIDADAS
-- =====================================================

CREATE TABLE pessoas_cuidadas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cuidador_id UUID NOT NULL,
  nome_completo VARCHAR(150) NOT NULL,
  data_nascimento DATE,
  genero genero_enum,
  grau_dependencia SMALLINT NOT NULL DEFAULT 3,
  comorbidades TEXT,
  alergias TEXT,
  condicoes_clinicas TEXT,
  contato_emergencia_nome VARCHAR(150),
  contato_emergencia_telefone VARCHAR(20),
  observacoes TEXT,
  ativo BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_pessoas_cuidadas_cuidador
    FOREIGN KEY (cuidador_id) REFERENCES cuidadores(id) ON DELETE RESTRICT,
  CONSTRAINT ck_pessoas_cuidadas_grau_dependencia
    CHECK (grau_dependencia BETWEEN 1 AND 5)
);

CREATE INDEX idx_pessoas_cuidadas_cuidador_id ON pessoas_cuidadas (cuidador_id);
CREATE INDEX idx_pessoas_cuidadas_ativo ON pessoas_cuidadas (ativo);

CREATE TRIGGER trg_pessoas_cuidadas_updated_at
BEFORE UPDATE ON pessoas_cuidadas
FOR EACH ROW EXECUTE FUNCTION atualizar_timestamp_modificacao();

COMMENT ON TABLE pessoas_cuidadas IS 'Perfis de idosos/pacientes acompanhados pelo CuidaFamília.';
COMMENT ON COLUMN pessoas_cuidadas.cuidador_id IS 'Cuidador principal responsável pelo cadastro e acompanhamento.';
COMMENT ON COLUMN pessoas_cuidadas.grau_dependencia IS 'Escala de 1 (baixa dependência) a 5 (alta dependência).';

-- =====================================================
-- 3) PLANOS_CUIDADO
-- =====================================================

CREATE TABLE planos_cuidado (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pessoa_cuidada_id UUID NOT NULL,
  cuidador_id UUID NOT NULL,
  titulo VARCHAR(200) NOT NULL,
  objetivo_geral TEXT NOT NULL,
  detalhes TEXT,
  status status_plano_enum NOT NULL DEFAULT 'rascunho',
  inicio_em DATE NOT NULL,
  fim_previsto_em DATE,
  versao INTEGER NOT NULL DEFAULT 1,
  gerado_por_ia BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_planos_cuidado_pessoa
    FOREIGN KEY (pessoa_cuidada_id) REFERENCES pessoas_cuidadas(id) ON DELETE CASCADE,
  CONSTRAINT fk_planos_cuidado_cuidador
    FOREIGN KEY (cuidador_id) REFERENCES cuidadores(id) ON DELETE RESTRICT,
  CONSTRAINT ck_planos_cuidado_periodo
    CHECK (fim_previsto_em IS NULL OR fim_previsto_em >= inicio_em),
  CONSTRAINT uq_planos_cuidado_versao UNIQUE (pessoa_cuidada_id, versao)
);

CREATE INDEX idx_planos_cuidado_pessoa_cuidada_id ON planos_cuidado (pessoa_cuidada_id);
CREATE INDEX idx_planos_cuidado_cuidador_id ON planos_cuidado (cuidador_id);
CREATE INDEX idx_planos_cuidado_status ON planos_cuidado (status);

CREATE TRIGGER trg_planos_cuidado_updated_at
BEFORE UPDATE ON planos_cuidado
FOR EACH ROW EXECUTE FUNCTION atualizar_timestamp_modificacao();

COMMENT ON TABLE planos_cuidado IS 'Planos de cuidado personalizados com metas, orientações e período de vigência.';
COMMENT ON COLUMN planos_cuidado.versao IS 'Controle de versão incremental por pessoa cuidada.';

-- =====================================================
-- 4) ROTINAS
-- =====================================================

CREATE TABLE rotinas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  plano_cuidado_id UUID NOT NULL,
  pessoa_cuidada_id UUID NOT NULL,
  medicamento_id UUID,
  titulo VARCHAR(200) NOT NULL,
  descricao TEXT,
  tipo tipo_rotina_enum NOT NULL,
  frequencia frequencia_rotina_enum NOT NULL,
  regra_personalizada_cron VARCHAR(120),
  horario_padrao TIME,
  dia_semana SMALLINT,
  dia_mes SMALLINT,
  status status_rotina_enum NOT NULL DEFAULT 'ativa',
  inicio_em DATE NOT NULL,
  fim_em DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_rotinas_plano
    FOREIGN KEY (plano_cuidado_id) REFERENCES planos_cuidado(id) ON DELETE CASCADE,
  CONSTRAINT fk_rotinas_pessoa
    FOREIGN KEY (pessoa_cuidada_id) REFERENCES pessoas_cuidadas(id) ON DELETE CASCADE,
  CONSTRAINT ck_rotinas_periodo CHECK (fim_em IS NULL OR fim_em >= inicio_em),
  CONSTRAINT ck_rotinas_dia_semana CHECK (dia_semana IS NULL OR dia_semana BETWEEN 0 AND 6),
  CONSTRAINT ck_rotinas_dia_mes CHECK (dia_mes IS NULL OR dia_mes BETWEEN 1 AND 31),
  CONSTRAINT ck_rotinas_regra_personalizada
    CHECK (frequencia <> 'personalizada' OR regra_personalizada_cron IS NOT NULL)
);

CREATE INDEX idx_rotinas_plano_cuidado_id ON rotinas (plano_cuidado_id);
CREATE INDEX idx_rotinas_pessoa_cuidada_id ON rotinas (pessoa_cuidada_id);
CREATE INDEX idx_rotinas_status ON rotinas (status);
CREATE INDEX idx_rotinas_tipo ON rotinas (tipo);
CREATE INDEX idx_rotinas_horario ON rotinas (horario_padrao);

CREATE TRIGGER trg_rotinas_updated_at
BEFORE UPDATE ON rotinas
FOR EACH ROW EXECUTE FUNCTION atualizar_timestamp_modificacao();

COMMENT ON TABLE rotinas IS 'Rotinas diárias/semanais/mensais para medicamentos, atividades e monitoramento.';
COMMENT ON COLUMN rotinas.regra_personalizada_cron IS 'Expressão cron para recorrência avançada quando frequência = personalizada.';

-- =====================================================
-- 10) MEDICAMENTOS
-- (Criada antes de constraints pendentes para referenciar em rotinas)
-- =====================================================

CREATE TABLE medicamentos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pessoa_cuidada_id UUID NOT NULL,
  plano_cuidado_id UUID,
  nome VARCHAR(150) NOT NULL,
  principio_ativo VARCHAR(150),
  dosagem VARCHAR(80) NOT NULL,
  via_administracao via_administracao_enum NOT NULL DEFAULT 'oral',
  intervalo_horas NUMERIC(5,2),
  orientacoes TEXT,
  prescrito_por VARCHAR(150),
  inicio_em DATE NOT NULL,
  fim_em DATE,
  status status_medicamento_enum NOT NULL DEFAULT 'ativo',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_medicamentos_pessoa
    FOREIGN KEY (pessoa_cuidada_id) REFERENCES pessoas_cuidadas(id) ON DELETE CASCADE,
  CONSTRAINT fk_medicamentos_plano
    FOREIGN KEY (plano_cuidado_id) REFERENCES planos_cuidado(id) ON DELETE SET NULL,
  CONSTRAINT ck_medicamentos_intervalo_horas CHECK (intervalo_horas IS NULL OR intervalo_horas > 0),
  CONSTRAINT ck_medicamentos_periodo CHECK (fim_em IS NULL OR fim_em >= inicio_em),
  CONSTRAINT uq_medicamentos_ativo
    UNIQUE (pessoa_cuidada_id, nome, dosagem, inicio_em)
);

CREATE INDEX idx_medicamentos_pessoa_cuidada_id ON medicamentos (pessoa_cuidada_id);
CREATE INDEX idx_medicamentos_plano_cuidado_id ON medicamentos (plano_cuidado_id);
CREATE INDEX idx_medicamentos_status ON medicamentos (status);

CREATE TRIGGER trg_medicamentos_updated_at
BEFORE UPDATE ON medicamentos
FOR EACH ROW EXECUTE FUNCTION atualizar_timestamp_modificacao();

COMMENT ON TABLE medicamentos IS 'Cadastro de medicamentos vinculados à pessoa cuidada e ao plano de cuidado.';
COMMENT ON COLUMN medicamentos.intervalo_horas IS 'Intervalo padrão entre doses em horas (ex.: 8.00).';

-- Constraint de rotinas para medicamento (após criação da tabela medicamentos)
ALTER TABLE rotinas
  ADD CONSTRAINT fk_rotinas_medicamento
  FOREIGN KEY (medicamento_id) REFERENCES medicamentos(id) ON DELETE SET NULL;

-- =====================================================
-- 5) EVENTOS_SAUDE
-- =====================================================

CREATE TABLE eventos_saude (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pessoa_cuidada_id UUID NOT NULL,
  cuidador_id UUID,
  rotina_id UUID,
  tipo tipo_evento_saude_enum NOT NULL,
  gravidade gravidade_enum NOT NULL DEFAULT 'baixa',
  titulo VARCHAR(200) NOT NULL,
  descricao TEXT,
  valor_numerico NUMERIC(10,2),
  unidade_medida VARCHAR(30),
  ocorreu_em TIMESTAMPTZ NOT NULL,
  localizacao VARCHAR(150),
  requer_atencao_imediata BOOLEAN NOT NULL DEFAULT FALSE,
  metadados JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_eventos_saude_pessoa
    FOREIGN KEY (pessoa_cuidada_id) REFERENCES pessoas_cuidadas(id) ON DELETE CASCADE,
  CONSTRAINT fk_eventos_saude_cuidador
    FOREIGN KEY (cuidador_id) REFERENCES cuidadores(id) ON DELETE SET NULL,
  CONSTRAINT fk_eventos_saude_rotina
    FOREIGN KEY (rotina_id) REFERENCES rotinas(id) ON DELETE SET NULL
);

CREATE INDEX idx_eventos_saude_pessoa_cuidada_id ON eventos_saude (pessoa_cuidada_id);
CREATE INDEX idx_eventos_saude_ocorreu_em ON eventos_saude (ocorreu_em DESC);
CREATE INDEX idx_eventos_saude_tipo ON eventos_saude (tipo);
CREATE INDEX idx_eventos_saude_gravidade ON eventos_saude (gravidade);

CREATE TRIGGER trg_eventos_saude_updated_at
BEFORE UPDATE ON eventos_saude
FOR EACH ROW EXECUTE FUNCTION atualizar_timestamp_modificacao();

COMMENT ON TABLE eventos_saude IS 'Registros de sintomas, crises, medições e outros eventos clínicos relevantes.';
COMMENT ON COLUMN eventos_saude.metadados IS 'Detalhes adicionais estruturados (ex.: pressão sistólica/diastólica).';

-- =====================================================
-- 6) INTERACOES
-- =====================================================

CREATE TABLE interacoes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cuidador_id UUID NOT NULL,
  pessoa_cuidada_id UUID,
  alerta_id UUID,
  tipo tipo_interacao_enum NOT NULL DEFAULT 'mensagem',
  papel_origem papel_interacao_enum NOT NULL,
  canal canal_interacao_enum NOT NULL DEFAULT 'whatsapp',
  conteudo TEXT NOT NULL,
  sentimento_detectado VARCHAR(50),
  confianca_sentimento NUMERIC(5,4),
  contexto_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  ocorreu_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_interacoes_cuidador
    FOREIGN KEY (cuidador_id) REFERENCES cuidadores(id) ON DELETE CASCADE,
  CONSTRAINT fk_interacoes_pessoa
    FOREIGN KEY (pessoa_cuidada_id) REFERENCES pessoas_cuidadas(id) ON DELETE SET NULL,
  CONSTRAINT ck_interacoes_confianca_sentimento
    CHECK (confianca_sentimento IS NULL OR (confianca_sentimento >= 0 AND confianca_sentimento <= 1))
);

CREATE INDEX idx_interacoes_cuidador_id ON interacoes (cuidador_id);
CREATE INDEX idx_interacoes_pessoa_cuidada_id ON interacoes (pessoa_cuidada_id);
CREATE INDEX idx_interacoes_ocorreu_em ON interacoes (ocorreu_em DESC);
CREATE INDEX idx_interacoes_tipo ON interacoes (tipo);

CREATE TRIGGER trg_interacoes_updated_at
BEFORE UPDATE ON interacoes
FOR EACH ROW EXECUTE FUNCTION atualizar_timestamp_modificacao();

COMMENT ON TABLE interacoes IS 'Histórico de conversas e trocas de mensagens com o agente de IA.';
COMMENT ON COLUMN interacoes.papel_origem IS 'Identifica se a interação veio do cuidador, do agente ou de um processo de sistema.';

-- =====================================================
-- 7) ALERTAS
-- =====================================================

CREATE TABLE alertas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pessoa_cuidada_id UUID NOT NULL,
  cuidador_id UUID NOT NULL,
  evento_saude_id UUID,
  rotina_id UUID,
  tipo tipo_alerta_enum NOT NULL,
  prioridade prioridade_alerta_enum NOT NULL DEFAULT 'media',
  status status_alerta_enum NOT NULL DEFAULT 'novo',
  titulo VARCHAR(200) NOT NULL,
  descricao TEXT NOT NULL,
  acao_recomendada TEXT,
  gerado_por_ia BOOLEAN NOT NULL DEFAULT TRUE,
  detectado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolvido_em TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_alertas_pessoa
    FOREIGN KEY (pessoa_cuidada_id) REFERENCES pessoas_cuidadas(id) ON DELETE CASCADE,
  CONSTRAINT fk_alertas_cuidador
    FOREIGN KEY (cuidador_id) REFERENCES cuidadores(id) ON DELETE CASCADE,
  CONSTRAINT fk_alertas_evento_saude
    FOREIGN KEY (evento_saude_id) REFERENCES eventos_saude(id) ON DELETE SET NULL,
  CONSTRAINT fk_alertas_rotina
    FOREIGN KEY (rotina_id) REFERENCES rotinas(id) ON DELETE SET NULL,
  CONSTRAINT ck_alertas_resolucao
    CHECK (resolvido_em IS NULL OR resolvido_em >= detectado_em)
);

CREATE INDEX idx_alertas_pessoa_cuidada_id ON alertas (pessoa_cuidada_id);
CREATE INDEX idx_alertas_cuidador_id ON alertas (cuidador_id);
CREATE INDEX idx_alertas_status ON alertas (status);
CREATE INDEX idx_alertas_prioridade ON alertas (prioridade);
CREATE INDEX idx_alertas_detectado_em ON alertas (detectado_em DESC);

CREATE TRIGGER trg_alertas_updated_at
BEFORE UPDATE ON alertas
FOR EACH ROW EXECUTE FUNCTION atualizar_timestamp_modificacao();

COMMENT ON TABLE alertas IS 'Alertas e notificações gerados automaticamente ou manualmente para situações de cuidado.';
COMMENT ON COLUMN alertas.acao_recomendada IS 'Orientação sugerida para o cuidador após detecção do alerta.';

-- Constraint pendente de interacoes -> alertas (após criação de alertas)
ALTER TABLE interacoes
  ADD CONSTRAINT fk_interacoes_alerta
  FOREIGN KEY (alerta_id) REFERENCES alertas(id) ON DELETE SET NULL;

-- Índice adicional útil para consultas por alerta
CREATE INDEX idx_interacoes_alerta_id ON interacoes (alerta_id);

-- =====================================================
-- 8) LEMBRETES
-- =====================================================

CREATE TABLE lembretes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pessoa_cuidada_id UUID NOT NULL,
  cuidador_id UUID NOT NULL,
  rotina_id UUID,
  medicamento_id UUID,
  consulta_id UUID,
  tipo tipo_lembrete_enum NOT NULL,
  status status_lembrete_enum NOT NULL DEFAULT 'agendado',
  titulo VARCHAR(200) NOT NULL,
  mensagem TEXT NOT NULL,
  agendado_para TIMESTAMPTZ NOT NULL,
  enviado_em TIMESTAMPTZ,
  confirmado_em TIMESTAMPTZ,
  canais JSONB NOT NULL DEFAULT '["whatsapp"]'::jsonb,
  tentativas_envio SMALLINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_lembretes_pessoa
    FOREIGN KEY (pessoa_cuidada_id) REFERENCES pessoas_cuidadas(id) ON DELETE CASCADE,
  CONSTRAINT fk_lembretes_cuidador
    FOREIGN KEY (cuidador_id) REFERENCES cuidadores(id) ON DELETE CASCADE,
  CONSTRAINT fk_lembretes_rotina
    FOREIGN KEY (rotina_id) REFERENCES rotinas(id) ON DELETE SET NULL,
  CONSTRAINT fk_lembretes_medicamento
    FOREIGN KEY (medicamento_id) REFERENCES medicamentos(id) ON DELETE SET NULL,
  CONSTRAINT ck_lembretes_tentativas_envio CHECK (tentativas_envio >= 0)
);

CREATE INDEX idx_lembretes_pessoa_cuidada_id ON lembretes (pessoa_cuidada_id);
CREATE INDEX idx_lembretes_cuidador_id ON lembretes (cuidador_id);
CREATE INDEX idx_lembretes_agendado_para ON lembretes (agendado_para);
CREATE INDEX idx_lembretes_status ON lembretes (status);
CREATE INDEX idx_lembretes_tipo ON lembretes (tipo);

CREATE TRIGGER trg_lembretes_updated_at
BEFORE UPDATE ON lembretes
FOR EACH ROW EXECUTE FUNCTION atualizar_timestamp_modificacao();

COMMENT ON TABLE lembretes IS 'Lembretes agendados para medicamentos, consultas, exames e check-ins.';
COMMENT ON COLUMN lembretes.canais IS 'Canais de envio planejados (ex.: whatsapp, push).';

-- =====================================================
-- 9) CONSULTAS
-- =====================================================

CREATE TABLE consultas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pessoa_cuidada_id UUID NOT NULL,
  cuidador_id UUID NOT NULL,
  tipo tipo_consulta_enum NOT NULL,
  status status_consulta_enum NOT NULL DEFAULT 'agendada',
  especialidade VARCHAR(120),
  profissional_saude VARCHAR(150),
  local_consulta VARCHAR(200),
  agendada_para TIMESTAMPTZ NOT NULL,
  duracao_minutos SMALLINT,
  via_agendamento via_agendamento_enum NOT NULL DEFAULT 'manual',
  observacoes TEXT,
  retorno_recomendado_em DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_consultas_pessoa
    FOREIGN KEY (pessoa_cuidada_id) REFERENCES pessoas_cuidadas(id) ON DELETE CASCADE,
  CONSTRAINT fk_consultas_cuidador
    FOREIGN KEY (cuidador_id) REFERENCES cuidadores(id) ON DELETE CASCADE,
  CONSTRAINT ck_consultas_duracao CHECK (duracao_minutos IS NULL OR duracao_minutos > 0)
);

CREATE INDEX idx_consultas_pessoa_cuidada_id ON consultas (pessoa_cuidada_id);
CREATE INDEX idx_consultas_cuidador_id ON consultas (cuidador_id);
CREATE INDEX idx_consultas_agendada_para ON consultas (agendada_para);
CREATE INDEX idx_consultas_status ON consultas (status);

CREATE TRIGGER trg_consultas_updated_at
BEFORE UPDATE ON consultas
FOR EACH ROW EXECUTE FUNCTION atualizar_timestamp_modificacao();

COMMENT ON TABLE consultas IS 'Agendamento e acompanhamento de consultas médicas e exames.';
COMMENT ON COLUMN consultas.via_agendamento IS 'Origem do agendamento (manual, agente de IA ou integração externa).';

-- Constraint pendente lembretes -> consultas
ALTER TABLE lembretes
  ADD CONSTRAINT fk_lembretes_consulta
  FOREIGN KEY (consulta_id) REFERENCES consultas(id) ON DELETE SET NULL;

CREATE INDEX idx_lembretes_consulta_id ON lembretes (consulta_id);

COMMIT;
