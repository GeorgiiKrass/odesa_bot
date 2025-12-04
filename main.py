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
user_route_state: dict[int, dict] = {}


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


def load_all_users() -> list[int]:
    """Возвращает список всех user_id из users.json."""
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        users = []
    return users


# --- Хендлер стартового меню ---
@dp.message(F.text == "/start")
async def start_handler(message: Message):
    save_user(message.from_user.id)

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="🎲 Випадкова рекомендація")],
        [KeyboardButton(text="🚶‍♂️ Вирушити на прогулянку")],
        [KeyboardButton(text="ℹ️ Як працює бот?"), KeyboardButton(text="Відгуки")],
        [KeyboardButton(text="Підтримати проєкт \"Одеса Навмання\"")],
    ])
    await message.answer(
        "Привіт! Я — бот <b>«Одеса Навмання»</b> 🧭\n\n"
        "Я допоможу тобі відкрити Одесу по-новому: випадкові маршрути, "
        "атмосферні місця та гастрономічні відкриття.\n\n"
        "Обирай, з чого почнемо 👇",
        reply_markup=keyboard
    )


# --- «Як працює бот?» ---
@dp.message(F.text == "ℹ️ Як працює бот?")
async def how_bot_works(message: Message):
    await message.answer(
        "<b>Як працює «Одеса Навмання»?</b>\n\n"
        "1️⃣ Обираєш режим: випадкове місце або прогулянка.\n"
        "2️⃣ Я підбираю цікавинки Одеси: історичні точки, дворики, кафе.\n"
        "3️⃣ Ти відкриваєш для себе нову Одесу — без довгих пошуків у Google.\n\n"
        "Спробуй один із режимів у меню 👇"
    )


# --- Випадочная рекомендация (одна точка) ---
@dp.message(F.text == "🎲 Випадкова рекомендація")
async def random_recommendation(message: Message):
    await message.answer("🔍 Шукаю для тебе цікаве місце в Одесі…")

    # Выбираем одну точку, используя уже существующую логику (по сути, маршрут из 1 точки)
    places = get_random_places(1)
    if not places:
        return await message.reply("Не вдалося знайти локацію 😞 Спробуй ще раз трохи пізніше.")

    p = places[0]
    caption = f"<b>{p['name']}</b>\n"
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

    # Кнопка доната и отзыва
    btns = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💛 Підтримати проєкт", url=PUMB_URL)],
        [InlineKeyboardButton(text="✍️ Залишити відгук", callback_data="leave_feedback")]
    ])
    await message.answer("Як тобі рекомендація? 😉", reply_markup=btns)


# --- Меню «Вирушити на прогулянку» ---
@dp.message(F.text == "🚶‍♂️ Вирушити на прогулянку")
async def walk_menu(message: Message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="🎯 Рандом з 3 локацій")],
        [KeyboardButton(text="🎯 Рандом з 5 локацій")],
        [KeyboardButton(text="🎯 Рандом з 10 локацій")],
        [KeyboardButton(text="🌟 Фірмовий маршрут")],
        [KeyboardButton(text="⬅ Назад")],
    ])
    await message.answer(
        "Обери, який маршрут хочеш сьогодні:\n"
        "• 3 локації — невелика прогулянка\n"
        "• 5 локацій — насичена прогулянка\n"
        "• 10 локацій — справжній квест містом\n"
        "• 🌟 Фірмовий маршрут — авторський маршрут за особливою логікою",
        reply_markup=keyboard
    )


@dp.message(F.text == "⬅ Назад")
async def go_back(message: Message):
    await start_handler(message)


@dp.message(F.text.startswith("🎯 Рандом з"))
async def route_handler(message: Message):
    count = 3 if "3" in message.text else 5 if "5" in message.text else 10

    user_route_state[message.from_user.id] = {
        "count": count,
        "status": "choose_start"
    }

    kb = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True,
        keyboard=[
            [KeyboardButton(text="🏙 Почнемо в центрі Одеси")],
            [KeyboardButton(text="📍 Почнемо там де ви зараз")],
            [KeyboardButton(text="⬅ Назад")]
        ],
    )

    await message.answer(
        "Звідки почнемо прогулянку? 👣",
        reply_markup=kb
    )


async def send_route(
    message: Message,
    count: int,
    start_lat: float | None = None,
    start_lon: float | None = None,
):
    await message.answer("🔄 Шукаю цікаві місця на мапі…")
    places = get_random_places(count, start_lat=start_lat, start_lon=start_lon)
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


@dp.message(F.text.startswith("🏙 Почнемо в центрі Одеси"))
async def start_from_center(message: Message):
    data = user_route_state.pop(message.from_user.id, None)
    if not data:
        return await message.answer(
            "Спочатку обери тип маршруту в меню «Вирушити на прогулянку»."
        )

    count = data.get("count", 3)
    await send_route(message, count)


