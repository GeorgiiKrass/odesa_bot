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
    get_directions_image_url,
    CENTER_LAT,
    CENTER_LON,
    HOTEL_TYPES,
    GASTRO_TYPES
)

# --- Google Sheets інтеграція ---
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

DAILY_WALKS_LIMIT = 3   
DAILY_RECS_LIMIT = 5    

REVIEWS_MAIN_LINK = "https://share.google/iUAPUiXnjQ0uOOhzk"
REVIEWS_BOT_LINK = "https://g.page/r/CYKKZ6sJyKz0EAE/review"

ODESSA_TZ = pytz.timezone("Europe/Kyiv")

# Ініціалізація файлів
for file in [VISITED_FILE, LIMITS_FILE, USERS_FILE]:
    if not os.path.exists(file):
        with open(file, "w", encoding="utf-8") as f:
            json.dump({} if file != USERS_FILE else [], f)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

user_feedback_state: dict[int, bool] = {}
user_route_state: dict[int, dict] = {}

# --- Утиліти ---

def save_user(user_id: int) -> None:
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f: users = json.load(f)
    except: users = []
    if user_id not in users:
        users.append(user_id)
        with open(USERS_FILE, "w", encoding="utf-8") as f: json.dump(users, f, ensure_ascii=False, indent=2)

def load_all_users() -> list[int]:
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def load_visited(user_id: int) -> set[str]:
    try:
        with open(VISITED_FILE, "r", encoding="utf-8") as f: return set(json.load(f).get(str(user_id), []))
    except: return set()

def add_visited(user_id: int, place_ids: list[str]) -> None:
    try:
        with open(VISITED_FILE, "r", encoding="utf-8") as f: data = json.load(f)
    except: data = {}
    cur = set(data.get(str(user_id), []))
    for pid in place_ids:
        if pid: cur.add(pid)
    data[str(user_id)] = list(cur)[-500:]
    with open(VISITED_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def _today_str() -> str: return datetime.now(ODESSA_TZ).strftime("%Y-%m-%d")

def load_limits() -> dict:
    try:
        with open(LIMITS_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_limits(data: dict) -> None:
    with open(LIMITS_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def can_use_limit(user_id: int, key: str, limit: int) -> bool:
    if user_id == MY_ID: return True
    data = load_limits()
    return data.get(_today_str(), {}).get(str(user_id), {}).get(key, 0) < limit

def inc_limit(user_id: int, key: str) -> None:
    if user_id == MY_ID: return
    data = load_limits()
    user_data = data.setdefault(_today_str(), {}).setdefault(str(user_id), {})
    user_data[key] = user_data.get(key, 0) + 1
    save_limits(data)

def distance_m(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2, dphi, dlambda = radians(lat1), radians(lat2), radians(lat2-lat1), radians(lon2-lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    return R * 2 * asin(sqrt(a))

# --- Основні хендлери ---

@dp.message(F.text == "/start")
async def start_handler(message: Message):
    save_user(message.from_user.id)
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="🎲 Випадкова рекомендація")],
        [KeyboardButton(text="🚶‍♂️ Вирушити на прогулянку")],
        [KeyboardButton(text="ℹ️ Як працює бот?")],
    ])
    await message.answer("Привіт! Я — бот <b>«Одеса Навмання»</b> 🧭\nОбирай режим 👇", reply_markup=kb)

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
    if not data: return await message.answer("Спочатку обери тип маршруту.")
    mode = data.get("mode")
    if mode == "random": await send_route(message, data["count"])
    elif mode == "hotels": await send_route(message, 3, allowed_types=HOTEL_TYPES)
    elif mode == "gastro": await send_route(message, 3, allowed_types=GASTRO_TYPES)
    elif mode == "firm": await start_firm_route(message)

@dp.message(F.text == "📍 Почнемо там де ви зараз")
async def start_from_loc(message: Message):
    if message.from_user.id not in user_route_state: return await message.answer("Спочатку обери тип маршруту.")
    user_route_state[message.from_user.id]["status"] = "waiting_location"
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
        [KeyboardButton(text="📌 Надіслати мою геолокацію", request_location=True)],
        [KeyboardButton(text="⬅ Назад")],
    ])
    await message.answer("Поділись геолокацією для побудови маршруту поруч 👇", reply_markup=kb)

