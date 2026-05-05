import { Injectable, OnModuleInit } from '@nestjs/common';
import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { logger } from './logger';

export interface Cuidador {
  id: string;
  nome_completo: string;
  telefone_whatsapp: string;
  parentesco: string;
  email?: string | null;
  preferencias_notificacao?: any;
  observacoes?: string | null;
  fuso_horario?: string | null;
  idioma_preferido?: string | null;
  ativo?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface PessoaCuidada {
  id: string;
  cuidador_id: string;
  nome_completo: string;
  data_nascimento?: string | null;
  observacoes?: string | null;
  condicoes_clinicas?: string | null;
}

export interface Interacao {
  id: string;
  cuidador_id: string;
  pessoa_cuidada_id?: string | null;
  tipo: string;
  papel_origem: 'cuidador' | 'agente' | 'sistema';
  canal: string;
  conteudo: string;
  contexto_json?: any;
  ocorreu_em?: string;
}

@Injectable()
export class SupabaseService implements OnModuleInit {
  private client!: SupabaseClient;

  onModuleInit() {
    this.client = createClient(
      process.env.SUPABASE_URL as string,
      process.env.SUPABASE_KEY as string,
      { auth: { persistSession: false } },
    );
    logger.info('Supabase client initialized');
  }

  get db() { return this.client; }

  async findCuidadorByPhone(phone: string): Promise<Cuidador | null> {
    const { data, error } = await this.client.from('cuidadores').select('*').eq('telefone_whatsapp', phone).maybeSingle();
    if (error) { logger.error('findCuidadorByPhone error', { error }); throw error; }
    return data as Cuidador | null;
  }

  async createCuidador(phone: string): Promise<Cuidador> {
    const initial = {
      nome_completo: 'Novo Cuidador',
      telefone_whatsapp: phone,
      parentesco: 'outro',
      idioma_preferido: 'pt-BR',
      fuso_horario: process.env.DEFAULT_TIMEZONE || 'America/Sao_Paulo',
      preferencias_notificacao: { onboarding: { step: 1, data: {} } },
    };
    const { data, error } = await this.client.from('cuidadores').insert(initial).select().single();
    if (error) { logger.error('createCuidador error', { error }); throw error; }
    return data as Cuidador;
  }

  async updateCuidador(id: string, patch: Partial<Cuidador>): Promise<Cuidador> {
    const { data, error } = await this.client.from('cuidadores').update(patch).eq('id', id).select().single();
    if (error) { logger.error('updateCuidador error', { error }); throw error; }
    return data as Cuidador;
  }

  async createPessoaCuidada(p: Partial<PessoaCuidada>): Promise<PessoaCuidada> {
    const { data, error } = await this.client.from('pessoas_cuidadas').insert(p).select().single();
    if (error) { logger.error('createPessoaCuidada error', { error }); throw error; }
    return data as PessoaCuidada;
  }

  async findPessoaCuidadaByCuidador(cuidador_id: string): Promise<PessoaCuidada | null> {
    const { data, error } = await this.client.from('pessoas_cuidadas').select('*').eq('cuidador_id', cuidador_id).order('created_at', { ascending: false }).limit(1).maybeSingle();
    if (error) { logger.error('findPessoaCuidadaByCuidador error', { error }); throw error; }
    return data as PessoaCuidada | null;
  }

  async logInteracao(i: Partial<Interacao>): Promise<void> {
    const payload = {
      tipo: i.tipo || 'mensagem',
      papel_origem: i.papel_origem || 'cuidador',
      canal: i.canal || 'whatsapp',
      conteudo: i.conteudo || '',
      contexto_json: i.contexto_json || {},
      cuidador_id: i.cuidador_id,
      pessoa_cuidada_id: i.pessoa_cuidada_id || null,
    };
    const { error } = await this.client.from('interacoes').insert(payload);
    if (error) { logger.error('logInteracao error', { error, payload }); }
  }

  async recentInteractions(cuidador_id: string, limit = 8): Promise<Interacao[]> {
    const { data, error } = await this.client.from('interacoes').select('*').eq('cuidador_id', cuidador_id).order('ocorreu_em', { ascending: false }).limit(limit);
    if (error) { logger.error('recentInteractions error', { error }); return []; }
    return ((data || []) as Interacao[]).reverse();
  }
}
