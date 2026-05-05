import { NestFactory } from '@nestjs/core';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { Request, Response, NextFunction } from 'express';
import { json, urlencoded } from 'express';
import { AppModule } from './app.module';
import { logger } from './common/logger';

async function bootstrap() {
  const app = await NestFactory.create(AppModule, { bodyParser: false });
  app.use(json());
  app.use(urlencoded({ extended: true }));
  app.enableCors({ origin: '*' });

  const swaggerPath = 'api-docs';
  app.use(`/${swaggerPath}`, (_req: Request, res: Response, next: NextFunction) => {
    res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');
    res.setHeader('Surrogate-Control', 'no-store');
    next();
  });

  const config = new DocumentBuilder()
    .setTitle('CuidaFamília API')
    .setDescription('Backend do agente CuidaFamília para WhatsApp')
    .setVersion('1.0.0')
    .build();
  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup(swaggerPath, app, document, {
    customSiteTitle: 'CuidaFamília API',
    customfavIcon: 'https://abacus.ai/favicon.ico',
    customCss: `.swagger-ui .topbar { display: none } .swagger-ui .info .title small { display:none } body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }`,
  });

  const port = parseInt(process.env.PORT || '3000', 10);
  await app.listen(port, '0.0.0.0');
  logger.info(`CuidaFamília backend listening on port ${port}`);
}
bootstrap();