@dp.message(F.text.startswith("📍 Почнемо там де ви зараз"))
async def start_from_user_location(message: Message):
    data = user_route_state.get(message.from_user.id)
    if not data:
        return await message.answer(
            "Спочатку обери тип маршруту в меню «Вирушити на прогулянку»."
        )

    user_route_state[message.from_user.id]["status"] = "waiting_location"

    kb = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True,
        keyboard=[
            [KeyboardButton(text="📌 Надіслати мою геолокацію", request_location=True)],
            [KeyboardButton(text="⬅ Назад")],
        ],
    )

    await message.answer(
        "Поділись своєю геолокацією, щоб я почав маршрут поруч з тобою 👇",
        reply_markup=kb,
    )


@dp.message(F.location)
async def handle_location(message: Message):
    data = user_route_state.pop(message.from_user.id, None)
    if not data or data.get("status") != "waiting_location":
        return

    count = data.get("count", 3)
    lat = message.location.latitude
    lon = message.location.longitude

    await send_route(message, count, start_lat=lat, start_lon=lon)


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
        f"{first.get('address', '')}",
        reply_markup=kb1
    )

    if first.get("photo"):
        await message.answer_photo(first["photo"])


@dp.callback_query(F.data.startswith("to_gps:"))
async def to_gps_step(callback: types.CallbackQuery):
    # Разбираем координаты из callback_data
    _, lat, lon = callback.data.split(":")
    lat = float(lat)
    lon = float(lon)

    await callback.message.answer("📍 Тепер обираю наступні точки навколо цієї локації…")

    # 2️⃣ и 3️⃣ точки — случайные рядом с первыми
    second = get_random_place_near(lat, lon)
    third = get_random_place_near(second["lat"], second["lon"])

    route = [  # полный маршрут
        {"step": "1️⃣", "place": {"name": "Перша точка", **{"name": "", "address": ""}}},
        {"step": "2️⃣", "place": second},
        {"step": "3️⃣", "place": third},
    ]

    # Переиспользуем уже существующую функцию получения карты
    maps_link, static_map = get_directions_image_url([second, third])
    if static_map:
        async with aiohttp.ClientSession() as s:
            resp = await s.get(static_map)
            if resp.status == 200:
                data = await resp.read()
                await callback.message.answer_photo(
                    types.BufferedInputFile(data, filename="firm_route.png"),
                    caption="🗺 Фірмовий маршрут побудовано!"
                )
    if maps_link:
        await callback.message.answer(f"🔗 <b>Переглянути маршрут у Google Maps:</b>\n{maps_link}")

    await callback.answer()


@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.answer()
    # Возвращаем пользователя в главное меню (можно вызвать start_handler)
    fake_message = types.Message(
        message_id=callback.message.message_id,
        date=callback.message.date,
        chat=callback.message.chat,
        from_user=callback.from_user,
        sender_chat=callback.message.sender_chat,
        text="/start"
    )
    await start_handler(fake_message)


# === ОБРАБОТКА ОТЗЫВОВ ===

@dp.callback_query(F.data == "leave_feedback")
async def handle_leave_feedback(callback: types.CallbackQuery):
    user_feedback_state[callback.from_user.id] = True
    await callback.answer()
    await callback.message.answer(
        "Напиши, будь ласка, свій відгук про бот чи прогулянку 📝\n\n"
        "Це допоможе зробити «Одесу Навмання» ще кращою!"
    )


@dp.message(F.text & (F.text != "/start"))
async def collect_feedback(message: Message):
    # Если пользователь в режиме оставления отзыва
    if user_feedback_state.get(message.from_user.id):
        user_feedback_state[message.from_user.id] = False

        # Отправляем отзыв тебе в личку
        text = (
            f"💬 <b>Новий відгук від @{message.from_user.username or message.from_user.id}:</b>\n\n"
            f"{message.text}"
        )
        await bot.send_message(MY_ID, text)

        await message.answer("Дякую за відгук! 💛 Це дуже допомагає розвивати проєкт.")
    else:
        # Если это не отзыв и не /start, можно проигнорировать или что-то ответить
        pass


# --- Раздел «Відгуки» ---
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

    await message.answer(
        "Проєкт «Одеса Навмання» існує завдяки підтримці таких людей, як ти 💛\n\n"
        "Якщо хочеш, можеш задонатити на розвиток бота, нові маршрути та локації.",
        reply_markup=keyboard
    )


# --- Админская рассылка ---
async def broadcast_to_all(text: str):
    users = load_all_users()
    if not users:
        await bot.send_message(MY_ID, "В базе пока нет пользователей для рассылки.")
        return

    ok, fail = 0, 0
    for uid in users:
        try:
            await bot.send_message(uid, text)
            ok += 1
            # Чтобы не попасть в лимит телеграма — небольшая задержка
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
    await bot.send_message(
        MY_ID,
        f"Рассылка завершена.\nУспешно: {ok}\nОшибок: {fail}"
    )


@dp.message(F.text.startswith("/broadcast"))
async def admin_broadcast(message: Message):
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
