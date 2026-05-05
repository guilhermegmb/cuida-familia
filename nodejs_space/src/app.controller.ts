import { Controller, Get, Redirect } from '@nestjs/common';
import { ApiExcludeEndpoint } from '@nestjs/swagger';

@Controller()
export class AppController {
  @Get()
  @Redirect('/api-docs', 302)
  @ApiExcludeEndpoint()
  root() {
    // Redirects to API documentation
  }
}
