import asyncio
import logging
import os
import json
from datetime import datetime
from typing import Dict, Set, List, Optional

import pytz
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart

from places import (
    get_random_place_near,
    CENTER_LAT,
    CENTER_LON,
)

# --- Google Sheets інтеграція (gspread) ---
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSHEETS_AVAILABLE = True
except ImportError:
    GSHEETS_AVAILABLE = False


# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    # можеш залишити пустим і брати з env, але краще щоб не стартувало без токена
    raise RuntimeError("Missing BOT_TOKEN env var")

PUMB_DONATE_URL = os.getenv("PUMB_DONATE_URL", "https://mobile-app.pumb.ua/VDdaNY9UzYmaK4fj8").strip()

ODESSA_TZ = pytz.timezone("Europe/Kyiv")

WALK_RADIUS_METERS = int(os.getenv("WALK_RADIUS_METERS", "500"))
FALLBACK_RADIUS_METERS = int(os.getenv("FALLBACK_RADIUS_METERS", "700"))

# ЛІМІТИ: 3 → paywall, 6 → paywall, 9 → stop
DAILY_MAX_QUOTA = 9
PAYWALL_STEP = 3  # додаємо +3 кожного разу

GS_FEEDBACK_SHEET = os.getenv("GS_FEEDBACK_SHEET", "feedback")
GS_PLACE_REVIEWS_SHEET = os.getenv("GS_PLACE_REVIEWS_SHEET", "place_reviews")
GS_BOT_REVIEWS_SHEET = os.getenv("GS_BOT_REVIEWS_SHEET", "bot_reviews")


# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mvp")


# =========================
# BOT INIT
# =========================
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


# =========================
# STATE
# =========================
# user_id -> dict
walk_state: Dict[int, Dict] = {}
limits_state: Dict[int, Dict] = {}


# =========================
# UX COPY (1-в-1)
# =========================
TEXT_START_WALK = (
    "🎲 <b>Почнемо прогулянку?</b>\n\n"
    "Обери, звідки стартуємо:"
)

TEXT_AFTER_MAP_MENU = "Що робимо далі? 👇"

TEXT_FIRM_ROUTES_STUB = (
    "🧭 <b>Фірмові маршрути вже в роботі</b>\n\n"
    "Ми готуємо тематичні прогулянки\n"
    "та гастро-маршрути Одеси 💛\n\n"
    "Поки що ви можете підтримати проєкт"
)

TEXT_NEED_LOCATION = (
    "🧭 Щоб почати там, де ти зараз — надішли геолокацію.\n\n"
    "Натисни кнопку нижче 👇"
)

TEXT_SEARCHING = "🔍 Шукаю для тебе цікаве місце в Одесі…"
TEXT_NO_PLACE = "Не вдалося знайти локацію 😞 Спробуй ще раз трохи пізніше."

TEXT_PAYWALL = (
    "🎲 <b>Сьогодні ти вже відкрив 3 локації</b>\n\n"
    "Одеса — велика, але і прогулянки мають ліміти 😉\n\n"
    "Хочеш продовжити?"
)

TEXT_STOP_9 = (
    "💛 <b>Дякуємо за інтерес до Одеси Навмання</b>\n\n"
    "Сьогодні ти вже відкрив максимальну кількість локацій 🗺\n\n"
    "Ми спеціально обмежуємо прогулянки,\n"
    "щоб кожна з них залишалась цікавою 😉\n\n"
    "🌅 <b>Повернись завтра — буде ще краще</b>"
)

TEXT_REVIEW_PLACE_PROMPT = (
    "✍️ <b>Як тобі це місце?</b>\n\n"
    "Напиши кілька слів про свої враження.\n"
    "Якщо є фото — буде супер 📸\n\n"
    "Ти допомагаєш відкривати Одесу по-справжньому 💛"
)

TEXT_REVIEW_BOT_PROMPT = (
    "💬 <b>Нам дуже важлива твоя думка</b>\n\n"
    "Напиши, що тобі подобається\n"
    "або що варто покращити в боті 💛"
)


