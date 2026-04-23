import json
import os
import asyncio
from math import radians, sin, cos, asin, sqrt
from datetime import datetime

import pytz
import gspread
from google.oauth2.service_account import Credentials

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    KeyboardButton, ReplyKeyboardMarkup
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from places import (
    get_random_places,
    get_random_place_near,
    CENTER_LAT,
    CENTER_LON,
    HOTEL_TYPES,
    GASTRO_TYPES,
    HISTORICAL_TYPES,
    SHOP_TYPES,
)

# --- Налаштування ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MY_ID = int(os.getenv("MY_ID", "909231739"))

PUMB_URL = os.getenv("PUMB_DONATE_URL", "https://mobile-app.pumb.ua/VDdaNY9UzYmaK4fj8")
USERS_FILE = "users.json"
VISITED_FILE = "visited.json"
LIMITS_FILE = "limits.json"
FEEDBACK_FILE = "place_feedback.json"
SAVED_FILE = "saved_places.json"
LAST_SHOWN_FILE = "last_shown_places.json"

SPREADSHEET_NAME = os.getenv("GOOGLE_SHEETS_SPREADSHEET")
CREDS_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

INSTAGRAM_URL = os.getenv("INSTAGRAM_URL", "https://www.instagram.com/odesa_navmannya")
BOT_LINK = os.getenv("BOT_LINK", "https://t.me/odesanavmannya_bot")

DAILY_WALKS_LIMIT = 3
DAILY_RECS_LIMIT = 5

ODESSA_TZ = pytz.timezone("Europe/Kyiv")

for file in [VISITED_FILE, LIMITS_FILE, USERS_FILE, FEEDBACK_FILE, SAVED_FILE, LAST_SHOWN_FILE]:
    if not os.path.exists(file):
        with open(file, "w", encoding="utf-8") as f:
            default_value = [] if file == USERS_FILE else {}
            json.dump(default_value, f, ensure_ascii=False, indent=2)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- Google Sheets ---
gs_client = None
if CREDS_JSON and SPREADSHEET_NAME:
    try:
        creds_dict = json.loads(CREDS_JSON)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        gs_client = gspread.authorize(creds)
        print("Google Sheets connected")
    except Exception as e:
        print("Google Sheets ERROR:", e)
else:
    print("Google Sheets disabled: missing GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SHEETS_SPREADSHEET")

user_route_state: dict[int, dict] = {}
user_feedback_state: dict[int, dict] = {}

SECTION_LABELS = {
    "gastro": "гастро",
    "hotels": "готелі",
    "history": "історичні місця",
    "shop": "магазини",
    "random": "рандом",
}

FEEDBACK_OPTIONS = {
    "gastro": [
        ("☕ Кафе", "cafe"),
        ("🍽 Ресторан", "restaurant"),
        ("🍺 Бар / паб", "bar"),
        ("🏪 Магазин", "shop"),
        ("❌ Не має відношення", "wrong"),
        ("🚫 Не працює", "closed"),
    ],
    "hotels": [
        ("🏨 Готель", "hotel"),
        ("🛏 Апарт-готель", "aparthotel"),
        ("🧳 Хостел", "hostel"),
        ("🏡 Котедж / база", "cottage"),
        ("❌ Не має відношення", "wrong"),
        ("🚫 Не працює", "closed"),
    ],
    "history": [
        ("🏛 Історична пам'ятка", "historical"),
        ("🌳 Скоріше парк / простір", "park"),
        ("❌ Не має відношення", "wrong"),
        ("🚫 Не працює", "closed"),
    ],
    "shop": [
        ("🏪 Магазин", "shop"),
        ("🛍 ТЦ / галерея", "mall"),
        ("❌ Не має відношення", "wrong"),
        ("🚫 Не працює", "closed"),
    ],
    "random": [
        ("👍 Підходить", "ok"),
        ("❌ Не має відношення", "wrong"),
        ("🚫 Не працює", "closed"),
    ],
}


def gs_append_row(worksheet_name: str, row: list):
    if not gs_client or not SPREADSHEET_NAME:
        return
    try:
        sheet = gs_client.open(SPREADSHEET_NAME).worksheet(worksheet_name)
        sheet.append_row(row)
    except Exception as e:
        print(f"GS append error [{worksheet_name}]:", e)


