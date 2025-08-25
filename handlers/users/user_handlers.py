# handlers/users/user_handlers.py

from aiogram import types, Router
from aiogram.filters import CommandStart

user_router = Router()

@user_router.message(CommandStart())
async def start_handler(message: types.Message):
    """
    Этот обработчик будет отвечать на команду /start.
    """
    await message.answer(f"Привет, {message.from_user.full_name}!")

@user_router.message()
async def any_message_handler(message: types.Message):
    """
    Этот обработчик будет ловить все остальные сообщения.
    """
    await message.answer("Я получил твое сообщение!")
