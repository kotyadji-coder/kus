"""
Модели данных: Pydantic-схемы анкеты + SQLite ORM.
"""

import enum
import aiosqlite
import os
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "kus.db")


# =====================================================================
# Pydantic — входные данные анкеты
# =====================================================================

class DogSize(str, enum.Enum):
    mini = "mini"
    small = "small"
    medium = "medium"
    large = "large"
    giant = "giant"

class Condition(str, enum.Enum):
    thin = "thin"
    athletic = "athletic"
    chubby = "chubby"
    obese = "obese"

class Activity(str, enum.Enum):
    lazy = "lazy"
    moderate = "moderate"
    high = "high"
    puppy = "puppy"

class DietType(str, enum.Enum):
    barf = "barf"
    cooked = "cooked"
    dry = "dry"
    barf_and_dry = "barf_and_dry"
    cooked_and_dry = "cooked_and_dry"

class Budget(str, enum.Enum):
    supermarket = "supermarket"
    market = "market"
    unlimited = "unlimited"

class CurrentFood(str, enum.Enum):
    dry = "dry"
    porridge = "porridge"
    natural = "natural"
    table = "table"
    mixed = "mixed"
    other = "other"

class Stool(str, enum.Enum):
    good = "good"
    loose = "loose"
    constipation = "constipation"
    high_volume = "high_volume"
    other = "other"


class OrderForm(BaseModel):
    """Полная анкета клиента."""
    # Шаг 1: О собаке
    dog_name: str = Field(..., min_length=1, max_length=50)
    breed: str = Field(..., min_length=1)
    age_months: int = Field(..., ge=1, le=300)
    sex: str = Field(..., pattern="^(male|female)$")
    neutered: bool
    pregnant: bool = False
    lactating: bool = False
    weight_kg: float = Field(..., gt=0, le=150)

    # Шаг 2: Рацион и активность
    current_food: CurrentFood
    current_food_other: Optional[str] = None
    condition: Condition
    activity: Activity

    # Шаг 3: Здоровье
    diagnoses: Optional[str] = None
    stool: Stool
    stool_other: Optional[str] = None

    # Шаг 4: Предпочтения
    diet_type: DietType
    budget: Optional[Budget] = None  # Только для натуралки
    stop_products: Optional[str] = None

    # Шаг 5: Контакты
    client_name: str = Field(..., min_length=1, max_length=100)
    phone_or_telegram: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=100)
    vk: Optional[str] = None  # ссылка/ID ВКонтакте (необязательно)
    # Куда доставить готовый рацион: telegram / vk / email (через запятую) или all
    delivery_channel: Optional[str] = None

    # Telegram deep link (если пришёл из бота)
    telegram_user_id: Optional[int] = None


# =====================================================================
# SQLite — заказы
# =====================================================================

