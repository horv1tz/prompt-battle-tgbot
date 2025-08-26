import aiohttp
from PIL import Image, ImageDraw, ImageFont
import io

async def get_user_avatar(bot, user_id):
    """Получает аватар пользователя и возвращает его в виде объекта Image."""
    try:
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        if photos.photos:
            file_id = photos.photos[0][-1].file_id
            file = await bot.get_file(file_id)
            file_path = file.file_path
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.telegram.org/file/bot{bot.token}/{file_path}") as response:
                    if response.status == 200:
                        image_data = await response.read()
                        return Image.open(io.BytesIO(image_data)).convert("RGBA")
    except Exception as e:
        print(f"Error getting avatar for {user_id}: {e}")
    # Возвращаем заглушку, если аватар не найден
    return Image.new("RGBA", (100, 100), (200, 200, 200, 255))


async def create_winners_image(bot, results):
    """Создает изображение с топ-3 победителями."""
    # Размеры и фон
    width, height = 800, 600
    background = Image.new("RGB", (width, height), color="#1E2A38")
    draw = ImageDraw.Draw(background)

    # Шрифты
    try:
        title_font = ImageFont.truetype("arial.ttf", 40)
        name_font = ImageFont.truetype("arial.ttf", 30)
        score_font = ImageFont.truetype("arial.ttf", 25)
    except IOError:
        title_font = ImageFont.load_default()
        name_font = ImageFont.load_default()
        score_font = ImageFont.load_default()

    # Заголовок
    draw.text((width / 2, 50), "🏆 Победители Раунда 🏆", font=title_font, anchor="ms", fill="white")

    # Позиции для победителей
    positions = [
        {"pos": (width / 2, 200), "size": 120, "place": "1st"}, # 1 место
        {"pos": (width / 4, 300), "size": 100, "place": "2nd"}, # 2 место
        {"pos": (width * 3 / 4, 300), "size": 100, "place": "3rd"} # 3 место
    ]

    top_winners = results[:3]

    for i, winner in enumerate(top_winners):
        user_id, username, _, score = winner
        pos_info = positions[i]

        # Аватар
        avatar = await get_user_avatar(bot, user_id)
        avatar = avatar.resize((pos_info["size"], pos_info["size"]))
        
        # Круглая маска для аватара
        mask = Image.new("L", avatar.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, avatar.size[0], avatar.size[1]), fill=255)
        
        # Координаты для вставки аватара
        avatar_x = int(pos_info["pos"][0] - avatar.width / 2)
        avatar_y = int(pos_info["pos"][1] - avatar.height / 2)
        
        background.paste(avatar, (avatar_x, avatar_y), mask)

        # Ник и очки
        draw.text((pos_info["pos"][0], pos_info["pos"][1] + 80), username or f"User {user_id}", font=name_font, anchor="ms", fill="white")
        draw.text((pos_info["pos"][0], pos_info["pos"][1] + 120), f"{score} очков", font=score_font, anchor="ms", fill="#FFD700")

    # Сохраняем в байты
    img_byte_arr = io.BytesIO()
    background.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return img_byte_arr