def save_user_to_sheets(user):
    gs_append_row("users", [
        user.id,
        user.username or "",
        user.first_name or "",
        datetime.now(ODESSA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    ])


def save_place_feedback_to_sheets(user_id: int, section: str, place_id: str, place_name: str, feedback: str):
    gs_append_row("place_feedback", [
        datetime.now(ODESSA_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        user_id,
        section,
        place_id,
        place_name,
        feedback
    ])


def save_bot_feedback_to_sheets(user, rating: int, text: str, photo_url: str):
    gs_append_row("bot_feedback", [
        datetime.now(ODESSA_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        user.id,
        user.username or "",
        rating,
        text,
        photo_url
    ])


def save_saved_place_to_sheets(user_id: int, place_id: str):
    gs_append_row("saved_places", [
        user_id,
        place_id,
        datetime.now(ODESSA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    ])


def save_shown_place_to_sheets(user_id: int, place: dict):
    gs_append_row("shown_places", [
        datetime.now(ODESSA_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        user_id,
        place.get("place_id", ""),
        place.get("name", ""),
        place.get("address", "")
    ])


def remember_last_shown_place(user_id: int, place: dict):
    try:
        with open(LAST_SHOWN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    user_places = data.setdefault(str(user_id), {})
    place_id = place.get("place_id")
    if place_id:
        user_places[place_id] = place

    with open(LAST_SHOWN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_last_shown_place(user_id: int, place_id: str):
    try:
        with open(LAST_SHOWN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    return data.get(str(user_id), {}).get(place_id)


def load_saved_places(user_id: int):
    try:
        with open(SAVED_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f).get(str(user_id), [])
    except Exception:
        return []

    if not raw:
        return []

    if isinstance(raw[0], str):
        places = []
        for pid in raw:
            place = get_last_shown_place(user_id, pid)
            if place:
                places.append(place)
        return places

    return raw


def save_user(user_id: int) -> None:
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
    except Exception:
        users = []
    if user_id not in users:
        users.append(user_id)
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)


def load_visited(user_id: int) -> set[str]:
    try:
        with open(VISITED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f).get(str(user_id), []))
    except Exception:
        return set()


def add_visited(user_id: int, place_ids: list[str]) -> None:
    try:
        with open(VISITED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    cur = set(data.get(str(user_id), []))
    for pid in place_ids:
        if pid:
            cur.add(pid)
    data[str(user_id)] = list(cur)[-500:]
    with open(VISITED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _today_str() -> str:
    return datetime.now(ODESSA_TZ).strftime("%Y-%m-%d")


def load_limits() -> dict:
    try:
        with open(LIMITS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_limits(data: dict) -> None:
    with open(LIMITS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def can_use_limit(user_id: int, key: str, limit: int) -> bool:
    if user_id == MY_ID:
        return True
    data = load_limits()
    return data.get(_today_str(), {}).get(str(user_id), {}).get(key, 0) < limit


def inc_limit(user_id: int, key: str) -> None:
    if user_id == MY_ID:
        return
    data = load_limits()
    user_data = data.setdefault(_today_str(), {}).setdefault(str(user_id), {})
    user_data[key] = user_data.get(key, 0) + 1
    save_limits(data)


def distance_m(lat1, lon1, lat2, lon2):
    r = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi, dlambda = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return r * 2 * asin((a ** 0.5))


def load_place_feedback() -> dict:
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_place_feedback(data: dict) -> None:
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_place_feedback(place_id: str, section: str, value: str, user_id: int, place_name: str = "") -> None:
    if not place_id:
        return
    data = load_place_feedback()
    rec = data.setdefault(place_id, {
        "place_name": place_name,
        "section": section,
        "votes": {},
        "user_votes": {},
        "updated_at": datetime.now(ODESSA_TZ).isoformat(),
    })

    rec["place_name"] = place_name or rec.get("place_name", "")
    rec["section"] = section
    rec.setdefault("votes", {})
    rec.setdefault("user_votes", {})

    user_key = str(user_id)
    prev_vote = rec["user_votes"].get(user_key)
    if prev_vote:
        prev_count = rec["votes"].get(prev_vote, 0)
        if prev_count > 0:
            rec["votes"][prev_vote] = prev_count - 1
            if rec["votes"][prev_vote] <= 0:
                rec["votes"].pop(prev_vote, None)

    rec["user_votes"][user_key] = value
    rec["votes"][value] = rec["votes"].get(value, 0) + 1
    rec["updated_at"] = datetime.now(ODESSA_TZ).isoformat()
    save_place_feedback(data)
    save_place_feedback_to_sheets(user_id, section, place_id, rec.get("place_name", ""), value)


def load_saved(user_id: int):
    try:
        with open(SAVED_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get(str(user_id), [])
    except Exception:
        return []


def save_place_for_user(user_id: int, place: dict):
    try:
        with open(SAVED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    user_data = data.setdefault(str(user_id), [])
    place_id = place.get("place_id", "")
    existing_ids = [p.get("place_id") for p in user_data if isinstance(p, dict)]

    if place_id and place_id not in existing_ids:
        user_data.append(place)

    with open(SAVED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    save_saved_place_to_sheets(user_id, place_id)


def build_feedback_prompt_keyboard(place_id: str, section: str) -> InlineKeyboardMarkup:
    buttons = []
    for text, value in FEEDBACK_OPTIONS.get(section, FEEDBACK_OPTIONS["random"]):
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"fb:{section}:{value}:{place_id}")])
    buttons.append([InlineKeyboardButton(text="⬅ Закрити", callback_data="fb_close")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_place_keyboard(place: dict, section: str) -> InlineKeyboardMarkup:
    place_id = place.get("place_id", "")
    buttons = [[InlineKeyboardButton(text="🗺 На мапі", url=place["url"])]]

    if place_id:
        buttons.append([
            InlineKeyboardButton(text="👍", callback_data=f"vote:like:{place_id}"),
            InlineKeyboardButton(text="👎", callback_data=f"vote:dislike:{place_id}")
        ])
        buttons.append([
            InlineKeyboardButton(text="❤️ Зберегти", callback_data=f"save:{place_id}"),
            InlineKeyboardButton(text="❌ Видалити", callback_data=f"remove:{place['place_id']}")
        ])
        buttons.append([
            InlineKeyboardButton(
                text="🛠 Зробіть нас краще",
                callback_data=f"rate:{section}:{place_id}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_route_end_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💛 Підтримати", url=PUMB_URL)],
        [
            InlineKeyboardButton(
    text="📤 Поділитися",
    url=f"https://t.me/share/url?url={BOT_LINK}&text=🔥 Спробуй цей бот для прогулянок по Одесі"
),
            InlineKeyboardButton(text="📸 Instagram", url=INSTAGRAM_URL),
        ],
        [InlineKeyboardButton(text="✍️ Відгук про бот", callback_data="leave_feedback")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")],
    ])


def feedback_rating_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⭐", callback_data="botrate:1"),
        InlineKeyboardButton(text="⭐⭐", callback_data="botrate:2"),
        InlineKeyboardButton(text="⭐⭐⭐", callback_data="botrate:3"),
        InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data="botrate:4"),
        InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data="botrate:5"),
    ]])


async def send_place_card(message: Message, place: dict, index: int | None = None, section: str = "random"):
    title = f"<b>{index}. {place['name']}</b>" if index is not None else f"<b>{place['name']}</b>"
    caption = title + "\n"
    if place.get("rating"):
        caption += f"⭐ {place['rating']} ({place.get('reviews', 0)} відгуків)\n"
    if place.get("address"):
        caption += place["address"]

    kb = build_place_keyboard(place, section)
    if place.get("photo"):
        await message.answer_photo(place["photo"], caption=caption, reply_markup=kb)
    else:
        await message.answer(caption, reply_markup=kb)

    if place.get("place_id"):
        save_shown_place_to_sheets(message.from_user.id, place)
        remember_last_shown_place(message.from_user.id, place)

@dp.message(F.text == "/start")
async def start_handler(message: Message):
    save_user(message.from_user.id)
    save_user_to_sheets(message.from_user)

    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="🎲 Випадкова рекомендація")],
        [KeyboardButton(text="🚶‍♂️ Вирушити на прогулянку")],
        [KeyboardButton(text="✍️ Відгук про бот")],
        [KeyboardButton(text="📤 Поділитися ботом")],
        [KeyboardButton(text="ℹ️ Як працює бот?")],
        [KeyboardButton(text="📍 Мої місця")],
    ])
    await message.answer("Привіт! Я — бот <b>«Одеса Навмання»</b> 🧭\nОбирай режим 👇", reply_markup=kb)


@dp.message(F.text == "📤 Поділитися ботом")
async def share_bot(message: Message):
    await message.answer(
        f"🔥 Кинь це друзям:\n\n{BOT_LINK}"
    )


@dp.message(F.text == "🚶‍♂️ Вирушити на прогулянку")
async def walk_menu(message: Message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="🎯 Рандом з 3 локацій")],
        [KeyboardButton(text="🏨 Маршрут «Готелі»"), KeyboardButton(text="🍴 Маршрут «Гастро»")],
        [KeyboardButton(text="🌟 Фірмовий маршрут")],
        [KeyboardButton(text="⬅ Назад")],
    ])
    await message.answer("Обери тип маршруту для прогулянки Одесою 👇", reply_markup=keyboard)


