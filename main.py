import json
import os
import asyncio
import aiohttp
import random

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton,
    KeyboardButton, ReplyKeyboardMarkup
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from places import get_random_places, get_random_place_near, get_directions_image_url

# --- Настройки ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MY_ID = int(os.getenv("MY_ID", "909231739"))
PUMB_URL = "https://mobile-app.pumb.ua/VDdaNY9UzYmaK4fj8"
USERS_FILE = "users.json"

# --- Инициализация бота и диспетчера ---
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- Словари состояний ---
user_booking_state: dict[int, str] = {}
user_feedback_state: dict[int, bool] = {}

# --- Утилиты для работы с users.json ---
def save_user(user_id: int):
    """Добавляет user_id в users.json, если его там ещё нет."""
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        users = []
    if user_id not in users:
        users.append(user_id)
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)

# --- Утилита для рассылки ---
async def broadcast_to_all(text: str):
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        users = []
    for uid in users:
        try:
            await bot.send_message(uid, text)
        except Exception:
            pass

# === СТАРТОВЫЙ МЕНЮ ===
@dp.message(F.text == "/start")
async def start_handler(message: Message):
    save_user(message.from_user.id)
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
        caption=(
            "<b>Привіт!</b> Це <i>Одесса навмання</i> — твоя несподівана, але продумана екскурсія містом.\n\n"
            "Ти не обираєш маршрут — маршрут обирає тебе.\n\n"
            "Обери, з чого хочеш почати 👇"
        ),
        reply_markup=kb
    )

# === Информация ===
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
        [InlineKeyboardButton(text="💛 Підтримати проєкт", url=PUMB_URL)]
    ])
    await message.answer("Дякуємо за підтримку! 🙏", reply_markup=keyboard)

# === ЗАКАЗ ПРОГУЛЯНКИ ===
@dp.message(F.text == "Замовити прогулянку зі мною")
async def book_me(message: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
        [KeyboardButton(text="Навмання 3 локації")],
        [KeyboardButton(text="Навмання 5 локацій")],
        [KeyboardButton(text="Мій улюблений маршрут в Одесі")]
    ])
    user_booking_state[message.from_user.id] = "waiting_choice"
    await message.answer("Обери маршрут, який тобі цікавий:", reply_markup=kb)

@dp.message(F.text.in_(["Навмання 3 локації", "Навмання 5 локацій", "Мій улюблений маршрут в Одесі"]))
async def request_phone(message: Message):
    if user_booking_state.get(message.from_user.id) == "waiting_choice":
        user_booking_state[message.from_user.id] = message.text
        contact_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
            [KeyboardButton(text="📞 Поділитися номером", request_contact=True)]
        ])
        await message.answer("Поділись своїм номером телефону 👇", reply_markup=contact_kb)

@dp.message(F.contact)
async def received_contact(message: Message):
    choice = user_booking_state.pop(message.from_user.id, "невідомо")
    phone = message.contact.phone_number
    summary = (
        f"📩 <b>Нове замовлення</b>:\n"
        f"Користувач: @{message.from_user.username or message.from_user.first_name}\n"
        f"Маршрут: {choice}\n"
        f"Телефон: {phone}"
    )
    await bot.send_message(MY_ID, summary)
    await message.answer("Дякую! Я зв’яжусь з тобою найближчим часом 💬")

# === ПРОГУЛЯНКА ===
@dp.message(F.text == "Вирушити на прогулянку")
async def start_walk(message: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="🎯 Рандом з 3 локацій")],
        [KeyboardButton(text="🎯 Рандом з 5 локацій")],
        [KeyboardButton(text="🎯 Рандом з 10 локацій")],
        [KeyboardButton(text="🌟 Фірмовий маршрут")],
        [KeyboardButton(text="⬅ Назад")]
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
    for i, p in enumerate(places, 1):
        caption = f"<b>{i}. {p['name']}</b>\n"
        if p.get("rating"):
            caption += f"⭐ {p['rating']} ({p.get('reviews',0)} відгуків)\n"
        caption += p.get("address", "")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗺 Відкрити на мапі", url=p["url"])]
        ])
        if p.get("photo"):
            await message.answer_photo(photo=p["photo"], caption=caption, reply_markup=kb)
        else:
            await message.answer(caption, reply_markup=kb)
    maps_link, static_map = get_directions_image_url(places)
    if static_map:
        async with aiohttp.ClientSession() as s:
            resp = await s.get(static_map)
            if resp.status == 200:
                data = await resp.read()
                await message.answer_photo(
                    types.BufferedInputFile(data, filename="route.png"),
                    caption="🗺 Побудований маршрут"
                )
    if maps_link:
        await message.answer(f"🔗 <b>Переглянути маршрут у Google Maps:</b>\n{maps_link}")
    btns = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💛 Підтримати проєкт", url=PUMB_URL)],
        [InlineKeyboardButton(text="✍️ Залишити відгук", callback_data="leave_feedback")]
    ])
    await message.answer("Що скажеш після прогулянки?", reply_markup=btns)

