-- Run in Supabase SQL editor if tables not yet created
create extension if not exists "pgcrypto";

create table if not exists cuidador (
  id uuid primary key default gen_random_uuid(),
  phone text unique not null,
  name text,
  relationship text,
  onboarding_step int not null default 0,
  onboarding_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists paciente (
  id uuid primary key default gen_random_uuid(),
  cuidador_id uuid not null references cuidador(id) on delete cascade,
  name text,
  age int,
  condition_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists interacao (
  id uuid primary key default gen_random_uuid(),
  cuidador_id uuid not null references cuidador(id) on delete cascade,
  paciente_id uuid references paciente(id) on delete set null,
  message_in text,
  message_out text,
  intent text,
  created_at timestamptz not null default now()
);

create index if not exists interacao_cuidador_created_idx on interacao(cuidador_id, created_at desc);
