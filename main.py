import json
import os
import asyncio
import aiohttp
import random
from math import radians, sin, cos, asin, sqrt
from datetime import datetime

import pytz
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
)

# --- Перевіряємо наявність gspread для Google Sheets ---
try:
    import gspread
    from google.oauth2.service_account import Credentials

    GSHEETS_AVAILABLE = True
except ImportError:
    GSHEETS_AVAILABLE = False


# --- Налаштування ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MY_ID = int(os.getenv("MY_ID", "909231739"))

PUMB_URL = "https://mobile-app.pumb.ua/VDdaNY9UzYmaK4fj8"
USERS_FILE = "users.json"
VISITED_FILE = "visited.json"
LIMITS_FILE = "limits.json"
FEEDBACK_FILE = "feedback.json"

DAILY_WALKS_LIMIT = 3   # прогулянки на добу
DAILY_RECS_LIMIT = 5    # випадкові рекомендації на добу

# Google Maps review links
REVIEWS_MAIN_LINK = "https://share.google/iUAPUiXnjQ0uOOhzk"   # загальна сторінка відгуків
REVIEWS_BOT_LINK = "https://g.page/r/CYKKZ6sJyKz0EAE/review"   # відгук саме про бот

ODESSA_TZ = pytz.timezone("Europe/Kyiv")

# Створюємо файли, якщо їх ще немає
if not os.path.exists(VISITED_FILE):
    with open(VISITED_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f)

if not os.path.exists(LIMITS_FILE):
    with open(LIMITS_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f)

if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

if not os.path.exists(FEEDBACK_FILE):
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

# --- Ініціалізація Google Sheets (якщо доступно) ---
GS_CLIENT = None
GS_FEEDBACK_SHEET = None
GS_PLACES_SHEET = None
GS_PLACE_REVIEWS_SHEET = None

