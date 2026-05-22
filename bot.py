import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
    WebAppInfo,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

from database import init_db, add_user, get_user, increment_step, get_users_at_step
from messages import (
    WELCOME, TRUST, NATURAL_PRAISE, NATURAL, DRY_PRAISE, DRY,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "856877325"))
BASE_URL = os.getenv("BASE_URL", "https://kus.dogfine.ru")
MESSAGE_INTERVAL_HOURS = int(os.getenv("MESSAGE_INTERVAL_HOURS", "24"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище: user_id клиента → message_id последнего пересланного сообщения админу
# Нужно для того, чтобы админ мог ответить реплаем
_support_map: dict[int, int] = {}  # admin_message_id → client_user_id


# ─── Главное меню (persistent keyboard) ──────────────────────────────────────

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Подобрать рацион"), KeyboardButton(text="Помощь")],
        ],
        resize_keyboard=True,
    )


# ─── /start ───────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: Message):
    first_name = message.from_user.first_name or ""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🥩 Натуралка", callback_data="track:natural"),
            InlineKeyboardButton(text="🍖 Сухой корм", callback_data="track:dry"),
        ]
    ])
    await message.answer(WELCOME.format(first_name=first_name), reply_markup=keyboard)
    # Показываем persistent-меню
    await message.answer("Выберите действие:", reply_markup=main_menu_keyboard())


# ─── Кнопка «Подобрать рацион» ───────────────────────────────────────────────

@dp.message(F.text == "Подобрать рацион")
async def btn_order(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Открыть сайт",
            url=BASE_URL,
        )],
    ])
    await message.answer(
        "На сайте вы можете узнать подробности и оформить подбор рациона — "
        "сухого корма или натуралки.\n\n"
        "Результат придёт сюда в течение 2 часов после оплаты.",
        reply_markup=keyboard,
    )


# ─── Кнопка «Помощь» ─────────────────────────────────────────────────────────

@dp.message(F.text == "Помощь")
async def btn_help(message: Message):
    await message.answer(
        "Напишите ваш вопрос прямо сюда — я передам его специалисту. "
        "Обычно отвечаем в течение 15 минут в рабочее время (10:00–20:00)."
    )
    # Ставим флаг, что следующее сообщение — вопрос в поддержку
    await _mark_waiting_support(message.from_user.id)


# Хранилище пользователей, ожидающих ответа поддержки
_waiting_support: set[int] = set()


async def _mark_waiting_support(user_id: int):
    _waiting_support.add(user_id)


# ─── Выбор трека ──────────────────────────────────────────────────────────────

@dp.callback_query(F.data.startswith("track:"))
async def choose_track(callback: CallbackQuery):
    track = callback.data.split(":")[1]
    user_id = callback.from_user.id
    first_name = callback.from_user.first_name or ""

    await callback.answer()

    await add_user(user_id, first_name, track)

    await bot.send_message(user_id, TRUST)
    await asyncio.sleep(2)

    praise = NATURAL_PRAISE if track == "natural" else DRY_PRAISE
    await bot.send_message(user_id, praise)
    await asyncio.sleep(3)

    messages = NATURAL if track == "natural" else DRY
    text = messages[0].format(first_name=first_name)
    await bot.send_message(user_id, text)

    await increment_step(user_id)


# ─── Ответ админа (реплай на пересланное сообщение) ──────────────────────────

@dp.message(F.chat.id == ADMIN_ID, F.reply_to_message)
async def admin_reply(message: Message):
    """Админ отвечает реплаем на пересланное сообщение — бот отправляет ответ клиенту."""
    replied_msg_id = message.reply_to_message.message_id
    client_id = _support_map.get(replied_msg_id)

    if not client_id:
        await message.reply("Не могу определить, кому ответить. Возможно, сообщение устарело.")
        return

    try:
        await bot.send_message(client_id, message.text)
        await message.reply("Отправлено клиенту.")
    except Exception as e:
        await message.reply(f"Ошибка отправки: {e}")


# ─── Все остальные сообщения — пересылка в поддержку ─────────────────────────

@dp.message(F.chat.id != ADMIN_ID)
async def user_message(message: Message):
    """Любое текстовое сообщение от пользователя пересылается админу."""
    user = message.from_user
    user_id = user.id

    # Если пользователь не в режиме поддержки и не ожидает — игнорируем
    # (чтобы не пересылать случайные сообщения)
    if user_id not in _waiting_support:
        await message.answer(
            "Я — бот для подбора рациона. Используйте кнопки меню внизу.",
            reply_markup=main_menu_keyboard(),
        )
        return

    _waiting_support.discard(user_id)

    # Формируем сообщение для админа (БЕЗ пересылки — чтобы не светить данные)
    name = user.first_name or ""
    username = f" (@{user.username})" if user.username else ""
    admin_text = (
        f"Вопрос от {name}{username}\n"
        f"ID: {user_id}\n"
        f"────────────\n"
        f"{message.text}"
    )

    sent = await bot.send_message(ADMIN_ID, admin_text)
    # Сохраняем связь: message_id у админа → user_id клиента
    _support_map[sent.message_id] = user_id

    await message.answer(
        "Вопрос отправлен. Ожидайте ответа — обычно в течение 15 минут.",
        reply_markup=main_menu_keyboard(),
    )


# ─── Планировщик рассылки ────────────────────────────────────────────────────

async def send_scheduled_messages():
    for step in range(1, 5):
        users = await get_users_at_step(step)
        messages_map = {"natural": NATURAL, "dry": DRY}

        for user in users:
            track = user["track"]
            msgs = messages_map.get(track)
            if not msgs or step >= len(msgs):
                continue

            first_name = user["first_name"] or ""
            text = msgs[step].format(first_name=first_name)

            try:
                await bot.send_message(user["user_id"], text)
                await increment_step(user["user_id"])
                log.info(f"Sent step {step + 1} to user {user['user_id']} ({track})")
            except Exception as e:
                log.error(f"Failed to send to {user['user_id']}: {e}")


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    await init_db()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_scheduled_messages,
        trigger=IntervalTrigger(hours=MESSAGE_INTERVAL_HOURS),
        id="course_sender",
        replace_existing=True,
    )
    scheduler.start()
    log.info(f"Scheduler started. Interval: {MESSAGE_INTERVAL_HOURS}h")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