# === ФІРМОВИЙ МАРШРУТ ===

@dp.message(F.text == "🌟 Фірмовий маршрут")
async def firmovyi_marshrut(message: Message):
    await message.answer("🔄 Створюю фірмовий маршрут з 3 точок…")
    # 1️⃣ Перша (історична) точка — без змін
    hist = ["museum", "art_gallery", "library", "church", "synagogue", "park", "tourist_attraction"]
    first = get_random_places(1, allowed_types=hist)[0]

    # Передаємо координати першої точки в callback_data
    kb1 = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="➡️ Далі — GPS-рандом",
            callback_data=f"to_gps:{first['lat']}:{first['lon']}"
        )],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")]
    ])
    await message.answer(
        f"1️⃣ <b>{first['name']}</b>\n"
        f"📍 {first['address']}\n"
        f"<a href='{first['url']}'>🗺</a>",
        reply_markup=kb1
    )

@dp.callback_query(F.data.startswith("to_gps"))
async def show_random_gps(callback: types.CallbackQuery):
    # Розбираємо координати першої точки
    _, lat_str, lon_str = callback.data.split(":")
    lat0, lon0 = float(lat_str), float(lon_str)

    # 2️⃣ Друга точка — рандомна з Google Maps у радіусі 700 м від першої
    second = get_random_place_near(lat0, lon0, radius=700)
    if not second:
        return await callback.message.answer("Не вдалося знайти другу точку поруч з першою.")

    # Передаємо координати другої точки далі
    kb2 = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="➡️ Далі — Гастро-точка",
            callback_data=f"to_food:{second['lat']}:{second['lon']}"
        )],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")]
    ])
    await callback.message.answer(
        f"2️⃣ <b>{second['name']}</b>\n"
        f"📍 {second['address']}\n"
        f"<a href='{second['url']}'>🗺</a>",
        reply_markup=kb2
    )

@dp.callback_query(F.data.startswith("to_food"))
async def show_food_place(callback: types.CallbackQuery):
    # Розбираємо координати другої точки
    _, lat_str, lon_str = callback.data.split(":")
    lat_prev, lon_prev = float(lat_str), float(lon_str)

    # 3️⃣ Третя точка — гастро-точка в межах 700 м від другої
    food = get_random_place_near(
        lat_prev, lon_prev,
        radius=700,
        allowed_types=["restaurant", "cafe", "bakery"]
    )
    if not food:
        return await callback.message.answer("Не вдалося знайти третю точку поруч з другою.")

    kb3 = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Кубик бюджету", callback_data="roll_budget")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")]
    ])
    await callback.message.answer(
        f"3️⃣ <b>{food['name']}</b>\n"
        f"📍 {food['address']}\n"
        f"<a href='{food['url']}'>🗺</a>",
        reply_markup=kb3
    )
@dp.callback_query(F.data == "roll_budget")
async def roll_budget(callback: types.CallbackQuery):
    import random
    # вибір випадкового бюджету
    b = random.choice(["1000 грн", "200 грн", "100 грн", "300 грн", "500 грн", "50 грн"])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")]
    ])
    await callback.message.answer(f"🎯 Бюджет: <b>{b}</b>", reply_markup=kb)
    

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    # повертаємось у головне меню викликом стартового хендлера
    await start_handler(callback.message)

# === ВІДГУК ===
@dp.callback_query(F.data == "leave_feedback")
async def ask_feedback(callback: types.CallbackQuery):
    user_feedback_state[callback.from_user.id] = True
    await callback.message.answer("Напиши свій відгук (до 256 символів) і можеш додати фото.")

@dp.message(F.photo | F.text)
async def collect_feedback(message: Message):
    if user_feedback_state.get(message.from_user.id):
        user_feedback_state.pop(message.from_user.id, None)
        await message.answer("Дякую за відгук! 💌")

# --- Хэндлер /broadcast ---
@dp.message(F.text.startswith("/broadcast"))
async def cmd_broadcast(message: Message):
    if message.from_user.id != MY_ID:
        return
    parts = message.text.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        return await message.answer("Використання: /broadcast <текст повідомлення>")
    await message.answer("Розсилаю…")
    await broadcast_to_all(parts[1])
    await message.answer("✅ Розсилка завершена.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

