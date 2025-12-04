import json
import os
import asyncio
import aiohttp
import random

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    KeyboardButton, ReplyKeyboardMarkup
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from places import get_random_places, get_random_place_near, get_directions_image_url

# --- Налаштування ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MY_ID = int(os.getenv("MY_ID", "909231739"))
PUMB_URL = "https://mobile-app.pumb.ua/VDdaNY9UzYmaK4fj8"
USERS_FILE = "users.json"

# Google Maps review links
REVIEWS_MAIN_LINK = "https://share.google/iUAPUiXnjQ0uOOhzk"   # кнопка «Відгуки» в меню
REVIEWS_BOT_LINK = "https://g.page/r/CYKKZ6sJyKz0EAE/review"   # «Залишити відгук про цей БОТ»

# --- Ініціалізація бота і диспетчера ---
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- Словники станів ---
user_booking_state: dict[int, str] = {}
user_feedback_state: dict[int, bool] = {}
# mode: "random" | "firm"
user_route_state: dict[int, dict] = {}


# --- Утиліти для роботи з users.json ---
def save_user(user_id: int):
    """Додає user_id в users.json, якщо його там ще немає."""
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
    """Повертає список усіх user_id з users.json."""
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        users = []
    return users


# --- Стартове меню ---
@dp.message(F.text == "/start")
async def start_handler(message: Message):
    save_user(message.from_user.id)

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="🎲 Випадкова рекомендація")],
        [KeyboardButton(text="🚶‍♂️ Вирушити на прогулянку")],
        [KeyboardButton(text="ℹ️ Як працює бот?")],
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
        "3️⃣ Ти відкриваш для себе нову Одесу — без довгих пошуків у Google.\n\n"
        "Спробуй один із режимів у меню 👇"
    )


# --- Випадкова рекомендація (одна точка) ---
@dp.message(F.text == "🎲 Випадкова рекомендація")
async def random_recommendation(message: Message):
    await message.answer("🔍 Шукаю для тебе цікаве місце в Одесі…")

    places = get_random_places(1)
    if not places:
        return await message.reply("Не вдалося знайти локацію 😞 Спробуй ще раз трохи пізніше.")

    p = places[0]
    caption = f"<b>{p['name']}</b>\n"
    if p.get("rating"):
        caption += f"⭐ {p['rating']} ({p.get('reviews', 0)} відгуків)\n"
    caption += p.get("address", "")

    # Лінк на відгуки по цьому місцю
    if p.get("place_id"):
        place_review_url = f"https://search.google.com/local/writereview?placeid={p['place_id']}"
    else:
        place_review_url = p["url"]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 Відкрити на мапі", url=p["url"])],
        [InlineKeyboardButton(text="⭐ Залишити відгук по цьому місцю", url=place_review_url)],
    ])

    if p.get("photo"):
        await message.answer_photo(photo=p["photo"], caption=caption, reply_markup=kb)
    else:
        await message.answer(caption, reply_markup=kb)

    btns = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💛 Підтримати проєкт", url=PUMB_URL)],
        [InlineKeyboardButton(text="✍️ Залишити відгук про цей БОТ", url=REVIEWS_BOT_LINK)],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")],
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


# --- Рандомні маршрути (3/5/10 точок) ---
@dp.message(F.text.startswith("🎯 Рандом з"))
async def route_handler(message: Message):
    count = 3 if "3" in message.text else 5 if "5" in message.text else 10

    user_route_state[message.from_user.id] = {
        "mode": "random",
        "count": count,
        "status": "choose_start",
    }

    kb = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True,
        keyboard=[
            [KeyboardButton(text="🏙 Почнемо в центрі Одеси")],
            [KeyboardButton(text="📍 Почнемо там де ви зараз")],
            [KeyboardButton(text="⬅ Назад")],
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

        if p.get("place_id"):
            place_review_url = f"https://search.google.com/local/writereview?placeid={p['place_id']}"
        else:
            place_review_url = p["url"]

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗺 Відкрити на мапі", url=p["url"])],
            [InlineKeyboardButton(text="⭐ Залишити відгук по цьому місцю", url=place_review_url)],
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
        [InlineKeyboardButton(text="✍️ Залишити відгук про цей БОТ", url=REVIEWS_BOT_LINK)],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")],
    ])
    await message.answer("Що скажеш після прогулянки?", reply_markup=btns)


