import json
import os
import asyncio
import aiohttp

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton,
    KeyboardButton, ReplyKeyboardMarkup
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from places import get_random_places, get_directions_image_url

# --- Настройки ---
load_dotenv()
BOT_TOKEN   = os.getenv("BOT_TOKEN")
MY_ID       = int(os.getenv("MY_ID", "909231739"))
PUMB_URL    = "https://mobile-app.pumb.ua/VDdaNY9UzYmaK4fj8"
USERS_FILE  = "users.json"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp  = Dispatcher()

# Состояния
user_booking_state  : dict[int,str]   = {}
user_feedback_state : dict[int,bool]  = {}

# --- Утилиты для users.json ---
def save_user(user_id: int):
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        users = []
    if user_id not in users:
        users.append(user_id)
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)

async def broadcast(text: str):
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        users = []
    for uid in users:
        try:
            await bot.send_message(uid, text)
        except:
            pass

# --- /start и главное меню ---
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    save_user(message.from_user.id)
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton("Що це таке?"), KeyboardButton("Як це працює?")],
        [KeyboardButton("Вирушити на прогулянку")],
        [KeyboardButton("Варіанти маршрутів")],
        [KeyboardButton("Відгуки")],
        [KeyboardButton("Замовити прогулянку зі мною")],
        [KeyboardButton("Підтримати проєкт \"Одеса Навмання\"")]
    ])
    photo = FSInputFile("odesa_logo.jpg")
    await message.answer_photo(photo, caption=(
        "<b>Привіт!</b> Це <i>Одесса навмання</i> — твоя несподівана, але продумана екскурсія містом.\n\n"
        "Ти не обираєш маршрут — маршрут обирає тебе.\n\n"
        "Обери, з чого хочеш почати 👇"
    ), reply_markup=kb)

# --- Информационные команды ---
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
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("💛 Підтримати проєкт", url=PUMB_URL)]])
    await message.answer("Дякуємо за підтримку! 🙏", reply_markup=kb)

# --- Заказ прогулки ---
@dp.message(F.text == "Замовити прогулянку зі мною")
async def book_me(message: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
        [KeyboardButton("Навмання 3 локації")],
        [KeyboardButton("Навмання 5 локацій")],
        [KeyboardButton("Мій улюблений маршрут в Одесі")]
    ])
    user_booking_state[message.from_user.id] = "waiting_choice"
    await message.answer("Обери маршрут:", reply_markup=kb)

@dp.message(F.text.in_(["Навмання 3 локації","Навмання 5 локацій","Мій улюблений маршрут в Одесі"]))
async def request_phone(message: Message):
    if user_booking_state.get(message.from_user.id) == "waiting_choice":
        user_booking_state[message.from_user.id] = message.text
        kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
            [KeyboardButton("📞 Поділитися номером", request_contact=True)]
        ])
        await message.answer("Поділись номером:", reply_markup=kb)

@dp.message(F.contact)
async def received_contact(message: Message):
    choice = user_booking_state.pop(message.from_user.id, "—")
    summary = (
        f"📩 <b>Новий заказ</b>:\n"
        f"Користувач: @{message.from_user.username or message.from_user.first_name}\n"
        f"Маршрут: {choice}\n"
        f"Телефон: {message.contact.phone_number}"
    )
    await bot.send_message(MY_ID, summary)
    await message.answer("Дякую! Я зв’яжусь з тобою.")

# --- Прогулка ---
@dp.message(F.text == "Вирушити на прогулянку")
async def start_walk(message: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton("🎯 Рандом з 3 локацій")],
        [KeyboardButton("🎯 Рандом з 5 локацій")],
        [KeyboardButton("🎯 Рандом з 10 локацій")],
        [KeyboardButton("🌟 Фірмовий маршрут")],
        [KeyboardButton("⬅ Назад")]
    ])
    await message.answer("Обери тип маршруту:", reply_markup=kb)

@dp.message(F.text == "⬅ Назад")
async def go_back(message: Message):
    await cmd_start(message)

@dp.message(F.text.startswith("🎯 Рандом з"))
async def route_handler(message: Message):
    count = int(message.text.split(" ")[2])
    await send_route(message, count)