# =========================
# KEYBOARDS
# =========================
def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎲 Випадкова прогулянка")],
            [KeyboardButton(text="🧭 Фірмові маршрути")],
            [KeyboardButton(text="💛 Підтримати проєкт")],
        ],
        resize_keyboard=True,
    )


def start_walk_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📍 Почнемо в центрі Одеси", callback_data="walk_start:center")],
            [InlineKeyboardButton(text="🧭 Почнемо там, де я зараз", callback_data="walk_start:near_me")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")],
        ]
    )


def firm_routes_stub_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💛 Підтримати проєкт (від 10 грн)", url=PUMB_DONATE_URL)],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")],
        ]
    )


def request_location_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Надіслати геолокацію", request_location=True)],
            [KeyboardButton(text="⬅️ Назад в меню")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def place_actions_kb(place_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧭 Цікаво, відкрити на мапі", callback_data=f"walk_map:{place_id}")],
            [InlineKeyboardButton(text="👎 Не цікаво, далі", callback_data=f"walk_skip:{place_id}")],
        ]
    )


def after_map_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Наступна локація (500 м)", callback_data="walk_next")],
            [InlineKeyboardButton(text="✅ Завершити прогулянку", callback_data="walk_finish")],
            [InlineKeyboardButton(text="✍️ Залишити відгук по цьому місцю", callback_data="review_place_start")],
            [InlineKeyboardButton(text="✍️ Залишити відгук про цей БОТ", callback_data="review_bot_start")],
        ]
    )


def paywall_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💛 Підтримати проєкт (від 10 грн) → +3 локації", url=PUMB_DONATE_URL)],
            [InlineKeyboardButton(text="✅ Я підтримав — продовжити", callback_data="paywall_continue")],
            [InlineKeyboardButton(text="🌅 Продовжити завтра", callback_data="paywall_tomorrow")],
            [InlineKeyboardButton(text="⬅️ В головне меню", callback_data="back_to_menu")],
        ]
    )


def stop_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В головне меню", callback_data="back_to_menu")]
        ]
    )


def skip_photo_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📎 Пропустити фото", callback_data="review_place_skip_photo")],
            [InlineKeyboardButton(text="⬅️ В головне меню", callback_data="back_to_menu")],
        ]
    )


# =========================
# HELPERS: state
# =========================
def reset_walk_state(user_id: int):
    walk_state.pop(user_id, None)


def ensure_walk_state(user_id: int) -> Dict:
    st = walk_state.get(user_id)
    if not st:
        st = {
            "mode": None,  # center / near_me
            "awaiting_location": False,

            "start_lat": None,
            "start_lon": None,

            "anchor_lat": None,
            "anchor_lon": None,

            "excluded_ids": set(),  # type: Set[str]
            "last_place": None,     # dict
            "last_place_id": None,  # str
            "last_was_interesting": False,

            # reviews flow
            "awaiting_place_review_text": False,
            "awaiting_place_review_photo": False,
            "place_review_text": None,
            "place_review_photos": [],

            "awaiting_bot_review_text": False,
        }
        walk_state[user_id] = st
    return st


# =========================
# HELPERS: limits
# =========================
def get_today_key() -> str:
    # локального часу достатньо; UTC теж ок, головне стабільно
    return datetime.now(ODESSA_TZ).strftime("%Y-%m-%d")


def get_user_limits(user_id: int) -> Dict:
    today = get_today_key()
    state = limits_state.get(user_id)
    if not state or state.get("date") != today:
        state = {"date": today, "quota": 3, "used": 0}
        limits_state[user_id] = state
    return state


# =========================
# GOOGLE SHEETS HELPERS
# =========================
_gs_spread = None
_gs_ws_cache = {}


