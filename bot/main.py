import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

CHURCHES = [
    {
        "id": 1,
        "name": "Источник",
        "leader": "Алексей Смирнов",
        "leader_username": "alex_source_test",
        "district": "Устиновский район",
        "address": "ул. Молодёжная, 45",
        "meeting": "Воскресенье, 18:00",
        "age": "25–35 лет",
        "participants": 14,
        "interests": "Общение · Семьи · Изучение Библии",
        "description": "Тёплая открытая группа для общения, молитвы, изучения Библии и поддержки друг друга.",
        "lat": 56.8468,
        "lon": 53.2812,
    },
    {
        "id": 2,
        "name": "Надежда",
        "leader": "Иван Петров",
        "leader_username": "ivan_nadezhda_test",
        "district": "Октябрьский район",
        "address": "ул. Пушкинская, 210",
        "meeting": "Суббота, 17:00",
        "age": "35–45 лет",
        "participants": 10,
        "interests": "Семьи · Общение · Поддержка",
        "description": "Спокойная семейная группа, где люди знакомятся, молятся вместе и поддерживают друг друга.",
        "lat": 56.8654,
        "lon": 53.2055,
    },
    {
        "id": 3,
        "name": "Живое сердце",
        "leader": "Мария Волкова",
        "leader_username": "maria_heart_test",
        "district": "Первомайский район",
        "address": "ул. Ленина, 98",
        "meeting": "Воскресенье, 16:00",
        "age": "18–30 лет",
        "participants": 18,
        "interests": "Молодёжь · Творчество · Поездки",
        "description": "Активная группа для молодых людей, которые хотят дружить, расти духовно и служить вместе.",
        "lat": 56.8421,
        "lon": 53.2309,
    },
    {
        "id": 4,
        "name": "Свет",
        "leader": "Дмитрий Орлов",
        "leader_username": "dmitry_svet_test",
        "district": "Индустриальный район",
        "address": "Воткинское шоссе, 34",
        "meeting": "Среда, 19:00",
        "age": "40+",
        "participants": 8,
        "interests": "Общение · Библия · Помощь людям",
        "description": "Небольшая группа для близкого общения, молитвы и совместного изучения Библии.",
        "lat": 56.8840,
        "lon": 53.2440,
    },
]

DISTRICTS = [
    "Все районы",
    "Устиновский район",
    "Октябрьский район",
    "Первомайский район",
    "Индустриальный район",
    "Ленинский район",
]


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Найти домашнюю церковь", callback_data="churches")],
        [InlineKeyboardButton(text="📍 По району", callback_data="districts")],
        [InlineKeyboardButton(text="ℹ️ Что такое домашняя церковь", callback_data="about")],
    ])


