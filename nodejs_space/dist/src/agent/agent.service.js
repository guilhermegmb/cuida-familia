"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AgentService = void 0;
const common_1 = require("@nestjs/common");
const supabase_service_1 = require("../common/supabase.service");
const openrouter_service_1 = require("../common/openrouter.service");
const logger_1 = require("../common/logger");
const SYSTEM_PROMPT = `Você é o CuidaFamília, um assistente virtual acolhedor e empático especializado em apoiar cuidadores familiares de pessoas idosas, doentes crônicos ou com necessidades especiais.

Personalidade e tom:
- Caloroso, paciente, encorajador e respeitoso.
- Linguagem clara, simples e humana, em português do Brasil.
- Reconheça o esforço emocional do cuidador. Valide sentimentos antes de aconselhar.

O que você FAZ:
- Oferece suporte emocional e escuta ativa.
- Sugere dicas práticas de rotina, organização, autocuidado do cuidador, comunicação com a pessoa cuidada.
- Ajuda a estruturar lembretes, perguntas para levar ao médico, e organização de medicamentos (sem prescrever).
- Lembra do nome do cuidador e da pessoa cuidada quando souber, e personaliza as respostas.

O que você NÃO FAZ:
- Nunca dá diagnóstico médico, prescrição, ajuste de dose ou interpretação de exames.
- Em qualquer dúvida clínica, oriente claramente a procurar um profissional de saúde (médico, enfermeiro, psicólogo, assistente social).
- Em sinais de emergência (dor no peito, falta de ar súbita, desmaio, sangramento intenso, pensamentos de autolesão), oriente ligar imediatamente para o SAMU 192 ou ir ao pronto-socorro.

Formato:
- Respostas curtas (idealmente até 4-6 frases) e fáceis de ler no WhatsApp.
- Use no máximo 1 emoji quando fizer sentido emocional.`;
let AgentService = class AgentService {
    db;
    llm;
    constructor(db, llm) {
        this.db = db;
        this.llm = llm;
    }
    async handleMessage(phone, body) {
        let cuidador = await this.db.findCuidadorByPhone(phone);
        let isNew = false;
        if (!cuidador) {
            cuidador = await this.db.createCuidador(phone);
            isNew = true;
            logger_1.logger.info('cuidador_created', { phone, id: cuidador.id });
        }
        const onboarding = (cuidador.preferencias_notificacao?.onboarding) || { step: 0, data: {} };
        if (onboarding.step > 0 && onboarding.step < 5) {
            const result = await this.handleOnboarding(cuidador, body, isNew, onboarding);
            return { reply: result.reply, cuidador: result.updated, intent: 'onboarding', pessoa_cuidada_id: result.pessoa_cuidada_id };
        }
        const recent = await this.db.recentInteractions(cuidador.id, 8);
        const pessoa = await this.db.findPessoaCuidadaByCuidador(cuidador.id);
        const ctxLines = [];
        if (cuidador.nome_completo && cuidador.nome_completo !== 'Novo Cuidador')
            ctxLines.push(`Nome do cuidador: ${cuidador.nome_completo}.`);
        if (cuidador.parentesco && cuidador.parentesco !== 'outro')
            ctxLines.push(`Relação com a pessoa cuidada: ${cuidador.parentesco}.`);
        if (pessoa?.nome_completo)
            ctxLines.push(`Nome da pessoa cuidada: ${pessoa.nome_completo}.`);
        if (pessoa?.condicoes_clinicas)
            ctxLines.push(`Condições clínicas: ${pessoa.condicoes_clinicas}.`);
        if (pessoa?.observacoes)
            ctxLines.push(`Observações: ${pessoa.observacoes}.`);
        const messages = [
            { role: 'system', content: SYSTEM_PROMPT + (ctxLines.length ? `\n\nContexto sobre este usuário:\n- ${ctxLines.join('\n- ')}` : '') },
        ];
        for (const r of recent) {
            const role = r.papel_origem === 'agente' ? 'assistant' : 'user';
            if (r.conteudo)
                messages.push({ role, content: r.conteudo });
        }
        messages.push({ role: 'user', content: body });
        const reply = await this.llm.chat(messages);
        return { reply, cuidador, intent: 'chat', pessoa_cuidada_id: pessoa?.id || null };
    }
    async handleOnboarding(cuidador, body, isNew, onboarding) {
        let { step, data } = onboarding;
        data = { ...(data || {}) };
        let reply = '';
        let pessoa_cuidada_id = null;
        const text = (body || '').trim();
        if (isNew) {
            reply = 'Olá! 💛 Eu sou o CuidaFamília, seu assistente para apoiar cuidadores familiares. Para começarmos, como posso te chamar?';
            const updated = await this.db.updateCuidador(cuidador.id, {
                preferencias_notificacao: { ...(cuidador.preferencias_notificacao || {}), onboarding: { step: 1, data: {} } },
            });
            return { reply, updated, pessoa_cuidada_id: null };
        }
        const patch = {};
        if (step === 1) {
            data.cuidador_name = text.slice(0, 120);
            patch.nome_completo = data.cuidador_name || 'Cuidador';
            step = 2;
            reply = `Prazer em te conhecer, ${data.cuidador_name}! Qual é o nome da pessoa que você cuida?`;
        }
        else if (step === 2) {
            data.paciente_name = text.slice(0, 120);
            step = 3;
            reply = `Que bom saber sobre ${data.paciente_name}. Qual a idade dele(a)?`;
        }
        else if (step === 3) {
            const ageMatch = text.match(/\d{1,3}/);
            data.paciente_age = ageMatch ? parseInt(ageMatch[0], 10) : null;
            step = 4;
            reply = 'Obrigado! Por último: você pode me contar brevemente sobre a condição de saúde ou os principais desafios do cuidado?';
        }
        else if (step === 4) {
            data.condition_notes = text.slice(0, 1000);
            step = 5;
            let dataNasc = null;
            if (data.paciente_age && Number.isFinite(data.paciente_age)) {
                const yr = new Date().getFullYear() - data.paciente_age;
                dataNasc = `${yr}-01-01`;
            }
            try {
                const pessoa = await this.db.createPessoaCuidada({
                    cuidador_id: cuidador.id,
                    nome_completo: data.paciente_name || 'Pessoa cuidada',
                    data_nascimento: dataNasc || undefined,
                    condicoes_clinicas: data.condition_notes || null,
                    observacoes: data.condition_notes || null,
                });
                pessoa_cuidada_id = pessoa.id;
            }
            catch (e) {
                logger_1.logger.error('onboarding_create_pessoa_failed', { e });
            }
            reply = `Anotado, ${data.cuidador_name || ''}! 💛 A partir de agora estou aqui para te ajudar no dia a dia do cuidado com ${data.paciente_name || 'a pessoa que você cuida'}. Pode me mandar dúvidas, desabafos ou pedir dicas práticas a qualquer momento. Lembre-se: não substituo um profissional de saúde, mas posso caminhar com você. Como posso te ajudar agora?`;
        }
        patch.preferencias_notificacao = { ...(cuidador.preferencias_notificacao || {}), onboarding: { step, data } };
        const updated = await this.db.updateCuidador(cuidador.id, patch);
        return { reply, updated, pessoa_cuidada_id };
    }
};
exports.AgentService = AgentService;
exports.AgentService = AgentService = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [supabase_service_1.SupabaseService,
        openrouter_service_1.OpenRouterService])
], AgentService);
//# sourceMappingURL=agent.service.js.map