# --- Вибір старту: центр / поточне місце (для рандомних і фірмового маршруту) ---
@dp.message(F.text.startswith("🏙 Почнемо в центрі Одеси"))
async def start_from_center(message: Message):
    data = user_route_state.pop(message.from_user.id, None)
    if not data:
        return await message.answer(
            "Спочатку обери тип маршруту в меню «Вирушити на прогулянку»."
        )

    mode = data.get("mode", "random")

    if mode == "random":
        count = data.get("count", 3)
        await send_route(message, count)
    elif mode == "firm":
        # старт фірмового маршруту від центру (start_lat/start_lon = None)
        await start_firm_route(message, start_lat=None, start_lon=None)
    else:
        await message.answer("Щось пішло не так. Спробуй ще раз обрати маршрут.")


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
        # геолокація не в контексті вибору маршруту
        return

    lat = message.location.latitude
    lon = message.location.longitude

    mode = data.get("mode", "random")

    if mode == "random":
        count = data.get("count", 3)
        await send_route(message, count, start_lat=lat, start_lon=lon)
    elif mode == "firm":
        await start_firm_route(message, start_lat=lat, start_lon=lon)
    else:
        await message.answer("Щось пішло не так. Спробуй ще раз обрати маршрут.")


# === ФІРМОВИЙ МАРШРУТ: вибір старту ===
@dp.message(F.text == "🌟 Фірмовий маршрут")
async def firmovyi_marshrut_start(message: Message):
    user_route_state[message.from_user.id] = {
        "mode": "firm",
        "status": "choose_start",
    }

    kb = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True,
        keyboard=[
            [KeyboardButton(text="🏙 Почнемо в центрі Одеси")],
            [KeyboardButton(text="📍 Почнемо там де ви зараз")],
            [KeyboardButton(text="⬅ Назад")],
        ],
    )

    await message.answer(
        "Фірмовий маршрут складається з:\n"
        "1️⃣ Історичної точки\n"
        "2️⃣ GPS-рандом точки поруч\n"
        "3️⃣ Гастрономічної точки\n"
        "4️⃣ Випадкового бюджету 🎲\n\n"
        "Спочатку обери, звідки почнемо 👇",
        reply_markup=kb
    )


async def start_firm_route(
    message: Message,
    start_lat: float | None = None,
    start_lon: float | None = None,
):
    """Старт фірмового маршруту від вказаних координат (або від центру, якщо None)."""
    await message.answer("🔄 Створюю фірмовий маршрут з 3 точок…")

    hist_types = ["museum", "art_gallery", "library", "church", "synagogue", "park", "tourist_attraction"]
    first_list = get_random_places(1, allowed_types=hist_types, start_lat=start_lat, start_lon=start_lon)
    if not first_list:
        await message.answer("Не вдалося знайти першу історичну точку 😞")
        return

    first = first_list[0]

    if first.get("place_id"):
        first_review_url = f"https://search.google.com/local/writereview?placeid={first['place_id']}"
    else:
        first_review_url = first["url"]

    kb1 = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="➡️ Далі — GPS-рандом",
            callback_data=f"firm_to_gps:{first['lat']}:{first['lon']}"
        )],
        [InlineKeyboardButton(text="⭐ Залишити відгук по цьому місцю", url=first_review_url)],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")],
    ])

    caption = (
        f"1️⃣ <b>{first['name']}</b>\n"
        f"📍 {first.get('address', '')}\n"
        f"<a href='{first['url']}'>🗺 Відкрити на мапі</a>"
    )

    if first.get("photo"):
        await message.answer_photo(first["photo"], caption=caption, reply_markup=kb1)
    else:
        await message.answer(caption, reply_markup=kb1)


@dp.callback_query(F.data.startswith("firm_to_gps:"))
async def firm_to_gps_step(callback: types.CallbackQuery):
    # Розбираємо координати першої точки
    _, lat_str, lon_str = callback.data.split(":")
    lat_first, lon_first = float(lat_str), float(lon_str)

    await callback.answer()
    await callback.message.answer("📍 Обираю наступну точку поруч з першою…")

    # 2️⃣ Друга точка — GPS-рандом поблизу першої
    second = get_random_place_near(lat_first, lon_first)
    if not second:
        await callback.message.answer("Не вдалося знайти другу точку 😞")
        return

    if second.get("place_id"):
        second_review_url = f"https://search.google.com/local/writereview?placeid={second['place_id']}"
    else:
        second_review_url = second["url"]

    kb2 = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="➡️ Далі — гастроточка",
            callback_data=f"firm_to_food:{second['lat']}:{second['lon']}"
        )],
        [InlineKeyboardButton(text="⭐ Залишити відгук по цьому місцю", url=second_review_url)],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")],
    ])

    caption = (
        f"2️⃣ <b>{second['name']}</b>\n"
        f"📍 {second.get('address', '')}\n"
        f"<a href='{second['url']}'>🗺 Відкрити на мапі</a>"
    )

    if second.get("photo"):
        await callback.message.answer_photo(second["photo"], caption=caption, reply_markup=kb2)
    else:
        await callback.message.answer(caption, reply_markup=kb2)


