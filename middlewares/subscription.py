from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram import types
from aiogram.types import Message, CallbackQuery
from config.config import CHANNEL_ID

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        bot = data.get('bot')

        try:
            member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
            if member.status in ['member', 'administrator', 'creator']:
                return await handler(event, data)
        except Exception as e:
            # Если произошла ошибка (например, бот не админ в канале), пропускаем проверку
            print(f"Ошибка проверки подписки: {e}")
            return await handler(event, data)

        # Если пользователь не подписан
        channel_link = "https://t.me/ci_jobs"
        keyboard = [
            [types.InlineKeyboardButton(text="↗️ Перейти в канал", url=channel_link)],
            [types.InlineKeyboardButton(text="✅ Я подписался(ась)", callback_data="subscription_confirmed")]
        ]
        markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

        text = (
            "Приветствую в «Битве Промптов»✨\n\n"
            "Чтобы присоединиться к соревнованию, тебе необходимо быть подписчиком нашего канала. "
            "Подпишись и нажми кнопку «✅ Я подписался(ась)», чтобы продолжить."
        )

        if isinstance(event, Message):
            await event.answer(text, reply_markup=markup, disable_web_page_preview=True)
        elif isinstance(event, CallbackQuery):
            await event.message.answer(text, reply_markup=markup, disable_web_page_preview=True)
            await event.answer()
