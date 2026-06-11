"""
Фоновый воркер: после оплаты запускает расчёт, AI-персонализацию, генерацию HTML
и доставку клиенту (ссылка в Telegram + email).
"""

import asyncio
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.yandex.ru")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID", "")


async def process_order(order: dict):
    """Основной пайплайн обработки заказа."""
    from models import update_order

    order_id = order["id"]
    diet_type = order["diet_type"]

    try:
        await update_order(order_id, status="processing")
        log.info(f"Order #{order_id}: processing started ({diet_type})")

        # 1. Парсим свободные поля через AI
        from ai_adapter import parse_diagnoses, parse_stop_products
        diagnoses = parse_diagnoses(order.get("diagnoses") or "")
        stop_products = parse_stop_products(order.get("stop_products") or "")

        # 2. Генерируем HTML
        if diet_type in ("barf_and_dry", "cooked_and_dry"):
            # Комбо: натуралка + сухой корм — два файла
            natural_type = "barf" if diet_type == "barf_and_dry" else "cooked"
            order_natural = {**order, "diet_type": natural_type}
            html_natural = await _generate_natural_html(order_natural, diagnoses, stop_products)
            html_dry = await _generate_dry_food_html(order, diagnoses, stop_products)
            await _deliver(order, html_natural)
            await _deliver(order, html_dry)
            pdf_path = html_natural  # для записи в БД (поле переиспользуем)
        elif diet_type in ("barf", "cooked"):
            pdf_path = await _generate_natural_html(order, diagnoses, stop_products)
            await _deliver(order, pdf_path)
        else:
            pdf_path = await _generate_dry_food_html(order, diagnoses, stop_products)
            await _deliver(order, pdf_path)

        # 4. Обновляем статус
        await update_order(order_id, status="done", pdf_path=pdf_path)
        log.info(f"Order #{order_id}: done! HTML: {pdf_path}")

        # 5. Уведомляем админа (нефатально)
        try:
            await _notify_admin(order)
        except Exception as e:
            log.error(f"Order #{order_id}: admin notification failed: {e}")

    except Exception as e:
        log.error(f"Order #{order_id}: error — {e}", exc_info=True)
        await update_order(order_id, status="error", error_message=str(e)[:500])


# =====================================================================
# Генерация PDF — натуралка
# =====================================================================

async def _generate_natural_html(order: dict, diagnoses: list, stop_products: list) -> str:
    from calculator import DietCalculator, DogProfile
    from pdf_generator import generate_html
    from ai_adapter import generate_natural_intro, generate_natural_product_notes, generate_cover_image, generate_personal_analysis

    dog = DogProfile(
        name=order["dog_name"],
        breed=order["breed"],
        age_months=order["age_months"],
        sex=order["sex"],
        neutered=bool(order["neutered"]),
        weight_kg=order["weight_kg"],
        current_food=order["current_food"],
        condition=order["condition"],
        activity=order["activity"],
        diagnoses=diagnoses,
        stool=order["stool"],
        diet_type=order["diet_type"],
        budget=order.get("budget") or "market",
        stop_products=stop_products,
        pregnant=bool(order.get("pregnant")),
        lactating=bool(order.get("lactating")),
    )

    calc = DietCalculator()
    result = calc.calculate(dog)

    # AI-персонализация
    summary = (
        f"{dog.weight_kg} кг, кондиция: {dog.condition}, "
        f"активность: {dog.activity}, тип: {dog.diet_type}, "
        f"стоп: {stop_products}, диагнозы: {diagnoses}"
    )
    result.ai_intro = await asyncio.to_thread(generate_natural_intro, dog.name, dog.breed, summary, dog.sex)
    result.ai_notes = await asyncio.to_thread(generate_natural_product_notes,
        {"name": dog.name, "breed": dog.breed, "weight_kg": dog.weight_kg,
         "sex": dog.sex, "condition": dog.condition, "activity": dog.activity,
         "diagnoses": diagnoses, "stop_products": stop_products,
         "daily_grams": result.daily_grams, "ideal_weight_kg": result.ideal_weight_kg,
         "meals_per_day": result.meals_per_day, "diet_type": dog.diet_type,
         "ca_p_ratio": result.ca_p_ratio},
        result.warnings
    )

    # AI персональный анализ — передаём ВСЕ данные расчёта
    diet_summary = {
        "ideal_weight_kg": result.ideal_weight_kg,
        "current_weight_kg": dog.weight_kg,
        "weight_diff": round(dog.weight_kg - result.ideal_weight_kg, 1),
        "daily_grams": result.daily_grams,
        "rer_kcal": result.rer_kcal,
        "mer_kcal": result.mer_kcal,
        "ca_total_mg": result.ca_total_mg,
        "p_total_mg": result.p_total_mg,
        "ca_p_ratio": result.ca_p_ratio,
        "ca_p_ratio_effective": result.ca_p_ratio_effective,  # после добавки кальция (реальный баланс)
        "meals_per_day": result.meals_per_day,
        "diet_type": dog.diet_type,
        "distribution": {k: round(v) for k, v in result.distribution.items() if v > 0},
        "supplements": result.supplements,
        "warnings": result.warnings,
        "cost_per_day": result.cost_per_day,
        "cost_per_month": result.cost_per_month,
        "puppy_note": result.puppy_next_recalc,
        "cooking_tips": result.cooking_tips,
    }
    dog_profile_full = {
        "name": dog.name, "breed": dog.breed, "weight_kg": dog.weight_kg,
        "age_months": dog.age_months, "sex": dog.sex, "neutered": dog.neutered,
        "condition": dog.condition, "activity": dog.activity,
        "diagnoses": diagnoses, "stop_products": stop_products,
        "pregnant": dog.pregnant, "lactating": dog.lactating,
        "stool": dog.stool, "diet_type": dog.diet_type,
        "season": dog.season,
    }
    result.ai_analysis = await asyncio.to_thread(generate_personal_analysis,
        dog_profile_full,
        diet_summary
    )

    # Обложка — иллюстрация собаки по породе
    result.cover_image_b64 = await asyncio.to_thread(generate_cover_image, dog.breed, dog.name)

    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"order_{order['id']}_natural.html")

    html_content = await asyncio.to_thread(generate_html, result)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return output_path


