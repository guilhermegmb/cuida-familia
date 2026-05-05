-- ============================================================
-- CuidaFamília — Schema Completo Supabase
-- Execute este SQL no SQL Editor do Supabase
-- ============================================================

-- Extensão para UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- TABELA: cuidadores
-- Pessoa que usa o agente (quem envia mensagens no WhatsApp)
-- ============================================================
CREATE TABLE IF NOT EXISTS cuidadores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome TEXT,
    telefone TEXT UNIQUE NOT NULL,          -- ex: +5511999999999
    onboarding_completo BOOLEAN DEFAULT FALSE,
    etapa_onboarding TEXT DEFAULT 'inicio', -- inicio | nome | pessoa_cuidada | completo
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: pessoas_cuidadas
-- O ente querido que está sendo cuidado
-- ============================================================
CREATE TABLE IF NOT EXISTS pessoas_cuidadas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cuidador_id UUID NOT NULL REFERENCES cuidadores(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    relacao TEXT,                           -- ex: mãe, pai, avó, cônjuge
    idade INTEGER,
    condicoes_saude TEXT,                   -- texto livre por ora
    medicamentos TEXT,                      -- texto livre por ora
    observacoes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: interacoes
-- Histórico de todas as mensagens trocadas
-- ============================================================
CREATE TABLE IF NOT EXISTS interacoes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cuidador_id UUID NOT NULL REFERENCES cuidadores(id) ON DELETE CASCADE,
    papel TEXT NOT NULL CHECK (papel IN ('user', 'assistant')),
    mensagem TEXT NOT NULL,
    tokens_usados INTEGER DEFAULT 0,
    modelo_llm TEXT DEFAULT 'openai/gpt-4o-mini',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: memoria_agente
-- Memória persistente do agente por cuidador
-- ============================================================
CREATE TABLE IF NOT EXISTS memoria_agente (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cuidador_id UUID NOT NULL REFERENCES cuidadores(id) ON DELETE CASCADE,
    chave TEXT NOT NULL,                    -- ex: "ultima_consulta", "medicamento_principal"
    valor TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(cuidador_id, chave)
);

-- ============================================================
-- TABELA: logs_sistema
-- Logs de erros e eventos importantes
-- ============================================================
CREATE TABLE IF NOT EXISTS logs_sistema (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nivel TEXT NOT NULL CHECK (nivel IN ('INFO', 'WARNING', 'ERROR')),
    evento TEXT NOT NULL,
    detalhes JSONB,
    telefone TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- ÍNDICES para performance
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_cuidadores_telefone ON cuidadores(telefone);
CREATE INDEX IF NOT EXISTS idx_interacoes_cuidador ON interacoes(cuidador_id);
CREATE INDEX IF NOT EXISTS idx_interacoes_created ON interacoes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memoria_cuidador ON memoria_agente(cuidador_id);
CREATE INDEX IF NOT EXISTS idx_pessoas_cuidador ON pessoas_cuidadas(cuidador_id);

-- ============================================================
-- FUNÇÃO: atualizar updated_at automaticamente
-- ============================================================
CREATE OR REPLACE FUNCTION atualizar_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers para updated_at
CREATE TRIGGER trg_cuidadores_updated_at
    BEFORE UPDATE ON cuidadores
    FOR EACH ROW EXECUTE FUNCTION atualizar_updated_at();

CREATE TRIGGER trg_pessoas_cuidadas_updated_at
    BEFORE UPDATE ON pessoas_cuidadas
    FOR EACH ROW EXECUTE FUNCTION atualizar_updated_at();

CREATE TRIGGER trg_memoria_agente_updated_at
    BEFORE UPDATE ON memoria_agente
    FOR EACH ROW EXECUTE FUNCTION atualizar_updated_at();

-- ============================================================
-- ROW LEVEL SECURITY (RLS) — Segurança básica
-- ============================================================
ALTER TABLE cuidadores ENABLE ROW LEVEL SECURITY;
ALTER TABLE pessoas_cuidadas ENABLE ROW LEVEL SECURITY;
ALTER TABLE interacoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE memoria_agente ENABLE ROW LEVEL SECURITY;
ALTER TABLE logs_sistema ENABLE ROW LEVEL SECURITY;

-- Política: service_role tem acesso total (usado pelo backend)
CREATE POLICY "service_role_all" ON cuidadores FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON pessoas_cuidadas FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON interacoes FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON memoria_agente FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON logs_sistema FOR ALL TO service_role USING (true);

-- ============================================================
-- FIM DO SCHEMA
-- ============================================================
SELECT 'Schema CuidaFamília criado com sucesso!' AS status;
