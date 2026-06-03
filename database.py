import aiosqlite
import os
from datetime import datetime, timezone, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "bot.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                track TEXT,
                current_step INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS support_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                user_name TEXT,
                username TEXT,
                direction TEXT,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

        # Миграция: поле срока поддержки
        async with db.execute("PRAGMA table_info(users)") as cur:
            cols = [r[1] for r in await cur.fetchall()]
        if "support_until" not in cols:
            await db.execute("ALTER TABLE users ADD COLUMN support_until TEXT")
            await db.commit()

        # Миграции таблицы support_log
        async with db.execute("PRAGMA table_info(support_log)") as cur:
            cols = [r[1] for r in await cur.fetchall()]
        if "answered" not in cols:
            await db.execute("ALTER TABLE support_log ADD COLUMN answered INTEGER DEFAULT 0")
            await db.execute("UPDATE support_log SET answered=1 WHERE direction='in'")
            await db.commit()
        if "is_ai" not in cols:
            await db.execute("ALTER TABLE support_log ADD COLUMN is_ai INTEGER DEFAULT 0")
            await db.commit()
        if "rating" not in cols:
            await db.execute("ALTER TABLE support_log ADD COLUMN rating INTEGER DEFAULT 0")
            await db.commit()


async def set_support_until(user_id: int):
    """Устанавливает срок поддержки: 7 дней с момента вызова (UTC ISO)."""
    until = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        # Если пользователь есть — обновляем, нет — создаём запись
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, support_until) VALUES (?, ?)",
            (user_id, until),
        )
        await db.execute(
            "UPDATE users SET support_until=? WHERE user_id=?",
            (until, user_id),
        )
        await db.commit()


async def log_support(
    user_id: int,
    user_name: str,
    username: str,
    direction: str,
    message: str,
    *,
    answered: int | None = None,
    is_ai: int = 0,
):
    """direction: 'in' (от клиента) или 'out' (ответ).
    answered: 0 = ждёт AI, 1 = обработано. По умолчанию: out→1, in→0.
    is_ai: 1 если ответил AI, 0 если человек.
    """
    if answered is None:
        answered = 1 if direction == "out" else 0
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO support_log (user_id, user_name, username, direction, message, answered, is_ai) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, user_name, username, direction, message, answered, is_ai),
        )
        await db.commit()


async def rate_support_message(msg_id: int, rating: int):
    """Оценка AI-ответа: 1 = хорошо, -1 = плохо, 0 = снять оценку."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE support_log SET rating=? WHERE id=?", (rating, msg_id)
        )
        await db.commit()


async def get_support_logs(limit: int = 100):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM support_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cursor:
            return await cursor.fetchall()


async def add_user(user_id: int, first_name: str, track: str):
    # INSERT OR IGNORE + UPDATE сохраняет support_until при повторном /start
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, first_name, track, current_step) VALUES (?, ?, ?, 0)",
            (user_id, first_name, track),
        )
        await db.execute(
            "UPDATE users SET first_name=?, track=?, current_step=0 WHERE user_id=?",
            (first_name, track, user_id),
        )
        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()


async def increment_step(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET current_step = current_step + 1 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def get_users_at_step(step: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE current_step = ?", (step,)
        ) as cursor:
            return await cursor.fetchall()
