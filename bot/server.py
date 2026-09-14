import asyncio
import logging
import os
from aiohttp import web
from sqlalchemy.exc import SQLAlchemyError
from bot.database import Database
from bot.api import register_routes
from bot.webapp import APP_HTML

log = logging.getLogger(__name__)

@web.middleware
async def security_headers(request, handler):
    try:
        result = await handler(request)
    except web.HTTPException as error:
        result = web.Response(status=error.status, text=error.text, headers=error.headers)
    except (SQLAlchemyError, OSError, asyncio.TimeoutError):
        log.error('Database or network operation failed (%s)', request.path)
        result = web.json_response({'error': 'Сервис временно недоступен. Попробуйте позже.'}, status=503)
    result.headers['X-Content-Type-Options'] = 'nosniff'
    result.headers['Referrer-Policy'] = 'no-referrer'
    result.headers['Cache-Control'] = 'no-store'
    if request.path == '/admin':
        result.headers['X-Frame-Options'] = 'DENY'
        result.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return result

async def health(request):
    await asyncio.wait_for(request.app['db'].ping(), timeout=5)
    task = request.app.get('polling_task')
    if task and task.done():
        return web.json_response({'status': 'error', 'database': 'ok', 'polling': 'stopped'}, status=503)
    return web.json_response({'status': 'ok', 'database': 'ok',
        'polling': request.app.get('polling_state', 'disabled')})

async def app_page(request):
    return web.Response(text=APP_HTML, content_type='text/html')

async def storage_context(app):
    try:
        await app['db'].initialize(seed=app['settings'].get('SEED_TEST_DATA', 'false').lower() == 'true')
        yield
    finally:
        await app['db'].close()


def create_app(settings=None):
    settings = dict(os.environ if settings is None else settings)
    app = web.Application(middlewares=[security_headers], client_max_size=32 * 1024)
    app['settings'] = settings
    app['db'] = Database(settings.get('DATABASE_URL'))
    app.cleanup_ctx.append(storage_context)
    app.router.add_get('/', health)
    app.router.add_get('/health', health)
    app.router.add_get('/app', app_page)
    register_routes(app)
    return app
