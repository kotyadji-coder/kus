import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    BotCommand,
    CallbackQuery, Message,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
    WebAppInfo,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

from database import init_db, add_user, get_user, increment_step, get_users_at_step, log_support
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
    user_id = message.from_user.id

    # Проверяем deep link: /start order_123
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("order_"):
        try:
            order_id = int(args[1].replace("order_", ""))
            delivered = await _deliver_order_by_id(user_id, order_id)
            if delivered:
                return
        except (ValueError, Exception) as e:
            log.error(f"Deep link delivery error: {e}")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🥩 Натуралка", callback_data="track:natural"),
            InlineKeyboardButton(text="🍖 Сухой корм", callback_data="track:dry"),
        ]
    ])
    await message.answer(WELCOME.format(first_name=first_name), reply_markup=keyboard)
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
        "Результат придёт сюда обычно в течение 2 часов, но не более 3 рабочих дней.",
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
        await log_support(client_id, "", "", "out", message.text)
        await message.reply("Отправлено клиенту.")
    except Exception as e:
        await message.reply(f"Ошибка отправки: {e}")


# ─── Все остальные сообщения — пересылка в поддержку ─────────────────────────

@dp.message()
async def user_message(message: Message):
    """Любое текстовое сообщение — fallback."""
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

    name = user.first_name or ""
    uname = user.username or ""
    username_display = f" (@{uname})" if uname else ""
    admin_text = (
        f"Вопрос от {name}{username_display}\n"
        f"ID: {user_id}\n"
        f"────────────\n"
        f"{message.text}"
    )

    # Логируем входящее сообщение
    await log_support(user_id, name, uname, "in", message.text)

    sent = await bot.send_message(ADMIN_ID, admin_text)
    _support_map[sent.message_id] = user_id

    await message.answer(
        "Вопрос отправлен. Ожидайте ответа — обычно в течение 15 минут.",
        reply_markup=main_menu_keyboard(),
    )


# ─── Доставка PDF по deep link ────────────────────────────────────────────────

async def _deliver_order_by_id(telegram_user_id: int, order_id: int) -> bool:
    """Привязывает telegram_user_id к заказу и отправляет PDF, если готов."""
    from models import get_order, update_order
    import aiohttp

    order = await get_order(order_id)
    if not order:
        return False

    # Привязываем Telegram ID к заказу
    await update_order(order_id, telegram_user_id=telegram_user_id)

    # Если PDF ещё не готов — привязка сохранится, worker доставит позже
    pdf_path = order.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path) or order["status"] != "done":
        await bot.send_message(
            telegram_user_id,
            f"Готовим рацион для {order['dog_name']}! Как только будет готов — отправлю PDF сюда.",
            reply_markup=main_menu_keyboard(),
        )
        return True

    # PDF готов — отправляем
    diet_type = order["diet_type"]
    diet_label = "натуральный рацион" if diet_type in ("barf", "cooked") else "подбор сухого корма"
    caption = (
        f"Вот ваш персональный {diet_label} для {order['dog_name']}!\n\n"
        f"У вас есть 7 дней поддержки — задавайте любые вопросы прямо в этот чат."
    )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    async with aiohttp.ClientSession() as session:
        with open(pdf_path, "rb") as f:
            form = aiohttp.FormData()
            form.add_field("chat_id", str(telegram_user_id))
            form.add_field("caption", caption)
            form.add_field("document", f, filename=os.path.basename(pdf_path))
            async with session.post(url, data=form) as resp:
                if resp.status == 200:
                    log.info(f"Delivered order #{order_id} to {telegram_user_id} via deep link")
                    return True
                else:
                    text = await resp.text()
                    log.error(f"Failed to deliver order #{order_id}: {text}")
                    return False


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

            # Последнее сообщение — продающее, добавляем кнопку
            reply_markup = None
            if step == len(msgs) - 1:
                price = "1 390 ₽" if track == "natural" else "990 ₽"
                reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=f"Подобрать рацион — {price}",
                        url=BASE_URL,
                    )],
                ])

            try:
                await bot.send_message(user["user_id"], text, reply_markup=reply_markup)
                await increment_step(user["user_id"])
                log.info(f"Sent step {step + 1} to user {user['user_id']} ({track})")
            except Exception as e:
                log.error(f"Failed to send to {user['user_id']}: {e}")


