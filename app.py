# app.py

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeChat
from config.config import BOT_TOKEN, ADMIN_IDS
from handlers.admin.admin_handlers import admin_router
from handlers.users.user_handlers import user_router
from db.database import init_db
from middlewares.subscription import SubscriptionMiddleware

# Включаем логирование, чтобы видеть сообщения в консоли
logging.basicConfig(level=logging.INFO)

# Объект бота
bot = Bot(token=BOT_TOKEN)
# Диспетчер
dp = Dispatcher()

async def set_commands(bot: Bot):
    user_commands = [
        BotCommand(command="start", description="Начать"),
        BotCommand(command="help", description="Помощь")
    ]
    
    admin_commands = user_commands + [
        BotCommand(command="makegame", description="Создать игру"),
        BotCommand(command="stopgame", description="Остановить игру"),
        BotCommand(command="excel", description="Экспорт результатов")
    ]

    # Установка команд для всех пользователей
    await bot.set_my_commands(user_commands)

    # Установка расширенных команд для админов
    for admin_id in ADMIN_IDS:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:
            logging.error(f"Could not set commands for admin {admin_id}: {e}")


async def on_startup(bot: Bot):
    await init_db()
    await set_commands(bot)

async def main():
    # Регистрируем роутеры
    dp.include_router(admin_router)
    dp.include_router(user_router)

    # Регистрируем middleware
    dp.message.middleware(SubscriptionMiddleware())

    # Запускаем polling
    dp.startup.register(on_startup)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
