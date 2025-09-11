from aiogram import types, Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from db.database import (add_result, get_user_attempts, get_game_prompt,
                         add_participant, get_current_active_game,
                         get_game, add_or_update_user, get_user_by_id,
                         update_user_state, update_user_phone)
from utils.similarity import get_similarity_score
from middlewares.subscription import is_user_subscribed
from config.config import CHANNEL_ID
import re

user_router = Router()

MAX_ATTEMPTS = 1

class UserState(StatesGroup):
    awaiting_phone_number = State()
    in_game = State()

# =================================================================================================
# HELPERS
# =================================================================================================

async def ask_for_subscription(message: types.Message, is_new_user: bool):
    channel_link = "https://t.me/ci_jobs" # Замените на реальную ссылку
    keyboard = [
        [types.InlineKeyboardButton(text="↗️ Перейти в канал", url=channel_link)],
        [types.InlineKeyboardButton(text="✅ Я подписался(ась)", callback_data="check_subscription_again")]
    ]
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

    if is_new_user:
        text = (
            "Чтобы присоединиться к соревнованию, тебе необходимо быть подписчиком нашего канала. "
            "Подпишись и нажми кнопку «✅ Я подписался(ась)», чтобы продолжить."
        )
    else:
        text = (
            "Похоже, ты отписался от нашего канала. "
            "Чтобы продолжить, пожалуйста, подпишись снова и нажми кнопку."
        )
    
    await message.answer(text, reply_markup=markup, disable_web_page_preview=True)

async def ask_for_phone(message: types.Message):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📞 Отправить мой номер", callback_data="request_contact_permission")]
    ])
    # Запрос контакта через Reply-кнопку, которая появится после нажатия на Inline
    reply_keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="📞 Отправить мой номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        "Здорово! Ты с нами 🚀\n\n"
        "Для связи в случае победы нам нужен твой номер телефона. Поделись им, нажав кнопку ниже 👇",
        reply_markup=reply_keyboard # Сначала показываем Reply-клавиатуру
    )


# =================================================================================================
# START AND REGISTRATION FLOW
# =================================================================================================

@user_router.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext, bot: Bot):
    await state.clear()
    user = message.from_user
    db_user = await get_user_by_id(user.id)
    is_new = not db_user

    if is_new:
        await add_or_update_user(user.id, user.username, user.first_name, user.last_name)
        await message.answer("Приветствую в «Битве Промптов»✨")

    subscribed = await is_user_subscribed(user.id, bot)
    if not subscribed:
        await ask_for_subscription(message, is_new)
        return

    if not db_user or not db_user['phone_number']:
        await state.set_state(UserState.awaiting_phone_number)
        await ask_for_phone(message)
    else:
        await show_main_menu(message)

@user_router.callback_query(F.data == 'check_subscription_again')
async def check_subscription_again_handler(callback_query: types.CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback_query.from_user.id
    subscribed = await is_user_subscribed(user_id, bot)
    
    if subscribed:
        await callback_query.message.delete()
        db_user = await get_user_by_id(user_id)
        if not db_user or not db_user['phone_number']:
            await state.set_state(UserState.awaiting_phone_number)
            await ask_for_phone(callback_query.message)
        else:
            await show_main_menu(callback_query.message)
    else:
        await callback_query.answer("Подписка не найдена. Попробуй еще раз.", show_alert=True)

@user_router.message(UserState.awaiting_phone_number, F.contact)
async def phone_number_handler(message: types.Message, state: FSMContext):
    phone_number = message.contact.phone_number
    await update_user_phone(message.from_user.id, phone_number)
    await update_user_state(message.from_user.id, 'registered')
    await message.answer("Отлично, всё готово для старта!", reply_markup=types.ReplyKeyboardRemove())
    await state.clear()
    await show_main_menu(message)

async def show_main_menu(message: types.Message):
    game_id = await get_current_active_game()
    text = "Сейчас нет активных игр. Как только начнется новая, я пришлю уведомление."
    keyboard = None

    if game_id:
        text = "Готов(а) сыграть прямо сейчас?"
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Подключиться к игре", callback_data="play_now")]
        ])

    await message.answer(text, reply_markup=keyboard)

# =================================================================================================
# GAME READINESS AND START
# =================================================================================================

@user_router.callback_query(F.data == 'play_now')
async def play_now_handler(callback_query: types.CallbackQuery, state: FSMContext):
    game_id = await get_current_active_game()
    if not game_id:
        await callback_query.message.edit_text("К сожалению, активная игра только что закончилась. Дождись следующей!")
        await callback_query.answer()
        return
        
    user_id = callback_query.from_user.id
    attempts = await get_user_attempts(game_id, user_id)
    if attempts >= MAX_ATTEMPTS:
        await callback_query.message.edit_text("Ты уже принял(а) участие в этом раунде. Жди результатов!")
        await callback_query.answer()
        return

    await callback_query.message.edit_text("Супер! Вот правила:\n\n"
                                         "1. Я отправлю тебе уникальное изображение, сгенерированное нейросетью.\n"
                                         "2. Твоя задача — угадать, какой промт (текстовый запрос) был использован для его создания.\n"
                                         "3. У тебя будет 1 попытка, чтобы предложить свой вариант. Чем точнее твой промт — тем выше шанс на победу!\n\n"
                                         "Внимание! Чтобы все играли честно, я не буду показывать процент схожести до конца раунда. "
                                         "Когда раунд завершится, я подведу итоги, пришлю правильный промт и твой результат.\n\n"
                                         "Удачи 🏆")
    
    game_data = await get_game(game_id)
    if game_data:
        _, photo_id = game_data
        await add_participant(game_id, user_id)
        await callback_query.message.answer_photo(photo_id, caption="Вот изображение. Жду твой вариант промпта!")
        await state.set_state(UserState.in_game)
    else:
        await callback_query.message.answer("Не удалось загрузить игру. Попробуй позже.")
        
    await callback_query.answer()


# =================================================================================================
# GAME PROCESS
# =================================================================================================

@user_router.message(UserState.in_game, F.text)
async def handle_prompt_submission(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    game_id = await get_current_active_game()

    if not game_id:
        await message.answer("Игра уже закончилась. Напиши /start, чтобы узнать о новых играх.")
        await state.clear()
        return

    attempts = await get_user_attempts(game_id, user_id)
    if attempts >= MAX_ATTEMPTS:
        await message.answer("Вы уже использовали свою попытку в этой игре. Ждите результатов!")
        return

    prompt_text = await get_game_prompt(game_id)
    if not prompt_text:
        await message.answer("Эта игра уже завершена. Дождитесь следующего раундов.")
        await state.clear()
        return

    score = await get_similarity_score(message.text, prompt_text)
    await add_result(game_id, user_id, message.from_user.username, message.text, score)

    await message.answer("✅ Спасибо! Твой ответ записан. Жди результатов!")
    await state.clear()

# =================================================================================================
# OTHER HANDLERS
# =================================================================================================

@user_router.message(F.text)
async def handle_other_text(message: types.Message, state: FSMContext, bot: Bot):
    # Если пользователь что-то пишет, не находясь в игре, просто предлагаем ему начать
    await start_handler(message, state, bot)
