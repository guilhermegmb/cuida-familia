import { OnModuleInit } from '@nestjs/common';
import { SupabaseClient } from '@supabase/supabase-js';
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
export declare class SupabaseService implements OnModuleInit {
    private client;
    onModuleInit(): void;
    get db(): SupabaseClient<any, "public", "public", any, any>;
    findCuidadorByPhone(phone: string): Promise<Cuidador | null>;
    createCuidador(phone: string): Promise<Cuidador>;
    updateCuidador(id: string, patch: Partial<Cuidador>): Promise<Cuidador>;
    createPessoaCuidada(p: Partial<PessoaCuidada>): Promise<PessoaCuidada>;
    findPessoaCuidadaByCuidador(cuidador_id: string): Promise<PessoaCuidada | null>;
    logInteracao(i: Partial<Interacao>): Promise<void>;
    recentInteractions(cuidador_id: string, limit?: number): Promise<Interacao[]>;
}
