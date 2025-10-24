import random
import string
from aiogram import types, Router, F, Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from openpyxl import Workbook
from config.config import ADMIN_IDS
from db.database import (add_game, stop_game, get_all_results, get_best_results, get_game,
                         get_game_status, get_participants, get_current_active_game, get_finished_games,
                         get_all_user_ids, get_user_result_for_game, start_next_game)
import io
from aiogram.types import BufferedInputFile

admin_router = Router()

class CreateGame(StatesGroup):
    waiting_for_photo = State()
    waiting_for_prompt = State()

class TestAnalyse(StatesGroup):
    waiting_for_text1 = State()
    waiting_for_text2 = State()

@admin_router.message(Command("help"), F.from_user.id.in_(ADMIN_IDS))
async def admin_help_command(message: types.Message):
    await message.answer(
        "Команды администратора:\n"
        "/makegame - Создать новую игру\n"
        "/startgame - Запустить первую игру из очереди\n"
        "/continuegame - Запустить следующую игру из очереди\n"
        "/stopgame - Остановить активную игру\n"
        "/excel - Экспортировать результаты\n"
        "/senduser <id> <message> - Отправить сообщение пользователю"
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
async def prompt_sent(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = data.get('photo_id')
    prompt = message.text
    
    game_id = await add_game(prompt, photo_id)
    await state.clear()

    await message.answer(f"Игра успешно добавлена в очередь. ID игры: `{game_id}`. Используйте /startgame, чтобы начать.")


async def start_game_logic(message: types.Message, bot: Bot):
    game_id = await start_next_game()
    if not game_id:
        await message.answer("Нет ожидающих игр для запуска.")
        return

    game_data = await get_game(game_id)
    if not game_data:
        await message.answer("Не удалось получить данные для запуска игры.")
        return
    
    _, photo_id = game_data
    
    all_user_ids = await get_all_user_ids()
    sent_count = 0
    for user_id in all_user_ids:
        try:
            # Убираем фото на старте раунда
            await bot.send_message(user_id, "Новый раунд начался! Нажмите /start, чтобы присоединиться")
            sent_count += 1
        except TelegramForbiddenError:
            print(f"Не удалось отправить сообщение пользователю {user_id}: бот заблокирован или это другой бот.")
        except Exception as e:
            print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

    await message.answer(f"Игра `{game_id}` успешно запущена. Уведомление разослано {sent_count} из {len(all_user_ids)} пользователей.")

@admin_router.message(Command("startgame"), F.from_user.id.in_(ADMIN_IDS))
async def start_game_command(message: types.Message, bot: Bot):
    await start_game_logic(message, bot)

async def stop_game_logic(message: types.Message, bot: Bot, is_continue: bool = False):
    game_id = await get_current_active_game()
    if not game_id:
        if not is_continue:
            await message.answer("Нет активных игр для остановки.")
        return

    await stop_game(game_id)
    
    participants = await get_participants(game_id)
    if not participants:
        if not is_continue:
            await message.answer(f"Игра {game_id} остановлена, но в ней не было участников.")
        return

    best_results = await get_best_results(game_id)
    game_data = await get_game(game_id)

    if not game_data:
        if not is_continue:
            await message.answer("Не удалось получить данные игры.")
        return
    
    true_prompt, _ = game_data
    
    winner_info_for_admin = "🏆 Победитель этого рауунда не определен."
    winner_score = 0
    winner_id = None
    if best_results:
        winner = best_results[0]
        winner_id = winner['user_id']
        winner_username = winner['username'] if winner['username'] else f"user_id: {winner['user_id']}"
        winner_score = winner['score']
        winner_prompt = winner['prompt_text']
        winner_phone = winner['phone_number'] if 'phone_number' in winner.keys() else 'Не указан'
        
        winner_info_for_admin = (
            f"🏆 Победитель: @{winner_username}\n"
            f"Процент: {winner_score}%\n"
            f"Промпт: «{winner_prompt}»\n"
            f"Телефон: {winner_phone}"
        )

    # Рассылка уведомлений о завершении игры участникам
    for user_id in participants:
        try:
            user_score = await get_user_result_for_game(game_id, user_id)
            
            message_text = (
                "Время подвести итоги! Раунд завершён!\n\n"
                f"Оригинальный промт был: «{true_prompt}»\n\n"
                f"🏆 В этом раунде победил игрок, набравший {winner_score}%.\n\n"
                f"Твой результат: {user_score}%\n\n"
                "Спасибо за участие! До следующей битвы! ✨"
            )

            await bot.send_message(user_id, message_text)
        except TelegramForbiddenError:
            print(f"Не удалось отправить итоги пользователю {user_id}: бот заблокирован.")
        except Exception as e:
            print(f"Не удалось отправить итоги пользователю {user_id}: {e}")

    # Отправка информации о победителе админам
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"<b>Информация для администратора:</b>\n\n"
                f"Игра <code>{game_id}</code> завершена.\n\n"
                f"{winner_info_for_admin}\n\n"
                f"Оригинальный промпт был: «{true_prompt}»",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Не удалось отправить итоги админу {admin_id}: {e}")

    if not is_continue:
        await message.answer(f"Игра {game_id} успешно остановлена. Результаты отправлены администраторам.")

@admin_router.message(Command("stopgame"), F.from_user.id.in_(ADMIN_IDS))
async def stop_game_command(message: types.Message, bot: Bot):
    await stop_game_logic(message, bot)

@admin_router.message(Command("continuegame"), F.from_user.id.in_(ADMIN_IDS))
async def continue_game_command(message: types.Message, bot: Bot):
    await message.answer("Завершаю текущую игру...")
    await stop_game_logic(message, bot, is_continue=True)
    await message.answer("Начинаю следующую игру...")
    await start_game_logic(message, bot)

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
    ws.append(["user_id", "ник", "номер телефона", "предложенный промпт", "очки", "время ответа"])

    for row in results:
        ws.append([row['user_id'], row['username'], row['phone_number'], row['prompt_text'], row['score'], row['timestamp']])

    # Сохраняем файл в байтовый поток в памяти
    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0) # Перемещаем курсор в начало файла

    file_name = f"results_{game_id}_{file_suffix}.xlsx"
    await callback_query.message.answer_document(
        BufferedInputFile(file_stream.read(), filename=file_name)
    )
    await callback_query.answer()

from utils.similarity import get_similarity_score

@admin_router.message(Command("senduser"), F.from_user.id.in_(ADMIN_IDS))
async def send_user_command(message: types.Message, bot: Bot):
    try:
        parts = message.text.split(maxsplit=2)
        user_id = int(parts[1])
        text_to_send = parts[2]
        
        await bot.send_message(user_id, text_to_send)
        await message.answer(f"Сообщение успешно отправлено пользователю {user_id}.")
    except (IndexError, ValueError):
        await message.answer("Неверный формат. Используйте: /senduser <id> <message>")
    except TelegramForbiddenError:
        await message.answer(f"Не удалось отправить сообщение пользователю {user_id}: бот заблокирован или это другой бот.")
    except Exception as e:
        await message.answer(f"Не удалось отправить сообщение: {e}")

@admin_router.message(Command("testanalyse"), F.from_user.id.in_(ADMIN_IDS))
async def test_analyse_start(message: types.Message, state: FSMContext):
    await state.set_state(TestAnalyse.waiting_for_text1)
    await message.answer("Введите первый текст для сравнения.")

@admin_router.message(TestAnalyse.waiting_for_text1, F.from_user.id.in_(ADMIN_IDS))
async def test_analyse_text1_received(message: types.Message, state: FSMContext):
    await state.update_data(text1=message.text)
    await state.set_state(TestAnalyse.waiting_for_text2)
    await message.answer("Отлично. Теперь введите второй текст.")

@admin_router.message(TestAnalyse.waiting_for_text2, F.from_user.id.in_(ADMIN_IDS))
async def test_analyse_text2_received(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text1 = data.get('text1')
    text2 = message.text

    score = await get_similarity_score(text1, text2)
    await message.answer(f"Сходство между текстами: {score}%")
    
    await state.clear()
