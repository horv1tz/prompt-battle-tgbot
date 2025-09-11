# app.py

import asyncio
import logging
import signal
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeChat
from aiogram.fsm.storage.memory import MemoryStorage
from config.config import BOT_TOKEN, ADMIN_IDS
from handlers.admin.admin_handlers import admin_router
from handlers.users.user_handlers import user_router
from middlewares.subscription import SubscriptionMiddleware
from db.database import init_db

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

async def set_commands(bot: Bot):
    user_commands = [
        BotCommand(command="start", description="Начать"),
        BotCommand(command="help", description="Помощь")
    ]
    
    admin_commands = user_commands + [
        BotCommand(command="makegame", description="Создать игру"),
        BotCommand(command="startgame", description="Запустить первую игру"),
        BotCommand(command="continuegame", description="Запустить следующую игру"),
        BotCommand(command="stopgame", description="Остановить игру"),
        BotCommand(command="excel", description="Экспорт результатов"),
        BotCommand(command="senduser", description="Отправить сообщение пользователю")
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
    logger.info("Бот запущен")

async def on_shutdown(bot: Bot):
    logger.info("Бот останавливается")

async def main():
    # Объект бота
    bot = Bot(token=BOT_TOKEN)
    # Диспетчер
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Регистрируем роутеры
    # Мы больше не используем middleware на уровне роутера,
    # так как логика проверки подписки перенесена в хендлеры.
    dp.include_router(admin_router)
    dp.include_router(user_router)

    # Регистрируем функции startup и shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Добавляем обработчики сигналов для graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ('SIGINT', 'SIGTERM'):
        loop.add_signal_handler(
            getattr(signal, signame),
            lambda: asyncio.create_task(dp.stop_polling())
        )

    # Запускаем polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную")