@dp.message(F.text.in_({"🏨 Маршрут «Готелі»", "🍴 Маршрут «Гастро»"}))
async def thematic_handler(message: Message):
    mode = "hotels" if "Готелі" in message.text else "gastro"
    user_route_state[message.from_user.id] = {"mode": mode, "count": 3, "status": "choose_start"}
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
        [KeyboardButton(text="🏙 Почнемо в центрі Одеси")],
        [KeyboardButton(text="📍 Почнемо там де ви зараз")],
        [KeyboardButton(text="⬅ Назад")],
    ])
    await message.answer(f"Ви обрали {message.text}! 👣\nЗвідки почнемо?", reply_markup=kb)


@dp.message(F.text == "🌟 Фірмовий маршрут")
async def firm_route_menu(message: Message):
    user_route_state[message.from_user.id] = {"mode": "firm", "status": "choose_start"}
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
        [KeyboardButton(text="🏙 Почнемо в центрі Одеси")],
        [KeyboardButton(text="📍 Почнемо там де ви зараз")],
        [KeyboardButton(text="⬅ Назад")],
    ])
    await message.answer("Фірмовий маршрут: історична точка → магазин → гастро.\nЗвідки почнемо?", reply_markup=kb)


@dp.message(F.text.startswith("🎯 Рандом з"))
async def route_handler(message: Message):
    count = 3 if "3" in message.text else 5 if "5" in message.text else 10
    user_route_state[message.from_user.id] = {"mode": "random", "count": count, "status": "choose_start"}
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
        [KeyboardButton(text="🏙 Почнемо в центрі Одеси")],
        [KeyboardButton(text="📍 Почнемо там де ви зараз")],
        [KeyboardButton(text="⬅ Назад")],
    ])
    await message.answer("Звідки почнемо прогулянку? 👣", reply_markup=kb)


