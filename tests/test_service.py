import asyncio
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode
from unittest.mock import AsyncMock
import pytest
from aiohttp import BasicAuth
from bot.server import create_app
from bot.database import Database
from bot.main import church_text, church_keyboard

TOKEN = '123456789:' + 'a' * 35  # Synthetic token; never contacts Telegram.
ADMIN = BasicAuth('admin', 'local-test-password-123456').encode()
HEADERS = {'Authorization': ADMIN, 'X-Admin-Request': '1'}

def signed(user_id=123456, age=0):
    data = {'auth_date': str(int(time.time()) - age), 'user': json.dumps({
        'id': user_id, 'first_name': 'Тест', 'last_name': 'Заявки', 'username': 'test_user'})}
    secret=hmac.new(b'WebAppData', TOKEN.encode(), hashlib.sha256).digest()
    data['hash']=hmac.new(secret, '\n'.join(f'{k}={v}' for k,v in sorted(data.items())).encode(),hashlib.sha256).hexdigest()
    return urlencode(data)

@pytest.fixture
async def client(aiohttp_client,tmp_path):
    settings={'DATABASE_URL':f'sqlite+aiosqlite:///{tmp_path}/test.db','SEED_TEST_DATA':'true',
              'BOT_TOKEN':TOKEN,'ADMIN_PASSWORD':'local-test-password-123456'}
    return await aiohttp_client(create_app(settings))

async def test_health_catalog_details_filters(client):
    assert (await client.get('/health')).status==200
    rows=await (await client.get('/api/churches')).json()
    assert len(rows)==4 and all(c['is_test'] and c['leader_username'] is None for c in rows)
    r=await client.get('/api/churches',params={'district':rows[0]['district']})
    assert len(await r.json())==1
    assert (await client.get('/api/churches/1')).status==200
    assert (await client.get('/api/churches/no')).status==400
    assert (await client.get('/api/churches/999')).status==404
    assert 'Тестовая' in await (await client.get('/app')).text()

async def test_authentication_fail_closed(client):
    for route in ['/admin','/api/requests','/api/requests/1','/api/admin/churches']:
        assert (await client.get(route)).status==401
    assert (await client.get('/admin',headers=HEADERS)).status==200
    client.app['settings']['ADMIN_PASSWORD']=''
    assert (await client.get('/admin',headers=HEADERS)).status==503

async def test_signed_identity_and_persistence(client):
    body={'church_id':1,'init_data':signed()}
    r=await client.post('/api/requests',json=body)
    assert r.status==201
    saved=await r.json()
    duplicate=await client.post('/api/requests',json=body)
    assert duplicate.status==200 and (await duplicate.json())['id']==saved['id']
    rows=await (await client.get('/api/requests',headers=HEADERS)).json()
    assert len(rows)==1 and rows[0]['telegram_id']==123456 and rows[0]['source']=='mini_app'
    db=Database(client.app['settings']['DATABASE_URL'])
    await db.initialize(seed=True)
    assert len(await db.list_requests())==1
    assert len(await db.list_churches())==4
    await db.close()
    detail=await client.get('/api/requests/'+str(saved['id']),headers=HEADERS)
    assert (await detail.json())['name']=='Тест Заявки'

@pytest.mark.parametrize('init',[signed(age=7200),signed(age=-300),'invalid',''])
async def test_reject_invalid_telegram(client,init):
    assert (await client.post('/api/requests',json={'church_id':1,'init_data':init})).status in (400,401)
    assert await client.app['db'].list_requests()==[]

async def test_reject_spoofed_identity(client):
    r=await client.post('/api/requests',json={'church_id':1,'telegram_id':999,'name':'fake','init_data':signed()})
    assert r.status==400
    assert (await client.post('/api/requests',json={'church_id':999,'init_data':signed()})).status==404
    assert (await client.post('/api/requests',data='{',headers={'Content-Type':'application/json'})).status==400

async def test_church_management_csrf_and_preservation(client):
    c=await (await client.get('/api/churches/1')).json();c.pop('id')
    c['name']='<script>alert(1)</script>'
    no_csrf=await client.post('/api/admin/churches',headers={'Authorization':ADMIN},json=c)
    assert no_csrf.status==403
    cross=await client.post('/api/admin/churches',headers={**HEADERS,'Sec-Fetch-Site':'cross-site'},json=c)
    assert cross.status==403
    created=await client.post('/api/admin/churches',headers=HEADERS,json=c)
    assert created.status==201
    row=await created.json();cid=row['id']
    await client.post('/api/requests',json={'church_id':cid,'init_data':signed()})
    c['active']=False
    assert (await client.put(f'/api/admin/churches/{cid}',headers=HEADERS,json=c)).status==200
    assert (await client.get(f'/api/churches/{cid}')).status==404
    assert (await client.post('/api/requests',json={'church_id':cid,'init_data':signed(99)})).status==404
    assert len(await client.app['db'].list_requests())==1
    await client.app['db'].initialize(seed=True)
    assert (await client.app['db'].church(cid,True))['name']==c['name']
    assert '&lt;script&gt;' in church_text(row)
    assert all(not b.url or 't.me' not in b.url for row in church_keyboard(row).inline_keyboard for b in row)

async def test_validation_and_status(client):
    c=await (await client.get('/api/churches/1')).json();c.pop('id');c['lat']=91
    assert (await client.post('/api/admin/churches',headers=HEADERS,json=c)).status==400
    await client.post('/api/requests',json={'church_id':1,'init_data':signed()})
    assert (await client.patch('/api/requests/1',json={'status':'invalid'},headers=HEADERS)).status==400
    assert (await client.patch('/api/requests/1',json={'status':'contacted'},headers=HEADERS)).status==200
    assert await (await client.get('/api/requests?status=new',headers=HEADERS)).json()==[]
    assert (await client.get('/api/requests?limit=1000',headers=HEADERS)).status==400
    assert (await client.get('/api/requests/999',headers=HEADERS)).status==404

async def test_database_failure_never_acknowledged(client,monkeypatch):
    from sqlalchemy.exc import OperationalError
    monkeypatch.setattr(client.app['db'],'join',AsyncMock(side_effect=OperationalError('query',{},Exception())))
    assert (await client.post('/api/requests',json={'church_id':1,'init_data':signed()})).status==503
    monkeypatch.setattr(client.app['db'],'ping',AsyncMock(side_effect=OSError()))
    assert (await client.get('/health')).status==503

async def test_bot_and_mini_app_share_requests(client):
    db=client.app['db']
    item,new=await db.join(1,{'id':123456,'name':'Тест Заявки','username':'test_user'},'telegram')
    assert new
    r=await client.post('/api/requests',json={'church_id':1,'init_data':signed()})
    assert r.status==200 and (await r.json())['id']==item['id']
