import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

from database import init_db, add_user, get_user, increment_step, get_users_at_step
from messages import (
    WELCOME, TRUST, NATURAL_PRAISE, NATURAL, DRY_PRAISE, DRY,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
# Интервал между сообщениями курса (в часах). По умолчанию 24 часа.
MESSAGE_INTERVAL_HOURS = int(os.getenv("MESSAGE_INTERVAL_HOURS", "24"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


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


# ─── Выбор трека ──────────────────────────────────────────────────────────────

@dp.callback_query(F.data.startswith("track:"))
async def choose_track(callback: CallbackQuery):
    track = callback.data.split(":")[1]  # "natural" или "dry"
    user_id = callback.from_user.id
    first_name = callback.from_user.first_name or ""

    await callback.answer()

    # Сохраняем пользователя
    await add_user(user_id, first_name, track)

    # 1. Сообщение «Почему нам можно доверять»
    await bot.send_message(user_id, TRUST)

    # Небольшая пауза между сообщениями
    await asyncio.sleep(2)

    # 2. Хвалим за выбор
    praise = NATURAL_PRAISE if track == "natural" else DRY_PRAISE
    await bot.send_message(user_id, praise)

    await asyncio.sleep(3)

    # 3. Первое сообщение курса — сразу
    messages = NATURAL if track == "natural" else DRY
    text = messages[0].format(first_name=first_name)
    await bot.send_message(user_id, text)

    # Инкремент шага: 0 → 1 (первое сообщение отправлено)
    await increment_step(user_id)


# ─── Планировщик рассылки ────────────────────────────────────────────────────

async def send_scheduled_messages():
    """Отправляет следующее сообщение курса всем пользователям, которым пора."""
    # Шаги 1-4 → сообщения с индексами 1-4 (0-е уже отправлено сразу)
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