# =====================================================================
# Генерация PDF — сухой корм
# =====================================================================

async def _generate_dry_food_html(order: dict, diagnoses: list, stop_products: list) -> str:
    from dry_food_selector import DryFoodSelector, DogProfileDry, generate_dry_food_html
    from ai_adapter import generate_dry_food_analysis, generate_dry_food_intro, generate_dry_food_conclusion, generate_cover_image

    dog = DogProfileDry(
        name=order["dog_name"],
        breed=order["breed"],
        age_months=order["age_months"],
        sex=order["sex"],
        neutered=bool(order["neutered"]),
        weight_kg=order["weight_kg"],
        condition=order["condition"],
        activity=order["activity"],
        diagnoses=diagnoses,
        stool=order["stool"],
        stop_products=stop_products,
    )

    selector = DryFoodSelector()
    result = selector.select(dog)

    # AI-персонализация для каждого корма из ТОП-9
    dog_dict = {
        "name": dog.name, "breed": dog.breed, "weight_kg": dog.weight_kg,
        "condition": dog.condition, "stop_products": stop_products, "diagnoses": diagnoses,
    }

    for rec in result.budget + result.mid + result.premium:
        rec.ai_analysis = await asyncio.to_thread(generate_dry_food_analysis, rec.food, dog_dict)

    # AI вступление и заключение
    result.ai_intro = await asyncio.to_thread(generate_dry_food_intro, dog_dict)
    result.ai_conclusion = await asyncio.to_thread(
        generate_dry_food_conclusion,
        [r.food for r in result.budget],
        [r.food for r in result.mid],
        [r.food for r in result.premium],
        dog_dict
    )

    # Обложка — иллюстрация собаки по породе
    result.cover_image_b64 = await asyncio.to_thread(generate_cover_image, dog.breed, dog.name)

    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"order_{order['id']}_dry.html")

    html_content = await asyncio.to_thread(generate_dry_food_html, result)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return output_path


# =====================================================================
# Доставка
# =====================================================================

BASE_URL = os.getenv("BASE_URL", "https://kus.dogfine.ru")


async def _deliver(order: dict, html_path: str):
    """Доставляет ссылку на расчёт в Telegram и/или на email."""
    delivered = False

    # Telegram — доставка через bot.py delivery loop (по статусу done)
    tg_id = order.get("telegram_user_id")
    if tg_id and BOT_TOKEN:
        log.info(f"Order #{order['id']}: HTML ready, bot delivery loop will send link to {tg_id}")
        delivered = True

    # Email
    email = order.get("email")
    if email and SMTP_USER:
        try:
            await asyncio.to_thread(_send_email_link, email, order)
            delivered = True
            log.info(f"Order #{order['id']}: link sent to {email}")
        except Exception as e:
            log.error(f"Order #{order['id']}: Email delivery failed: {e}")

    if not delivered:
        log.warning(f"Order #{order['id']}: HTML generated but not delivered (no Telegram/Email configured)")


def _send_email_link(email: str, order: dict):
    """Отправляет ссылку на расчёт на email."""
    diet_label = "натуральный рацион" if order["diet_type"] in ("barf", "cooked") else "подбор сухого корма"
    view_url = f"{BASE_URL}/order/{order['id']}/view"

    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM
    msg["To"] = email
    msg["Subject"] = f"Персональный {diet_label} для {order['dog_name']} — Doggi"

    body = (
        f"Здравствуйте, {order['client_name']}!\n\n"
        f"Готов персональный {diet_label} для {order['dog_name']}.\n\n"
        f"Открыть рацион: {view_url}\n\n"
        f"На странице есть кнопка «Печать / Сохранить PDF» — можно распечатать или сохранить как PDF.\n\n"
        f"У вас 7 дней поддержки. Пишите нам в Telegram: @doggifood_bot\n\n"
        f"С заботой о вашем питомце,\nКоманда Doggi"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


# =====================================================================
# Уведомление админа
# =====================================================================

async def _notify_admin(order: dict):
    """Admin notification is handled by bot's delivery loop (bot.py)."""
    log.info(f"Order #{order['id']}: done, bot will notify admin")
