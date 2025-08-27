from aiogram import types, Router
from aiogram.filters import Command, CommandStart
from db.database import (add_result, get_user_attempts, get_game_prompt, 
                         add_participant, get_user_active_game, get_current_active_game, get_game, has_user_won, get_game_status, add_or_update_user)
from utils.similarity import get_similarity_score

user_router = Router()

@user_router.message(CommandStart())
async def start_handler(message: types.Message):
    user = message.from_user
    await add_or_update_user(user.id, user.username, user.first_name, user.last_name)
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Начать игру", callback_data="start_game")]
    ])
    await message.answer(f"Привет, {message.from_user.full_name}!\n"
                         f"Я бот для игры 'Битва Промптов'.\n"
                         f"Нажми кнопку ниже, чтобы начать.", reply_markup=keyboard)

@user_router.message(Command("help"))
async def user_help_command(message: types.Message):
    await message.answer(
        "Команды пользователя:\n"
        "/start - Приветствие\n"
        "/help - Показать это сообщение"
    )

@user_router.callback_query(lambda c: c.data == 'start_game')
async def process_start_game_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    game_id = await get_current_active_game()

    if game_id:
        # Проверяем, не выиграл ли пользователь уже эту игру
        if await has_user_won(game_id, user_id):
            await callback_query.message.answer("Вы уже угадали промпт в текущей игре. Пожалуйста, дождитесь следующего раунда.")
            await callback_query.answer()
            return

        # Дополнительная проверка статуса на случай race condition
        status = await get_game_status(game_id)
        if status != 'active':
            await callback_query.message.answer("На данный момент нет активных игр. Попробуйте позже.")
            await callback_query.answer()
            return

        await add_participant(game_id, user_id)
        game_data = await get_game(game_id)
        if game_data:
            _, photo_id = game_data
            await callback_query.bot.send_photo(user_id, photo_id, caption="Вы присоединились к текущей игре! Присылайте ваши варианты промптов.")
        else:
            await callback_query.message.answer("Не удалось получить данные игры.")
    else:
        await callback_query.message.answer("На данный момент нет активных игр. Попробуйте позже.")
    
    await callback_query.answer()


@user_router.message()
async def handle_prompt_submission(message: types.Message):
    user_id = message.from_user.id
    game_id = await get_user_active_game(user_id)

    if not game_id:
        # Сообщение можно убрать, чтобы не спамить, если пользователь просто пишет в чат
        # await message.answer("Сейчас нет активных игр, в которых вы участвуете.")
        return

    prompt_text = await get_game_prompt(game_id)
    if not prompt_text:
        await message.answer("Эта игра уже завершена. Вы не можете отправлять промпты.")
        return

    if await has_user_won(game_id, user_id):
        await message.answer("Вы уже угадали промпт в этой игре. Дождитесь окончания раунда.")
        return

    attempts = await get_user_attempts(game_id, user_id)
    if attempts >= 3:
        await message.answer("Вы уже использовали все 3 попытки в этой игре.")
        return

    score = get_similarity_score(message.text, prompt_text)
    await add_result(game_id, user_id, message.from_user.username, message.text, score)

    if score == 100:
        await message.answer("Поздравляем! Вы угадали истинный промпт и набрали 100 очков! Ваше участие в этой игре завершено.")
        # Можно добавить логику для досрочного завершения участия, например, установив attempts = 3
    else:
        remaining_attempts = 2 - attempts
        await message.answer(f"Ваш промпт принят! Ваш результат: {score} очков.\n"
                             f"У вас осталось попыток: {remaining_attempts}.")
