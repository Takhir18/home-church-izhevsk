"""One process: HTTP server and a single PostgreSQL-coordinated Telegram poller."""
import sys
from pathlib import Path
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import contextlib
import hashlib
import logging
import os
from html import escape
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton as Button, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy import text
from bot.server import create_app
from bot.notifications import notify

log = logging.getLogger(__name__)

def keyboard(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)

def menu(public_url):
    rows = []
    if public_url:
        rows.append([Button(text='🗺 Открыть карту и каталог', web_app=WebAppInfo(url=public_url+'/app'))])
    rows += [[Button(text='🏠 Найти домашнюю церковь', callback_data='churches')],
             [Button(text='📍 По району', callback_data='districts')],
             [Button(text='ℹ️ Что такое домашняя церковь', callback_data='about')]]
    return keyboard(rows)

def church_keyboard(c):
    rows = [[Button(text='🙋 Хочу присоединиться', callback_data=f"join:{c['id']}")]]
    if not c['is_test'] and c['leader_username']:
        rows.append([Button(text='💬 Связаться с лидером', url='https://t.me/'+c['leader_username'])])
    rows.append([Button(text='🗺 Построить маршрут', url=f"https://yandex.ru/maps/?rtext=~{c['lat']},{c['lon']}&rtt=auto")])
    rows.append([Button(text='⬅️ К списку', callback_data='churches')])
    return keyboard(rows)

def church_text(c):
    e=lambda k: escape(str(c[k]))
    return (('🧪 <b>Тестовая группа: адрес и лидер — примеры.</b>\n\n' if c['is_test'] else '')+
        f"🏠 <b>{e('name')}</b>\n\n📍 {e('district')}\n🏡 {e('address')}\n🕒 {e('meeting')}\n"
        f"👤 {e('leader')}\n👥 {e('participants')} участников · {e('age')}\n\n{e('description')}\n\n"
        + ' · '.join(escape(i) for i in c['interests']))

def dispatcher(db, public_url, settings=None):
    dp = Dispatcher()

    @dp.message(Command('start'))
    async def start(message: types.Message):
        await message.answer('🏠 Домашние церкви Ижевска\n\nНайдите группу для общения, молитвы и изучения Библии.', reply_markup=menu(public_url))

    @dp.callback_query()
    async def callback(q: types.CallbackQuery):
        data=q.data or ''
        if data == 'home':
            await q.message.answer('Выберите действие:', reply_markup=menu(public_url))
        elif data == 'about':
            await q.message.answer('Домашняя церковь — небольшая группа для общения, молитвы, изучения Библии и поддержки друг друга.', reply_markup=menu(public_url))
        elif data == 'districts':
            catalog=await db.list_churches()
            # Numeric IDs avoid Telegram's 64-byte callback_data limit for Cyrillic districts.
            districts={}
            for c in catalog:
                districts.setdefault(c['district'], c['id'])
            rows=[[Button(text=d,callback_data=f'district:{i}')] for d,i in districts.items()]
            rows.append([Button(text='Все районы',callback_data='churches')])
            await q.message.answer('📍 Выберите район:',reply_markup=keyboard(rows))
        elif data == 'churches' or data.startswith('district:'):
            district=None
            if data.startswith('district:'):
                try:
                    c=await db.church(int(data.split(':')[1]))
                except ValueError:
                    c=None
                if not c:
                    await q.answer('Обновите список районов.',show_alert=True);return
                district=c['district']
            catalog=await db.list_churches(district)
            # Telegram permits at most 100 buttons per message.
            for start in range(0, max(1,len(catalog)), 90):
                rows=[[Button(text=('🧪 ' if c['is_test'] else '🏠 ')+c['name'],callback_data=f"church:{c['id']}")] for c in catalog[start:start+90]]
                rows += [[Button(text='📍 По району',callback_data='districts')],[Button(text='⬅️ На главную',callback_data='home')]]
                await q.message.answer('Выберите группу:' if catalog else 'В этом районе пока нет групп.',reply_markup=keyboard(rows))
        elif data.startswith(('church:', 'join:')):
            try:
                c=await db.church(int(data.split(':')[1]))
            except ValueError:
                c=None
            if not c:
                await q.answer('Группа больше не доступна. Откройте каталог.',show_alert=True);return
            if data.startswith('church:'):
                await q.message.answer(church_text(c),parse_mode='HTML',reply_markup=church_keyboard(c))
            else:
                u=q.from_user
                try:
                    item,created=await db.join(c['id'],dict(id=u.id,name=u.full_name[:200],username=u.username),'telegram')
                except LookupError:
                    await q.answer('Группа больше не доступна.',show_alert=True);return
                if created:
                    await notify(settings or {}, item)
                note='🧪 Это тестовая группа; реальный лидер пока не назначен.' if c['is_test'] else 'Администратор увидит вашу заявку и сможет связаться с вами.'
                await q.message.answer(('Заявка сохранена.' if created else 'Ваша заявка уже сохранена.')+f" Номер: {item['id']}.\n\n"+note,reply_markup=menu(public_url))
        await q.answer()

    @dp.errors()
    async def on_error(event):
        log.error('Telegram handler failed: %s',type(event.exception).__name__)
        q=event.update.callback_query
        if q:
            with contextlib.suppress(Exception):
                await q.answer('Не удалось выполнить действие. Попробуйте позже.',show_alert=True)
        return True
    return dp

async def polling(app):
    token=app['settings']['BOT_TOKEN']
    bot=Bot(token)
    public=(app['settings'].get('WEB_APP_URL') or app['settings'].get('RENDER_EXTERNAL_URL') or '').rstrip('/')
    dp=dispatcher(app['db'], public, app['settings'])
    # Each token has a distinct lock. Old/new Render processes cannot poll together.
    key=int.from_bytes(hashlib.sha256(token.encode()).digest()[:8], 'big', signed=True)
    try:
        async with app['db'].engine.connect() as conn:
            if app['db'].engine.dialect.name == 'postgresql':
                while not await conn.scalar(text('SELECT pg_try_advisory_lock(:key)'), {'key': key}):
                    await conn.rollback()
                    await asyncio.sleep(2)
                await conn.commit()
            app['polling_state']='running'
            await bot.delete_webhook(drop_pending_updates=False)
            poll=asyncio.create_task(dp.start_polling(bot,handle_signals=False,close_bot_session=False))
            try:
                while not poll.done():
                    done,_=await asyncio.wait({poll},timeout=5)
                    if not done:
                        # Losing the lock connection must stop polling immediately.
                        await conn.execute(text('SELECT 1'))
                await poll
            finally:
                poll.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await poll
                if app['db'].engine.dialect.name == 'postgresql':
                    with contextlib.suppress(Exception):
                        await conn.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': key})
    finally:
        app['polling_state']='stopped'
        await bot.session.close()

async def polling_context(app):
    app['polling_state']='standby'
    app['polling_task']=asyncio.create_task(polling(app))
    yield
    app['polling_task'].cancel()
    with contextlib.suppress(asyncio.CancelledError,Exception):
        await app['polling_task']


def main():
    logging.basicConfig(level=logging.INFO)
    app=create_app()
    if os.getenv('BOT_ENABLED','true').lower() == 'true':
        if not os.getenv('BOT_TOKEN'):
            raise RuntimeError('BOT_TOKEN must be set, or BOT_ENABLED=false for local HTTP testing')
        app.cleanup_ctx.append(polling_context)
    web.run_app(app, host='0.0.0.0',port=int(os.getenv('PORT','10000')),access_log=None)

if __name__ == '__main__':
    main()
