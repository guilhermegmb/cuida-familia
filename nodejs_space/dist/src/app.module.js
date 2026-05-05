"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AppModule = void 0;
const common_1 = require("@nestjs/common");
const config_1 = require("@nestjs/config");
const app_controller_1 = require("./app.controller");
const health_controller_1 = require("./health/health.controller");
const webhook_controller_1 = require("./webhook/webhook.controller");
const supabase_service_1 = require("./common/supabase.service");
const openrouter_service_1 = require("./common/openrouter.service");
const twilio_service_1 = require("./common/twilio.service");
const agent_service_1 = require("./agent/agent.service");
let AppModule = class AppModule {
};
exports.AppModule = AppModule;
exports.AppModule = AppModule = __decorate([
    (0, common_1.Module)({
        imports: [config_1.ConfigModule.forRoot({ isGlobal: true })],
        controllers: [app_controller_1.AppController, health_controller_1.HealthController, webhook_controller_1.WebhookController],
        providers: [supabase_service_1.SupabaseService, openrouter_service_1.OpenRouterService, twilio_service_1.TwilioService, agent_service_1.AgentService],
    })
], AppModule);
//# sourceMappingURL=app.module.js.map