@dp.message(F.location)
async def handle_location(message: Message):
    data = user_route_state.pop(message.from_user.id, None)
    if not data or data.get("status") != "waiting_location": return
    lat, lon = message.location.latitude, message.location.longitude
    mode = data.get("mode")
    if distance_m(lat, lon, CENTER_LAT, CENTER_LON) > 20000:
        await message.answer("Ви задалеко від Одеси, почнемо з центру 🏙")
        lat, lon = None, None
    if mode == "random": await send_route(message, data["count"], lat, lon)
    elif mode == "hotels": await send_route(message, 3, lat, lon, HOTEL_TYPES)
    elif mode == "gastro": await send_route(message, 3, lat, lon, GASTRO_TYPES)
    elif mode == "firm": await start_firm_route(message, lat, lon)

async def send_route(message, count, start_lat=None, start_lon=None, allowed_types=None):
    user_id = message.from_user.id
    if not can_use_limit(user_id, "walks", DAILY_WALKS_LIMIT):
        return await message.answer("На сьогодні ліміт прогулянок (3) вичерпано 🚶‍♂️")

    await message.answer("🔄 Шукаю цікаві локації…")
    visited = load_visited(user_id)
    places = get_random_places(count, allowed_types=allowed_types, start_lat=start_lat, start_lon=start_lon, excluded_ids=visited)
    if not places: return await message.reply("Локацій не знайдено 😞")

    for i, p in enumerate(places, 1):
        caption = f"<b>{i}. {p['name']}</b>\n"
        if p.get("rating"): caption += f"⭐ {p['rating']} ({p.get('reviews', 0)} відгуків)\n"
        caption += p.get("address", "")
        rev_url = f"https://search.google.com/local/writereview?placeid={p['place_id']}" if p.get("place_id") else p["url"]
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗺 На мапі", url=p["url"])],
            [InlineKeyboardButton(text="⭐ Залишити відгук", url=rev_url)],
        ])
        if p.get("photo"): await message.answer_photo(p["photo"], caption=caption, reply_markup=kb)
        else: await message.answer(caption, reply_markup=kb)

    add_visited(user_id, [p["place_id"] for p in places if p.get("place_id")])
    inc_limit(user_id, "walks")
    maps_link, static_map = get_directions_image_url(places)
    if static_map:
        async with aiohttp.ClientSession() as s:
            resp = await s.get(static_map)
            if resp.status == 200: await message.answer_photo(types.BufferedInputFile(await resp.read(), filename="route.png"), caption="🗺 Побудований маршрут")
    if maps_link: await message.answer(f"🔗 <b>Google Maps:</b>\n{maps_link}")
    
    btns = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💛 Підтримати", url=PUMB_URL)],
        [InlineKeyboardButton(text="✍️ Відгук про бот", url=REVIEWS_BOT_LINK)],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")],
    ])
    await message.answer("Як вам прогулянка? 😉", reply_markup=btns)

# --- Фірмовий маршрут ( GPS-рандом) ---

async def start_firm_route(message, start_lat=None, start_lon=None):
    user_id = message.from_user.id
    if not can_use_limit(user_id, "walks", DAILY_WALKS_LIMIT): return await message.answer("Ліміт вичерпано 🚶‍♂️")
    await message.answer("🔄 Створюю фірмовий маршрут…")
    visited = load_visited(user_id)
    first_list = get_random_places(1, allowed_types=["museum", "park", "tourist_attraction"], start_lat=start_lat, start_lon=start_lon, excluded_ids=visited)
    if not first_list: return await message.answer("Не знайдено точку 😞")
    first = first_list[0]
    inc_limit(user_id, "walks")
    if first.get("place_id"): add_visited(user_id, [first["place_id"]])
    rev_url = f"https://search.google.com/local/writereview?placeid={first['place_id']}" if first.get("place_id") else first["url"]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Далі — GPS-рандом", callback_data=f"firm_to_gps:{first['lat']}:{first['lon']}")],
        [InlineKeyboardButton(text="⭐ Залишити відгук", url=rev_url)],
    ])
    caption = f"1️⃣ <b>{first['name']}</b>\n📍 {first.get('address', '')}\n<a href='{first['url']}'>🗺 На мапі</a>"
    if first.get("photo"): await message.answer_photo(first["photo"], caption=caption, reply_markup=kb)
    else: await message.answer(caption, reply_markup=kb)

