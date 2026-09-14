"""Optional best-effort notification; the committed database row is authoritative."""
import asyncio
import logging
from aiogram import Bot

async def notify(settings, item):
    if not settings.get('ADMIN_CHAT_ID') or not settings.get('BOT_TOKEN'):
        return
    try:
        async with asyncio.timeout(5):
            async with Bot(settings['BOT_TOKEN']).context() as bot:
                await bot.send_message(int(settings['ADMIN_CHAT_ID']),
                    f"Новая заявка №{item['id']}\nЦерковь №{item['church_id']}\n"
                    f"Имя: {item['name']}\nTelegram ID: {item['telegram_id']}\n"
                    'Подробности доступны в защищённой админке.')
    except Exception as exc:
        logging.getLogger(__name__).warning('Notification failed: %s; request remains saved',type(exc).__name__)
