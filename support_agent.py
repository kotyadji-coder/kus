"""
Агент поддержки клиентов: 3 раза в день отвечает на вопросы через Claude CLI.
Запускается systemd timer'ом (09:00, 14:00, 20:00 МСК = 06:00, 11:00, 17:00 UTC).

Использует подписку Claude Code — без API-ключа, через `claude -p`.
"""

import json
import logging
import os
import re
import sqlite3
import subprocess
import urllib.request
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DRY_RUN = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_BOT = os.path.join(BASE_DIR, "bot.db")
DB_KUS = os.path.join(BASE_DIR, "kus.db")


# ─── БД: чтение ───────────────────────────────────────────────────────────────

def get_pending_users() -> list[int]:
    """user_id'ы с неотвеченными входящими сообщениями."""
    with sqlite3.connect(DB_BOT) as con:
        con.row_factory = sqlite3.Row
        return [
            r["user_id"]
            for r in con.execute(
                "SELECT DISTINCT user_id FROM support_log "
                "WHERE direction='in' AND answered=0"
            )
        ]


def get_pending_messages(user_id: int) -> list[dict]:
    with sqlite3.connect(DB_BOT) as con:
        con.row_factory = sqlite3.Row
        return [
            dict(r)
            for r in con.execute(
                "SELECT message, created_at FROM support_log "
                "WHERE user_id=? AND direction='in' AND answered=0 ORDER BY created_at",
                (user_id,),
            )
        ]


def get_support_history(user_id: int, limit: int = 10) -> list[dict]:
    """Последние отвеченные сообщения диалога — для контекста."""
    with sqlite3.connect(DB_BOT) as con:
        con.row_factory = sqlite3.Row
        rows = list(con.execute(
            "SELECT direction, message FROM support_log "
            "WHERE user_id=? AND answered=1 ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ))
        return list(reversed([dict(r) for r in rows]))


def get_order_for_user(telegram_user_id: int) -> dict | None:
    """Последний выполненный заказ пользователя."""
    with sqlite3.connect(DB_KUS) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM orders WHERE telegram_user_id=? AND status='done' "
            "ORDER BY created_at DESC LIMIT 1",
            (telegram_user_id,),
        ).fetchone()
        return dict(row) if row else None


# ─── БД: запись ───────────────────────────────────────────────────────────────

def mark_answered(user_id: int):
    with sqlite3.connect(DB_BOT) as con:
        con.execute(
            "UPDATE support_log SET answered=1 "
            "WHERE user_id=? AND direction='in' AND answered=0",
            (user_id,),
        )
        con.commit()


def log_outgoing(user_id: int, message: str):
    with sqlite3.connect(DB_BOT) as con:
        con.execute(
            "INSERT INTO support_log (user_id, user_name, username, direction, message, answered, is_ai) "
            "VALUES (?, '', '', 'out', ?, 1, 1)",
            (user_id, message),
        )
        con.commit()


# ─── Форматирование промпта ────────────────────────────────────────────────────

def _age_str(months: int) -> str:
    if months < 12:
        return f"{months} мес."
    y, m = divmod(months, 12)
    return f"{y} г. {m} мес." if m else f"{y} г."


_DIET_LABELS = {
    "barf": "сырая натуралка (BARF)",
    "cooked": "варёная натуралка",
    "dry": "сухой корм",
    "barf_and_dry": "смешанный (BARF + сухой корм)",
    "cooked_and_dry": "смешанный (варёный + сухой корм)",
}
_CONDITION_LABELS = {
    "thin": "худой (недовес)", "athletic": "спортивный (норма)",
    "chubby": "лёгкий перевес", "obese": "ожирение",
}
_ACTIVITY_LABELS = {
    "lazy": "малоактивный", "moderate": "умеренная активность",
    "high": "высокая активность", "puppy": "щенок",
}


def build_prompt(order: dict, pending: list[dict], history: list[dict]) -> str:
    dog = order["dog_name"]
    sex = "кобель" if order["sex"] == "male" else "сука"
    neutered = "кастрирован" if order["neutered"] else "не кастрирован"

    history_lines = []
    for msg in history:
        role = "Клиент" if msg["direction"] == "in" else "Анастасия"
        history_lines.append(f"{role}: {msg['message']}")
    history_text = "\n".join(history_lines) if history_lines else "(начало переписки)"

    questions = "\n".join(f"Клиент: {m['message']}" for m in pending)

    return f"""Ты Анастасия — нутрициолог по питанию собак сервиса Doggi. Ты составила персональный рацион для собаки клиента.

ПРОФИЛЬ СОБАКИ:
Имя: {dog}
Порода: {order['breed']}, {_age_str(order['age_months'])}, {sex}, {neutered}
Вес: {order['weight_kg']} кг, кондиция: {_CONDITION_LABELS.get(order['condition'], order['condition'])}
Активность: {_ACTIVITY_LABELS.get(order['activity'], order['activity'])}
Тип рациона: {_DIET_LABELS.get(order['diet_type'], order['diet_type'])}
Диагнозы/особенности: {order.get('diagnoses') or 'нет'}
Стоп-продукты: {order.get('stop_products') or 'нет'}

ИСТОРИЯ ПЕРЕПИСКИ (для контекста):
{history_text}

НОВЫЕ ВОПРОСЫ КЛИЕНТА:
{questions}

Ответь тепло и профессионально, как живой специалист-нутрициолог. Обращайся к собаке по имени ({dog}) где уместно. Ответь на все вопросы по существу. 2–4 абзаца, без воды. Не упоминай что ты ИИ."""


# ─── Claude CLI ───────────────────────────────────────────────────────────────

def call_claude(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", "claude-sonnet-4-6"],
        capture_output=True, text=True, timeout=120, cwd=BASE_DIR,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude exit {result.returncode}: {result.stderr[:300]}")
    return result.stdout.strip()


# ─── Telegram ─────────────────────────────────────────────────────────────────

def _md_to_html(text: str) -> str:
    """Конвертирует markdown Claude в Telegram HTML."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)
    return text


def send_telegram(user_id: int, text: str):
    html = _md_to_html(text)
    payload = json.dumps({"chat_id": user_id, "text": html, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")


# ─── Основной цикл ────────────────────────────────────────────────────────────

def process_user(user_id: int):
    pending = get_pending_messages(user_id)
    if not pending:
        return

    order = get_order_for_user(user_id)
    if not order:
        log.warning(f"User {user_id}: нет заказа в БД, пропускаю")
        return

    history = get_support_history(user_id)
    prompt = build_prompt(order, pending, history)

    log.info(f"User {user_id}: спрашиваю Claude ({len(pending)} сообщ.)...")
    reply = call_claude(prompt)

    if DRY_RUN:
        log.info(f"[DRY_RUN] Ответ для user {user_id}:\n{reply}\n")
    else:
        send_telegram(user_id, reply)
    mark_answered(user_id)
    log_outgoing(user_id, reply)
    log.info(f"User {user_id}: ответ {'(не отправлен, DRY_RUN)' if DRY_RUN else 'отправлен'} ({len(reply)} символов)")


def run_batch():
    users = get_pending_users()
    if not users:
        log.info("Нет неотвеченных сообщений.")
        return

    log.info(f"Запуск: {len(users)} пользователей с вопросами")
    for user_id in users:
        try:
            process_user(user_id)
        except Exception as e:
            log.error(f"User {user_id}: ошибка — {e}", exc_info=True)


if __name__ == "__main__":
    run_batch()
