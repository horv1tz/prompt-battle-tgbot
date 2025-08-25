# handlers/admin/admin_handlers.py

from aiogram import types, Router
from config.config import ADMIN_IDS

admin_router = Router()

@admin_router.message(lambda message: message.from_user.id in ADMIN_IDS)
async def admin_message_handler(message: types.Message):
    """
    Этот обработчик будет ловить все сообщения от администраторов.
    """
    await message.answer("Привет, админ!")