# Жизненный цикл заказа:
#   new → paid → processing → review → done
# review  — рацион сгенерирован, прошёл авто-проверку (агент) и ждёт кинолога.
# rework  — кинолог вернул на переделку с замечаниями (review_notes); воркер
#           перегенерирует и снова ставит review.
# done    — кинолог одобрил; запускается доставка (TG/VK/email).
ORDER_STATUSES = ["new", "paid", "processing", "review", "rework", "done", "error"]

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'new',

                -- Анкета
                dog_name TEXT,
                breed TEXT,
                age_months INTEGER,
                sex TEXT,
                neutered BOOLEAN,
                pregnant BOOLEAN DEFAULT 0,
                lactating BOOLEAN DEFAULT 0,
                weight_kg REAL,
                current_food TEXT,
                current_food_other TEXT,
                condition TEXT,
                activity TEXT,
                diagnoses TEXT,
                stool TEXT,
                stool_other TEXT,
                diet_type TEXT,
                budget TEXT,
                stop_products TEXT,

                -- Контакты
                client_name TEXT,
                phone_or_telegram TEXT,
                email TEXT,
                telegram_user_id INTEGER,

                -- Оплата
                payment_id TEXT,
                payment_status TEXT,
                amount REAL,

                -- Результат
                pdf_path TEXT,
                error_message TEXT
            )
        """)
        # Миграции (безопасны для существующей таблицы; SQLite не умеет ADD COLUMN
        # IF NOT EXISTS, поэтому через try). QA-аудит заказа + флаг фолбэка Gemini.
        for col, decl in (("qa_score", "REAL"), ("qa_checked_at", "TIMESTAMP"),
                          ("qa_notes", "TEXT"), ("ai_fallback", "INTEGER DEFAULT 0"),
                          # Контакты/доставка
                          ("vk", "TEXT"), ("delivery_channel", "TEXT"),
                          ("delivered", "INTEGER DEFAULT 0"),         # доставлено в Telegram
                          ("delivered_email", "INTEGER DEFAULT 0"),
                          ("delivered_vk", "INTEGER DEFAULT 0"),
                          ("admin_notified", "INTEGER DEFAULT 0"),
                          # Ревью кинолога
                          ("review_notes", "TEXT"),                   # замечания на переделку
                          ("reviewed_by", "TEXT"), ("reviewed_at", "TIMESTAMP"),
                          ("rework_count", "INTEGER DEFAULT 0"),
                          # Авто-проверка (агент перед кинологом)
                          ("auto_check", "TEXT"), ("auto_check_ok", "INTEGER")):
            try:
                await db.execute(f"ALTER TABLE orders ADD COLUMN {col} {decl}")
            except Exception:
                pass
        await db.commit()


async def create_order(form: OrderForm, amount: float) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO orders (
                dog_name, breed, age_months, sex, neutered, pregnant, lactating, weight_kg,
                current_food, current_food_other, condition, activity,
                diagnoses, stool, stool_other,
                diet_type, budget, stop_products,
                client_name, phone_or_telegram, email, vk, delivery_channel, telegram_user_id,
                amount, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
        """, (
            form.dog_name, form.breed, form.age_months, form.sex, form.neutered, form.pregnant, form.lactating, form.weight_kg,
            form.current_food.value, form.current_food_other, form.condition.value, form.activity.value,
            form.diagnoses, form.stool.value, form.stool_other,
            form.diet_type.value, form.budget.value if form.budget else None, form.stop_products,
            form.client_name, form.phone_or_telegram, form.email, form.vk, form.delivery_channel, form.telegram_user_id,
            amount,
        ))
        await db.commit()
        return cursor.lastrowid


async def get_order(order_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_order(order_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [order_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE orders SET {sets} WHERE id = ?", vals)
        await db.commit()


async def set_order_qa(order_id: int, score: float | None, notes: str = ""):
    """Записывает результат QA-аудита заказа (балл рубрики + заметки судьи)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET qa_score = ?, qa_notes = ?, qa_checked_at = CURRENT_TIMESTAMP WHERE id = ?",
            (score, notes, order_id))
        await db.commit()


async def get_order_by_telegram_user_id(telegram_user_id: int) -> dict | None:
    """Последний выполненный заказ пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders WHERE telegram_user_id=? AND status='done' "
            "ORDER BY created_at DESC LIMIT 1",
            (telegram_user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def list_orders(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def list_orders_by_status(statuses: list[str], limit: int = 100) -> list[dict]:
    """Заказы с любым из перечисленных статусов (для очереди ревью)."""
    if not statuses:
        return []
    ph = ",".join("?" for _ in statuses)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT * FROM orders WHERE status IN ({ph}) ORDER BY created_at ASC LIMIT ?",
            (*statuses, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def set_auto_check(order_id: int, ok: bool, summary: str):
    """Сохраняет результат авто-проверки (агент) перед ревью кинолога."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET auto_check = ?, auto_check_ok = ? WHERE id = ?",
            (summary, 1 if ok else 0, order_id))
        await db.commit()


async def approve_order(order_id: int, reviewed_by: str = "кинолог"):
    """Кинолог одобрил рацион → статус done (доставку запускает вызывающий код)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET status='done', reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP, "
            "review_notes=NULL WHERE id=?",
            (reviewed_by, order_id))
        await db.commit()


async def request_rework(order_id: int, notes: str, reviewed_by: str = "кинолог"):
    """Кинолог вернул рацион на переделку с замечаниями → статус rework."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET status='rework', review_notes=?, reviewed_by=?, "
            "reviewed_at=CURRENT_TIMESTAMP, rework_count=COALESCE(rework_count,0)+1 WHERE id=?",
            (notes, reviewed_by, order_id))
        await db.commit()
