import random
from aiogram import types, Router
from aiogram.filters import Command, CommandStart
from db.database import (add_result, get_user_attempts, get_game_prompt, 
                         get_game_status, add_participant, get_user_active_game)

user_router = Router()

@user_router.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(f"Привет, {message.from_user.full_name}!\n"
                         f"Я бот для игры 'Битва Промптов'.\n"
                         f"Чтобы присоединиться к игре, используй команду /join ИГРОВОЙ_ID")

@user_router.message(Command("help"))
async def user_help_command(message: types.Message):
    await message.answer(
        "Команды пользователя:\n"
        "/start - Приветствие\n"
        "/join [ID] - Присоединиться к игре\n"
        "/help - Показать это сообщение"
    )

@user_router.message(Command("join"))
async def join_game_command(message: types.Message):
    try:
        game_id = message.text.split()[1].upper()
        status = await get_game_status(game_id)

        if status == 'pending':
            user_id = message.from_user.id
            await add_participant(game_id, user_id)
            await message.answer(f"Вы присоединились к игре {game_id} и добавлены в список ожидания.\n"
                                 "Когда админ начнет игру, вы получите уведомление.")
        elif status in ['active', 'finished']:
            await message.answer("Нельзя присоединиться к игре, которая уже началась или завершена.")
        else:
            await message.answer("Игра с таким ID не найдена.")
    except IndexError:
        await message.answer("Пожалуйста, укажите ID игры. Пример: /join AAAAA")

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

    attempts = await get_user_attempts(game_id, user_id)
    if attempts >= 3:
        await message.answer("Вы уже использовали все 3 попытки в этой игре.")
        return

    score = random.randint(0, 100)
    await add_result(game_id, user_id, message.from_user.username, message.text, score)

    remaining_attempts = 2 - attempts
    await message.answer(f"Ваш промпт принят! Ваш результат: {score} очков.\n"
                         f"У вас осталось попыток: {remaining_attempts}.")