@dp.message(F.text == "🏙 Почнемо в центрі Одеси")
async def start_from_center(message: Message):
    data = user_route_state.pop(message.from_user.id, None)
    if not data:
        return await message.answer("Спочатку обери тип маршруту.")
    mode = data.get("mode")
    if mode == "random":
        await send_route(message, data["count"], section="random")
    elif mode == "hotels":
        await send_route(message, 3, allowed_types=HOTEL_TYPES, section="hotels")
    elif mode == "gastro":
        await send_route(message, 3, allowed_types=GASTRO_TYPES, section="gastro")
    elif mode == "firm":
        await start_firm_route(message)


@dp.message(F.text == "📍 Почнемо там де ви зараз")
async def start_from_loc(message: Message):
    if message.from_user.id not in user_route_state:
        return await message.answer("Спочатку обери тип маршруту.")
    user_route_state[message.from_user.id]["status"] = "waiting_location"
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
        [KeyboardButton(text="📌 Надіслати мою геолокацію", request_location=True)],
        [KeyboardButton(text="⬅ Назад")],
    ])
    await message.answer("Поділись геолокацією для підбору точок поруч 👇", reply_markup=kb)


@dp.message(F.location)
async def handle_location(message: Message):
    data = user_route_state.pop(message.from_user.id, None)
    if not data or data.get("status") != "waiting_location":
        return
    lat, lon = message.location.latitude, message.location.longitude
    mode = data.get("mode")
    if distance_m(lat, lon, CENTER_LAT, CENTER_LON) > 20000:
        await message.answer("Ви задалеко від Одеси, почнемо з центру 🏙")
        lat, lon = None, None
    if mode == "random":
        await send_route(message, data["count"], lat, lon, section="random")
    elif mode == "hotels":
        await send_route(message, 3, lat, lon, HOTEL_TYPES, section="hotels")
    elif mode == "gastro":
        await send_route(message, 3, lat, lon, GASTRO_TYPES, section="gastro")
    elif mode == "firm":
        await start_firm_route(message, lat, lon)


