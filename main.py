import os
import asyncio
import random
import aiohttp
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.enums import ParseMode

from places import get_random_places, get_directions_image_url

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MY_ID = int(os.getenv("MY_ID", "909231739"))
PUMB_URL = "https://mobile-app.pumb.ua/VDdaNY9UzYmaK4fj8"

bot = Bot(token=BOT_TOKEN, default=types.ParseMode.HTML)
dp = Dispatcher()

user_feedback = {}
user_booking = {}

# ----- Меню та старт -----
@dp.message(F.text == "/start")
async def cmd_start(msg: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton("🎯 Рандом з 3 локацій"),
         KeyboardButton("🎯 Рандом з 5 локацій")],
        [KeyboardButton("🎯 Рандом з 10 локацій"),
         KeyboardButton("🌟 Фірмовий маршрут")]
    ])
    photo = FSInputFile("odesa_logo.jpg")
    await msg.answer_photo(
        photo=photo,
        caption="<b>Привіт!</b> Обери тип маршруту:",
        reply_markup=kb
    )

# ----- Рандомні маршрути -----
@dp.message(F.text.startswith("🎯 Рандом"))
async def random_route(msg: types.Message):
    # по тексту визначаєм кількість
    if "3" in msg.text: n = 3
    elif "5" in msg.text: n = 5
    else: n = 10
    await send_route(msg, n)

async def send_route(msg: types.Message, n: int):
    await msg.answer("🔄 Шукаю місця на мапі…")
    places = get_random_places(n=n)
    if not places:
        return await msg.answer("😢 Не вдалося знайти локації.")
    for i, p in enumerate(places, 1):
        caption = f"<b>{i}. {p['name']}</b>\n{p['address']}"
        if p.get("rating"):
            caption = f"⭐{p['rating']}  " + caption
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🗺 Відкрити на мапі", url=p["url"])
        )
        if p.get("photo"):
            await msg.answer_photo(photo=p["photo"], caption=caption, reply_markup=kb)
        else:
            await msg.answer(caption, reply_markup=kb)

    link, img = get_directions_image_url(places)
    if img:
        async with aiohttp.ClientSession() as sess:
            r = await sess.get(img)
            if r.status == 200:
                data = await r.read()
                await msg.answer_photo(data, caption="🗺 Маршрут", parse_mode=None)
    if link:
        await msg.answer(f"🔗 Подивитися в Google Maps:\n{link}")

# ----- Фірмовий маршрут -----
@dp.message(F.text == "🌟 Фірмовий маршрут")
async def branded_route(msg: types.Message):
    await msg.answer("🔄 Створюю фірмовий маршрут з 3 точок…")
    historical = [
        "museum", "art_gallery", "library",
        "church", "synagogue", "park",
        "historical_landmark", "monument"
    ]
    # 1) історична локація
    places = get_random_places(n=1, allowed_types=historical)
    if not places:
        return await msg.answer("😢 Не вдалося знайти історичну локацію.")
    p = places[0]
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("➡️ Далі — GPS-рандом", callback_data="to_gps"),
        InlineKeyboardButton("💛 Підтримати проєкт", url=PUMB_URL)
    )
    text = (
        f"1️⃣ <b>{p['name']}</b>\n"
        f"{p['address']}\n"
        f"<a href='{p['url']}'>🗺 Відкрити на мапі</a>"
    )
    await msg.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "to_gps")
async def cb_gps(q: types.CallbackQuery):
    lat = 46.4825 + random.uniform(-0.045, 0.045)
    lng = 30.7233 + random.uniform(-0.045, 0.045)
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("➡️ Далі — Гастро-точка", callback_data="to_food"),
        InlineKeyboardButton("💛 Підтримати проєкт", url=PUMB_URL)
    )
    text = f"2️⃣ Випадкова точка\n📍 {lat:.5f}, {lng:.5f}\n<a href='https://maps.google.com/?q={lat},{lng}'>🗺 Відкрити</a>"
    await q.message.edit_reply_markup()  # приберемо старі кнопки
    await q.message.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "to_food")
async def cb_food(q: types.CallbackQuery):
    food_types = ["restaurant", "cafe", "bakery"]
    p = get_random_places(n=1, allowed_types=food_types)[0]
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("🎲 Обери бюджет", callback_data="roll_budget"),
        InlineKeyboardButton("💛 Підтримати проєкт", url=PUMB_URL)
    )
    text = (
        f"3️⃣ <b>{p['name']}</b>\n"
        f"{p['address']}\n"
        f"<a href='{p['url']}'>🗺 Відкрити на мапі</a>"
    )
    await q.message.edit_reply_markup()
    await q.message.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "roll_budget")
async def cb_budget(q: types.CallbackQuery):
    budgets = [
        "10 грн — смак виживання", "50 грн — базарний делюкс",
        "100 грн — як місцевий", "300 грн — одна страва",
        "500 грн — їжа як пригода", "Що порадить офіціант"
    ]
    b = random.choice(budgets)
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("⬅ Повернутись у меню", callback_data="back_to_menu"),
        InlineKeyboardButton("✍️ Відгук", callback_data="leave_feedback")
    )
    await q.message.edit_reply_markup()
    await q.message.answer(f"🎯 Твій бюджет: <b>{b}</b>", reply_markup=kb)

@dp.callback_query(F.data == "back_to_menu")
async def cb_back(q: types.CallbackQuery):
    await cmd_start(q.message)

# ----- Відгуки -----
@dp.callback_query(F.data == "leave_feedback")
async def ask_review(q: types.CallbackQuery):
    user_feedback[q.from_user.id] = True
    await q.message.answer("Напиши свій відгук (можеш фото)…")

@dp.message()
async def collect_review(msg: types.Message):
    if user_feedback.pop(msg.from_user.id, False):
        text = f"📩 Відгук від @{msg.from_user.username}:\n{msg.text or ''}"
        if msg.photo:
            await bot.send_photo(MY_ID, msg.photo[-1].file_id, caption=text)
        else:
            await bot.send_message(MY_ID, text)
        await msg.answer("Дякую за відгук! ❤️")

# ----- Запуск -----
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