@dp.callback_query(F.data.startswith("firm_to_food:"))
async def firm_to_food_place(callback: types.CallbackQuery):
    # Розбираємо координати другої точки
    _, lat_str, lon_str = callback.data.split(":")
    lat_prev, lon_prev = float(lat_str), float(lon_str)

    await callback.answer()
    await callback.message.answer("🍽 Шукаю гастроточку поблизу…")

    food_types = ["restaurant", "cafe"]
    third = get_random_place_near(lat_prev, lon_prev, radius=700, allowed_types=food_types)
    if not third:
        await callback.message.answer("Не вдалося знайти гастроточку 😞")
        return

    if third.get("place_id"):
        third_review_url = f"https://search.google.com/local/writereview?placeid={third['place_id']}"
    else:
        third_review_url = third["url"]

    kb3 = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Показати бюджет", callback_data="firm_show_budget")],
        [InlineKeyboardButton(text="⭐ Залишити відгук по цьому місцю", url=third_review_url)],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")],
    ])

    caption = (
        f"3️⃣ <b>{third['name']}</b>\n"
        f"📍 {third.get('address', '')}\n"
        f"<a href='{third['url']}'>🗺 Відкрити на мапі</a>"
    )

    if third.get("photo"):
        await callback.message.answer_photo(third["photo"], caption=caption, reply_markup=kb3)
    else:
        await callback.message.answer(caption, reply_markup=kb3)


@dp.callback_query(F.data == "firm_show_budget")
async def firm_show_budget(callback: types.CallbackQuery):
    await callback.answer()

    budget = random.choice([
        "100 грн", "200 грн", "300 грн", "500 грн", "1000 грн",
        "50 грн", "150 грн", "250 грн"
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")],
        [InlineKeyboardButton(text="💛 Підтримати проєкт", url=PUMB_URL)],
        [InlineKeyboardButton(text="✍️ Залишити відгук про цей БОТ", url=REVIEWS_BOT_LINK)],
    ])

    await callback.message.answer(f"🎯 Бюджет: <b>{budget}</b>", reply_markup=kb)


@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.answer()
    await start_handler(callback.message)


# === Відгуки (старий FSM залишаємо, раптом стане в пригоді) ===
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
    if user_feedback_state.get(message.from_user.id):
        user_feedback_state[message.from_user.id] = False

        text = (
            f"💬 <b>Новий відгук від @{message.from_user.username or message.from_user.id}:</b>\n\n"
            f"{message.text}"
        )
        await bot.send_message(MY_ID, text)

        await message.answer("Дякую за відгук! 💛 Це дуже допомагає розвивати проєкт.")
    else:
        # інші текстові повідомлення, які не підпали під хендлери — ігноруємо
        pass


# --- Розділ «Відгуки» ---
@dp.message(F.text == "Відгуки")
async def reviews(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⭐ Переглянути та залишити відгук на Google Maps",
            url=REVIEWS_MAIN_LINK
        )],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")],
    ])

    await message.answer(
        "Тут ти можеш переглянути відгуки та залишити свій про «Одеса Навмання» 💛",
        reply_markup=kb
    )


@dp.message(F.text == "Підтримати проєкт \"Одеса Навмання\"")
async def donate_handler(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💛 Підтримати проєкт", url=PUMB_URL)],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")],
    ])

    await message.answer(
        "Проєкт «Одеса Навмання» існує завдяки підтримці таких людей, як ти 💛\n\n"
        "Якщо хочеш, можеш задонатити на розвиток бота, нові маршрути та локації.",
        reply_markup=keyboard
    )


# --- Адмінська розсилка ---
async def broadcast_to_all(text: str):
    users = load_all_users()
    if not users:
        await bot.send_message(MY_ID, "В базі поки немає користувачів для розсилки.")
        return

    ok, fail = 0, 0
    for uid in users:
        try:
            await bot.send_message(uid, text)
            ok += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1

    await bot.send_message(
        MY_ID,
        f"Розсилка завершена.\nУспішно: {ok}\nПомилок: {fail}"
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
