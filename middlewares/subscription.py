from typing import Callable, Dict, Any, Awaitable, Union
from aiogram import BaseMiddleware
from aiogram import Bot, types
from aiogram.types import Message, CallbackQuery
from config.config import CHANNEL_ID

async def is_user_subscribed(user_id: int, bot: Bot) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Ошибка проверки подписки для user_id {user_id}: {e}")
        # В случае ошибки (например, бот не в канале), считаем, что пользователь подписан,
        # чтобы не блокировать работу бота.
        return True

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        # Middleware теперь просто проверяет подписку и добавляет флаг в data.
        # Вся логика по отправке сообщений перенесена в хендлеры.
        user_id = event.from_user.id
        bot = data.get('bot')
        
        data['is_subscribed'] = await is_user_subscribed(user_id, bot)
        
        return await handler(event, data)
