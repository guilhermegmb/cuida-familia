"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.TwilioService = void 0;
const common_1 = require("@nestjs/common");
const twilio_1 = require("twilio");
const logger_1 = require("./logger");
let TwilioService = class TwilioService {
    validateSignature(signature, url, params) {
        const enabled = (process.env.VALIDATE_TWILIO_SIGNATURE || 'false').toLowerCase() === 'true';
        if (!enabled)
            return true;
        const token = process.env.TWILIO_AUTH_TOKEN || '';
        if (!signature) {
            logger_1.logger.warn('twilio_signature_missing');
            return false;
        }
        try {
            return (0, twilio_1.validateRequest)(token, signature, url, params);
        }
        catch (e) {
            logger_1.logger.error('twilio_signature_validation_error', { e });
            return false;
        }
    }
    twiml(message) {
        const safe = (message || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return `<?xml version="1.0" encoding="UTF-8"?>\n<Response><Message>${safe}</Message></Response>`;
    }
};
exports.TwilioService = TwilioService;
exports.TwilioService = TwilioService = __decorate([
    (0, common_1.Injectable)()
], TwilioService);
//# sourceMappingURL=twilio.service.js.map