async def send_route(message: Message, count: int, start_lat=None, start_lon=None, allowed_types=None, section: str = "random"):
    user_id = message.from_user.id
    if not can_use_limit(user_id, "walks", DAILY_WALKS_LIMIT):
        return await message.answer("На сьогодні ліміт прогулянок (3) вичерпано 🚶‍♂️")

    await message.answer("🔄 Шукаю цікаві локації…")
    visited = load_visited(user_id)
    places = get_random_places(
        count,
        allowed_types=allowed_types,
        start_lat=start_lat,
        start_lon=start_lon,
        excluded_ids=visited,
        section=section,
    )
    if not places:
        return await message.reply("Локацій не знайдено 😞")

    for i, place in enumerate(places, 1):
        await send_place_card(message, place, i, section=section)

    add_visited(user_id, [p["place_id"] for p in places if p.get("place_id")])
    inc_limit(user_id, "walks")

    await message.answer("Як вам прогулянка? 😉", reply_markup=build_route_end_keyboard())


async def start_firm_route(message: Message, start_lat=None, start_lon=None):
    user_id = message.from_user.id
    if not can_use_limit(user_id, "walks", DAILY_WALKS_LIMIT):
        return await message.answer("Ліміт вичерпано 🚶‍♂️")

    await message.answer("🔄 Створюю фірмовий маршрут…")
    visited = load_visited(user_id)

    first_list = get_random_places(
        1,
        allowed_types=HISTORICAL_TYPES,
        start_lat=start_lat,
        start_lon=start_lon,
        excluded_ids=visited,
        section="history",
    )
    if not first_list:
        return await message.answer("Не знайшов історичну точку 😞")
    first = first_list[0]
    add_visited(user_id, [first.get("place_id")])
    await send_place_card(message, first, 1, section="history")

    second = get_random_place_near(
        first["lat"],
        first["lon"],
        radius=900,
        allowed_types=SHOP_TYPES,
        excluded_ids=load_visited(user_id),
        section="shop",
    )
    if not second:
        return await message.answer("Не знайшов магазин поруч 😞")
    add_visited(user_id, [second.get("place_id")])
    await send_place_card(message, second, 2, section="shop")

    third = get_random_place_near(
        second["lat"],
        second["lon"],
        radius=900,
        allowed_types=GASTRO_TYPES,
        excluded_ids=load_visited(user_id),
        section="gastro",
    )
    if not third:
        return await message.answer("Не знайшов гастро-точку поруч 😞")
    add_visited(user_id, [third.get("place_id")])
    await send_place_card(message, third, 3, section="gastro")

    inc_limit(user_id, "walks")
    await message.answer("Фірмовий маршрут готовий ✨", reply_markup=build_route_end_keyboard())


@dp.message(F.text == "🎲 Випадкова рекомендація")
async def random_recs(message: Message):
    if not can_use_limit(message.from_user.id, "recs", DAILY_RECS_LIMIT):
        return await message.answer("Ліміт вичерпано 🎲")
    await message.answer("🔍 Шукаю цікаве місце…")
    places = get_random_places(1, excluded_ids=load_visited(message.from_user.id), section="random")
    if not places:
        return await message.reply("Не знайдено 😞")
    place = places[0]
    inc_limit(message.from_user.id, "recs")
    add_visited(message.from_user.id, [place.get("place_id")])
    await send_place_card(message, place, section="random")


@dp.callback_query(F.data.startswith("vote:"))
async def handle_vote(callback: types.CallbackQuery):
    _, vote_type, place_id = callback.data.split(":")
    add_place_feedback(place_id, "rating", vote_type, callback.from_user.id)
    await callback.answer("Збережено 👍")


@dp.callback_query(F.data.startswith("save:"))
async def save_place_handler(callback: types.CallbackQuery):
    place_id = callback.data.split(":")[1]
    place = get_last_shown_place(callback.from_user.id, place_id)

    if not place:
        await callback.answer("Спочатку відкрий місце ще раз 🙌", show_alert=True)
        return

    save_place_for_user(callback.from_user.id, place)
    await callback.answer("Збережено ❤️")

@dp.callback_query(F.data.startswith("rate:"))
async def rate_place(callback: types.CallbackQuery):
    try:
        _, section, place_id = callback.data.split(":", 2)
    except ValueError:
        return await callback.answer("Помилка", show_alert=True)

    await callback.answer()
    label = SECTION_LABELS.get(section, section)
    await callback.message.answer(
        f"Оберіть, що це реально за місце у розділі «{label}»:",
        reply_markup=build_feedback_prompt_keyboard(place_id, section),
    )


