import json
from datetime import datetime
from pathlib import Path
from aiohttp import web
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Annotated
from bot.security import require_admin, telegram_user
from bot.notifications import notify

class ChurchInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    leader: str = Field(min_length=1, max_length=120)
    leader_username: str | None = Field(default=None, pattern=r'^[A-Za-z][A-Za-z0-9_]{4,31}$')
    district: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=300)
    meeting: str = Field(min_length=1, max_length=160)
    age: str = Field(min_length=1, max_length=80)
    participants: int = Field(ge=0, le=10000, strict=True)
    interests: list[Annotated[str, Field(min_length=1, max_length=60)]] = Field(max_length=15)
    description: str = Field(min_length=1, max_length=3000)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    is_test: bool = Field(default=True, strict=True)
    active: bool = Field(default=True, strict=True)

class JoinInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    church_id: int = Field(gt=0, strict=True)
    init_data: str = Field(min_length=1, max_length=8192)

class StatusInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: str = Field(pattern=r'^(new|contacted|closed)$')

def response(data, status=200):
    return web.json_response(data, status=status, dumps=lambda x: json.dumps(x, ensure_ascii=False,
        default=lambda v: v.isoformat() if isinstance(v, datetime) else str(v)))

async def payload(request, model):
    if request.content_type != 'application/json':
        raise web.HTTPBadRequest(text='Нужен JSON.')
    try:
        return model.model_validate(await request.json()).model_dump()
    except (ValueError, ValidationError, TypeError):
        raise web.HTTPBadRequest(text='Проверьте поля: неверный формат или значение.')

def ident(request, key):
    try:
        value = int(request.match_info[key])
        if value < 1:
            raise ValueError()
        return value
    except ValueError:
        raise web.HTTPBadRequest(text='Неверный ID.')

async def catalog(request):
    return response(await request.app['db'].list_churches(request.query.get('district')))

async def church(request):
    item = await request.app['db'].church(ident(request, 'church_id'))
    if not item:
        raise web.HTTPNotFound(text='Церковь не найдена.')
    return response(item)

async def join(request):
    data = await payload(request, JoinInput)
    user = telegram_user(data['init_data'], request.app['settings'].get('BOT_TOKEN'))
    try:
        item, created = await request.app['db'].join(data['church_id'], user, 'mini_app')
    except LookupError:
        raise web.HTTPNotFound(text='Церковь не найдена.')
    if created:
        await notify(request.app['settings'], item)
    # Acknowledgment is returned only after the database transaction commits.
    return response({'id': item['id'], 'status': item['status'], 'created': created}, 201 if created else 200)

async def admin_page(request):
    await require_admin(request)
    return web.Response(text=Path(__file__).with_name('admin.html').read_text(), content_type='text/html')

async def admin_churches(request):
    await require_admin(request)
    if request.method == 'GET':
        return response(await request.app['db'].list_churches(include_inactive=True))
    data = await payload(request, ChurchInput)
    return response(await request.app['db'].save_church(data), 201)

async def edit_church(request):
    await require_admin(request)
    data = await payload(request, ChurchInput)
    item = await request.app['db'].save_church(data, ident(request, 'church_id'))
    if not item:
        raise web.HTTPNotFound(text='Церковь не найдена.')
    return response(item)

async def admin_requests(request):
    await require_admin(request)
    try:
        limit = int(request.query.get('limit', 50)); offset = int(request.query.get('offset', 0))
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError()
    except ValueError:
        raise web.HTTPBadRequest(text='Неверная пагинация.')
    status = request.query.get('status') or None
    if status and status not in ('new', 'contacted', 'closed'):
        raise web.HTTPBadRequest(text='Неверный статус.')
    return response(await request.app['db'].list_requests(limit, offset, status))

async def admin_request(request):
    await require_admin(request)
    request_id = ident(request, 'request_id')
    if request.method == 'PATCH':
        data = await payload(request, StatusInput)
        item = await request.app['db'].request_status(request_id, data['status'])
    else:
        rows = await request.app['db'].list_requests(request_id=request_id)
        item = rows[0] if rows else None
    if not item:
        raise web.HTTPNotFound(text='Заявка не найдена.')
    return response(item)


def register_routes(app):
    app.router.add_get('/api/churches', catalog)
    app.router.add_get('/api/churches/{church_id}', church)
    app.router.add_post('/api/requests', join)
    app.router.add_get('/api/requests', admin_requests)
    app.router.add_get('/api/requests/{request_id}', admin_request)
    app.router.add_patch('/api/requests/{request_id}', admin_request)
    app.router.add_get('/admin', admin_page)
    app.router.add_get('/api/admin/churches', admin_churches)
    app.router.add_post('/api/admin/churches', admin_churches)
    app.router.add_put('/api/admin/churches/{church_id}', edit_church)
