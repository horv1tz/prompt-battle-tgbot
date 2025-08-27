import random
import string
from aiogram import types, Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from openpyxl import Workbook
from config.config import ADMIN_IDS
from db.database import (add_game, stop_game, get_all_results, get_best_results, get_game, 
                         get_game_status, get_participants, get_current_active_game, get_finished_games)
import os

admin_router = Router()

class CreateGame(StatesGroup):
    waiting_for_photo = State()
    waiting_for_prompt = State()

@admin_router.message(Command("help"), F.from_user.id.in_(ADMIN_IDS))
async def admin_help_command(message: types.Message):
    await message.answer(
        "Команды администратора:\n"
        "/makegame - Создать новую игру\n"
        "/stopgame - Остановить активную игру\n"
        "/excel - Экспортировать результаты"
    )

@admin_router.message(Command("makegame"), F.from_user.id.in_(ADMIN_IDS))
async def make_game_command(message: types.Message, state: FSMContext):
    await message.answer("Загрузите фото для новой игры.")
    await state.set_state(CreateGame.waiting_for_photo)

@admin_router.message(CreateGame.waiting_for_photo, F.photo, F.from_user.id.in_(ADMIN_IDS))
async def photo_sent(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await message.answer("Отлично! Теперь введите истинный промпт.")
    await state.set_state(CreateGame.waiting_for_prompt)

@admin_router.message(CreateGame.waiting_for_prompt, F.from_user.id.in_(ADMIN_IDS))
async def prompt_sent(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    photo_id = data.get('photo_id')
    prompt = message.text
    
    game_id = await add_game(prompt, photo_id)
    await state.clear()

    # Рассылка всем пользователям, которые есть в базе
    # Это упрощение, в идеале нужна таблица users
    all_users = [] # Тут должен быть код для получения всех юзеров
    # for user_id in all_users:
    #     try:
    #         await bot.send_photo(user_id, photo_id, caption="Новая игра началась! Присоединяйтесь и присылайте свои варианты промптов.")
    #     except Exception as e:
    #         print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

    await message.answer(f"Игра успешно создана и запущена! ID игры: `{game_id}`.")


@admin_router.message(Command("stopgame"), F.from_user.id.in_(ADMIN_IDS))
async def stop_game_command(message: types.Message, bot: Bot):
    game_id = await get_current_active_game()
    if not game_id:
        await message.answer("Нет активных игр для остановки.")
        return

    await stop_game(game_id)
    
    participants = await get_participants(game_id)
    results = await get_all_results(game_id)
    game_data = await get_game(game_id)
    if not game_data:
        await message.answer("Не удалось получить данные игры.")
        return
    
    true_prompt, _ = game_data

    # Отправка сообщения о начале следующей игры
    for user_id in participants:
        user_result = next((res for res in results if res[0] == user_id), None)
        score = user_result[3] if user_result else "нет данных"
        try:
            await bot.send_message(user_id, f"Ваш личный результат: {score} очков.\n"
                                                f"Истинный промпт был: '{true_prompt}'\n"
                                                "Скоро начнется следующая игра.")
        except Exception as e:
            print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

    await message.answer(f"Игра {game_id} успешно остановлена.")

@admin_router.message(Command("excel"), F.from_user.id.in_(ADMIN_IDS))
async def excel_export_command(message: types.Message):
    finished_games = await get_finished_games()
    if not finished_games:
        await message.answer("Нет завершенных игр для экспорта.")
        return

    buttons = []
    for game_id, prompt in finished_games:
        # Обрезаем промпт для отображения на кнопке
        short_prompt = (prompt[:20] + '...') if len(prompt) > 20 else prompt
        buttons.append([types.InlineKeyboardButton(text=f"Игра: {short_prompt}", callback_data=f"select_game:{game_id}")])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите игру для экспорта:", reply_markup=keyboard)

@admin_router.callback_query(F.data.startswith("select_game:"))
async def select_game_for_export(callback_query: types.CallbackQuery):
    game_id = callback_query.data.split(":")[1]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Выгрузить лучший результат", callback_data=f"excel_best:{game_id}")],
        [types.InlineKeyboardButton(text="Выгрузить все результаты", callback_data=f"excel_all:{game_id}")]
    ])
    await callback_query.message.edit_text("Выберите тип выгрузки:", reply_markup=keyboard)
    await callback_query.answer()

@admin_router.callback_query(F.data.startswith("excel_"))
async def excel_export_callback(callback_query: types.CallbackQuery):
    action, game_id = callback_query.data.split(":")
    
    if action == "excel_best":
        results = await get_best_results(game_id)
        file_suffix = "best"
    else:
        results = await get_all_results(game_id)
        file_suffix = "all"

    if not results:
        await callback_query.message.answer("Нет данных для этой игры.")
        await callback_query.answer()
        return

    wb = Workbook()
    ws = wb.active
    ws.title = f"Результаты {game_id}"
    ws.append(["user_id", "ник", "предложенный промпт", "очки"])

    for user_id, username, prompt, score in results:
        ws.append([user_id, username, prompt, score])

    file_path = f"results_{game_id}_{file_suffix}.xlsx"
    wb.save(file_path)

    await callback_query.message.answer_document(types.FSInputFile(file_path))
    os.remove(file_path)
    await callback_query.answer()
