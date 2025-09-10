from aiogram import types, Router, F
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from db.database import (add_result, get_user_attempts, get_game_prompt, 
                         add_participant, get_user_active_game, get_current_active_game, 
                         get_game, has_user_won, get_game_status, add_or_update_user, 
                         set_user_attempts_to_max, get_user_by_id, update_user_state, update_user_phone)
from utils.similarity import get_similarity_score
from config.config import CHANNEL_ID
import re

user_router = Router()

MAX_ATTEMPTS = 1

class UserState(StatesGroup):
    awaiting_subscription_check = State()
    awaiting_phone_number = State()
    awaiting_readiness_to_play = State()
    in_game = State()

# =================================================================================================
# HELPERS
# =================================================================================================

async def send_game_image(message: types.Message, state: FSMContext):
    user_id = message.chat.id
    game_id = await get_current_active_game()
    if not game_id:
        await message.answer("К сожалению, сейчас нет активных игр. Попробуйте позже.")
        return

    # Проверяем, участвовал ли пользователь уже (по наличию результата)
    attempts = await get_user_attempts(game_id, user_id)
    if attempts > 0:
        await message.answer("Вы уже приняли участие в этом раунде. Ждите результатов!")
        return

    game_data = await get_game(game_id)
    if game_data:
        _, photo_id = game_data
        await add_participant(game_id, user_id)
        try:
            await message.bot.send_photo(user_id, photo_id)
            await state.set_state(UserState.in_game)
        except TelegramForbiddenError:
            print(f"Не удалось отправить фото пользователю {user_id}: бот заблокирован или это другой бот.")
        except Exception as e:
            print(f"Ошибка при отправке фото пользователю {user_id}: {e}")
    else:
        await message.answer("Не удалось получить данные игры. Попробуйте позже.")

# =================================================================================================
# START AND REGISTRATION FLOW
# =================================================================================================

@user_router.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    db_user = await get_user_by_id(user.id)

    if not db_user:
        await add_or_update_user(user.id, user.username, user.first_name, user.last_name)
        db_user = await get_user_by_id(user.id)

    if db_user and db_user['phone_number']:
        await update_user_state(user.id, 'registered')
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🎯 Да, начинаем!", callback_data="play_now")],
            [types.InlineKeyboardButton(text="⏰ Не сейчас", callback_data="play_later")]
        ])
        await message.answer(
            "С возвращением! Готов(а) сыграть прямо сейчас?",
            reply_markup=keyboard,
        )
        await state.set_state(UserState.awaiting_readiness_to_play)
    else:
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="📞 Отправить мой номер", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(
            "Здорово! Ты с нами 🚀\n\n"
            "Для связи в случае победы нам нужен твой номер телефона. "
            "Поделись им, нажав кнопку ниже 👇\n\n"
            "Или просто напиши его в формате: +7 XXX XXX XX XX",
            reply_markup=keyboard
        )
        await state.set_state(UserState.awaiting_phone_number)

@user_router.callback_query(F.data == 'subscription_confirmed')
async def subscription_confirmed_handler(callback_query: types.CallbackQuery, state: FSMContext):
    # Этот обработчик теперь может быть пустым или использоваться для дополнительной логики,
    # так как основная проверка происходит в middleware.
    # Для чистоты, можно просто перенаправить на /start.
    await start_handler(callback_query.message, state)
    await callback_query.answer()

@user_router.message(UserState.awaiting_phone_number, F.contact)
async def phone_number_handler_contact(message: types.Message, state: FSMContext):
    phone_number = message.contact.phone_number
    await update_user_phone(message.from_user.id, phone_number)
    await update_user_state(message.from_user.id, 'registered')
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🎯 Да, начинаем!", callback_data="play_now")],
        [types.InlineKeyboardButton(text="⏰ Не сейчас", callback_data="play_later")]
    ])
    await message.answer(
        "Отлично, всё готово для старта! Ты готов(а) сыграть прямо сейчас?",
        reply_markup=keyboard,
    )
    await state.set_state(UserState.awaiting_readiness_to_play)

