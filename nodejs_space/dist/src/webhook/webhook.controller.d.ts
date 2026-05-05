import type { Request, Response } from 'express';
import { AgentService } from '../agent/agent.service';
import { TwilioService } from '../common/twilio.service';
import { SupabaseService } from '../common/supabase.service';
export declare class WebhookController {
    private readonly agent;
    private readonly twilio;
    private readonly db;
    constructor(agent: AgentService, twilio: TwilioService, db: SupabaseService);
    twilioWebhook(req: Request, res: Response, signature: string, body: any): Promise<void>;
    test(body: any, res: Response): Promise<void>;
}
