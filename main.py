from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import asyncio
import os

from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Стартове повідомлення з фото
@dp.message(F.text == "/start")
async def start_handler(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="Що це таке?")
    kb.button(text="Як це працює?")
    kb.button(text="Замовити екскурсію")
    kb.button(text="Варіанти маршрутів")
    kb.button(text="Відгуки")
    kb.adjust(2)

    photo = FSInputFile("odesa_logo.jpg")
    await message.answer_photo(
        photo=photo,
        caption=(
            "<b>Привіт!</b> Це <i>Одесса навмання</i> — твоя несподівана, але продумана екскурсія містом.\n\n"
            "Ти не обираєш маршрут — маршрут обирає тебе.\n\n"
            "Я проведу тебе в ті місця Одеси, які ти міг роками проходити повз. "
            "Випадкові, емоційні, живі. Але з одеським блогером.\n\n"
            "Обери нижче, з чого хочеш почати 👇"
        ),
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

# Інформаційні кнопки
@dp.message(F.text == "Що це таке?")
async def what_is_it(message: Message):
    await message.answer(
        "“Одесса навмання” — це Telegram-бот, який обирає маршрут по Одесі замість тебе. "
        "Ти натискаєш кнопку — і отримуєш маршрут з 3, 5 або 10 локацій.\n\n"
        "Все, що треба — просто вирушити!"
    )

@dp.message(F.text == "Як це працює?")
async def how_it_works(message: Message):
    await message.answer(
        "1️⃣ Обираєш кількість локацій\n"
        "2️⃣ Отримуєш маршрут (першу і останню ми обираємо спеціально)\n"
        "3️⃣ Йдеш гуляти, досліджуєш, фотографуєш\n"
        "4️⃣ Можеш поділитися враженнями тут ✍️"
    )

@dp.message(F.text == "Варіанти маршрутів")
async def routes_options(message: Message):
    await message.answer(
        "Можна обрати маршрут на:\n\n"
        "🔸 3 локації — коротка прогулянка\n"
        "🔸 5 локацій — ідеально на пів дня\n"
        "🔸 10 локацій — справжня пригода!\n\n"
        "Почати маршрут — натисни /start і обери формат 😉"
    )

@dp.message(F.text == "Відгуки")
async def reviews(message: Message):
    await message.answer(
        "🔹 «Думав, що знаю Одесу — але цей бот показав іншу!»\n"
        "🔹 «Пройшли маршрут з друзями — було цікаво і незвично!»\n"
        "🔹 «Кайф! Дуже атмосферно. Ще б на райончики 😏»\n\n"
        "Хочеш залишити свій відгук? Напиши його у відповідь на це повідомлення ✍️"
    )

# Кнопка "Замовити екскурсію"
@dp.message(F.text == "Замовити екскурсію")
async def order_tour(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="З гідом")
    kb.button(text="Самостійно")
    kb.button(text="⬅ Назад")
    kb.adjust(2)

    await message.answer(
        "<b>Обери формат своєї екскурсії:</b>\n\n"
        "👥 <b>З гідом</b> — реальна екскурсія з одеським блогером\n"
        "🧭 <b>Самостійно</b> — маршрут з точками та описом у Google Maps",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

# З гідом
@dp.message(F.text == "З гідом")
async def with_guide(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="Маршрут з 3 локації")
    kb.button(text="Маршрут з 5 локацій")
    kb.button(text="Маршрут з 10 локацій")
    kb.button(text="⬅ Назад")
    kb.adjust(2)

    await message.answer(
        "<b>Щоб замовити реальну екскурсію з блогером</b> — обери формат:\n\n"
        "🚶‍♂️ <b>Маршрут з 3 локації</b>\n"
        "30–50 хвилин • 3–5 осіб • 4000 грн\n\n"
        "🚶‍♂️ <b>Маршрут з 5 локацій</b>\n"
        "2–3 години • 3–5 осіб • 6000 грн\n\n"
        "🚶‍♂️ <b>Маршрут з 10 локацій</b>\n"
        "Повноцінна пригода містом • 3–5 осіб • 15000 грн",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

# Самостійно
@dp.message(F.text == "Самостійно")
async def self_guided(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="Маршрут з 3 локації (149 грн)")
    kb.button(text="Маршрут з 5 локацій (249 грн)")
    kb.button(text="Маршрут з 10 локацій (449 грн)")
    kb.button(text="⬅ Назад")
    kb.adjust(1)

    await message.answer(
        "<b>Варіанти самостійних маршрутів:</b>\n\n"
        "📍 <b>Маршрут з 3 локації</b> — 149 грн\n"
        "📍 <b>Маршрут з 5 локацій</b> — 249 грн\n"
        "📍 <b>Маршрут з 10 локацій</b> — 449 грн\n\n"
        "Після оплати ви миттєво отримаєте посилання на маршрут у Google Maps з описом усіх локацій 💌",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )
@dp.message(F.text == "⬅ Назад")
async def go_back(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="Що це таке?")
    kb.button(text="Як це працює?")
    kb.button(text="Замовити екскурсію")
    kb.button(text="Варіанти маршрутів")
    kb.button(text="Відгуки")
    kb.adjust(2)

    await message.answer(
        "⬅ Повернув тебе в головне меню. Обери, з чого хочеш почати 👇",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