@user_router.message(UserState.awaiting_phone_number, F.text)
async def phone_number_handler_text(message: types.Message, state: FSMContext):
    phone_pattern = re.compile(r'^\+7\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{2}$')
    if phone_pattern.match(message.text):
        await update_user_phone(message.from_user.id, message.text)
        await update_user_state(message.from_user.id, 'registered')
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🎯 Да, начинаем!", callback_data="play_now")],
            [types.InlineKeyboardButton(text="⏰ Не сейчас", callback_data="play_later")]
        ])
        await message.answer(
            "Отлично, всё готово для старта! Ты готов(а) сыграть прямо сейчас?",
            reply_markup=keyboard,
        )
        await state.set_state(UserState.awaiting_readiness_to_play)
    else:
        await message.answer("Неверный формат номера. Пожалуйста, отправьте номер в формате: +7 XXX XXX XX XX или через кнопку.")

# =================================================================================================
# GAME READINESS AND START
# =================================================================================================

@user_router.callback_query(F.data == 'play_now', UserState.awaiting_readiness_to_play)
async def play_now_handler(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("Супер! Вот правила:\n\n"
                                         "1. Я отправлю тебе уникальное изображение, сгенерированное нейросетью.\n"
                                         "2. Твоя задача — угадать, какой промт (текстовый запрос) был использован для его создания.\n"
                                         "3. У тебя будет 1 попытка, чтобы предложить свой вариант. Чем точнее твой промт — тем выше шанс на победу!\n\n"
                                         "Внимание! Чтобы все играли честно, я не буду показывать процент схожести до конца раунда. "
                                         "Когда раунд завершится, я подведу итоги, пришлю правильный промт и твой результат.\n\n"
                                         "Удачи 🏆")
    await send_game_image(callback_query.message, state)
    await callback_query.answer()

@user_router.callback_query(F.data == 'play_later', UserState.awaiting_readiness_to_play)
async def play_later_handler(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("Когда будешь готов(а) — просто напиши мне команду /start, и мы начнём.")
    await state.clear()
    await callback_query.answer()

# =================================================================================================
# GAME PROCESS
# =================================================================================================

@user_router.message(UserState.in_game, F.text)
async def handle_prompt_submission(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    game_id = await get_user_active_game(user_id)

    if not game_id:
        await message.answer("Сейчас нет активных игр, в которых вы участвуете. Напишите /start, чтобы начать.")
        await state.clear()
        return

    prompt_text = await get_game_prompt(game_id)
    if not prompt_text:
        await message.answer("Эта игра уже завершена. Дождитесь следующего раунда.")
        await state.clear()
        return

    attempts = await get_user_attempts(game_id, user_id)
    if attempts >= MAX_ATTEMPTS:
        await message.answer("Вы уже использовали свою попытку в этой игре. Ждите результатов!")
        return

    score = await get_similarity_score(message.text, prompt_text)
    await add_result(game_id, user_id, message.from_user.username, message.text, score)

    await message.answer("✅ Спасибо! Твой ответ записан. Жди результатов!")
    await state.clear() # Очищаем состояние после успешной попытки

# =================================================================================================
# OTHER HANDLERS
# =================================================================================================

@user_router.message(Command("help"))
async def user_help_command(message: types.Message):
    await message.answer(
        "Команды пользователя:\n"
        "/start - Начать или перезапустить бота\n"
        "/help - Показать это сообщение"
    )

# Обработчик для любого другого текста, когда пользователь не в состоянии игры
@user_router.message(F.text)
async def handle_other_text(message: types.Message):
    user = await get_user_by_id(message.from_user.id)
    # Если пользователь уже зарегистрирован, но не в игре, предлагаем начать
    if user and user['state'] == 'registered':
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🎯 Да, начинаем!", callback_data="play_now_from_text")],
            [types.InlineKeyboardButton(text="⏰ Не сейчас", callback_data="play_later_from_text")]
        ])
        await message.answer("Хотите начать игру?", reply_markup=keyboard)
    else:
        # Если пользователь новый или в процессе регистрации, отправляем на /start
        await message.answer("Чтобы начать, используйте команду /start.")

@user_router.callback_query(F.data == 'play_now_from_text')
async def play_now_from_text_handler(callback_query: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserState.awaiting_readiness_to_play)
    await play_now_handler(callback_query, state)

@user_router.callback_query(F.data == 'play_later_from_text')
async def play_later_from_text_handler(callback_query: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserState.awaiting_readiness_to_play)
    await play_later_handler(callback_query, state)
