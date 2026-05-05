"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.OpenRouterService = void 0;
const common_1 = require("@nestjs/common");
const axios_1 = __importDefault(require("axios"));
const logger_1 = require("./logger");
let OpenRouterService = class OpenRouterService {
    url = 'https://openrouter.ai/api/v1/chat/completions';
    fallback = 'Desculpe, estou tendo dificuldades técnicas no momento. Por favor, tente novamente em alguns instantes.';
    async chat(messages) {
        const model = process.env.OPENROUTER_MODEL || 'openai/gpt-4o-mini';
        const apiKey = process.env.OPENROUTER_API_KEY;
        const maxAttempts = 3;
        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
            const start = Date.now();
            try {
                const resp = await axios_1.default.post(this.url, {
                    model, messages, temperature: 0.7, max_tokens: 600,
                }, {
                    headers: {
                        Authorization: `Bearer ${apiKey}`,
                        'Content-Type': 'application/json',
                        'HTTP-Referer': 'https://cuidafamilia.abacusai.app',
                        'X-Title': 'CuidaFamilia',
                    },
                    timeout: 15000,
                });
                const content = resp.data?.choices?.[0]?.message?.content?.trim();
                const latency = Date.now() - start;
                logger_1.logger.info('openrouter_call_success', { attempt, latency, model });
                if (content)
                    return content;
                throw new Error('Empty content from OpenRouter');
            }
            catch (err) {
                const latency = Date.now() - start;
                logger_1.logger.error('openrouter_call_error', { attempt, latency, error: err?.message, data: err?.response?.data });
                if (attempt === maxAttempts) {
                    logger_1.logger.warn('openrouter_fallback_activated');
                    return this.fallback;
                }
                await new Promise(r => setTimeout(r, 500 * Math.pow(2, attempt - 1)));
            }
        }
        return this.fallback;
    }
};
exports.OpenRouterService = OpenRouterService;
exports.OpenRouterService = OpenRouterService = __decorate([
    (0, common_1.Injectable)()
], OpenRouterService);
//# sourceMappingURL=openrouter.service.js.map