def _gs_get_spread():
    global _gs_spread
    if _gs_spread is not None:
        return _gs_spread

    if not GSHEETS_AVAILABLE:
        raise RuntimeError("gspread/google creds not available. Install gspread + google-auth.")

    creds_json = os.getenv("GSPREAD_CREDENTIALS_JSON")
    sheet_id = os.getenv("GSPREAD_SPREADSHEET_ID")
    if not creds_json or not sheet_id:
        raise RuntimeError("Missing GSPREAD_CREDENTIALS_JSON or GSPREAD_SPREADSHEET_ID")

    info = json.loads(creds_json)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(creds)
    _gs_spread = gc.open_by_key(sheet_id)
    return _gs_spread


def _gs_get_ws(name: str):
    if name in _gs_ws_cache:
        return _gs_ws_cache[name]
    sp = _gs_get_spread()
    try:
        ws = sp.worksheet(name)
    except Exception:
        ws = sp.add_worksheet(title=name, rows=2000, cols=30)
    _gs_ws_cache[name] = ws
    return ws


def _gs_ensure_header(ws, header: List[str]):
    existing = ws.row_values(1)
    if not existing:
        ws.update("A1", [header])


async def gs_append_row(sheet_name: str, row: List, header: Optional[List[str]] = None):
    def _do():
        ws = _gs_get_ws(sheet_name)
        if header:
            _gs_ensure_header(ws, header)
        ws.append_row(row, value_input_option="RAW")
    await asyncio.to_thread(_do)


def _tg_username(user: types.User) -> str:
    return user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()


async def log_feedback_action(action: str, user: types.User, place_id: str, maps_url: str | None, context: str = "walk"):
    ts = datetime.now(ODESSA_TZ).isoformat()
    row = [ts, str(user.id), _tg_username(user), place_id, maps_url or "", action, context]
    header = ["timestamp", "user_id", "user_name", "place_id", "maps_url", "action", "context"]
    try:
        await gs_append_row(GS_FEEDBACK_SHEET, row, header=header)
    except Exception as e:
        logger.warning(f"GSHEETS feedback write error: {e}")


async def log_place_review(user: types.User, place_id: str, maps_url: str, review_text: str, photo_file_ids: List[str], context: str = "walk"):
    ts = datetime.now(ODESSA_TZ).isoformat()
    row = [
        ts,
        str(user.id),
        _tg_username(user),
        place_id,
        maps_url,
        review_text,
        ";".join(photo_file_ids),
        context,
    ]
    header = ["timestamp", "user_id", "user_name", "place_id", "maps_url", "review_text", "photo_file_ids", "context"]
    try:
        await gs_append_row(GS_PLACE_REVIEWS_SHEET, row, header=header)
    except Exception as e:
        logger.warning(f"GSHEETS place_reviews write error: {e}")


async def log_bot_review(user: types.User, review_text: str, context: str = "menu"):
    ts = datetime.now(ODESSA_TZ).isoformat()
    row = [ts, str(user.id), _tg_username(user), review_text, context]
    header = ["timestamp", "user_id", "user_name", "review_text", "context"]
    try:
        await gs_append_row(GS_BOT_REVIEWS_SHEET, row, header=header)
    except Exception as e:
        logger.warning(f"GSHEETS bot_reviews write error: {e}")


# =========================
# HELPERS: places / rendering
# =========================
def build_place_caption(p: dict) -> str:
    caption = f"<b>{p.get('name','Без назви')}</b>\n"
    if p.get("rating"):
        caption += f"⭐ {p['rating']} ({p.get('reviews', 0)} відгуків)\n"
    addr = p.get("address", "")
    if addr:
        caption += addr
    return caption


async def send_place(chat_id: int, user: types.User, p: dict, place_id: str):
    # LOG: shown
    await log_feedback_action("shown", user, place_id, p.get("url"), context="walk")

    caption = build_place_caption(p)
    kb = place_actions_kb(place_id)

    if p.get("photo"):
        await bot.send_photo(chat_id, photo=p["photo"], caption=caption, reply_markup=kb)
    else:
        await bot.send_message(chat_id, caption, reply_markup=kb)


