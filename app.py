"""
FastAPI бэкенд — Кусь.
Анкета -> Оплата -> Генерация PDF -> Доставка.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import uuid

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

from models import OrderForm, init_db, create_order, get_order, update_order, list_orders
from worker import process_order

# --- Config ---
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
BASE_URL = os.getenv("BASE_URL", "https://kus.dogfine.ru")
PRICES = {
    "barf": 1390,
    "cooked": 1390,
    "dry": 990,
    "barf_and_dry": 1950,
    "cooked_and_dry": 1950,
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# --- App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    log.info("Database initialized")
    yield

app = FastAPI(title="Kus — Dog Diet Service", lifespan=lifespan)

# Шаблоны и статика
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(templates_dir, exist_ok=True)
os.makedirs(static_dir, exist_ok=True)

templates = Jinja2Templates(directory=templates_dir)
output_dir = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(output_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/preview", StaticFiles(directory=output_dir), name="preview")


# =====================================================================
# Страницы
# =====================================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная — лендинг."""
    return templates.TemplateResponse(request=request, name="landing.html")


@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return templates.TemplateResponse(request=request, name="privacy.html")


@app.get("/oferta", response_class=HTMLResponse)
async def oferta(request: Request):
    return templates.TemplateResponse(request=request, name="oferta.html")


@app.get("/order", response_class=HTMLResponse)
async def order_form(request: Request, tg: int = None):
    """Форма-анкета (wizard 5 шагов)."""
    # Загружаем список пород для выпадающего списка
    breeds_path = os.path.join(os.path.dirname(__file__), "data", "breeds.json")
    with open(breeds_path, "r", encoding="utf-8") as f:
        breeds = json.load(f)
    breed_names = sorted([b["name"] for b in breeds])

    return templates.TemplateResponse(request=request, name="order.html", context={
        "breeds": breed_names,
        "telegram_user_id": tg,
    })


@app.post("/order")
async def submit_order(request: Request, background_tasks: BackgroundTasks):
    """Приём анкеты, создание заказа, редирект на оплату."""
    form_data = await request.form()
    data = dict(form_data)

    # Чекбокс neutered
    data["neutered"] = data.get("neutered") == "on" or data.get("neutered") == "true"
    data["age_months"] = int(data.get("age_months", 0))
    data["weight_kg"] = float(data.get("weight_kg", 0))
    if data.get("telegram_user_id"):
        data["telegram_user_id"] = int(data["telegram_user_id"])

    # Комбо: натуралка + сухой корм
    if data.get("diet_type") == "combo":
        combo_natural = data.get("combo_natural", "barf")
        data["diet_type"] = f"{combo_natural}_and_dry"

    try:
        form = OrderForm(**data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Цена
    amount = PRICES.get(form.diet_type.value, 1390)

    # Создаём заказ в БД
    order_id = await create_order(form, amount)
    log.info(f"Order #{order_id} created: {form.dog_name} ({form.breed}), {form.diet_type.value}")

    # Если ЮKassa настроена — редирект на оплату
    if YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY:
        payment_url = await _create_yookassa_payment(order_id, amount, form)
        return RedirectResponse(payment_url, status_code=303)

    # Если ЮKassa не настроена — сразу запускаем генерацию (для тестов)
    log.info(f"Order #{order_id}: no payment configured, starting generation directly")
    order = await get_order(order_id)
    await update_order(order_id, payment_status="test", status="paid")
    order["status"] = "paid"
    background_tasks.add_task(process_order, order)

    return RedirectResponse(f"/order/{order_id}/status", status_code=303)


# =====================================================================
# Оплата ЮKassa
# =====================================================================

async def _create_yookassa_payment(order_id: int, amount: float, form: OrderForm) -> str:
    """Создаёт платёж в ЮKassa, возвращает URL для редиректа."""
    import aiohttp
    import base64

    auth = base64.b64encode(f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}".encode()).decode()
    idempotency_key = str(uuid.uuid4())

    dt = form.diet_type.value
    if dt in ("barf_and_dry", "cooked_and_dry"):
        diet_label = "Натуралка + сухой корм"
    elif dt in ("barf", "cooked"):
        diet_label = "Расчёт натурального рациона"
    else:
        diet_label = "Подбор сухого корма"

    payload = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "confirmation": {
            "type": "redirect",
            "return_url": f"{BASE_URL}/order/{order_id}/status"
        },
        "capture": True,
        "description": f"{diet_label} для {form.dog_name}",
        "metadata": {"order_id": str(order_id)},
        "receipt": {
            "customer": {"email": form.email},
            "items": [{
                "description": diet_label,
                "quantity": "1",
                "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
                "vat_code": 1,
            }]
        }
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.yookassa.ru/v3/payments",
            json=payload,
            headers={
                "Authorization": f"Basic {auth}",
                "Idempotence-Key": idempotency_key,
                "Content-Type": "application/json",
            }
        ) as resp:
            data = await resp.json()
            if resp.status != 200:
                log.error(f"YooKassa error: {data}")
                raise HTTPException(status_code=500, detail="Payment creation failed")

            payment_id = data["id"]
            confirm_url = data["confirmation"]["confirmation_url"]

            await update_order(order_id, payment_id=payment_id, payment_status="pending")
            return confirm_url