@dp.callback_query(F.data.startswith("fb:"))
async def save_feedback_callback(callback: types.CallbackQuery):
    try:
        _, section, value, place_id = callback.data.split(":", 3)
    except ValueError:
        return await callback.answer("Помилка", show_alert=True)

    data = load_place_feedback()
    place_name = data.get(place_id, {}).get("place_name", "")
    add_place_feedback(place_id, section, value, callback.from_user.id, place_name=place_name)
    await callback.answer("Дякую, зберіг ✅")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Дякуємо! Це допоможе очистити базу місць 💛")


@dp.callback_query(F.data == "fb_close")
async def close_feedback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)


@dp.message(F.text == "✍️ Відгук про бот")
async def feedback_start(message: Message):
    user_feedback_state[message.from_user.id] = {"step": "rating"}
    await message.answer("Оцініть бота ⭐", reply_markup=feedback_rating_keyboard())


@dp.callback_query(F.data == "leave_feedback")
async def leave_feedback(callback: types.CallbackQuery):
    user_feedback_state[callback.from_user.id] = {"step": "rating"}
    await callback.message.answer("Оцініть бота ⭐", reply_markup=feedback_rating_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("botrate:"))
async def bot_rating(callback: types.CallbackQuery):
    rating = int(callback.data.split(":")[1])
    user_feedback_state[callback.from_user.id] = {
        "step": "text",
        "rating": rating
    }
    await callback.message.answer("Напишіть відгук або додайте фото 📸")
    await callback.answer()


@dp.callback_query(F.data == "back_to_menu")
async def btm(callback: types.CallbackQuery):
    await callback.answer()
    await start_handler(callback.message)


@dp.message(F.text == "⬅ Назад")
async def back(message: Message):
    await start_handler(message)


@dp.message(F.text == "ℹ️ Як працює бот?")
async def how(message: Message):
    await message.answer(
        "Обирай режим, а я підберу місця Одесою 🧭\n"
        "Після кожної точки можна оцінити місце, зберегти його або допомогти очистити базу."
    )


@dp.message()
async def handle_feedback_message(message: Message):
    state = user_feedback_state.get(message.from_user.id)
    if not state:
        return

    if state.get("step") != "text":
        return

    text = message.text or message.caption or ""
    photo_url = ""

    if message.photo:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"

    save_bot_feedback_to_sheets(message.from_user, state["rating"], text, photo_url)

    user_feedback_state.pop(message.from_user.id, None)
    await message.answer("Дякуємо 💛")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(1)
    await dp.start_polling(bot)
# =========================
# 🔥 МОЇ МІСЦЯ (АПГРЕЙД)
# =========================

@dp.message(F.text == "📍 Мої місця")
async def my_places(message: Message):
    saved_places = load_saved_places(message.from_user.id)

    if not saved_places:
        return await message.answer("У вас ще немає збережених місць 😌")

    await message.answer("🔖 Ваші збережені місця:")

    for place in saved_places[:10]:
        await send_place_card(message, place, section="saved")

    await message.answer(
        "Хочеш побудувати маршрут з них?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚶‍♂️ Побудувати маршрут", callback_data="route_saved")]
        ])
    )


@dp.callback_query(F.data == "route_saved")
async def route_saved(callback: types.CallbackQuery):
    saved_places = load_saved_places(callback.from_user.id)

    if not saved_places:
        return await callback.answer("Немає місць", show_alert=True)

    for i, place in enumerate(saved_places[:3], 1):
        await send_place_card(callback.message, place, i, section="saved")

    await callback.answer()


def remove_place(user_id, place_id):
    try:
        with open(SAVED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return

    user_data = data.get(str(user_id), [])
    user_data = [p for p in user_data if not (isinstance(p, dict) and p.get("place_id") == place_id)]
    user_data = [p for p in user_data if p != place_id]
    data[str(user_id)] = user_data

    with open(SAVED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@dp.callback_query(F.data.startswith("remove:"))
async def remove_handler(callback: types.CallbackQuery):
    place_id = callback.data.split(":")[1]
    remove_place(callback.from_user.id, place_id)
    await callback.answer("Видалено ❌")

if __name__ == "__main__":
    asyncio.run(main())
