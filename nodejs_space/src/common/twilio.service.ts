import { Injectable } from '@nestjs/common';
import { validateRequest } from 'twilio';
import { logger } from './logger';

@Injectable()
export class TwilioService {
  validateSignature(signature: string | undefined, url: string, params: Record<string, any>): boolean {
    const enabled = (process.env.VALIDATE_TWILIO_SIGNATURE || 'false').toLowerCase() === 'true';
    if (!enabled) return true;
    const token = process.env.TWILIO_AUTH_TOKEN || '';
    if (!signature) { logger.warn('twilio_signature_missing'); return false; }
    try {
      return validateRequest(token, signature, url, params as any);
    } catch (e) {
      logger.error('twilio_signature_validation_error', { e });
      return false;
    }
  }

  twiml(message: string): string {
    const safe = (message || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return `<?xml version="1.0" encoding="UTF-8"?>\n<Response><Message>${safe}</Message></Response>`;
  }
}
