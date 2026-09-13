
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import asyncio

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🏠 Домашние церкви Ижевска\n\n"
        "Настоящая церковь начинается не в здании, а в людях.\n\n"
        "Найди свою домашнюю церковь."
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
