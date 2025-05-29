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
import random

from places import get_random_places, get_directions_image_url

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MY_ID = int(os.getenv("MY_ID", "909231739"))
PUMB_URL = "https://mobile-app.pumb.ua/VDdaNY9UzYmaK4fj8"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
user_feedback_state = {}
user_booking_state = {}

# ——— Основное меню ————————————————————————————————

@dp.message(F.text == "/start")
async def start_handler(message: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton("Що це таке?"), KeyboardButton("Як це працює?")],
        [KeyboardButton("Вирушити на прогулянку")],
        [KeyboardButton("Варіанти маршрутів")],
        [KeyboardButton("Відгуки")],
        [KeyboardButton("Замовити прогулянку зі мною")],
        [KeyboardButton("Підтримати проєкт \"Одеса Навмання\"")]
    ])
    photo = FSInputFile("odesa_logo.jpg")
    await message.answer_photo(
        photo=photo,
        caption=(
            "<b>Привіт!</b> Це <i>Одесса навмання</i> — твоя несподівана, але продумана екскурсія містом.\n\n"
            "Ти не обираєш маршрут — маршрут обирає тебе.\n\n"
            "Обери, з чого хочеш почати 👇"
        ),
        reply_markup=kb
    )

@dp.message(F.text == "Що це таке?")
async def what_is_it(message: Message):
    await message.answer(
        "“Одесса навмання” — Telegram-бот, який обирає маршрут по Одесі замість тебе.\n"
        "Тисни кнопку — отримай маршрут із 3, 5 або 10 локацій."
    )

@dp.message(F.text == "Як це працює?")
async def how_it_works(message: Message):
    await message.answer(
        "1️⃣ Обираєш кількість локацій\n"
        "2️⃣ Отримуєш маршрут і карту\n"
        "3️⃣ Йдеш гуляти\n"
        "4️⃣ Ділишся враженнями"
    )

@dp.message(F.text == "Варіанти маршрутів")
async def routes_options(message: Message):
    await message.answer(
        "🔸 3 локації — коротка прогулянка\n"
        "🔸 5 локацій — на пів дня\n"
        "🔸 10 локацій — справжня пригода!"
    )

@dp.message(F.text == "Відгуки")
async def reviews(message: Message):
    await message.answer(
        "🔹 «Кайф! Дуже атмосферно»\n"
        "🔹 «Думав, що знаю Одесу — але бот здивував»\n"
        "🔹 «Брали маршрут втрьох — було круто!»"
    )

@dp.message(F.text == "Підтримати проєкт \"Одеса Навмання\"")
async def donate_handler(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("💛 Підтримати проєкт", url=PUMB_URL)]
    ])
    await message.answer("Дякуємо за підтримку! 🙏", reply_markup=keyboard)


# ——— Замовлення індивідуального маршруту —————————————————————

@dp.message(F.text == "Замовити прогулянку зі мною")
async def book_me(message: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
        [KeyboardButton("Навмання 3 локації")],
        [KeyboardButton("Навмання 5 локацій")],
        [KeyboardButton("Мій улюблений маршрут в Одесі")]
    ])
    await message.answer("Обери маршрут, який тобі цікавий:", reply_markup=kb)
    user_booking_state[message.from_user.id] = "waiting_choice"

@dp.message(F.text.in_(["Навмання 3 локації", "Навмання 5 локацій", "Мій улюблений маршрут в Одесі"]))
async def request_phone(message: Message):
    if user_booking_state.get(message.from_user.id) == "waiting_choice":
        contact_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
            [KeyboardButton("📞 Поділитися номером", request_contact=True)]
        ])
        user_booking_state[message.from_user.id] = message.text
        await message.answer("Поділись своїм номером телефону 👇", reply_markup=contact_kb)

@dp.message(F.contact)
async def received_contact(message: Message):
    choice = user_booking_state.pop(message.from_user.id, "невідомо")
    contact = message.contact.phone_number
    text = (
        f"📩 Замовлення:\n"
        f"Користувач: @{message.from_user.username or message.from_user.first_name}\n"
        f"Маршрут: {choice}\n"
        f"Телефон: {contact}"
    )
    await bot.send_message(MY_ID, text)
    await message.answer("Дякую! Я напишу найближчим часом 💬")


# ——— Рандомні маршрути ——————————————————————————————

@dp.message(F.text == "Вирушити на прогулянку")
async def start_walk(message: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton("🎯 Рандом з 3 локацій")],
        [KeyboardButton("🎯 Рандом з 5 локацій")],
        [KeyboardButton("🎯 Рандом з 10 локацій")],
        [KeyboardButton("🌟 Фірмовий маршрут")],
        [KeyboardButton("⬅ Назад")]
    ])
    await message.answer("Обери тип маршруту 👇", reply_markup=kb)

@dp.message(F.text == "⬅ Назад")
async def go_back(message: Message):
    await start_handler(message)

@dp.message(F.text.startswith("🎯 Рандом з"))
async def route_handler(message: Message):
    count = 3 if "3" in message.text else 5 if "5" in message.text else 10
    await send_route(message, count)