async def send_route(message: Message, count: int):
    await message.answer("🔄 Шукаю локації…")
    places = get_random_places(count)
    for i,p in enumerate(places,1):
        cap = f"<b>{i}. {p['name']}</b>\n{p.get('address','')}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗺 Відкрити", url=p["url"])]])
        if p.get("photo"):
            await message.answer_photo(p["photo"], cap, reply_markup=kb)
        else:
            await message.answer(cap, reply_markup=kb)
    maps_link, static_url = get_directions_image_url(places)
    if static_url:
        async with aiohttp.ClientSession() as s:
            r = await s.get(static_url)
            if r.status==200:
                data=await r.read()
                await message.answer_photo(types.BufferedInputFile(data,"route.png"),"🗺 Маршрут")
    if maps_link:
        await message.answer(f"🔗 Google Maps:\n{maps_link}")
    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton("💛 Підтримати", url=PUMB_URL)],
        [InlineKeyboardButton("✍️ Відгук", callback_data="leave_feedback")]
    ])
    await message.answer("Враження?", reply_markup=btns)

# --- Фірмовий маршрут ---
@dp.message(F.text == "🌟 Фірмовий маршрут")
async def firm_route(message: Message):
    await message.answer("🔄 Складаю фірмовий маршрут…")
    hist = ["museum","art_gallery","library","church","synagogue","park","tourist_attraction"]
    first = get_random_places(1, allowed_types=hist)[0]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➡️ GPS-рандом", callback_data="to_gps")],
        [InlineKeyboardButton("⬅ Назад", callback_data="back_to_menu")]
    ])
    await message.answer(
        f"1️⃣ <b>{first['name']}</b>\n📍 {first['address']}",
        reply_markup=kb
    )

@dp.callback_query(F.data == "to_gps")
async def to_gps(cb: types.CallbackQuery):
    import random
    lat0,lon0,r=46.4825,30.7233,0.045
    lat,lon=lat0+random.uniform(-r,r),lon0+random.uniform(-r,r)
    url=f"https://maps.google.com/?q={lat},{lon}"
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("➡️ Гастро-точка", callback_data="to_food")],
        [InlineKeyboardButton("⬅ Назад", callback_data="back_to_menu")]
    ])
    await cb.message.answer(f"2️⃣ Випадкова точка\n📍 {lat:.5f},{lon:.5f}", reply_markup=kb)

@dp.callback_query(F.data == "to_food")
async def to_food(cb: types.CallbackQuery):
    food = get_random_places(1, allowed_types=["restaurant","cafe","bakery"])[0]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Бюджет", callback_data="roll_budget")],
        [InlineKeyboardButton("⬅ Назад", callback_data="back_to_menu")]
    ])
    await cb.message.answer(f"3️⃣ <b>{food['name']}</b>\n📍 {food['address']}", reply_markup=kb)

@dp.callback_query(F.data == "roll_budget")
async def roll_budget(cb: types.CallbackQuery):
    import random
    b = random.choice(["10 грн","50 грн","100 грн","300 грн","500 грн","Що порадить офіціант"])
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Назад", callback_data="back_to_menu")]])
    await cb.message.answer(f"🎯 Бюджет: <b>{b}</b>", reply_markup=kb)

@dp.callback_query(F.data == "back_to_menu")
async def back_menu(cb: types.CallbackQuery):
    await cmd_start(cb.message)

# --- Відгуки ---
@dp.callback_query(F.data == "leave_feedback")
async def ask_feedback(cb: types.CallbackQuery):
    user_feedback_state[cb.from_user.id] = True
    await cb.message.answer("Напиши відгук і можеш додати фото.")

@dp.message(F.photo | F.text)
async def collect_feedback(message: Message):
    if user_feedback_state.pop(message.from_user.id, False):
        await message.answer("Дякую за відгук! 💌")

# --- Админ: рассылка ---
@dp.message(F.text.startswith("/broadcast"))
async def cmd_broadcast(message: Message):
    if message.from_user.id != MY_ID:
        return
    parts = message.text.split(" ",1)
    if len(parts)<2:
        await message.answer("Використання: /broadcast Текст повідомлення")
        return
    await message.answer("Розсилаю…")
    await broadcast(parts[1])
    await message.answer("✅ Розсилка завершена.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
