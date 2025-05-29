# main.py
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

# ========== СТАРТОВЫЙ МЕНЮ ==========
@dp.message(F.text == "/start")
async def start_handler(message: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [
            KeyboardButton(text="Що це таке?"),
            KeyboardButton(text="Як це працює?")
        ],
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


# ========== БРОДІЛКА ==========
@dp.message(F.text == "Вирушити на прогулянку")
async def start_walk(message: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="🎯 Рандом з 3 локацій")],
        [KeyboardButton(text="🎯 Рандом з 5 локацій")],
        [KeyboardButton(text="🎯 Рандом з 10 локацій")],
        [KeyboardButton(text="🌟 Фірмовий маршрут")]
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
            caption += f"⭐ {p['rating']} ({p.get('reviews', 0)} відгуків)\n"
        caption += p.get("address", "")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗺 Відкрити на мапі", url=p["url"])]
        ])
        if p.get("photo"):
            await message.answer_photo(photo=p["photo"], caption=caption, reply_markup=kb)
        else:
            await message.answer(caption, reply_markup=kb)

    maps_link, static_map_url = get_directions_image_url(places)
    if static_map_url:
        async with aiohttp.ClientSession() as session:
            async with session.get(static_map_url) as resp:
                if resp.status == 200:
                    img = await resp.read()
                    await message.answer_photo(types.BufferedInputFile(img, filename="route.png"),
                                               caption="🗺 Побудований маршрут")
    if maps_link:
        await message.answer(f"🔗 <b>Переглянути маршрут у Google Maps:</b>\n{maps_link}")

    btns = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💛 Підтримати проєкт", url=PUMB_URL)],
        [InlineKeyboardButton(text="✍️ Залишити відгук", callback_data="leave_feedback")]
    ])
    await message.answer("Що скажеш після прогулянки?", reply_markup=btns)


# ========== ФІРМОВИЙ МАРШРУТ ==========
@dp.message(F.text == "🌟 Фірмовий маршрут")
async def firmovyi_marshrut(message: Message):
    await message.answer("🔄 Створюю фірмовий маршрут з 3 точок…")
    # 1) Історична точка
    hist_types = ["museum", "art_gallery", "library", "church", "synagogue", "park", "monument", "tourist_attraction"]
    places = get_random_places(1, allowed_types=hist_types)
    if not places:
        return await message.answer("😢 Не вдалося знайти історичну локацію.")
    p = places[0]
    kb1 = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Далі — GPS-рандом", callback_data="to_gps")]
    ])
    await message.answer(f"1️⃣ <b>{p['name']}</b>\n📍 {p['address']}\n<a href='{p['url']}'>🗺 Відкрити на мапі</a>",
                         reply_markup=kb1)

@dp.callback_query(F.data == "to_gps")
async def show_random_gps(callback: types.CallbackQuery):
    import random
    lat0, lon0 = 46.4825, 30.7233
    r = 0.045
    lat = lat0 + random.uniform(-r, r)
    lon = lon0 + random.uniform(-r, r)
    url = f"https://maps.google.com/?q={lat},{lon}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Далі — Гастро-точка", callback_data="to_food")]
    ])
    await callback.message.answer(f"2️⃣ Випадкова точка\n📍 Координати: {lat:.5f}, {lon:.5f}\n<a href='{url}'>🗺</a>",
                                  reply_markup=kb)

@dp.callback_query(F.data == "to_food")
async def show_food_place(callback: types.CallbackQuery):
    types_food = ["restaurant", "cafe", "bakery"]
    p = get_random_places(1, allowed_types=types_food)[0]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Обери бюджет з кубика", callback_data="roll_budget")]
    ])
    await callback.message.answer(f"3️⃣ <b>{p['name']}</b>\n📍 {p['address']}\n<a href='{p['url']}'>🗺</a>",
                                  reply_markup=kb)

@dp.callback_query(F.data == "roll_budget")
async def roll_budget(callback: types.CallbackQuery):
    import random
    budgets = [
        "10 грн — смак виживання", "50 грн — базарний делюкс",
        "100 грн — як місцевий", "300 грн — одна страва і розмова",
        "500 грн — їжа як пригода", "Що порадить офіціант"
    ]
    b = random.choice(budgets)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Повернутись в меню", callback_data="back_to_menu")]
    ])
    await callback.message.answer(f"🎯 Твій бюджет: <b>{b}</b>", reply_markup=kb)

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await start_handler(callback.message)


# ========== ОСТАЛЬНОЕ ==========
@dp.callback_query(F.data == "leave_feedback")
async def ask_feedback(callback: types.CallbackQuery):
    await callback.message.answer("Напиши свій відгук (до 256 символів) і можеш додати 1 фото 📝📸")

@dp.message(F.photo | F.text)
async def collect_feedback(message: Message):
    # ... оставляем как есть ...
    await message.answer("Дякую за відгук! 💌")


async def main():
    # удаляем webhooks, включаем polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
