"""
Фоновый воркер: после оплаты запускает расчёт, AI-персонализацию, генерацию HTML.

ВАЖНО (храповик доверия): отчёт НЕ уходит клиенту автоматически.
Пайплайн: оплата → расчёт+генерация → авто-проверка (агент) → статус `review`
(ждёт кинолога). Доставку (email/VK/Telegram) запускает кинолог, одобрив рацион
в админке (см. app.py: approve_order → deliver_order). Telegram доставляется
циклом bot._delivery_loop по статусу `done`.

При переделке (status=rework, review_notes заданы) воркер перегенерирует рацион
с учётом замечаний кинолога и снова ставит `review`.
"""

import asyncio
import json
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
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "") or os.getenv("SMTP_USER", "")
VK_TOKEN = os.getenv("VK_TOKEN", "")
BASE_URL = os.getenv("BASE_URL", "https://kus.dogfine.ru")
VK_COMMUNITY_URL = os.getenv("VK_COMMUNITY_URL", "")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


# =====================================================================
# Sidecar с AI-текстами (нужен админке для правки и повторного рендера)
# =====================================================================

def _meta_path(order_id: int, kind: str = "natural") -> str:
    # Отдельный sidecar на каждую часть — у комбо две (natural + dry).
    return os.path.join(OUTPUT_DIR, f"order_{order_id}_{kind}.meta.json")