async def pick_and_show_next(chat_id: int, user: types.User):
    user_id = user.id
    st = ensure_walk_state(user_id)
    lim = get_user_limits(user_id)

    # paywall / stop BEFORE searching
    if lim["used"] >= lim["quota"]:
        if lim["quota"] >= DAILY_MAX_QUOTA:
            await bot.send_message(chat_id, TEXT_STOP_9, reply_markup=stop_kb())
            reset_walk_state(user_id)
            return
        await bot.send_message(chat_id, TEXT_PAYWALL, reply_markup=paywall_kb())
        return

    anchor_lat = st.get("anchor_lat")
    anchor_lon = st.get("anchor_lon")
    if anchor_lat is None or anchor_lon is None:
        anchor_lat, anchor_lon = CENTER_LAT, CENTER_LON
        st["anchor_lat"], st["anchor_lon"] = anchor_lat, anchor_lon

    excluded: Set[str] = st.get("excluded_ids") or set()

    p = get_random_place_near(
        lat=anchor_lat,
        lon=anchor_lon,
        radius=WALK_RADIUS_METERS,
        excluded_ids=excluded,
    )

    if not p:
        p = get_random_place_near(
            lat=anchor_lat,
            lon=anchor_lon,
            radius=FALLBACK_RADIUS_METERS,
            excluded_ids=excluded,
        )

    if not p:
        await bot.send_message(chat_id, TEXT_NO_PLACE, reply_markup=main_menu_kb())
        reset_walk_state(user_id)
        return

    place_id = p.get("place_id") or f"noid_{abs(hash(p.get('url','')))}"

    excluded.add(place_id)
    st["excluded_ids"] = excluded
    st["last_place"] = p
    st["last_place_id"] = place_id
    st["last_was_interesting"] = False

    await send_place(chat_id, user, p, place_id)

    lim["used"] += 1


# =========================
# REVIEWS HELPERS
# =========================
async def finalize_place_review(message: Message):
    user_id = message.from_user.id
    st = walk_state.get(user_id)
    if not st:
        return

    p = st.get("last_place") or {}
    place_id = st.get("last_place_id")
    maps_url = p.get("url") or ""
    review_text = (st.get("place_review_text") or "").strip()
    photos = st.get("place_review_photos") or []

    st["awaiting_place_review_photo"] = False
    st["place_review_photos"] = []

    if not place_id or not review_text:
        await message.answer("Не вдалося зберегти відгук 😞 Спробуй ще раз.")
        return

    await log_place_review(message.from_user, place_id, maps_url, review_text, photos, context="walk")
    await message.answer(
        "Дякуємо за відгук 💛 Він збережений і допоможе зробити прогулянки кращими.",
        reply_markup=after_map_kb(),
    )


# =========================
# HANDLERS: menu
# =========================
@dp.message(CommandStart())
async def cmd_start(message: Message):
    reset_walk_state(message.from_user.id)
    await message.answer(
        "Привіт 👋\n\n"
        "Цей бот допоможе відкрити Одесу несподівано.\n"
        "Крок за кроком, без маршрутів і поспіху 💛",
        reply_markup=main_menu_kb(),
    )


@dp.message(F.text == "🎲 Випадкова прогулянка")
async def start_random_walk(message: Message):
    await message.answer(TEXT_START_WALK, reply_markup=start_walk_kb())


@dp.message(F.text == "🧭 Фірмові маршрути")
async def firm_routes_stub(message: Message):
    await message.answer(TEXT_FIRM_ROUTES_STUB, reply_markup=firm_routes_stub_kb())


@dp.message(F.text == "💛 Підтримати проєкт")
async def donate_entry(message: Message):
    await message.answer(
        "Дякуємо за підтримку 💛",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💛 Підтримати проєкт (від 10 грн)", url=PUMB_DONATE_URL)]]
        ),
    )


@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    reset_walk_state(callback.from_user.id)
    await callback.answer()
    await callback.message.answer("Повертаємось в меню 👇", reply_markup=main_menu_kb())


@dp.message(F.text == "⬅️ Назад в меню")
async def back_to_menu_text(message: Message):
    reset_walk_state(message.from_user.id)
    await message.answer("Повертаємось в меню 👇", reply_markup=main_menu_kb())


