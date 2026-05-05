import { Injectable } from '@nestjs/common';
import axios from 'axios';
import { logger } from './logger';

export interface ChatMessage { role: 'system' | 'user' | 'assistant'; content: string; }

@Injectable()
export class OpenRouterService {
  private readonly url = 'https://openrouter.ai/api/v1/chat/completions';
  private readonly fallback = 'Desculpe, estou tendo dificuldades técnicas no momento. Por favor, tente novamente em alguns instantes.';

  async chat(messages: ChatMessage[]): Promise<string> {
    const model = process.env.OPENROUTER_MODEL || 'openai/gpt-4o-mini';
    const apiKey = process.env.OPENROUTER_API_KEY;
    const maxAttempts = 3;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      const start = Date.now();
      try {
        const resp = await axios.post(this.url, {
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
        logger.info('openrouter_call_success', { attempt, latency, model });
        if (content) return content;
        throw new Error('Empty content from OpenRouter');
      } catch (err: any) {
        const latency = Date.now() - start;
        logger.error('openrouter_call_error', { attempt, latency, error: err?.message, data: err?.response?.data });
        if (attempt === maxAttempts) {
          logger.warn('openrouter_fallback_activated');
          return this.fallback;
        }
        await new Promise(r => setTimeout(r, 500 * Math.pow(2, attempt - 1)));
      }
    }
    return this.fallback;
  }
}
