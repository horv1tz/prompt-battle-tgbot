import random
import string
from aiogram import types, Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from openpyxl import Workbook
from config.config import ADMIN_IDS
from db.database import (add_game, stop_game, get_results, get_game, 
                         activate_game, get_game_status, get_participants)
from utils.image_generator import create_winners_image
import os

admin_router = Router()

class CreateGame(StatesGroup):
    waiting_for_photo = State()
    waiting_for_prompt = State()

def generate_game_id(length=5):
    letters = string.ascii_uppercase
    return ''.join(random.choice(letters) for _ in range(length))

@admin_router.message(Command("help"), F.from_user.id.in_(ADMIN_IDS))
async def admin_help_command(message: types.Message):
    await message.answer(
        "Команды администратора:\n"
        "/makegame - Создать новую игру\n"
        "/startgame [ID] - Запустить созданную игру\n"
        "/stopgame [ID] - Остановить активную игру\n"
        "/excel [ID] - Экспортировать результаты"
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
    game_id = generate_game_id()

    await add_game(game_id, prompt, photo_id)
    await state.clear()

    await message.answer(f"Игра успешно создана! ID игры: `{game_id}`.\n"
                         f"Используйте /startgame {game_id}, чтобы начать ее и разослать уведомления игрокам.")

@admin_router.message(Command("startgame"), F.from_user.id.in_(ADMIN_IDS))
async def start_game_command(message: types.Message, bot: Bot):
    try:
        game_id = message.text.split()[1].upper()
        status = await get_game_status(game_id)

        if status == 'pending':
            await activate_game(game_id)
            game_data = await get_game(game_id)
            if not game_data:
                await message.answer("Не удалось получить данные игры.")
                return
            
            _, photo_id = game_data
            participants = await get_participants(game_id)
            
            for user_id in participants:
                try:
                    await bot.send_photo(user_id, photo_id, caption=f"Игра {game_id} началась! Присылайте ваши варианты промптов.")
                except Exception as e:
                    print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            
            await message.answer(f"Игра {game_id} успешно запущена!")
        elif status == 'active':
            await message.answer("Эта игра уже запущена.")
        elif status == 'finished':
            await message.answer("Эта игра уже завершена.")
        else:
            await message.answer("Игра с таким ID не найдена.")
    except IndexError:
        await message.answer("Укажите ID игры: /startgame AAAAA")

@admin_router.message(Command("stopgame"), F.from_user.id.in_(ADMIN_IDS))
async def stop_game_command(message: types.Message, bot: Bot):
    try:
        game_id = message.text.split()[1].upper()
        await stop_game(game_id)
        
        participants = await get_participants(game_id)
        results = await get_results(game_id)
        game_data = await get_game(game_id)
        if not game_data:
            await message.answer("Не удалось получить данные игры.")
            return
        
        true_prompt, _ = game_data

        if results:
            winners_image_bytes = await create_winners_image(bot, results)
            if winners_image_bytes:
                winners_photo = types.BufferedInputFile(winners_image_bytes.getvalue(), filename="winners.png")
                
                for user_id in participants:
                    try:
                        await bot.send_photo(user_id, winners_photo, caption=f"Игра {game_id} завершена!")
                    except Exception as e:
                        print(f"Не удалось отправить фото победителей пользователю {user_id}: {e}")

        for user_id in participants:
            user_result = next((res for res in results if res[0] == user_id), None)
            score = user_result[3] if user_result else "нет данных"
            try:
                await bot.send_message(user_id, f"Ваш личный результат: {score} очков.\n"
                                                f"Истинный промпт был: '{true_prompt}'")
            except Exception as e:
                print(f"Не удалось отправить личный результат пользователю {user_id}: {e}")
        
        await message.answer(f"Игра {game_id} успешно остановлена.")
    except IndexError:
        await message.answer("Укажите ID игры: /stopgame AAAAA")

@admin_router.message(Command("excel"), F.from_user.id.in_(ADMIN_IDS))
async def excel_export_command(message: types.Message):
    try:
        game_id = message.text.split()[1].upper()
        results = await get_results(game_id)

        if not results:
            await message.answer("Нет данных для этой игры.")
            return

        wb = Workbook()
        ws = wb.active
        ws.title = f"Результаты {game_id}"
        ws.append(["user_id", "ник", "предложенный промпт", "очки"])

        for user_id, username, prompt, score in results:
            ws.append([user_id, username, prompt, score])

        file_path = f"results_{game_id}.xlsx"
        wb.save(file_path)

        await message.answer_document(types.FSInputFile(file_path))
        os.remove(file_path)
    except IndexError:
        await message.answer("Укажите ID игры: /excel AAAAA")
