-- Migração corretiva para alinhar a tabela public.cuidadores com o schema.sql
-- Objetivo principal: corrigir erro "column cuidadores.data_nascimento does not exist"
-- Seguro para reexecução (idempotente): usa IF NOT EXISTS.

BEGIN;

-- Garante tipos ENUM necessários, caso não existam no banco atual
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'genero_enum') THEN
    CREATE TYPE public.genero_enum AS ENUM ('feminino', 'masculino', 'nao_binario', 'prefiro_nao_informar');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'parentesco_enum') THEN
    CREATE TYPE public.parentesco_enum AS ENUM (
      'filho', 'filha', 'conjuge', 'irmao', 'irma', 'neto', 'neta', 'sobrinho', 'sobrinha',
      'amigo', 'vizinho', 'cuidador_profissional', 'outro'
    );
  END IF;
END $$;

ALTER TABLE IF EXISTS public.cuidadores
  ADD COLUMN IF NOT EXISTS nome_completo VARCHAR(150),
  ADD COLUMN IF NOT EXISTS telefone_whatsapp VARCHAR(20),
  ADD COLUMN IF NOT EXISTS email VARCHAR(255),
  ADD COLUMN IF NOT EXISTS data_nascimento DATE,
  ADD COLUMN IF NOT EXISTS genero public.genero_enum,
  ADD COLUMN IF NOT EXISTS parentesco public.parentesco_enum,
  ADD COLUMN IF NOT EXISTS idioma_preferido VARCHAR(10) DEFAULT 'pt-BR',
  ADD COLUMN IF NOT EXISTS fuso_horario VARCHAR(60) DEFAULT 'America/Sao_Paulo',
  ADD COLUMN IF NOT EXISTS ativo BOOLEAN DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS preferencias_notificacao JSONB DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS observacoes TEXT,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Garantir defaults esperados (sem forçar NOT NULL para não quebrar dados legados)
ALTER TABLE IF EXISTS public.cuidadores
  ALTER COLUMN idioma_preferido SET DEFAULT 'pt-BR',
  ALTER COLUMN fuso_horario SET DEFAULT 'America/Sao_Paulo',
  ALTER COLUMN ativo SET DEFAULT TRUE,
  ALTER COLUMN preferencias_notificacao SET DEFAULT '{}'::jsonb,
  ALTER COLUMN created_at SET DEFAULT NOW(),
  ALTER COLUMN updated_at SET DEFAULT NOW();

-- Backfill leve para linhas antigas onde fizer sentido
UPDATE public.cuidadores
SET
  idioma_preferido = COALESCE(idioma_preferido, 'pt-BR'),
  fuso_horario = COALESCE(fuso_horario, 'America/Sao_Paulo'),
  ativo = COALESCE(ativo, TRUE),
  preferencias_notificacao = COALESCE(preferencias_notificacao, '{}'::jsonb),
  created_at = COALESCE(created_at, NOW()),
  updated_at = COALESCE(updated_at, NOW())
WHERE
  idioma_preferido IS NULL
  OR fuso_horario IS NULL
  OR ativo IS NULL
  OR preferencias_notificacao IS NULL
  OR created_at IS NULL
  OR updated_at IS NULL;

COMMIT;
