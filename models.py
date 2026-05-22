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

    # Telegram deep link (если пришёл из бота)
    telegram_user_id: Optional[int] = None


# =====================================================================
# SQLite — заказы
# =====================================================================

ORDER_STATUSES = ["new", "paid", "processing", "done", "error"]

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
        await db.commit()


async def create_order(form: OrderForm, amount: float) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO orders (
                dog_name, breed, age_months, sex, neutered, weight_kg,
                current_food, current_food_other, condition, activity,
                diagnoses, stool, stool_other,
                diet_type, budget, stop_products,
                client_name, phone_or_telegram, email, telegram_user_id,
                amount, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
        """, (
            form.dog_name, form.breed, form.age_months, form.sex, form.neutered, form.weight_kg,
            form.current_food.value, form.current_food_other, form.condition.value, form.activity.value,
            form.diagnoses, form.stool.value, form.stool_other,
            form.diet_type.value, form.budget.value if form.budget else None, form.stop_products,
            form.client_name, form.phone_or_telegram, form.email, form.telegram_user_id,
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


async def list_orders(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