def churches_keyboard(churches):
    rows = [[InlineKeyboardButton(text=f"🏠 {c['name']} · {c['district'].replace(' район','')}", callback_data=f"church:{c['id']}")] for c in churches]
    rows.append([InlineKeyboardButton(text="🔎 Фильтр по району", callback_data="districts")])
    rows.append([InlineKeyboardButton(text="⬅️ На главную", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def district_keyboard():
    rows = [[InlineKeyboardButton(text=d, callback_data=f"district:{d}")] for d in DISTRICTS]
    rows.append([InlineKeyboardButton(text="⬅️ На главную", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def church_keyboard(church):
    route = f"https://yandex.ru/maps/?rtext=~{church['lat']},{church['lon']}&rtt=auto"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🙋 Хочу присоединиться", callback_data=f"join:{church['id']}")],
        [InlineKeyboardButton(text="💬 Связаться с лидером", url=f"https://t.me/{church['leader_username']}")],
        [InlineKeyboardButton(text="🗺 Построить маршрут", url=route)],
        [InlineKeyboardButton(text="⬅️ К списку", callback_data="churches")],
    ])


def church_text(church):
    return (
        f"🏠 <b>Домашняя церковь «{church['name']}»</b>\n\n"
        f"📍 <b>Район:</b> {church['district']}\n"
        f"🏡 <b>Адрес:</b> {church['address']}\n"
        f"🕒 <b>Встречи:</b> {church['meeting']}\n"
        f"👤 <b>Лидер:</b> {church['leader']}\n"
        f"👥 <b>Участников:</b> {church['participants']}\n"
        f"🎂 <b>Средний возраст:</b> {church['age']}\n\n"
        f"<b>О группе</b>\n{church['description']}\n\n"
        f"❤️ <b>Интересы:</b> {church['interests']}"
    )


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🏠 <b>Домашние церкви Ижевска</b>\n\n"
        "Домашняя церковь — это место, где люди собираются для общения, молитвы, изучения Библии и поддержки друг друга.\n\n"
        "Найдите группу рядом и познакомьтесь с её лидером.",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "home")
async def home(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🏠 <b>Домашние церкви Ижевска</b>\n\n"
        "Настоящая церковь начинается не в здании, а в людях.\n\n"
        "Выберите действие:",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data == "about")
async def about(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "<b>Что такое домашняя церковь?</b>\n\n"
        "Это небольшая духовная семья, где люди встречаются, общаются, молятся, изучают Библию, поддерживают друг друга и учатся служить.\n\n"
        "Наша цель — помочь человеку найти близкое окружение и стать частью живого сообщества.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Найти церковь", callback_data="churches")],[InlineKeyboardButton(text="⬅️ На главную", callback_data="home")]]),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data == "churches")
async def show_churches(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🏠 <b>Домашние церкви</b>\n\nВыберите группу:",
        reply_markup=churches_keyboard(CHURCHES),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data == "districts")
async def show_districts(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📍 <b>Выберите район</b>",
        reply_markup=district_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("district:"))
async def district_filter(callback: types.CallbackQuery):
    district = callback.data.split(":", 1)[1]
    selected = CHURCHES if district == "Все районы" else [c for c in CHURCHES if c["district"] == district]
    if selected:
        text = f"📍 <b>{district}</b>\n\nНайдено групп: {len(selected)}"
        keyboard = churches_keyboard(selected)
    else:
        text = f"📍 <b>{district}</b>\n\nПока здесь нет домашних церквей в тестовой базе."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Выбрать другой район", callback_data="districts")],[InlineKeyboardButton(text="⬅️ На главную", callback_data="home")]])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("church:"))
async def church_detail(callback: types.CallbackQuery):
    church_id = int(callback.data.split(":", 1)[1])
    church = next(c for c in CHURCHES if c["id"] == church_id)
    await callback.message.edit_text(church_text(church), reply_markup=church_keyboard(church), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("join:"))
async def join_church(callback: types.CallbackQuery):
    church_id = int(callback.data.split(":", 1)[1])
    church = next(c for c in CHURCHES if c["id"] == church_id)
    user = callback.from_user
    username = f"@{user.username}" if user.username else "username не указан"

    if ADMIN_CHAT_ID:
        await bot.send_message(
            int(ADMIN_CHAT_ID),
            "🆕 <b>Новая заявка</b>\n\n"
            f"Домашняя церковь: <b>{church['name']}</b>\n"
            f"Имя: {user.full_name}\n"
            f"Telegram: {username}\n"
            f"ID: <code>{user.id}</code>",
            parse_mode="HTML",
        )

    await callback.message.answer(
        f"🙌 Заявка на домашнюю церковь «{church['name']}» принята.\n\n"
        "Лидер сможет связаться с вами в Telegram. Пока вы также можете написать ему напрямую кнопкой ниже.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💬 Написать {church['leader']}", url=f"https://t.me/{church['leader_username']}")],
            [InlineKeyboardButton(text="🏠 К списку церквей", callback_data="churches")],
        ]),
    )
    await callback.answer("Заявка отправлена")


async def health(_request):
    return web.json_response({"status": "ok", "service": "home-church-bot"})


async def run_health_server():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    while True:
        await asyncio.sleep(3600)


async def run_bot():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


async def main():
    await asyncio.gather(run_health_server(), run_bot())


if __name__ == "__main__":
    asyncio.run(main())
