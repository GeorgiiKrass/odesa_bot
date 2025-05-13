from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import asyncio
import os

from places import get_random_places

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
MY_ID = 909231739  # Замени на свой Telegram user_id

def is_authorized(user_id):
    return user_id == MY_ID

@dp.message(F.text == "/start")
async def start_handler(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="Що це таке?")
    kb.button(text="Як це працює?")
    kb.button(text="Вирушити на прогулянку")
    kb.button(text="Варіанти маршрутів")
    kb.button(text="Відгуки")
    kb.adjust(2)
    photo = FSInputFile("odesa_logo.jpg")
    await message.answer_photo(
        photo=photo,
        caption=(
            "<b>Привіт!</b> Це <i>Одесса навмання</i> — твоя несподівана, але продумана екскурсія містом.\n\n"
            "Ти не обираєш маршрут — маршрут обирає тебе.\n\n"
            "Бот проведе тебе в ті місця Одеси, які ти міг роками проходити повз. "
            "Випадкові, емоційні, живі.\n\n"
            "Обери нижче, з чого хочеш почати 👇"
        ),
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

@dp.message(F.text == "Вирушити на прогулянку")
async def self_guided(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="Маршрут з 3 локації (29 грн)")
    kb.button(text="Маршрут з 5 локацій (49 грн)")
    kb.button(text="Маршрут з 10 локацій (79 грн)")
    kb.button(text="⬅ Назад")
    kb.adjust(1)
    await message.answer(
        "<b>Варіанти самостійних маршрутів:</b>\n\n"
        "📍 <b>Маршрут з 3 локації</b> — 29 грн\n"
        "📍 <b>Маршрут з 5 локацій</b> — 49 грн\n"
        "📍 <b>Маршрут з 10 локацій</b> — 79 грн\n\n"
        "Після оплати ви миттєво отримаєте посилання на маршрут у Google Maps з описом усіх локацій 💌",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

@dp.message(F.text == "⬅ Назад")
async def go_back(message: Message):
    await start_handler(message)

@dp.message(F.text == "Маршрут з 3 локації (29 грн)")
async def route_3(message: Message):
    await send_fake_paid_route(message, 3)

@dp.message(F.text == "Маршрут з 5 локацій (49 грн)")
async def route_5(message: Message):
    await send_fake_paid_route(message, 5)

@dp.message(F.text == "Маршрут з 10 локацій (79 грн)")
async def route_10(message: Message):
    await send_fake_paid_route(message, 10)

@dp.message(F.text.startswith("/getroute"))
async def send_route(message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply("Цей бот ще не доступний публічно 🤓")
        return
    try:
        count = int(message.text.split(" ")[1])
        if count not in [3, 5, 10]:
            raise ValueError
    except:
        await message.reply("Використання: /getroute 3 або /getroute 5 або /getroute 10")
        return
    await send_fake_paid_route(message, count)

async def send_fake_paid_route(message: Message, count: int):
    await message.answer("🔄 Шукаю цікаві місця на мапі…")
    places = get_random_places(count)

    if not places:
        await message.reply("Не вдалося знайти локації 😞 Спробуй ще раз.")
        return

    for i, place in enumerate(places, 1):
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗺 Відкрити на мапі", url=place["url"])]
        ])

        caption = f"<b>{i}. {place['name']}</b>\n"
        if place.get("rating"):
            caption += f"⭐ {place['rating']}\n"
        if place.get("address"):
            caption += f"{place['address']}\n"

        if place.get("photo_url"):
            await message.answer_photo(photo=place["photo_url"], caption=caption, reply_markup=btn)
        else:
            await message.answer(caption, reply_markup=btn)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