# ─── Внутренний HTTP API (для worker → бот) ──────────────────────────────────


# ─── Очередь доставки: бот проверяет готовые заказы и отправляет PDF ──────────

async def _delivery_loop():
    """Периодически проверяет заказы со статусом done + telegram_user_id, отправляет PDF."""
    from models import get_order, update_order
    import aiosqlite
    DB_PATH = os.path.join(os.path.dirname(__file__), "kus.db")

    while True:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                # Заказы: done, есть telegram_user_id, ещё не доставлены (delivered=0)
                async with db.execute(
                    "SELECT * FROM orders WHERE status='done' AND telegram_user_id IS NOT NULL AND telegram_user_id > 0 AND COALESCE(delivered, 0) = 0 AND pdf_path IS NOT NULL"
                ) as cursor:
                    rows = await cursor.fetchall()

            for row in rows:
                order = dict(row)
                tg_id = order["telegram_user_id"]
                pdf_path = order["pdf_path"]
                if not os.path.exists(pdf_path):
                    continue

                diet_type = order["diet_type"]
                diet_label = "натуральный рацион" if diet_type in ("barf", "cooked") else "подбор сухого корма"
                caption = (
                    f"Готово! Вот ваш персональный {diet_label} для {order['dog_name']}.\n\n"
                    f"У вас есть 7 дней поддержки — задавайте любые вопросы прямо в этот чат."
                )

                try:
                    from aiogram.types import FSInputFile
                    doc = FSInputFile(pdf_path)
                    await bot.send_document(tg_id, doc, caption=caption)
                    await update_order(order["id"], delivered=1)
                    log.info(f"Delivery loop: sent order #{order['id']} to {tg_id}")
                except Exception as e:
                    log.error(f"Delivery loop: failed order #{order['id']}: {e}")

            # Уведомления админу о новых заказах
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM orders WHERE status='done' AND COALESCE(admin_notified, 0) = 0"
                ) as cursor:
                    rows = await cursor.fetchall()

            for row in rows:
                order = dict(row)
                diet_label = "Натуралка" if order["diet_type"] in ("barf", "cooked") else "Сухой корм"
                text = (
                    f"Новый заказ выполнен!\n\n"
                    f"#{order['id']} | {diet_label}\n"
                    f"Собака: {order['dog_name']} ({order['breed']})\n"
                    f"Клиент: {order['client_name']}\n"
                    f"Телефон: {order['phone_or_telegram']}\n"
                    f"Email: {order.get('email', '')}\n"
                    f"Сумма: {order.get('amount', '?')} руб."
                )
                try:
                    await bot.send_message(ADMIN_ID, text)
                    await update_order(order["id"], admin_notified=1)
                    log.info(f"Delivery loop: admin notified about order #{order['id']}")
                except Exception as e:
                    log.error(f"Delivery loop: admin notify failed: {e}")

        except Exception as e:
            log.error(f"Delivery loop error: {e}")

        await asyncio.sleep(10)  # Проверяем каждые 10 секунд


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

    await bot.set_my_commands([
        BotCommand(command="start", description="Начать / Главное меню"),
    ])

    # Добавляем колонки delivered/admin_notified если их нет
    import aiosqlite
    DB_PATH = os.path.join(os.path.dirname(__file__), "kus.db")
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("ALTER TABLE orders ADD COLUMN delivered INTEGER DEFAULT 0")
            await db.commit()
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE orders ADD COLUMN admin_notified INTEGER DEFAULT 0")
            await db.commit()
        except Exception:
            pass

    # Запускаем цикл доставки PDF через Telegram
    asyncio.create_task(_delivery_loop())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
