from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest
import logging
from config.config import CHANNEL_ID

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        if CHANNEL_ID:
            try:
                user_channel_status = await event.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=event.from_user.id)
                if user_channel_status.status == 'left':
                    await event.answer(f"Для использования бота, пожалуйста, подпишитесь на наш канал.")
                    return
            except TelegramBadRequest as e:
                if "chat not found" in e.message:
                    logging.error(f"Error checking subscription: Chat with ID {CHANNEL_ID} not found. Bot is likely not a member or ID is incorrect.")
                else:
                    logging.error(f"Error checking subscription: {e}")
        return await handler(event, data)
