import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { AppController } from './app.controller';
import { HealthController } from './health/health.controller';
import { WebhookController } from './webhook/webhook.controller';
import { SupabaseService } from './common/supabase.service';
import { OpenRouterService } from './common/openrouter.service';
import { TwilioService } from './common/twilio.service';
import { AgentService } from './agent/agent.service';

@Module({
  imports: [ConfigModule.forRoot({ isGlobal: true })],
  controllers: [AppController, HealthController, WebhookController],
  providers: [SupabaseService, OpenRouterService, TwilioService, AgentService],
})
export class AppModule {}
