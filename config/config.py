# config/config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Вставьте сюда токен вашего бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ID администраторов бота
admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(admin_id) for admin_id in admin_ids_str.split(",") if admin_id.isdigit()]

# ID канала для проверки подписки
CHANNEL_ID = os.getenv("CHANNEL_ID")
