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
var __param = (this && this.__param) || function (paramIndex, decorator) {
    return function (target, key) { decorator(target, key, paramIndex); }
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.WebhookController = void 0;
const common_1 = require("@nestjs/common");
const swagger_1 = require("@nestjs/swagger");
const agent_service_1 = require("../agent/agent.service");
const twilio_service_1 = require("../common/twilio.service");
const supabase_service_1 = require("../common/supabase.service");
const logger_1 = require("../common/logger");
let WebhookController = class WebhookController {
    agent;
    twilio;
    db;
    constructor(agent, twilio, db) {
        this.agent = agent;
        this.twilio = twilio;
        this.db = db;
    }
    async twilioWebhook(req, res, signature, body) {
        const url = `${process.env.APP_ORIGIN ? process.env.APP_ORIGIN.replace(/\/$/, '') : `${req.protocol}://${req.get('host')}`}/webhook/twilio`;
        logger_1.logger.info('twilio_webhook_received', { from: body?.From, sid: body?.MessageSid, body: body?.Body });
        if (!this.twilio.validateSignature(signature, url, body)) {
            logger_1.logger.warn('twilio_signature_invalid');
            res.status(403).type('text/xml').send(this.twilio.twiml('Assinatura inválida.'));
            return;
        }
        const from = (body?.From || '').toString();
        const text = (body?.Body || '').toString();
        const phone = from.replace(/^whatsapp:/i, '').trim();
        if (!phone) {
            res.status(200).type('text/xml').send(this.twilio.twiml('Não consegui identificar o remetente.'));
            return;
        }
        try {
            const { reply, cuidador, intent, pessoa_cuidada_id } = await this.agent.handleMessage(phone, text);
            await this.db.logInteracao({
                cuidador_id: cuidador.id,
                pessoa_cuidada_id,
                tipo: 'mensagem',
                papel_origem: 'cuidador',
                canal: 'whatsapp',
                conteudo: text,
                contexto_json: { intent, message_sid: body?.MessageSid },
            });
            await this.db.logInteracao({
                cuidador_id: cuidador.id,
                pessoa_cuidada_id,
                tipo: 'mensagem',
                papel_origem: 'agente',
                canal: 'whatsapp',
                conteudo: reply,
                contexto_json: { intent, in_reply_to: body?.MessageSid },
            });
            res.status(200).type('text/xml').send(this.twilio.twiml(reply));
        }
        catch (err) {
            logger_1.logger.error('webhook_handler_error', { error: err?.message, stack: err?.stack });
            res.status(200).type('text/xml').send(this.twilio.twiml('Desculpe, tive um problema agora. Pode tentar novamente em instantes? 💛'));
        }
    }
    async test(body, res) {
        const phone = body?.phone || '+550000000000';
        const text = body?.text || 'Olá';
        const result = await this.agent.handleMessage(phone, text);
        res.json({ reply: result.reply, intent: result.intent });
    }
};
exports.WebhookController = WebhookController;
__decorate([
    (0, common_1.Post)('twilio'),
    (0, swagger_1.ApiOperation)({ summary: 'Twilio WhatsApp webhook (form-encoded)' }),
    __param(0, (0, common_1.Req)()),
    __param(1, (0, common_1.Res)()),
    __param(2, (0, common_1.Headers)('x-twilio-signature')),
    __param(3, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object, Object, String, Object]),
    __metadata("design:returntype", Promise)
], WebhookController.prototype, "twilioWebhook", null);
__decorate([
    (0, common_1.Post)('twilio/test'),
    (0, swagger_1.ApiExcludeEndpoint)(),
    __param(0, (0, common_1.Body)()),
    __param(1, (0, common_1.Res)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object, Object]),
    __metadata("design:returntype", Promise)
], WebhookController.prototype, "test", null);
exports.WebhookController = WebhookController = __decorate([
    (0, swagger_1.ApiTags)('webhook'),
    (0, common_1.Controller)('webhook'),
    __metadata("design:paramtypes", [agent_service_1.AgentService,
        twilio_service_1.TwilioService,
        supabase_service_1.SupabaseService])
], WebhookController);
//# sourceMappingURL=webhook.controller.js.map