def save_meta(order_id: int, kind: str, data: dict):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(_meta_path(order_id, kind), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def load_meta(order_id: int, kind: str = "natural") -> dict:
    # Новый путь order_{id}_{kind}.meta.json; фолбэк на старый order_{id}.meta.json.
    for path in (_meta_path(order_id, kind), os.path.join(OUTPUT_DIR, f"order_{order_id}.meta.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            continue
    return {}


# =====================================================================
# Основной пайплайн
# =====================================================================

async def process_order(order: dict):
    """Расчёт → генерация → авто-проверка → статус review (ждёт кинолога).

    Используется и для первичной обработки, и для переделки (rework): если
    order['review_notes'] заполнены, они передаются в AI как замечания кинолога.
    """
    from models import update_order, set_auto_check

    order_id = order["id"]
    diet_type = order["diet_type"]
    guidance = (order.get("review_notes") or "").strip()

    try:
        await update_order(order_id, status="processing")
        log.info(f"Order #{order_id}: processing started ({diet_type})"
                 + (" [переделка]" if guidance else ""))

        # 1. Парсим свободные поля через AI
        from ai_adapter import parse_diagnoses, parse_stop_products, reset_fallback, fallback_count
        diagnoses = parse_diagnoses(order.get("diagnoses") or "")
        stop_products = parse_stop_products(order.get("stop_products") or "")
        reset_fallback()  # считаем фолбэки Gemini именно за этот заказ

        # 2. Генерируем HTML + получаем результат авто-проверки
        if diet_type in ("barf_and_dry", "cooked_and_dry"):
            natural_type = "barf" if diet_type == "barf_and_dry" else "cooked"
            order_natural = {**order, "diet_type": natural_type}
            path_n, chk_n = await _generate_natural_html(order_natural, diagnoses, stop_products, guidance=guidance)
            path_d, chk_d = await _generate_dry_food_html(order, diagnoses, stop_products, guidance=guidance)
            pdf_path = path_n
            auto_ok = chk_n[0] and chk_d[0]
            auto_summary = chk_n[1] + chk_d[1]
        elif diet_type in ("barf", "cooked"):
            pdf_path, (auto_ok, auto_summary) = await _generate_natural_html(
                order, diagnoses, stop_products, guidance=guidance)
        else:
            pdf_path, (auto_ok, auto_summary) = await _generate_dry_food_html(
                order, diagnoses, stop_products, guidance=guidance)

        # 3. Авто-проверка (агент) перед кинологом
        fb = fallback_count()
        ok = auto_ok and not fb
        summary_text = "; ".join(auto_summary) if auto_summary else "проверки пройдены"
        if fb:
            summary_text += f" | ⚠ Gemini-фолбэков: {fb} (текст на шаблоне)"
        await set_auto_check(order_id, ok, summary_text)

        # 4. НЕ done — ставим review (ждёт кинолога), доставку НЕ запускаем.
        #    review_notes гасим: замечания уже учтены в перегенерации.
        await update_order(order_id, status="review", pdf_path=pdf_path,
                           ai_fallback=1 if fb else 0, review_notes=None)
        log.info(f"Order #{order_id}: готов, ждёт ревью кинолога. Авто-проверка: "
                 f"{'OK' if ok else 'ЕСТЬ ЗАМЕЧАНИЯ'} — {summary_text}")

        # 5. Уведомляем админа/кинолога, что заказ ждёт проверки (нефатально)
        try:
            await _notify_review(order, ok, summary_text)
        except Exception as e:
            log.error(f"Order #{order_id}: не смог уведомить о ревью: {e}")

    except Exception as e:
        log.error(f"Order #{order_id}: error — {e}", exc_info=True)
        await update_order(order_id, status="error", error_message=str(e)[:500])


# =====================================================================
# Генерация — натуралка
# =====================================================================

async def _generate_natural_html(order: dict, diagnoses: list, stop_products: list,
                                 ai_overrides: dict | None = None, guidance: str = ""):
    """Возвращает (output_path, (auto_ok, [summary])).

    ai_overrides — готовые AI-тексты (правка кинолога): пропускаем их генерацию.
    guidance — замечания кинолога для переделки, подмешиваются в промпты.
    """
    from calculator import DietCalculator, DogProfile
    from pdf_generator import generate_html
    from ai_adapter import (generate_natural_intro, generate_natural_product_notes,
                            generate_cover_image, generate_personal_analysis)

    ov = ai_overrides or {}

    dog = DogProfile(
        name=order["dog_name"], breed=order["breed"], age_months=order["age_months"],
        sex=order["sex"], neutered=bool(order["neutered"]), weight_kg=order["weight_kg"],
        current_food=order["current_food"], condition=order["condition"], activity=order["activity"],
        diagnoses=diagnoses, stool=order["stool"], diet_type=order["diet_type"],
        budget=order.get("budget") or "market", stop_products=stop_products,
        pregnant=bool(order.get("pregnant")), lactating=bool(order.get("lactating")),
    )

    calc = DietCalculator()
    result = calc.calculate(dog)

    # --- AI-персонализация (или готовые тексты из правки) ---
    if "ai_intro" in ov:
        result.ai_intro = ov["ai_intro"]
    else:
        summary = (f"{dog.weight_kg} кг, кондиция: {dog.condition}, активность: {dog.activity}, "
                   f"тип: {dog.diet_type}, стоп: {stop_products}, диагнозы: {diagnoses}")
        if guidance:
            summary += f"\nЗАМЕЧАНИЯ КИНОЛОГА (учти при правке текста): {guidance}"
        result.ai_intro = await asyncio.to_thread(generate_natural_intro, dog.name, dog.breed, summary, dog.sex)

    if "ai_notes" in ov:
        result.ai_notes = ov["ai_notes"]
    else:
        notes_warnings = list(result.warnings)
        if guidance:
            notes_warnings.append(f"Замечания кинолога: {guidance}")
        result.ai_notes = await asyncio.to_thread(generate_natural_product_notes,
            {"name": dog.name, "breed": dog.breed, "weight_kg": dog.weight_kg,
             "sex": dog.sex, "condition": dog.condition, "activity": dog.activity,
             "diagnoses": diagnoses, "stop_products": stop_products,
             "daily_grams": result.daily_grams, "ideal_weight_kg": result.ideal_weight_kg,
             "meals_per_day": result.meals_per_day, "diet_type": dog.diet_type,
             "ca_p_ratio": result.ca_p_ratio},
            notes_warnings)

    if "ai_analysis" in ov:
        result.ai_analysis = ov["ai_analysis"]
    else:
        diet_summary = {
            "ideal_weight_kg": result.ideal_weight_kg, "current_weight_kg": dog.weight_kg,
            "weight_diff": round(dog.weight_kg - result.ideal_weight_kg, 1),
            "daily_grams": result.daily_grams, "rer_kcal": result.rer_kcal, "mer_kcal": result.mer_kcal,
            "ca_total_mg": result.ca_total_mg, "p_total_mg": result.p_total_mg,
            "ca_p_ratio": result.ca_p_ratio, "ca_p_ratio_effective": result.ca_p_ratio_effective,
            "meals_per_day": result.meals_per_day, "diet_type": dog.diet_type,
            "distribution": {k: round(v) for k, v in result.distribution.items() if v > 0},
            "supplements": result.supplements, "warnings": result.warnings,
            "cost_per_day": result.cost_per_day, "cost_per_month": result.cost_per_month,
            "puppy_note": result.puppy_next_recalc, "cooking_tips": result.cooking_tips,
        }
        if guidance:
            diet_summary["reviewer_guidance"] = guidance
        dog_profile_full = {
            "name": dog.name, "breed": dog.breed, "weight_kg": dog.weight_kg,
            "age_months": dog.age_months, "sex": dog.sex, "neutered": dog.neutered,
            "condition": dog.condition, "activity": dog.activity, "diagnoses": diagnoses,
            "stop_products": stop_products, "pregnant": dog.pregnant, "lactating": dog.lactating,
            "stool": dog.stool, "diet_type": dog.diet_type, "season": dog.season,
        }
        result.ai_analysis = await asyncio.to_thread(generate_personal_analysis, dog_profile_full, diet_summary)

    # Обложка — не перегенерируем при правке (дорого)
    if "cover_image_b64" in ov:
        result.cover_image_b64 = ov["cover_image_b64"]
    else:
        result.cover_image_b64 = await asyncio.to_thread(generate_cover_image, dog.breed, dog.name)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"order_{order['id']}_natural.html")
    html_content = await asyncio.to_thread(generate_html, result)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Sidecar для правки кинологом
    save_meta(order["id"], "natural", {
        "kind": "natural",
        "ai_intro": result.ai_intro or "",
        "ai_notes": result.ai_notes or "",
        "ai_analysis": result.ai_analysis or "",
        "cover_image_b64": result.cover_image_b64,
    })

    # Авто-проверка согласования (агент)
    auto_ok, summary = _auto_check_natural(result, html_content)
    return output_path, (auto_ok, summary)


def _auto_check_natural(result, html: str):
    """Прогоняет инварианты согласования (reconcile) как авто-проверку перед кинологом."""
    try:
        from reconcile import reconciliation_checks
        checks = reconciliation_checks(result, html)
    except Exception as e:
        return False, [f"авто-проверка упала: {e}"]
    fails = [c for c in checks if c["status"] == "fail"]
    warns = [c for c in checks if c["status"] == "warn"]
    summary = [f"✗ {c['key']}: {c['detail']}" for c in fails] + \
              [f"⚠ {c['key']}: {c['detail']}" for c in warns]
    if not summary:
        summary = ["согласование сводка↔меню↔покупки: ок"]
    return (not fails), summary


# =====================================================================
# Генерация — сухой корм
# =====================================================================

async def _generate_dry_food_html(order: dict, diagnoses: list, stop_products: list,
                                  ai_overrides: dict | None = None, guidance: str = ""):
    """Возвращает (output_path, (auto_ok, [summary]))."""
    from dry_food_selector import DryFoodSelector, DogProfileDry, generate_dry_food_html
    from ai_adapter import (generate_dry_food_analysis, generate_dry_food_intro,
                            generate_dry_food_conclusion, generate_cover_image)

    ov = ai_overrides or {}

    dog = DogProfileDry(
        name=order["dog_name"], breed=order["breed"], age_months=order["age_months"],
        sex=order["sex"], neutered=bool(order["neutered"]), weight_kg=order["weight_kg"],
        condition=order["condition"], activity=order["activity"], diagnoses=diagnoses,
        stool=order["stool"], stop_products=stop_products,
        pregnant=bool(order.get("pregnant")), lactating=bool(order.get("lactating")),
    )

    selector = DryFoodSelector()
    result = selector.select(dog)

    dog_dict = {"name": dog.name, "breed": dog.breed, "weight_kg": dog.weight_kg,
                "condition": dog.condition, "stop_products": stop_products, "diagnoses": diagnoses}

    food_overrides = ov.get("food_analyses") or {}
    for rec in result.budget + result.mid + result.premium:
        key = rec.food.get("name", "") if isinstance(rec.food, dict) else str(rec.food)
        if key in food_overrides:
            rec.ai_analysis = food_overrides[key]
        else:
            rec.ai_analysis = await asyncio.to_thread(generate_dry_food_analysis, rec.food, dog_dict)

    if "ai_intro" in ov:
        result.ai_intro = ov["ai_intro"]
    else:
        result.ai_intro = await asyncio.to_thread(generate_dry_food_intro, dog_dict)

    if "ai_conclusion" in ov:
        result.ai_conclusion = ov["ai_conclusion"]
    else:
        result.ai_conclusion = await asyncio.to_thread(
            generate_dry_food_conclusion,
            [r.food for r in result.budget], [r.food for r in result.mid],
            [r.food for r in result.premium], dog_dict)

    if "cover_image_b64" in ov:
        result.cover_image_b64 = ov["cover_image_b64"]
    else:
        result.cover_image_b64 = await asyncio.to_thread(generate_cover_image, dog.breed, dog.name)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"order_{order['id']}_dry.html")
    html_content = await asyncio.to_thread(generate_dry_food_html, result)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Sidecar для правки
    save_meta(order["id"], "dry", {
        "kind": "dry",
        "ai_intro": result.ai_intro or "",
        "ai_conclusion": result.ai_conclusion or "",
        "cover_image_b64": result.cover_image_b64,
        "food_analyses": {
            (r.food.get("name", "") if isinstance(r.food, dict) else str(r.food)): (r.ai_analysis or "")
            for r in result.budget + result.mid + result.premium
        },
    })

    # Лёгкая авто-проверка: во всех трёх категориях есть рекомендации
    empty = [name for name, lst in (("бюджет", result.budget), ("середина", result.mid),
                                    ("премиум", result.premium)) if not lst]
    if empty:
        return output_path, (False, [f"✗ нет кормов в категориях: {', '.join(empty)}"])
    return output_path, (True, [f"подбор: бюджет {len(result.budget)} / середина {len(result.mid)} / премиум {len(result.premium)}"])


# =====================================================================
# Повторный рендер из правок кинолога (без новых AI-вызовов)
# =====================================================================

async def regenerate_with_edits(order: dict, edits: dict, part: str = "natural"):
    """Перерисовывает ОДНУ часть отчёта с отредактированными текстами.

    part — 'natural' или 'dry' (для комбо части правятся независимо). Тексты вне
    edits и обложка берутся из sidecar этой части — новых обращений к Gemini нет.
    """
    from ai_adapter import parse_diagnoses, parse_stop_products

    order_id = order["id"]
    diet_type = order["diet_type"]
    meta = load_meta(order_id, part)
    diagnoses = parse_diagnoses(order.get("diagnoses") or "")
    stop_products = parse_stop_products(order.get("stop_products") or "")

    # Собираем overrides: правки поверх ранее сохранённых текстов
    overrides = dict(meta)
    overrides.pop("kind", None)
    overrides.update({k: v for k, v in edits.items() if v is not None})

    is_combo = diet_type in ("barf_and_dry", "cooked_and_dry")
    if part == "dry":
        await _generate_dry_food_html(order, diagnoses, stop_products, ai_overrides=overrides)
    else:
        natural_type = order["diet_type"]
        if is_combo:
            natural_type = "barf" if diet_type == "barf_and_dry" else "cooked"
        await _generate_natural_html({**order, "diet_type": natural_type},
                                     diagnoses, stop_products, ai_overrides=overrides)
    log.info(f"Order #{order_id}: часть '{part}' перерисована после правки кинолога")


# =====================================================================
# Доставка (запускается при одобрении кинологом)
# =====================================================================

def _wanted_channels(order: dict) -> set:
    """Какие каналы доставки нужны. Пусто/all → все, по которым есть контакт."""
    pref = (order.get("delivery_channel") or "").strip().lower()
    avail = set()
    if order.get("telegram_user_id"):
        avail.add("telegram")
    if order.get("email"):
        avail.add("email")
    if order.get("vk"):
        avail.add("vk")
    if not pref or pref == "all":
        return avail
    chosen = {c.strip() for c in pref.replace(";", ",").split(",") if c.strip()}
    return chosen & avail or avail


async def deliver_order(order: dict) -> dict:
    """Шлёт ссылку на готовый рацион. Email и VK — здесь; Telegram — циклом
    bot._delivery_loop (по статусу done + delivered=0). Возвращает {channel: bool}."""
    from models import update_order

    order_id = order["id"]
    channels = _wanted_channels(order)
    results: dict = {}

    if "email" in channels and order.get("email") and SMTP_USER:
        try:
            await asyncio.to_thread(_send_email_link, order["email"], order)
            await update_order(order_id, delivered_email=1)
            results["email"] = True
            log.info(f"Order #{order_id}: ссылка отправлена на {order['email']}")
        except Exception as e:
            results["email"] = False
            log.error(f"Order #{order_id}: email delivery failed: {e}")

    if "vk" in channels and order.get("vk"):
        ok = await _send_vk_link(order)
        results["vk"] = ok
        if ok:
            await update_order(order_id, delivered_vk=1)

    if "telegram" in channels:
        # Доставит bot._delivery_loop по статусу done; здесь только отмечаем намерение.
        results["telegram"] = "pending (bot loop)"

    return results


def _diet_label(order: dict) -> str:
    dt = order["diet_type"]
    if dt in ("barf_and_dry", "cooked_and_dry"):
        return "натуральный рацион + подбор сухого корма"
    if dt in ("barf", "cooked"):
        return "натуральный рацион"
    return "подбор сухого корма"


def _send_email_link(email: str, order: dict):
    """Отправляет ссылку на расчёт на email."""
    diet_label = _diet_label(order)
    view_url = f"{BASE_URL}/order/{order['id']}/view"
    wants_vk = "vk" in _wanted_channels(order)
    vk_note = ""
    if wants_vk:
        if VK_COMMUNITY_URL:
            vk_note = (
                f"\nЕсли хотите получить рацион во ВКонтакте, напишите нам в сообщество: "
                f"{VK_COMMUNITY_URL}\n"
            )
        else:
            vk_note = (
                "\nЕсли хотите получить рацион во ВКонтакте, сначала напишите нам в сообщения "
                "сообщества: без первого сообщения ВК может не принять доставку.\n"
            )

    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM
    msg["To"] = email
    msg["Subject"] = f"Персональный {diet_label} для {order['dog_name']} — Кусь"

    body = (
        f"Здравствуйте, {order['client_name']}!\n\n"
        f"Готов персональный {diet_label} для {order['dog_name']} — его рассчитали по "
        f"ветеринарным нормам и проверил наш специалист.\n\n"
        f"Открыть рацион: {view_url}\n\n"
        f"На странице есть кнопка «Печать / Сохранить PDF» — можно распечатать или сохранить как PDF.\n\n"
        f"У вас 7 дней поддержки. Пишите нам в Telegram: @doggifood_bot\n"
        f"{vk_note}\n"
        f"С заботой о вашем питомце,\nКоманда «Кусь»"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


async def _send_vk_link(order: dict) -> bool:
    """Шлёт ссылку в ВКонтакте через сообщество (нужен VK_TOKEN сообщества).

    order['vk'] — числовой id или короткое имя/ссылка. Если токена нет или
    пользователь не писал сообществу — доставка не выполняется (вернётся False),
    и заказ остаётся помеченным как недоставленный в VK для ручной отправки.
    """
    if not VK_TOKEN:
        log.warning(f"Order #{order['id']}: VK_TOKEN не задан — VK-доставка пропущена, отправьте вручную")
        return False

    import aiohttp
    raw = (order.get("vk") or "").strip()
    # Достаём идентификатор из ссылки vk.com/<id>
    screen = raw.replace("https://", "").replace("http://", "").replace("vk.com/", "").lstrip("@/").strip()
    if not screen:
        return False

    diet_label = _diet_label(order)
    view_url = f"{BASE_URL}/order/{order['id']}/view"
    text = (
        f"Здравствуйте, {order['client_name']}! Готов персональный {diet_label} "
        f"для {order['dog_name']} — рассчитан по ветеринарным нормам и проверен нашим специалистом.\n\n"
        f"Открыть рацион: {view_url}\n\nУ вас 7 дней поддержки."
    )

    try:
        async with aiohttp.ClientSession() as session:
            user_id = screen
            if not screen.isdigit():
                # Разрешаем короткое имя в числовой id
                async with session.get("https://api.vk.com/method/users.get",
                                       params={"user_ids": screen, "access_token": VK_TOKEN,
                                               "v": "5.199"}) as r:
                    d = await r.json()
                    if d.get("response"):
                        user_id = str(d["response"][0]["id"])
                    else:
                        log.error(f"Order #{order['id']}: VK не разрешил id для '{screen}': {d}")
                        return False
            # random_id фиксированный по заказу — VK дедуплицирует повторы
            async with session.get("https://api.vk.com/method/messages.send",
                                   params={"user_id": user_id, "message": text,
                                           "random_id": order["id"], "access_token": VK_TOKEN,
                                           "v": "5.199"}) as r:
                d = await r.json()
                if d.get("response"):
                    log.info(f"Order #{order['id']}: ссылка отправлена в VK ({user_id})")
                    return True
                log.error(f"Order #{order['id']}: VK messages.send error: {d}")
                return False
    except Exception as e:
        log.error(f"Order #{order['id']}: VK delivery failed: {e}")
        return False


# =====================================================================
# Уведомление кинолога/админа о заказе на ревью
# =====================================================================

async def _notify_review(order: dict, ok: bool, summary: str):
    """Сообщает кинологу/админу, что заказ ждёт проверки — email (надёжно с 5.42)
    + Telegram (если egress доступен)."""
    flag = "✅ авто-проверка ок" if ok else "⚠ авто-проверка: ЕСТЬ ЗАМЕЧАНИЯ"
    review_url = f"{BASE_URL}/admin/review/{order['id']}"
    text = (
        f"🔍 Заказ #{order['id']} ждёт проверки кинолога\n"
        f"Собака: {order.get('dog_name','?')} ({order.get('breed','?')})\n"
        f"Тип: {_diet_label(order)}\n"
        f"{flag}\n{summary}\n\n"
        f"Открыть на проверку: {review_url}"
    )

    # 1. Email админу/кинологу — основной канал (egress SMTP с 5.42 работает).
    if ADMIN_EMAIL and SMTP_USER:
        try:
            await asyncio.to_thread(_send_admin_email,
                f"🔍 #{order['id']} на проверку — {order.get('dog_name','?')}", text)
        except Exception as e:
            log.error(f"Order #{order['id']}: не смог отправить review-email админу: {e}")

    # 2. Telegram — если доступен (с 5.42 обычно нет — не критично).
    try:
        from bot import bot, ADMIN_ID
        await bot.send_message(ADMIN_ID, text)
    except Exception as e:
        log.info(f"Order #{order['id']}: review-уведомление не ушло в TG ({e}); ждёт в /admin/review")


def _send_admin_email(subject: str, body: str):
    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM
    msg["To"] = ADMIN_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