# =========================
# WALK: start choice
# =========================
@dp.callback_query(F.data.startswith("walk_start:"))
async def walk_start_choice(callback: CallbackQuery):
    user_id = callback.from_user.id
    st = ensure_walk_state(user_id)

    choice = callback.data.split(":", 1)[1]
    await callback.answer()

    if choice == "center":
        st["mode"] = "center"
        st["awaiting_location"] = False
        st["start_lat"], st["start_lon"] = CENTER_LAT, CENTER_LON
        st["anchor_lat"], st["anchor_lon"] = CENTER_LAT, CENTER_LON
        st["excluded_ids"] = set()

        await callback.message.answer(TEXT_SEARCHING)
        await pick_and_show_next(callback.message.chat.id, callback.from_user)
        return

    if choice == "near_me":
        st["mode"] = "near_me"
        st["awaiting_location"] = True
        await callback.message.answer(TEXT_NEED_LOCATION, reply_markup=request_location_kb())
        return


@dp.message(F.location)
async def got_location(message: Message):
    user_id = message.from_user.id
    st = ensure_walk_state(user_id)

    if not st.get("awaiting_location"):
        return

    st["awaiting_location"] = False
    lat = message.location.latitude
    lon = message.location.longitude

    st["start_lat"], st["start_lon"] = lat, lon
    st["anchor_lat"], st["anchor_lon"] = lat, lon
    st["excluded_ids"] = set()

    await message.answer(TEXT_SEARCHING, reply_markup=main_menu_kb())
    await pick_and_show_next(message.chat.id, message.from_user)


# =========================
# WALK: actions under place
# =========================
@dp.callback_query(F.data.startswith("walk_skip:"))
async def walk_skip(callback: CallbackQuery):
    user_id = callback.from_user.id
    st = ensure_walk_state(user_id)
    await callback.answer()

    place_id = callback.data.split(":", 1)[1]
    last_id = st.get("last_place_id")
    if not last_id or place_id != last_id:
        return

    # якщо не натискав 🧭 → not_interesting
    if not st.get("last_was_interesting"):
        p = st.get("last_place") or {}
        await log_feedback_action("not_interesting", callback.from_user, place_id, p.get("url"), context="walk")

    await pick_and_show_next(callback.message.chat.id, callback.from_user)


@dp.callback_query(F.data.startswith("walk_map:"))
async def walk_map(callback: CallbackQuery):
    user_id = callback.from_user.id
    st = ensure_walk_state(user_id)
    await callback.answer()

    place_id = callback.data.split(":", 1)[1]
    last_id = st.get("last_place_id")
    if not last_id or place_id != last_id:
        return

    p = st.get("last_place") or {}
    maps_url = p.get("url") or ""

    await log_feedback_action("interesting", callback.from_user, place_id, maps_url, context="walk")

    # anchor = остання цікава
    if p.get("lat") is not None and p.get("lon") is not None:
        st["anchor_lat"], st["anchor_lon"] = p["lat"], p["lon"]

    st["last_was_interesting"] = True

    # 1) лінк
    await callback.message.answer(f"🧭 <b>Відкрити на мапі:</b>\n{maps_url}")
    # 2) меню далі
    await callback.message.answer(TEXT_AFTER_MAP_MENU, reply_markup=after_map_kb())


@dp.callback_query(F.data == "walk_next")
async def walk_next(callback: CallbackQuery):
    await callback.answer()
    await pick_and_show_next(callback.message.chat.id, callback.from_user)


@dp.callback_query(F.data == "walk_finish")
async def walk_finish(callback: CallbackQuery):
    reset_walk_state(callback.from_user.id)
    await callback.answer()
    await callback.message.answer("✅ Прогулянку завершено. Повертаємось в меню 👇", reply_markup=main_menu_kb())


