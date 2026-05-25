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

from aiohttp import web

async def _tg_request(method: str, data: dict = None, files: dict = None):
    """Send request to Telegram API reusing bot's aiohttp connector."""
    import aiohttp
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    # Reuse bot's connector to keep TCP connection alive
    connector = bot.session._session.connector if hasattr(bot.session, '_session') else None
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(connector=connector, connector_owner=False, timeout=timeout) as session:
        if files:
            form_data = aiohttp.FormData()
            for k, v in (data or {}).items():
                form_data.add_field(k, str(v))
            for k, v in files.items():
                form_data.add_field(k, open(v, 'rb'), filename=os.path.basename(v))
            async with session.post(url, data=form_data) as resp:
                return await resp.json()
        else:
            async with session.post(url, json=data) as resp:
                return await resp.json()


async def _handle_send_document(request: web.Request):
    """Worker вызывает POST /send_document с chat_id, file_path, caption."""
    try:
        data = await request.json()
        chat_id = int(data["chat_id"])
        file_path = data["file_path"]
        caption = data.get("caption", "")

        result = await _tg_request("sendDocument",
            data={"chat_id": chat_id, "caption": caption},
            files={"document": file_path})
        if result.get("ok"):
            log.info(f"Internal API: sent {file_path} to {chat_id}")
            return web.json_response({"ok": True})
        else:
            raise Exception(str(result))
    except Exception as e:
        log.error(f"Internal API error: {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=500)


async def _handle_send_message(request: web.Request):
    """Worker вызывает POST /send_message с chat_id, text."""
    try:
        data = await request.json()
        chat_id = int(data["chat_id"])
        text = data["text"]

        result = await _tg_request("sendMessage", data={"chat_id": chat_id, "text": text})
        if result.get("ok"):
            log.info(f"Internal API: sent message to {chat_id}")
            return web.json_response({"ok": True})
        else:
            raise Exception(str(result))
    except Exception as e:
        log.error(f"Internal API send_message error: {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=500)


async def _start_internal_api():
    app = web.Application()
    app.router.add_post("/send_document", _handle_send_document)
    app.router.add_post("/send_message", _handle_send_message)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8907)
    await site.start()
    log.info("Internal API started on 127.0.0.1:8907")


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

    # Запускаем внутренний API для отправки PDF из worker
    await _start_internal_api()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
