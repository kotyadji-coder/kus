import aiosqlite
import os

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


async def log_support(user_id: int, user_name: str, username: str, direction: str, message: str):
    """direction: 'in' (от клиента) или 'out' (ответ админа)"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO support_log (user_id, user_name, username, direction, message) VALUES (?, ?, ?, ?, ?)",
            (user_id, user_name, username, direction, message),
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
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (user_id, first_name, track, current_step) VALUES (?, ?, ?, 0)",
            (user_id, first_name, track),
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
