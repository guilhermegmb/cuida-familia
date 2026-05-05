"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const core_1 = require("@nestjs/core");
const swagger_1 = require("@nestjs/swagger");
const express_1 = require("express");
const app_module_1 = require("./app.module");
const logger_1 = require("./common/logger");
async function bootstrap() {
    const app = await core_1.NestFactory.create(app_module_1.AppModule, { bodyParser: false });
    app.use((0, express_1.json)());
    app.use((0, express_1.urlencoded)({ extended: true }));
    app.enableCors({ origin: '*' });
    const swaggerPath = 'api-docs';
    app.use(`/${swaggerPath}`, (_req, res, next) => {
        res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
        res.setHeader('Pragma', 'no-cache');
        res.setHeader('Expires', '0');
        res.setHeader('Surrogate-Control', 'no-store');
        next();
    });
    const config = new swagger_1.DocumentBuilder()
        .setTitle('CuidaFamília API')
        .setDescription('Backend do agente CuidaFamília para WhatsApp')
        .setVersion('1.0.0')
        .build();
    const document = swagger_1.SwaggerModule.createDocument(app, config);
    swagger_1.SwaggerModule.setup(swaggerPath, app, document, {
        customSiteTitle: 'CuidaFamília API',
        customfavIcon: 'https://abacus.ai/favicon.ico',
        customCss: `.swagger-ui .topbar { display: none } .swagger-ui .info .title small { display:none } body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }`,
    });
    await app.listen(3000, '0.0.0.0');
    logger_1.logger.info('CuidaFamília backend listening on port 3000');
}
bootstrap();
//# sourceMappingURL=main.js.map