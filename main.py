#Оновлений main.py з Monobank URL і публічним доступом до бота

from aio gram import Bot, Dispatcher, types, F
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import asyncio
import os

from places import get_random_places, get_directions_image_url

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MY_ID = int(os.getenv("MY_ID", "909231739"))  # Твій Telegram ID
MONOBANK_URL = "https://send.monobank.ua/jar/6B7BvEHqXG"  # Замінити на твій лінк

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Додаткові змінні для станів відгуку
user_feedback_state = {}

@dp.message(F.text == "/start")
async def start_handler(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="Що це таке?")
    kb.button(text="Як це працює?")
    kb.button(text="Вирушити на прогулянку")
    kb.button(text="Варіанти маршрутів")
    kb.button(text="Відгуки")
    kb.button(text="Замовити прогулянку зі мною")
    kb.button(text="Підтримати проєкт \"Одеса Навмання\"")
    kb.adjust(2)

    photo = FSInputFile("odesa_logo.jpg")
    await message.answer_photo(
        photo=photo,
        caption=(
            "<b>Привіт!</b> Це <i>Одесса навмання</i> — твоя несподівана, але продумана екскурсія містом.\n\n"
            "Ти не обираєш маршрут — маршрут обирає тебе.\n\n"
            "Обери, з чого хочеш почати 👇"
        ),
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

@dp.message(F.text == "Підтримати проєкт \"Одеса Навмання\"")
async def donate_handler(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💛 Підтримати на Monobank", url=MONOBANK_URL)]
    ])
    await message.answer("Дякуємо за підтримку! 🙏", reply_markup=keyboard)

# Обробка маршруту
@dp.message(F.text.startswith("Маршрут з"))
async def route_handler(message: Message):
    if "3" in message.text:
        await send_route(message, 3)
    elif "5" in message.text:
        await send_route(message, 5)
    elif "10" in message.text:
        await send_route(message, 10)

async def send_route(message: Message, count: int):
    await message.answer("🔄 Шукаю цікаві місця на мапі…")
    places = get_random_places(count)

    if not places:
        await message.reply("Не вдалося знайти локації 😞 Спробуй ще раз.")
        return

    for i, place in enumerate(places, 1):
        caption = f"<b>{i}. {place['name']}</b>\n"
        if place.get("rating"):
            caption += f"⭐ {place['rating']} ({place.get('reviews', 0)} відгуків)\n"
        caption += f"{place.get('address', '')}"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗺 Відкрити на мапі", url=place["url"])]
        ])

        if place.get("photo"):
            await message.answer_photo(photo=place["photo"], caption=caption, reply_markup=keyboard)
        else:
            await message.answer(caption, reply_markup=keyboard)

    # Картинка + маршрут
    map_url, directions_url = get_directions_image_url(places)
    await message.answer_photo(photo=map_url, caption="🗺 Ось твій маршрут!", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔗 Відкрити маршрут у Google Maps", url=directions_url)]]))

    # Додати кнопки Підтримати / Відгук
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💛 Підтримати проєкт", url=MONOBANK_URL)],
        [InlineKeyboardButton(text="✍️ Залишити відгук", callback_data="leave_feedback")]
    ])
    await message.answer("Що скажеш після прогулянки?", reply_markup=buttons)

@dp.callback_query(F.data == "leave_feedback")
async def ask_feedback(callback: types.CallbackQuery):
    user_feedback_state[callback.from_user.id] = True
    await callback.message.answer("Напиши свій відгук (до 256 символів) і можеш додати 1 фото 📝📸")

@dp.message(F.photo | F.text)
async def collect_feedback(message: Message):
    if user_feedback_state.get(message.from_user.id):
        user_feedback_state[message.from_user.id] = False

        # Надсилання адміну
        caption = f"📝 Новий відгук від @{message.from_user.username or message.from_user.first_name} (ID {message.from_user.id}):\n"
        if message.text:
            caption += message.text

        if message.photo:
            photo = message.photo[-1].file_id
            await bot.send_photo(MY_ID, photo=photo, caption=caption)
        else:
            await bot.send_message(MY_ID, caption)

        # Дякуємо користувачу + кнопка підтримки
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💛 Підтримати на Monobank", url=MONOBANK_URL)]
        ])
        await message.answer("Дякуємо за відгук! 💌", reply_markup=keyboard)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
