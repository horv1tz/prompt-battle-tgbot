# app.py

import asyncio
import logging
from aiogram import Bot, Dispatcher
from config.config import BOT_TOKEN
from handlers.admin.admin_handlers import admin_router
from handlers.users.user_handlers import user_router

# Включаем логирование, чтобы видеть сообщения в консоли
logging.basicConfig(level=logging.INFO)

# Объект бота
bot = Bot(token=BOT_TOKEN)
# Диспетчер
dp = Dispatcher()

async def main():
    # Регистрируем роутеры
    dp.include_router(admin_router)
    dp.include_router(user_router)

    # Запускаем polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
