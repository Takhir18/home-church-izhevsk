import asyncio
import hmac
from datetime import datetime, timezone
from aiohttp import web, BasicAuth
from aiogram.utils.web_app import safe_parse_webapp_init_data


def telegram_user(init_data, token):
    if not token or not isinstance(init_data, str) or len(init_data) > 8192:
        raise web.HTTPUnauthorized(text='Откройте каталог заново через Telegram-бота.')
    try:
        parsed = safe_parse_webapp_init_data(token=token, init_data=init_data)
        age = (datetime.now(timezone.utc) - parsed.auth_date).total_seconds()
        if age < -30 or age > 3600 or not parsed.user or parsed.user.id <= 0:
            raise ValueError('Expired or missing user')
    except (ValueError, TypeError, KeyError):
        raise web.HTTPUnauthorized(text='Откройте каталог заново через Telegram-бота.')
    return dict(id=parsed.user.id, name=' '.join(filter(None, [parsed.user.first_name, parsed.user.last_name]))[:200], username=parsed.user.username)


async def require_admin(request):
    settings = request.app['settings']
    password = settings.get('ADMIN_PASSWORD', '')
    username = settings.get('ADMIN_USERNAME', 'admin')
    if len(password) < 16 or not username:
        raise web.HTTPServiceUnavailable(text='Админка не настроена: задайте ADMIN_PASSWORD (от 16 символов).')
    try:
        auth = BasicAuth.decode(request.headers.get('Authorization', ''))
        valid = hmac.compare_digest(auth.login.encode(), username.encode()) & hmac.compare_digest(auth.password.encode(), password.encode())
    except (ValueError, UnicodeError):
        valid = False
    if not valid:
        await asyncio.sleep(0.3)
        raise web.HTTPUnauthorized(headers={'WWW-Authenticate': 'Basic realm="Church admin", charset="UTF-8"'})
    # Custom header cannot be sent by cross-origin forms; CORS is deliberately disabled.
    if request.method not in ('GET', 'HEAD'):
        if request.headers.get('X-Admin-Request') != '1':
            raise web.HTTPForbidden(text='Missing X-Admin-Request')
        if request.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise web.HTTPForbidden(text='Cross-site request denied')
