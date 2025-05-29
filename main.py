import os
import asyncio
import logging
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

# --- Налаштування ---
logging.basicConfig(level=logging.INFO)
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MY_ID = int(os.getenv("MY_ID", "909231739"))
PUMB_URL = "https://mobile-app.pumb.ua/VDdaNY9UzYmaK4fj8"

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# --- /start ---
@dp.message(F.text == "/start")
async def cmd_start(msg: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton("🎯 Рандом з 3 локацій"), KeyboardButton("🎯 Рандом з 5 локацій")],
        [KeyboardButton("🎯 Рандом з 10 локацій"), KeyboardButton("🌟 Фірмовий маршрут")]
    ])
    photo = FSInputFile("odesa_logo.jpg")
    await msg.answer_photo(
        photo=photo,
        caption="<b>Привіт!</b> Обери тип маршруту:",
        reply_markup=kb
    )

# --- Рандомні маршрути ---
@dp.message(F.text.startswith("🎯 Рандом"))
async def random_route(msg: types.Message):
    n = 3 if "3" in msg.text else 5 if "5" in msg.text else 10
    await msg.answer("🔄 Шукаю місця…")
    places = get_random_places(n=n)
    if not places:
        return await msg.answer("😢 Не знайшло нічого.")
    for i, p in enumerate(places, 1):
        cap = f"<b>{i}. {p['name']}</b>\n{p['address']}"
        if p.get("rating"):
            cap = f"⭐ {p['rating']}  " + cap
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🗺 Відкрити на мапі", url=p["url"])
        )
        if p.get("photo"):
            await msg.answer_photo(photo=p["photo"], caption=cap, reply_markup=kb)
        else:
            await msg.answer(cap, reply_markup=kb)
    link, img = get_directions_image_url(places)
    if img:
        async with aiohttp.ClientSession() as sess:
            r = await sess.get(img)
            if r.status == 200:
                data = await r.read()
                await msg.answer_photo(data, caption="🗺 Маршрут")
    if link:
        await msg.answer(f"🔗 Подивитися в Google Maps:\n{link}")

# --- Фірмовий маршрут ---
@dp.message(F.text == "🌟 Фірмовий маршрут")
async def branded_route(msg: types.Message):
    await msg.answer("🔄 Формую фірмовий маршрут з 3 точок…")
    hist_types = ["museum","art_gallery","library","church","synagogue","park","historical_landmark","monument"]
    # 1. Історична локація
    h = get_random_places(n=1, allowed_types=hist_types)
    if not h:
        return await msg.answer("😢 Не вдалося знайти історичну локацію.")
    p = h[0]
    kb = InlineKeyboardMarkup(row_width=1).add(
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
    # 2. GPS-рандом
    lat = 46.4825 + random.uniform(-0.045,0.045)
    lng = 30.7233 + random.uniform(-0.045,0.045)
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("➡️ Далі — Гастро-точка", callback_data="to_food"),
        InlineKeyboardButton("💛 Підтримати проєкт", url=PUMB_URL)
    )
    txt = f"2️⃣ Випадкова точка\n📍 {lat:.5f}, {lng:.5f}\n<a href='https://maps.google.com/?q={lat},{lng}'>🗺 Відкрити</a>"
    await q.message.edit_reply_markup()  # приберемо старі кнопки
    await q.message.answer(txt, reply_markup=kb)

@dp.callback_query(F.data == "to_food")
async def cb_food(q: types.CallbackQuery):
    # 3. Гастро-точка
    ftypes = ["restaurant","cafe","bakery"]
    p = get_random_places(n=1, allowed_types=ftypes)[0]
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("🎲 Обери бюджет", callback_data="roll_budget"),
        InlineKeyboardButton("💛 Підтримати проєкт", url=PUMB_URL)
    )
    txt = (
        f"3️⃣ <b>{p['name']}</b>\n"
        f"{p['address']}\n"
        f"<a href='{p['url']}'>🗺 Відкрити на мапі</a>"
    )
    await q.message.edit_reply_markup()
    await q.message.answer(txt, reply_markup=kb)

@dp.callback_query(F.data == "roll_budget")
async def cb_budget(q: types.CallbackQuery):
    opts = [
        "10 грн — виживання", "50 грн — делюкс",
        "100 грн — як місцевий", "300 грн — страва і розмова",
        "500 грн — пригода", "Що порадить офіціант"
    ]
    b = random.choice(opts)
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("⬅ Повернутись у меню", callback_data="back_to_menu"),
        InlineKeyboardButton("✍️ Відгук", callback_data="leave_feedback")
    )
    await q.message.edit_reply_markup()
    await q.message.answer(f"🎯 Твій бюджет: <b>{b}</b>", reply_markup=kb)

@dp.callback_query(F.data == "back_to_menu")
async def cb_back(q: types.CallbackQuery):
    await cmd_start(q.message)

# --- Відгуки ---
user_fb = {}
@dp.callback_query(F.data == "leave_feedback")
async def ask_fb(q: types.CallbackQuery):
    user_fb[q.from_user.id] = True
    await q.message.answer("Напиши відгук…")

@dp.message()
async def catch_all(msg: types.Message):
    if user_fb.pop(msg.from_user.id, False):
        text = f"📩 Відгук @{msg.from_user.username}:\n{msg.text}"
        await bot.send_message(MY_ID, text)
        return await msg.answer("Дякую!")
    # якщо нічого не зловили
    logging.info(f"Надійшло повідомлення: {msg.text}")

# --- Запуск ---
async def main():
    # Видаляємо вебхук, щоб запрацювало getUpdates
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