@dp.callback_query(F.data.startswith("firm_to_gps:"))
async def firm_to_gps_step(callback: types.CallbackQuery):
    _, lat_str, lon_str = callback.data.split(":")
    lat, lon = float(lat_str), float(lon_str)
    await callback.answer()
    await callback.message.answer("📍 Шукаю точку поруч…")
    second = get_random_place_near(lat, lon, excluded_ids=load_visited(callback.from_user.id))
    if not second: return await callback.message.answer("Не знайдено 😞")
    if second.get("place_id"): add_visited(callback.from_user.id, [second["place_id"]])
    rev_url = f"https://search.google.com/local/writereview?placeid={second['place_id']}" if second.get("place_id") else second["url"]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Далі — гастроточка", callback_data=f"firm_to_food:{second['lat']}:{second['lon']}")],
        [InlineKeyboardButton(text="⭐ Відгук", url=rev_url)],
    ])
    caption = f"2️⃣ <b>{second['name']}</b>\n📍 {second.get('address', '')}\n<a href='{second['url']}'>🗺 На мапі</a>"
    if second.get("photo"): await callback.message.answer_photo(second["photo"], caption=caption, reply_markup=kb)
    else: await callback.message.answer(caption, reply_markup=kb)

@dp.callback_query(F.data.startswith("firm_to_food:"))
async def firm_to_food_place(callback: types.CallbackQuery):
    _, lat_str, lon_str = callback.data.split(":")
    lat, lon = float(lat_str), float(lon_str)
    await callback.answer()
    await callback.message.answer("🍽 Шукаю гастроточку…")
    third = get_random_place_near(lat, lon, radius=700, allowed_types=["restaurant", "cafe"], excluded_ids=load_visited(callback.from_user.id))
    if not third: return await callback.message.answer("Не знайдено 😞")
    if third.get("place_id"): add_visited(callback.from_user.id, [third["place_id"]])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Бюджет", callback_data="firm_show_budget")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")],
    ])
    caption = f"3️⃣ <b>{third['name']}</b>\n📍 {third.get('address', '')}\n<a href='{third['url']}'>🗺 На мапі</a>"
    if third.get("photo"): await callback.message.answer_photo(third["photo"], caption=caption, reply_markup=kb)
    else: await callback.message.answer(caption, reply_markup=kb)

@dp.callback_query(F.data == "firm_show_budget")
async def firm_show_budget(callback: types.CallbackQuery):
    await callback.answer()
    budget = random.choice(["100 грн", "300 грн", "500 грн", "50 грн", "150 грн"])
    await callback.message.answer(f"🎯 Бюджет: <b>{budget}</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")]]))

# --- Додаткові функції ---

@dp.message(F.text == "🎲 Випадкова рекомендація")
async def random_recs(message: Message):
    if not can_use_limit(message.from_user.id, "recs", DAILY_RECS_LIMIT): return await message.answer("Ліміт вичерпано 🎲")
    await message.answer("🔍 Шукаю цікаве місце…")
    p = get_random_places(1, excluded_ids=load_visited(message.from_user.id))
    if not p: return await message.reply("Не знайдено 😞")
    p = p[0]
    inc_limit(message.from_user.id, "recs")
    add_visited(message.from_user.id, [p["place_id"]])
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗺 Мапа", url=p["url"])]])
    await message.answer(f"<b>{p['name']}</b>\n{p['address']}", reply_markup=kb)

@dp.callback_query(F.data == "back_to_menu")
async def btm(callback: types.CallbackQuery):
    await callback.answer()
    await start_handler(callback.message)

@dp.message(F.text == "⬅ Назад")
async def back(message: Message): await start_handler(message)

@dp.message(F.text == "ℹ️ Як працює бот?")
async def how(message: Message): await message.answer("Обирай режим, а я побудую маршрут Одесою 🧭")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
