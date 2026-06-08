"""
Smoke-тест пайплайна: один профиль -> боевая генерация HTML (worker, реальный Gemini)
-> три состояния рендера. Проверяем, что цепочка скриншотов вообще работает,
прежде чем раскатывать матрицу.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from render import render_report  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# Один реалистичный профиль (взрослый лабрадор, лишний вес, стоп-курица)
SMOKE_ORDER = {
    "id": 990001,
    "diet_type": "barf",
    "dog_name": "Барон",
    "breed": "Лабрадор-ретривер",
    "age_months": 36,
    "sex": "male",
    "neutered": True,
    "weight_kg": 34,
    "current_food": "dry",
    "condition": "chubby",
    "activity": "moderate",
    "diagnoses": "",
    "stop_products": "курица",
    "stool": "good",
    "budget": "market",
    "pregnant": False,
    "lactating": False,
}


async def _generate(order):
    """Боевая генерация HTML (async, реальный Gemini). Возвращает путь к HTML."""
    from worker import _generate_natural_html
    from ai_adapter import parse_diagnoses, parse_stop_products

    print(f"[gen] {order['dog_name']} ({order['breed']}) — генерация HTML через worker…")
    diagnoses = parse_diagnoses(order.get("diagnoses") or "")
    stop = parse_stop_products(order.get("stop_products") or "")
    print(f"[gen] diagnoses={diagnoses} stop={stop}")
    html_path = await _generate_natural_html(order, diagnoses, stop)
    print(f"[gen] HTML: {html_path}  ({os.path.getsize(html_path)} bytes)")
    return html_path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    order = SMOKE_ORDER
    # Генерация — внутри event loop; рендер (sync Playwright) — СНАРУЖИ него.
    html_path = asyncio.run(_generate(order))

    prefix = os.path.join(OUT_DIR, f"smoke_{order['id']}")
    print("[render] скриншоты…")
    res = render_report(html_path, prefix)
    print(f"[render] desktop: {res.desktop_png}")
    print(f"[render] mobile:  {res.mobile_png}")
    print(f"[render] print:   {res.print_pdf} -> {len(res.print_pngs)} стр.")
    for png in res.print_pngs:
        print(f"           {png}")
    if res.errors:
        print(f"[render] ОШИБКИ: {res.errors}")
    else:
        print("[render] OK — все три состояния сняты")


if __name__ == "__main__":
    main()