# =========================
# PAYWALL
# =========================
@dp.callback_query(F.data == "paywall_continue")
async def paywall_continue(callback: CallbackQuery):
    user_id = callback.from_user.id
    lim = get_user_limits(user_id)
    await callback.answer()

    # +3, але не більше 9
    lim["quota"] = min(DAILY_MAX_QUOTA, lim["quota"] + PAYWALL_STEP)

    await callback.message.answer("💛 Дякуємо за підтримку! Продовжуємо прогулянку 👇")
    await pick_and_show_next(callback.message.chat.id, callback.from_user)


@dp.callback_query(F.data == "paywall_tomorrow")
async def paywall_tomorrow(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🌅 Домовились! Повернись завтра — буде ще краще 💛",
        reply_markup=main_menu_kb(),
    )


# =========================
# REVIEWS: place & bot
# =========================
@dp.callback_query(F.data == "review_place_start")
async def review_place_start(callback: CallbackQuery):
    user_id = callback.from_user.id
    st = ensure_walk_state(user_id)
    await callback.answer()

    p = st.get("last_place")
    place_id = st.get("last_place_id")
    if not p or not place_id:
        await callback.message.answer("Не бачу активної локації для відгуку 😞")
        return

    st["awaiting_place_review_text"] = True
    st["awaiting_place_review_photo"] = False
    st["place_review_text"] = None
    st["place_review_photos"] = []

    await callback.message.answer(TEXT_REVIEW_PLACE_PROMPT)


@dp.callback_query(F.data == "review_bot_start")
async def review_bot_start(callback: CallbackQuery):
    user_id = callback.from_user.id
    st = ensure_walk_state(user_id)
    await callback.answer()

    st["awaiting_bot_review_text"] = True
    await callback.message.answer(TEXT_REVIEW_BOT_PROMPT)


@dp.callback_query(F.data == "review_place_skip_photo")
async def review_place_skip_photo(callback: CallbackQuery):
    await callback.answer()
    msg = callback.message
    await finalize_place_review(msg)


@dp.message(F.photo)
async def catch_place_review_photo(message: Message):
    user_id = message.from_user.id
    st = walk_state.get(user_id)
    if not st or not st.get("awaiting_place_review_photo"):
        return

    file_id = message.photo[-1].file_id
    photos = st.get("place_review_photos") or []
    photos.append(file_id)
    st["place_review_photos"] = photos

    # обмежимо 5 фото
    if len(photos) >= 5:
        await message.answer("Ок, фото достатньо ✅ Зберігаю відгук…")
        await finalize_place_review(message)
    else:
        await message.answer("Фото додано ✅ Можеш надіслати ще або натиснути «Пропустити фото».", reply_markup=skip_photo_kb())


@dp.message()
async def catch_reviews_text(message: Message):
    """
    Один handler на текст відгуків:
    - якщо чекаємо відгук по місцю -> приймаємо текст, потім чекаємо фото або skip
    - якщо чекаємо відгук про бота -> приймаємо текст і пишемо в Sheets
    """
    user_id = message.from_user.id
    st = walk_state.get(user_id)
    if not st:
        return

    # PLACE REVIEW TEXT
    if st.get("awaiting_place_review_text"):
        if not message.text:
            await message.answer("Надішли, будь ласка, текстом 🙂")
            return

        st["awaiting_place_review_text"] = False
        st["awaiting_place_review_photo"] = True
        st["place_review_text"] = message.text.strip()
        st["place_review_photos"] = []

        await message.answer(
            "Дякую! Якщо маєш фото — надішли зараз 📸\n"
            "Або натисни «Пропустити фото».",
            reply_markup=skip_photo_kb(),
        )
        return

    # BOT REVIEW TEXT
    if st.get("awaiting_bot_review_text"):
        if not message.text:
            await message.answer("Надішли, будь ласка, текстом 🙂")
            return

        st["awaiting_bot_review_text"] = False
        review_text = message.text.strip()

        await log_bot_review(message.from_user, review_text, context=st.get("mode") or "menu")
        await message.answer("Дякуємо! Твій відгук реально допоможе зробити бот кращим 🙌", reply_markup=main_menu_kb())
        return

    # якщо це не review-flow — нічого не робимо
    return


# =========================
# RUN
# =========================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
