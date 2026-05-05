import { Body, Controller, Headers, Post, Req, Res } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiExcludeEndpoint } from '@nestjs/swagger';
import type { Request, Response } from 'express';
import { AgentService } from '../agent/agent.service';
import { TwilioService } from '../common/twilio.service';
import { SupabaseService } from '../common/supabase.service';
import { logger } from '../common/logger';

@ApiTags('webhook')
@Controller('webhook')
export class WebhookController {
  constructor(
    private readonly agent: AgentService,
    private readonly twilio: TwilioService,
    private readonly db: SupabaseService,
  ) {}

  @Post('twilio')
  @ApiOperation({ summary: 'Twilio WhatsApp webhook (form-encoded)' })
  async twilioWebhook(
    @Req() req: Request,
    @Res() res: Response,
    @Headers('x-twilio-signature') signature: string,
    @Body() body: any,
  ) {
    const url = `${process.env.APP_ORIGIN ? process.env.APP_ORIGIN.replace(/\/$/, '') : `${req.protocol}://${req.get('host')}`}/webhook/twilio`;
    logger.info('twilio_webhook_received', { from: body?.From, sid: body?.MessageSid, body: body?.Body });

    if (!this.twilio.validateSignature(signature, url, body)) {
      logger.warn('twilio_signature_invalid');
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
      // Persist incoming + outgoing as two interacao rows
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
    } catch (err: any) {
      logger.error('webhook_handler_error', { error: err?.message, stack: err?.stack });
      res.status(200).type('text/xml').send(this.twilio.twiml('Desculpe, tive um problema agora. Pode tentar novamente em instantes? 💛'));
    }
  }

  @Post('twilio/test')
  @ApiExcludeEndpoint()
  async test(@Body() body: any, @Res() res: Response) {
    const phone = body?.phone || '+550000000000';
    const text = body?.text || 'Olá';
    const result = await this.agent.handleMessage(phone, text);
    res.json({ reply: result.reply, intent: result.intent });
  }
}