async def send_route(message: Message, count: int):
    await message.answer("🔄 Шукаю цікаві місця на мапі…")
    places = get_random_places(count)
    if not places:
        return await message.reply("Не вдалося знайти локації 😞")

    for i, place in enumerate(places, 1):
        caption = f"<b>{i}. {place['name']}</b>\n"
        if place.get("rating"):
            caption += f"⭐ {place['rating']} ({place.get('reviews', 0)} відгуків)\n"
        caption += place.get("address", "")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("🗺 Відкрити на мапі", url=place["url"])]
        ])
        if place.get("photo"):
            await message.answer_photo(place["photo"], caption=caption, reply_markup=kb)
        else:
            await message.answer(caption, reply_markup=kb)

    maps_link, static_map_url = get_directions_image_url(places)
    if static_map_url:
        async with aiohttp.ClientSession() as session:
            resp = await session.get(static_map_url)
            if resp.status == 200:
                photo_bytes = await resp.read()
                await message.answer_photo(photo_bytes, caption="🗺 Побудований маршрут")
    if maps_link:
        await message.answer(f"🔗 <b>Переглянути маршрут у Google Maps:</b>\n{maps_link}")

    await message.answer(
        "Що скажеш після прогулянки?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("💛 Підтримати проєкт", url=PUMB_URL)],
            [InlineKeyboardButton("✍️ Залишити відгук", callback_data="leave_feedback")]
        ])
    )

@dp.callback_query(F.data == "leave_feedback")
async def ask_feedback(callback: types.CallbackQuery):
    await callback.answer()
    user_feedback_state[callback.from_user.id] = True
    await callback.message.answer("Напиши свій відгук (до 256 символів) і можеш додати 1 фото 📝📸")

@dp.message(F.photo | F.text)
async def collect_feedback(message: Message):
    if user_feedback_state.pop(message.from_user.id, False):
        text = f"📝 Відгук від @{message.from_user.username or message.from_user.first_name}:\n"
        text += message.text or ""
        if message.photo:
            await bot.send_photo(MY_ID, message.photo[-1].file_id, caption=text)
        else:
            await bot.send_message(MY_ID, text)
        await message.answer("Дякую за відгук! 💌", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("💛 Підтримати проєкт", url=PUMB_URL)]
        ]))


# ——— Фірмовий маршрут ————————————————————————————————

@dp.message(F.text == "🌟 Фірмовий маршрут")
async def firmovyi_marshrut(message: Message):
    print("✅ Отримано запит на Фірмовий маршрут")
    await message.answer("🔄 Створюю фірмовий маршрут з 3 точок…")

    historical_types = [
        "museum", "art_gallery", "library", "church",
        "synagogue", "park", "monument", "tourist_attraction"
    ]
    places = get_random_places(1, allowed_types=historical_types)
    if not places:
        return await message.answer("😢 Не вдалося знайти історичну локацію.")

    place = places[0]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("➡️ Далі – GPS-рандом", callback_data="to_gps")],
        [InlineKeyboardButton("💛 Підтримати проєкт", url=PUMB_URL)]
    ])
    await message.answer(
        f"1️⃣ <b>{place['name']}</b>\n📍 {place['address']}\n"
        f"<a href='{place['url']}'>🗺 Відкрити на мапі</a>",
        reply_markup=kb
    )

@dp.callback_query(F.data == "to_gps")
async def show_random_gps(callback: types.CallbackQuery):
    await callback.answer()
    print("⚡ GPS-рандом сработал")
    center_lat, center_lng = 46.4825, 30.7233
    radius = 0.045
    rand_lat = center_lat + random.uniform(-radius, radius)
    rand_lng = center_lng + random.uniform(-radius, radius)
    rand_url = f"https://maps.google.com/?q={rand_lat},{rand_lng}"
    kb2 = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("➡️ Далі – Гастро-точка", callback_data="to_food")],
        [InlineKeyboardButton("💛 Підтримати проєкт", url=PUMB_URL)]
    ])
    await callback.message.answer(
        f"2️⃣ Випадкова точка\n📍 {rand_lat:.5f}, {rand_lng:.5f}\n<a href='{rand_url}'>🗺 Відкрити на мапі</a>",
        reply_markup=kb2
    )

@dp.callback_query(F.data == "to_food")
async def show_food_place(callback: types.CallbackQuery):
    await callback.answer()
    food_place = get_random_places(1, allowed_types=["restaurant", "cafe", "bakery"])[0]
    kb3 = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🎲 Обери бюджет з кубика", callback_data="roll_budget")],
        [InlineKeyboardButton("💛 Підтримати проєкт", url=PUMB_URL)]
    ])
    await callback.message.answer(
        f"3️⃣ <b>{food_place['name']}</b>\n📍 {food_place['address']}\n"
        f"<a href='{food_place['url']}'>🗺 Відкрити на мапі</a>",
        reply_markup=kb3
    )

@dp.callback_query(F.data == "roll_budget")
async def roll_budget(callback: types.CallbackQuery):
    await callback.answer()
    budget = random.choice([
        "10 грн — смак виживання",
        "50 грн — базарний делюкс",
        "100 грн — як місцевий",
        "300 грн — одна страва і розмова",
        "500 грн — їжа як пригода",
        "Що порадить офіціант"
    ])
    btns = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("💛 Підтримати проєкт", url=PUMB_URL)],
        [InlineKeyboardButton("✍️ Залишити відгук", callback_data="leave_feedback")],
        [InlineKeyboardButton("⬅ Повернутись в меню", callback_data="back_to_menu")]
    ])
    await callback.message.answer(f"🎯 Твій бюджет: <b>{budget}</b>", reply_markup=btns)

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.answer()
    await start_handler(callback.message)


# ——— Запуск бота ————————————————————————————————————

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
