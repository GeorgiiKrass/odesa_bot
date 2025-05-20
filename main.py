from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton,
    KeyboardButton, ReplyKeyboardMarkup
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import asyncio
import os
import aiohttp

from places import get_random_places, get_directions_image_url

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MY_ID = int(os.getenv("MY_ID", "909231739"))
PUMB_URL = "https://mobile-app.pumb.ua/VDdaNY9UzYmaK4fj8"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
user_feedback_state = {}
user_booking_state = {}

@dp.message(F.text == "/start")
async def start_handler(message: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="Що це таке?"), KeyboardButton(text="Як це працює?")],
        [KeyboardButton(text="Вирушити на прогулянку")],
        [KeyboardButton(text="Варіанти маршрутів")],
        [KeyboardButton(text="Відгуки")],
        [KeyboardButton(text="Замовити прогулянку зі мною")],
        [KeyboardButton(text="Підтримати проєкт \"Одеса Навмання\"")]
    ])
    photo = FSInputFile("odesa_logo.jpg")
    await message.answer_photo(
        photo=photo,
        caption="<b>Привіт!</b> Це <i>Одесса навмання</i> — твоя несподівана, але продумана екскурсія містом.\n\nТи не обираєш маршрут — маршрут обирає тебе.\n\nОбери, з чого хочеш почати 👇",
        reply_markup=kb
    )

@dp.message(F.text == "Що це таке?")
async def what_is_it(message: Message):
    await message.answer("“Одесса навмання” — Telegram-бот, який обирає маршрут по Одесі замість тебе.\nТисни кнопку — отримай маршрут із 3, 5 або 10 локацій.")

@dp.message(F.text == "Як це працює?")
async def how_it_works(message: Message):
    await message.answer("1️⃣ Обираєш кількість локацій\n2️⃣ Отримуєш маршрут і карту\n3️⃣ Йдеш гуляти\n4️⃣ Ділишся враженнями")

@dp.message(F.text == "Варіанти маршрутів")
async def routes_options(message: Message):
    await message.answer("🔸 3 локації — коротка прогулянка\n🔸 5 локацій — на пів дня\n🔸 10 локацій — справжня пригода!")

@dp.message(F.text == "Відгуки")
async def reviews(message: Message):
    await message.answer("🔹 «Кайф! Дуже атмосферно»\n🔹 «Думав, що знаю Одесу — але бот здивував»\n🔹 «Брали маршрут втрьох — було круто!»")

@dp.message(F.text == "Підтримати проєкт \"Одеса Навмання\"")
async def donate_handler(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💛 Підтримати проєкт", url=PUMB_URL)]
    ])
    await message.answer("Дякуємо за підтримку! 🙏", reply_markup=keyboard)

@dp.message(F.text == "Замовити прогулянку зі мною")
async def book_me(message: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
        [KeyboardButton(text="Навмання 3 локації")],
        [KeyboardButton(text="Навмання 5 локацій")],
        [KeyboardButton(text="Мій улюблений маршрут в Одесі")]
    ])
    await message.answer("Обери маршрут, який тобі цікавий:", reply_markup=kb)
    user_booking_state[message.from_user.id] = "waiting_choice"

@dp.message(F.text.in_(["Навмання 3 локації", "Навмання 5 локацій", "Мій улюблений маршрут в Одесі"]))
async def request_phone(message: Message):
    if user_booking_state.get(message.from_user.id) == "waiting_choice":
        contact_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
            [KeyboardButton(text="📞 Поділитися номером", request_contact=True)]
        ])
        user_booking_state[message.from_user.id] = message.text
        await message.answer("Поділись своїм номером телефону 👇", reply_markup=contact_kb)

@dp.message(F.contact)
async def received_contact(message: Message):
    choice = user_booking_state.pop(message.from_user.id, "невідомо")
    contact = message.contact.phone_number
    text = f"📩 Замовлення:\nКористувач: @{message.from_user.username or message.from_user.first_name}\nМаршрут: {choice}\nТелефон: {contact}"
    await bot.send_message(MY_ID, text)
    await message.answer("Дякую! Я напишу найближчим часом 💬")

@dp.message(F.text == "Вирушити на прогулянку")
async def show_walk_options(message: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="Маршрут з 3 локації")],
        [KeyboardButton(text="Маршрут з 5 локацій")],
        [KeyboardButton(text="Маршрут з 10 локацій")],
        [KeyboardButton(text="⬅ Назад")]
    ])
    await message.answer("📍 Обери маршрут:", reply_markup=kb)

@dp.message(F.text == "⬅ Назад")
async def go_back(message: Message):
    await start_handler(message)

@dp.message(F.text.startswith("Маршрут з"))
async def route_handler(message: Message):
    count = 3 if "3" in message.text else 5 if "5" in message.text else 10
    await send_route(message, count)

async def send_route(message: Message, count: int):
    await message.answer("🔄 Шукаю цікаві місця на мапі…")
    places = get_random_places(count)

    if not places:
        await message.reply("Не вдалося знайти локації 😞")
        return

    for i, place in enumerate(places, 1):
        caption = f"<b>{i}. {place['name']}</b>\n"
        if place.get("rating"):
            caption += f"⭐ {place['rating']} ({place.get('reviews', 0)} відгуків)\n"
        caption += f"{place.get('address', '')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗺 Відкрити на мапі", url=place["url"])]
        ])
        if place.get("photo"):
            await message.answer_photo(photo=place["photo"], caption=caption, reply_markup=kb)
        else:
            await message.answer(caption, reply_markup=kb)

    # Картинка + маршрут
    maps_link, static_map_url = get_directions_image_url(places)
    if static_map_url:
        async with aiohttp.ClientSession() as session:
            async with session.get(static_map_url) as resp:
                if resp.status == 200:
                    photo_bytes = await resp.read()
                    await message.answer_photo(
                        types.BufferedInputFile(photo_bytes, filename="route.png"),
                        caption="🗺 Побудований маршрут"
                    )
    if maps_link:
        await message.answer(f"🔗 <b>Переглянути маршрут у Google Maps:</b>\n{maps_link}")

    # Відгук + підтримка
    btns = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💛 Підтримати проєкт", url=PUMB_URL)],
        [InlineKeyboardButton(text="✍️ Залишити відгук", callback_data="leave_feedback")]
    ])
    await message.answer("Що скажеш після прогулянки?", reply_markup=btns)

@dp.callback_query(F.data == "leave_feedback")
async def ask_feedback(callback: types.CallbackQuery):
    user_feedback_state[callback.from_user.id] = True
    await callback.message.answer("Напиши свій відгук (до 256 символів) і можеш додати 1 фото 📝📸")

@dp.message(F.photo | F.text)
async def collect_feedback(message: Message):
    if user_feedback_state.get(message.from_user.id):
        user_feedback_state[message.from_user.id] = False
        text = f"📝 Відгук від @{message.from_user.username or message.from_user.first_name}:\n"
        if message.text:
            text += message.text
        if message.photo:
            await bot.send_photo(MY_ID, photo=message.photo[-1].file_id, caption=text)
        else:
            await bot.send_message(MY_ID, text)
        await message.answer("Дякую за відгук! 💌", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💛 Підтримати проєкт", url=PUMB_URL)]
        ]))

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