if GSHEETS_AVAILABLE:
    try:
        creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        if creds_json:
            info = json.loads(creds_json)
            creds = Credentials.from_service_account_info(
                info,
                scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            GS_CLIENT = gspread.authorize(creds)

            spreadsheet_id = os.getenv("SPREADSHEET_ID")
            if spreadsheet_id:
                sh = GS_CLIENT.open_by_key(spreadsheet_id)
                GS_FEEDBACK_SHEET = sh.worksheet("feedback")
                GS_PLACES_SHEET = sh.worksheet("places_catalog")
                GS_PLACE_REVIEWS_SHEET = sh.worksheet("place_reviews")
    except Exception as e:
        print("Не вдалося ініціалізувати Google Sheets:", e)
        GS_CLIENT = None
        GS_FEEDBACK_SHEET = None
        GS_PLACES_SHEET = None
        GS_PLACE_REVIEWS_SHEET = None

# --- Ініціалізація бота і диспетчера ---
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- Словники станів ---
user_feedback_state: dict[int, bool] = {}
# mode: "random" | "firm"
user_route_state: dict[int, dict] = {}

# Активні маршрути: user_id -> {"places": [...], "index": 0, "interesting": set[int]}
active_routes: dict[int, dict] = {}

# Кеш урлів для місць (place_id -> maps_url)
place_url_cache: dict[str, str] = {}


# --- Утиліти для роботи з users.json ---
def save_user(user_id: int) -> None:
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


def load_users() -> list[int]:
    """Повертає список всіх user_id."""
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# --- Утиліти для visited.json ---
def load_visited(user_id: int) -> set[str]:
    """
    Повертає множину place_id, які вже показували цьому користувачу.
    """
    try:
        with open(VISITED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    ids = data.get(str(user_id), [])
    return set(ids)


def add_visited(user_id: int, place_ids: list[str]) -> None:
    """
    Додає нові place_id до visited.json для користувача.
    """
    if not place_ids:
        return

    try:
        with open(VISITED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    cur = set(data.get(str(user_id), []))
    for pid in place_ids:
        if pid:
            cur.add(pid)

    trimmed = list(cur)[-500:]  # обмеження історії

    data[str(user_id)] = trimmed

    with open(VISITED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def remember_place(p: dict) -> str:
    """
    Записує place_id -> url у кеш, повертає place_id (або сурогатний id, якщо немає).
    """
    pid = p.get("place_id") or p.get("url")
    if not pid:
        pid = f"noid_{random.randint(1, 10**9)}"
    url = p.get("url")
    if url:
        place_url_cache[pid] = url
    return pid


def log_feedback_action(
    action: str,
    user: types.User,
    place_id: str,
    maps_url: str | None,
    context: str = "route",
) -> None:
    """
    Тимчасовий лог у локальний feedback.json.
    Згодом це можна замінити на запис у Google Sheets.
    """
    if maps_url is None:
        maps_url = ""

    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = []

    data.append({
        "timestamp": datetime.now(ODESSA_TZ).isoformat(),
        "user_id": user.id,
        "user_name": user.username or user.full_name,
        "place_id": place_id,
        "maps_url": maps_url,
        "action": action,
        "context": context,
    })

    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_visited_all() -> dict[str, list[str]]:
    """
    Повертає весь словник користувач -> список place_id.
    """
    try:
        with open(VISITED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# --- Ліміти на добу (прогулянки, рекомендації) ---
def _reset_limits_if_new_day(data: dict) -> dict:
    """
    Якщо в limits.json зберігається "дата" і "лічильники",
    то при зміні дати лічильники обнуляються.
    """
    tz_now = datetime.now(ODESSA_TZ)
    today_str = tz_now.date().isoformat()

    stored_date = data.get("_date")
    if stored_date != today_str:
        # Обнуляємо
        for uid in list(data.keys()):
            if uid != "_date":
                data[uid] = {"walks": 0, "recs": 0}
        data["_date"] = today_str
    return data


def can_use_limit(user_id: int, key: str, daily_limit: int) -> bool:
    """
    Перевіряє, чи може користувач ще скористатися дією (прогулянка / рек).
    """
    try:
        with open(LIMITS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    data = _reset_limits_if_new_day(data)

    u = data.get(str(user_id), {"walks": 0, "recs": 0})
    used = u.get(key, 0)
    return used < daily_limit


def inc_limit(user_id: int, key: str) -> None:
    """
    Збільшує лічильник дій для користувача (walks / recs).
    """
    try:
        with open(LIMITS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    data = _reset_limits_if_new_day(data)

    u = data.get(str(user_id), {"walks": 0, "recs": 0})
    u[key] = u.get(key, 0) + 1
    data[str(user_id)] = u

    with open(LIMITS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# --- Утиліта для підрахунку відстані ---
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Обчислює відстань між двома точками на сфері (в км).
    """
    r = 6371  # радіус Землі в кілометрах
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return r * c


# --- Обгортка для Google Maps Directions (картинка маршруту) ---
def get_directions_image_url(places: list[dict]) -> tuple[str | None, str | None]:
    """
    Повертає (maps_url, static_map_url) для маршруту між усіма точками places.
    Якщо не вдається, повертає (None, None).
    """
    if not places:
        return None, None

    base_url = "https://www.google.com/maps/dir/"
    parts = []
    for p in places:
        lat = p.get("lat")
        lon = p.get("lon")
        if lat is not None and lon is not None:
            parts.append(f"{lat},{lon}")
    if not parts:
        return None, None

    maps_url = base_url + "/".join(parts)

    try:
        from urllib.parse import urlencode
    except ImportError:
        return maps_url, None

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return maps_url, None

    base_static = "https://maps.googleapis.com/maps/api/staticmap"
    markers = []
    for idx, p in enumerate(places, start=1):
        lat = p.get("lat")
        lon = p.get("lon")
        if lat is not None and lon is not None:
            markers.append(f"label:{idx}|{lat},{lon}")

    params = {
        "size": "800x600",
        "maptype": "roadmap",
        "key": api_key,
        "markers": markers,
    }

    query = []
    for k, v in params.items():
        if k == "markers":
            for m in v:
                query.append(("markers", m))
        else:
            query.append((k, v))

    qs = "&".join(f"{k}={os.path.basename(str(v))}" for k, v in query)
    static_url = f"{base_static}?{qs}"

    return maps_url, static_url


# --- /start і головне меню ---
@dp.message(F.text == "/start")
async def start_handler(message: Message) -> None:
    save_user(message.from_user.id)

    keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [KeyboardButton(text="🎲 Випадкова рекомендація")],
            [KeyboardButton(text="🚶‍♂️ Вирушити на прогулянку")],
            [KeyboardButton(text="ℹ️ Як працює бот?")],
        ],
    )

    await message.answer(
        "Привіт! Я бот <b>«Одеса Навмання»</b> 🌊\n\n"
        "Я допоможу тобі спонтанно відкривати цікаві місця Одеси — "
        "кафе, ресторани, парки, музеї та інші локації.\n\n"
        "Обери в меню, що саме хочеш зараз:",
        reply_markup=keyboard,
    )


@dp.message(F.text == "ℹ️ Як працює бот?")
async def help_handler(message: Message) -> None:
    await message.answer(
        "Я підбираю випадкові місця в Одесі, спираючись на Google Maps.\n\n"
        "👉 <b>🎲 Випадкова рекомендація</b> — одна цікава локація для натхнення.\n"
        "👉 <b>🚶‍♂️ Вирушити на прогулянку</b> — отримай маршрут із кількох точок.\n\n"
        "Також ти можеш залишити відгук про бот, а згодом — про кожне місце окремо 💛"
    )


# --- Випадкова рекомендація (одна точка) ---
@dp.message(F.text == "🎲 Випадкова рекомендація")
async def random_recommendation(message: Message) -> None:
    user_id = message.from_user.id

    if not can_use_limit(user_id, "recs", DAILY_RECS_LIMIT):
        await message.answer(
            "На сьогодні ти вже отримав максимальну кількість рекомендацій (5) 🎲\n"
            "Повернись завтра — знайдемо щось новеньке 💛"
        )
        return

    await message.answer("🔎 Зараз підберу щось цікаве…")

    visited = load_visited(user_id)
    places = get_random_places(1, excluded_ids=visited)
    if not places:
        await message.reply("Не вдалося знайти локації 😞")
        return

    place = places[0]
    add_visited(user_id, [place.get("place_id")])
    inc_limit(user_id, "recs")

    pid = remember_place(place)
    maps_url = place_url_cache.get(pid, place.get("url", ""))

    caption = f"<b>{place['name']}</b>\n"
    if place.get("rating"):
        caption += f"⭐ {place['rating']} ({place.get('reviews', 0)} відгуків)\n"
    caption += place.get("address", "")

    log_feedback_action(
        action="shown",
        user=message.from_user,
        place_id=pid,
        maps_url=maps_url,
        context="single",
    )

    buttons = [
        [
            InlineKeyboardButton(
                text="🧭 Цікаво, відкрити на мапі",
                callback_data=f"single_map:{pid}",
            )
        ],
        [
            InlineKeyboardButton(
                text="✍️ Залишити відгук по цьому місцю",
                callback_data=f"single_review:{pid}",
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Хочу іншу рекомендацію",
                callback_data=f"single_next:{pid}",
            )
        ],
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    if place.get("photo"):
        await message.answer_photo(photo=place["photo"], caption=caption, reply_markup=kb)
    else:
        await message.answer(caption, reply_markup=kb)


@dp.callback_query(F.data.startswith("single_map:"))
async def single_map_callback(callback: types.CallbackQuery) -> None:
    _, pid = callback.data.split(":", 1)
    maps_url = place_url_cache.get(pid, "")
    if not maps_url:
        await callback.answer("Не вдалося знайти лінк на мапу 😞", show_alert=True)
        return

    log_feedback_action(
        action="interesting",
        user=callback.from_user,
        place_id=pid,
        maps_url=maps_url,
        context="single",
    )

    await callback.answer()
    await callback.message.answer(f"🧭 Відкрити на мапі:\n{maps_url}")


@dp.callback_query(F.data.startswith("single_next:"))
async def single_next_callback(callback: types.CallbackQuery) -> None:
    """
    Для простої рекомендації:
    - якщо юзер не натиснув 'цікаво', single_next вважаємо not_interesting для попередньої.
    Тут для простоти просто видаємо нову рекомендацію.
    """
    await callback.answer()
    fake_msg = callback.message
    fake_msg.from_user = callback.from_user
    await random_recommendation(fake_msg)


@dp.callback_query(F.data.startswith("single_review:"))
async def single_review_callback(callback: types.CallbackQuery) -> None:
    await callback.answer(
        "Скоро тут можна буде залишити свій відгук по місцю 💛",
        show_alert=True,
    )


# --- Меню «Вирушити на прогулянку» ---
@dp.message(F.text == "🚶‍♂️ Вирушити на прогулянку")
async def walk_menu(message: Message) -> None:
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="🎯 Рандом з 3 локацій")],
        [KeyboardButton(text="🎯 Рандом з 5 локацій")],
        [KeyboardButton(text="🌟 Фірмовий маршрут")],
        [KeyboardButton(text="⬅ Назад")],
    ])
    await message.answer(
        "Обери, який маршрут хочеш сьогодні:\n"
        "• 3 локації — невелика прогулянка\n"
        "• 5 локацій — насичена прогулянка\n"
        "• 🌟 Фірмовий маршрут — авторський маршрут за особливою логікою",
        reply_markup=keyboard
    )


@dp.message(F.text == "⬅ Назад")
async def go_back(message: Message) -> None:
    await start_handler(message)


# --- Рандомні маршрути ---
@dp.message(F.text.startswith("🎯 Рандом з"))
async def route_handler(message: Message) -> None:
    # Підтримуємо тільки 3 та 5 локацій
    if "3" in message.text:
        count = 3
    else:
        count = 5

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
) -> None:
    """
    Створює рандомний маршрут з count точок і показує його по одній точці.
    """
    user_id = message.from_user.id

    # Перевіряємо ліміт прогулянок
    if not can_use_limit(user_id, "walks", DAILY_WALKS_LIMIT):
        await message.answer(
            "На сьогодні ти вже пройшов максимальну кількість прогулянок (3) 🚶‍♂️\n"
            "Повернись завтра — будемо досліджувати Одесу далі 💛"
        )
        return

    await message.answer("🔄 Шукаю цікаві місця на мапі…")

    visited = load_visited(user_id)
    places = get_random_places(
        count,
        start_lat=start_lat,
        start_lon=start_lon,
        excluded_ids=visited,
    )
    if not places:
        await message.reply("Не вдалося знайти локації 😞")
        return

    # позначаємо всі місця як відвідані
    new_ids = [p["place_id"] for p in places if p.get("place_id")]
    add_visited(user_id, new_ids)

    # Фіксуємо використання прогулянки
    inc_limit(user_id, "walks")

    # Записуємо місця в кеш урлів
    for p in places:
        remember_place(p)

    # Зберігаємо стан маршруту для користувача
    active_routes[user_id] = {
        "places": places,
        "index": 0,
        "interesting": set(),  # індекси точок, де юзер натискав "Цікаво"
    }

    # Показуємо першу точку
    await send_route_step(message, user_id)


async def send_route_step(message: Message, user_id: int) -> None:
    """
    Показує поточну точку маршруту для user_id з кнопками:
    🧭 Цікаво, ✍️ Відгук, ➡️ Далі / Завершити.
    """
    route = active_routes.get(user_id)
    if not route:
        await message.answer(
            "Маршрут не знайдено. Обери його ще раз у меню «Вирушити на прогулянку»."
        )
        return

    places: list[dict] = route["places"]
    idx: int = route["index"]
    if idx < 0 or idx >= len(places):
        await message.answer("Маршрут завершено 🎉")
        active_routes.pop(user_id, None)
        return

    p = places[idx]

    place_id = p.get("place_id") or p.get("url") or f"{user_id}_{idx}"
    maps_url = place_url_cache.get(place_id, p.get("url"))

    # Лог: місце показане
    log_feedback_action(
        action="shown",
        user=message.from_user,
        place_id=place_id,
        maps_url=maps_url,
        context="route",
    )

    caption = f"<b>{idx + 1}. {p['name']}</b>\n"
    if p.get("rating"):
        caption += f"⭐ {p['rating']} ({p.get('reviews', 0)} відгуків)\n"
    caption += p.get("address", "")

    buttons: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="🧭 Цікаво, відкрити на мапі",
                callback_data=f"route_map:{place_id}:{idx}",
            )
        ],
        [
            InlineKeyboardButton(
                text="✍️ Залишити відгук по цьому місцю",
                callback_data=f"route_review:{place_id}:{idx}",
            )
        ],
    ]

    if idx < len(places) - 1:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="➡️ Далі",
                    callback_data=f"route_next:{place_id}:{idx}",
                )
            ]
        )
    else:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="✅ Завершити маршрут",
                    callback_data="route_finish",
                )
            ]
        )

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    if p.get("photo"):
        await message.answer_photo(photo=p["photo"], caption=caption, reply_markup=kb)
    else:
        await message.answer(caption, reply_markup=kb)


# --- Вибір старту: центр / поточне місце (для рандомних і фірмового маршруту) ---
@dp.message(F.text.startswith("🏙 Почнемо в центрі Одеси"))
async def start_from_center(message: Message) -> None:
    data = user_route_state.pop(message.from_user.id, None)
    if not data:
        await message.answer(
            "Спочатку обери тип маршруту в меню «Вирушити на прогулянку»."
        )
        return

    mode = data.get("mode", "random")

    if mode == "random":
        count = data.get("count", 3)
        await send_route(message, count)
    elif mode == "firm":
        await start_firm_route(message, CENTER_LAT, CENTER_LON)


@dp.message(F.text.startswith("📍 Почнемо там де ви зараз"))
async def start_from_here(message: Message) -> None:
    data = user_route_state.get(message.from_user.id)
    if not data:
        await message.answer(
            "Спочатку обери тип маршруту в меню «Вирушити на прогулянку»."
        )
        return

    await message.answer(
        "Надішли геолокацію 📍 (поділися своєю локацією через скріпку або кнопку в Telegram)."
    )


@dp.message(F.location)
async def handle_location(message: Message) -> None:
    data = user_route_state.get(message.from_user.id)
    if not data:
        await message.answer(
            "Спочатку обери тип маршруту в меню «Вирушити на прогулянку»."
        )
        return

    lat = message.location.latitude
    lon = message.location.longitude
    mode = data.get("mode", "random")

    if mode == "random":
        count = data.get("count", 3)
        await send_route(message, count, start_lat=lat, start_lon=lon)
    elif mode == "firm":
        await start_firm_route(message, lat, lon)


# --- Фірмовий маршрут ---
async def start_firm_route(
    message: Message,
    start_lat: float,
    start_lon: float,
) -> None:
    """
    Фірмовий маршрут:
    1) Історична / цікава точка
    2) Гастро-точка
    3) Місце для завершення прогулянки
    Поки залишаємо в старому форматі, можна буде потім перевести на "точка за точкою".
    """
    user_id = message.from_user.id

    if not can_use_limit(user_id, "walks", DAILY_WALKS_LIMIT):
        await message.answer(
            "На сьогодні ти вже пройшов максимальну кількість прогулянок (3) 🚶‍♂️\n"
            "Повернись завтра — будемо досліджувати Одесу далі 💛"
        )
        return

    await message.answer("🔄 Готую фірмовий маршрут…")

    visited = load_visited(user_id)
    places = get_random_places(3, start_lat=start_lat, start_lon=start_lon, excluded_ids=visited)

    if not places:
        await message.reply("Не вдалося знайти локації для фірмового маршруту 😞")
        return

    add_visited(user_id, [p["place_id"] for p in places if p.get("place_id")])
    inc_limit(user_id, "walks")

    for i, p in enumerate(places, 1):
        remember_place(p)
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


# --- Callback-и для маршрутів "точка за точкою" ---
@dp.callback_query(F.data.startswith("route_map:"))
async def route_map_callback(callback: types.CallbackQuery) -> None:
    """
    🧭 Цікаво, відкрити на мапі:
    - лог action = interesting
    - позначає поточну точку як "цікаву", щоб потім "Далі" не рахувалось як not_interesting
    """
    try:
        _, place_id, idx_str = callback.data.split(":", 2)
        idx = int(idx_str)
    except Exception:
        await callback.answer()
        return

    user = callback.from_user
    user_id = user.id
    route = active_routes.get(user_id)

    maps_url = place_url_cache.get(place_id)
    if (not maps_url) and route and 0 <= idx < len(route["places"]):
        p = route["places"][idx]
        maps_url = p.get("url")

    if not maps_url:
        await callback.answer("Не вдалося знайти лінк на мапу 😞", show_alert=True)
        return

    # логіка "цікаво"
    log_feedback_action(
        action="interesting",
        user=user,
        place_id=place_id,
        maps_url=maps_url,
        context="route",
    )

    # позначаємо індекс як цікавий
    if route is not None:
        route["interesting"].add(idx)

    await callback.answer()
    await callback.message.answer(f"🧭 Відкрити на мапі:\n{maps_url}")


@dp.callback_query(F.data.startswith("route_next:"))
async def route_next_callback(callback: types.CallbackQuery) -> None:
    """
    ➡️ Далі:
    - якщо по цій точці НЕ було "Цікаво" → лог action = not_interesting
    - показує наступну точку
    """
    try:
        _, place_id, idx_str = callback.data.split(":", 2)
        idx = int(idx_str)
    except Exception:
        await callback.answer()
        return

    user = callback.from_user
    user_id = user.id
    route = active_routes.get(user_id)

    if not route:
        await callback.answer(
            "Маршрут не знайдено. Обери новий у меню «Вирушити на прогулянку».",
            show_alert=True,
        )
        return

    maps_url = place_url_cache.get(place_id, "")

    # Якщо юзер не тискав "Цікаво" по цій точці → вважаємо її not_interesting
    if idx not in route["interesting"]:
        log_feedback_action(
            action="not_interesting",
            user=user,
            place_id=place_id,
            maps_url=maps_url,
            context="route",
        )

    # Рухаємось далі
    if idx + 1 < len(route["places"]):
        route["index"] = idx + 1
        await callback.answer()
        await send_route_step(callback.message, user_id)
    else:
        # це була остання точка, маршрут завершено
        active_routes.pop(user_id, None)
        await callback.answer()
        await callback.message.answer(
            "Маршрут завершено 🎉 Дякую за прогулянку Одесою Навмання 💛"
        )


@dp.callback_query(F.data.startswith("route_review:"))
async def route_review_callback(callback: types.CallbackQuery) -> None:
    """
    Поки що просто кажемо юзеру, що внутрішні відгуки в розробці.
    Потім тут підв'яжемо діалог збору рейтингу + тексту + фото.
    """
    await callback.answer(
        "Скоро тут можна буде залишити свій відгук по місцю 💛",
        show_alert=True,
    )


@dp.callback_query(F.data == "route_finish")
async def route_finish_callback(callback: types.CallbackQuery) -> None:
    """
    Ручне завершення маршруту (коли показана остання точка).
    """
    user_id = callback.from_user.id
    active_routes.pop(user_id, None)
    await callback.answer()
    await callback.message.answer(
        "Маршрут завершено 🎉 Повернись у меню, щоб запустити новий."
    )


@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery) -> None:
    await callback.answer()
    await start_handler(callback.message)


# === Відгуки через FSM (внутрішні, до адміна) ===
@dp.callback_query(F.data == "leave_feedback")
async def handle_leave_feedback(callback: types.CallbackQuery) -> None:
    user_feedback_state[callback.from_user.id] = True
    await callback.answer()
    await callback.message.answer(
        "Напиши, будь ласка, свій відгук або пропозицію одним повідомленням 💬"
    )


@dp.message(F.text & (F.chat.type == "private"))
async def handle_feedback_message(message: Message) -> None:
    user_id = message.from_user.id
    if user_feedback_state.get(user_id):
        user_feedback_state[user_id] = False
        text = message.text

        await bot.send_message(
            MY_ID,
            f"📩 <b>Новий відгук від @{message.from_user.username or message.from_user.full_name} (ID: {user_id}):</b>\n\n"
            f"{text}"
        )

        await message.answer(
            "Дякую за відгук! 💛\n"
            "Твої слова допомагають зробити проєкт кращим."
        )
    else:
        await message.answer(
            "Я тебе почув 😊\n"
            "Якщо хочеш спеціально залишити відгук про бот — натисни кнопку внизу,"
            " і я надішлю його автору напряму.",
        )


# --- Запуск бота ---
async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
