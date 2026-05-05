"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.SupabaseService = void 0;
const common_1 = require("@nestjs/common");
const supabase_js_1 = require("@supabase/supabase-js");
const logger_1 = require("./logger");
let SupabaseService = class SupabaseService {
    client;
    onModuleInit() {
        this.client = (0, supabase_js_1.createClient)(process.env.SUPABASE_URL, process.env.SUPABASE_KEY, { auth: { persistSession: false } });
        logger_1.logger.info('Supabase client initialized');
    }
    get db() { return this.client; }
    async findCuidadorByPhone(phone) {
        const { data, error } = await this.client.from('cuidadores').select('*').eq('telefone_whatsapp', phone).maybeSingle();
        if (error) {
            logger_1.logger.error('findCuidadorByPhone error', { error });
            throw error;
        }
        return data;
    }
    async createCuidador(phone) {
        const initial = {
            nome_completo: 'Novo Cuidador',
            telefone_whatsapp: phone,
            parentesco: 'outro',
            idioma_preferido: 'pt-BR',
            fuso_horario: process.env.DEFAULT_TIMEZONE || 'America/Sao_Paulo',
            preferencias_notificacao: { onboarding: { step: 1, data: {} } },
        };
        const { data, error } = await this.client.from('cuidadores').insert(initial).select().single();
        if (error) {
            logger_1.logger.error('createCuidador error', { error });
            throw error;
        }
        return data;
    }
    async updateCuidador(id, patch) {
        const { data, error } = await this.client.from('cuidadores').update(patch).eq('id', id).select().single();
        if (error) {
            logger_1.logger.error('updateCuidador error', { error });
            throw error;
        }
        return data;
    }
    async createPessoaCuidada(p) {
        const { data, error } = await this.client.from('pessoas_cuidadas').insert(p).select().single();
        if (error) {
            logger_1.logger.error('createPessoaCuidada error', { error });
            throw error;
        }
        return data;
    }
    async findPessoaCuidadaByCuidador(cuidador_id) {
        const { data, error } = await this.client.from('pessoas_cuidadas').select('*').eq('cuidador_id', cuidador_id).order('created_at', { ascending: false }).limit(1).maybeSingle();
        if (error) {
            logger_1.logger.error('findPessoaCuidadaByCuidador error', { error });
            throw error;
        }
        return data;
    }
    async logInteracao(i) {
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
        if (error) {
            logger_1.logger.error('logInteracao error', { error, payload });
        }
    }
    async recentInteractions(cuidador_id, limit = 8) {
        const { data, error } = await this.client.from('interacoes').select('*').eq('cuidador_id', cuidador_id).order('ocorreu_em', { ascending: false }).limit(limit);
        if (error) {
            logger_1.logger.error('recentInteractions error', { error });
            return [];
        }
        return (data || []).reverse();
    }
};
exports.SupabaseService = SupabaseService;
exports.SupabaseService = SupabaseService = __decorate([
    (0, common_1.Injectable)()
], SupabaseService);
//# sourceMappingURL=supabase.service.js.map