@app.post("/webhook/yookassa")
async def yookassa_webhook(request: Request, background_tasks: BackgroundTasks):
    """Webhook от ЮKassa — подтверждение оплаты."""
    body = await request.body()
    data = json.loads(body)

    event = data.get("event")
    payment = data.get("object", {})
    payment_id = payment.get("id")
    status = payment.get("status")
    metadata = payment.get("metadata", {})
    order_id = metadata.get("order_id")

    log.info(f"YooKassa webhook: event={event}, payment={payment_id}, status={status}, order={order_id}")

    if not order_id:
        return JSONResponse({"status": "ok"})

    order_id = int(order_id)

    if event == "payment.succeeded" and status == "succeeded":
        await update_order(order_id, payment_status="succeeded", status="paid")
        order = await get_order(order_id)
        background_tasks.add_task(process_order, order)
        log.info(f"Order #{order_id}: payment succeeded, generation started")

    elif event == "payment.canceled":
        await update_order(order_id, payment_status="canceled")
        log.info(f"Order #{order_id}: payment canceled")

    return JSONResponse({"status": "ok"})


# =====================================================================
# Статус заказа
# =====================================================================

@app.get("/order/{order_id}/status", response_class=HTMLResponse)
async def order_status(request: Request, order_id: int):
    """Страница статуса заказа (клиент видит после оплаты)."""
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return templates.TemplateResponse(request=request, name="status.html", context={
        "order": order,
    })


@app.get("/api/order/{order_id}/status")
async def order_status_api(order_id: int):
    """API для AJAX-поллинга статуса."""
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"status": order["status"], "diet_type": order["diet_type"]}


# =====================================================================
# API — список пород (для автокомплита в форме)
# =====================================================================

@app.get("/api/breeds")
async def api_breeds():
    breeds_path = os.path.join(os.path.dirname(__file__), "data", "breeds.json")
    with open(breeds_path, "r", encoding="utf-8") as f:
        breeds = json.load(f)
    return [b["name"] for b in sorted(breeds, key=lambda x: x["name"])]


# =====================================================================
# Админка (простая)
# =====================================================================

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    orders = await list_orders(100)
    return templates.TemplateResponse(request=request, name="admin.html", context={
        "orders": orders,
    })


@app.get("/admin/support", response_class=HTMLResponse)
async def admin_support(request: Request):
    from database import get_support_logs
    logs = await get_support_logs(200)
    # Группируем по user_id для удобного просмотра
    conversations = {}
    for log in reversed(list(logs)):
        uid = log["user_id"]
        if uid not in conversations:
            conversations[uid] = {"name": log["user_name"], "username": log["username"], "messages": []}
        conversations[uid]["messages"].append({
            "direction": log["direction"],
            "message": log["message"],
            "time": log["created_at"],
        })
    html = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Поддержка — Кусь</title>
    <style>
    body{font-family:system-ui,sans-serif;background:#f5f7fa;margin:0;padding:20px;}
    .container{max-width:800px;margin:0 auto;}
    h1{color:#055ba9;margin-bottom:20px;}
    .conv{background:#fff;border:1px solid #e2e8f0;border-radius:12px;margin-bottom:16px;overflow:hidden;}
    .conv-header{padding:14px 18px;background:#f8f9fb;border-bottom:1px solid #e2e8f0;font-weight:700;font-size:15px;}
    .conv-header span{color:#888;font-weight:400;font-size:13px;margin-left:8px;}
    .msg{padding:10px 18px;border-bottom:1px solid #f0f0f0;font-size:14px;display:flex;gap:10px;align-items:flex-start;}
    .msg:last-child{border-bottom:none;}
    .msg-in{background:#fff;}
    .msg-out{background:#f0f6ff;}
    .msg-dir{flex:0 0 auto;font-size:11px;font-weight:700;padding:2px 8px;border-radius:100px;margin-top:2px;}
    .msg-in .msg-dir{background:#fee2e2;color:#dc2626;}
    .msg-out .msg-dir{background:#dcfce7;color:#16a34a;}
    .msg-text{flex:1;line-height:1.5;}
    .msg-time{flex:0 0 auto;font-size:11px;color:#999;margin-top:3px;}
    .back{display:inline-block;margin-bottom:16px;color:#055ba9;text-decoration:none;font-weight:600;}
    .empty{color:#999;text-align:center;padding:40px;}
    </style></head><body><div class="container">
    <a href="/admin" class="back">&larr; Заказы</a>
    <h1>Диалоги поддержки</h1>"""

    if not conversations:
        html += '<div class="empty">Пока нет обращений</div>'
    else:
        for uid, conv in conversations.items():
            name = conv["name"] or "Без имени"
            uname = f'@{conv["username"]}' if conv["username"] else ""
            html += f'<div class="conv"><div class="conv-header">{name} <span>{uname} · ID {uid}</span></div>'
            for m in conv["messages"]:
                cls = "msg-in" if m["direction"] == "in" else "msg-out"
                label = "Клиент" if m["direction"] == "in" else "Вы"
                time_str = m["time"][:16] if m["time"] else ""
                text = m["message"].replace("<", "&lt;").replace(">", "&gt;")
                html += f'<div class="msg {cls}"><div class="msg-dir">{label}</div><div class="msg-text">{text}</div><div class="msg-time">{time_str}</div></div>'
            html += '</div>'

    html += '</div></body></html>'
    return HTMLResponse(html)


# =====================================================================
# Запуск
# =====================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
