"""Прогон ОДНОГО профиля матрицы через боевую генерацию (реальный Gemini) и аудит.

Идём по матрице по одному: генерим HTML, вытаскиваем РЕАЛЬНЫЙ текст ИИ (интро +
6 блоков insight + заметки), прогоняем стража check_ai_text (числа/стоп в кормовом
контексте) и контент-чеки по полному тексту (протечка стоп-листа, нулевые дозы).
Дампим текст ИИ дословно — чтобы человек оценил прозу по существу.

Запуск:  venv/bin/python tools/report_qa/run_one.py <индекс_профиля>
Список:  venv/bin/python tools/report_qa/run_one.py --list
"""
from __future__ import annotations

import asyncio
import html as H
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evals import PROFILES  # noqa: E402
from check_ai_text import audit_ai_text, _is_excluded_context  # noqa: E402
from check_natural import _visible_text, _stop_forms  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def _order_from_profile(p: dict, idx: int) -> dict:
    return {
        "id": 990100 + idx,
        "diet_type": p["diet_type"],
        "dog_name": p["name"],
        "breed": p["breed"],
        "age_months": p["age_months"],
        "sex": p["sex"],
        "neutered": p["neutered"],
        "weight_kg": p["weight_kg"],
        "current_food": "dry",
        "condition": p["condition"],
        "activity": p["activity"],
        "stool": p.get("stool", "good"),
        "budget": p.get("budget", "market"),
        "pregnant": p.get("pregnant", False),
        "lactating": p.get("lactating", False),
    }


def _strip(t: str) -> str:
    t = re.sub(r"<br\s*/?>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return H.unescape(re.sub(r"\s+", " ", t)).strip()


def _extract_ai(doc: str) -> list[tuple[str, str]]:
    """Достаёт ровно ИИ-секции (НЕ статич. шаблоны и НЕ таблицы)."""
    ai: list[tuple[str, str]] = []
    subs = re.findall(r'<p class="section-sub">(.*?)</p>', doc, re.S)
    if subs:  # интро = первый section-sub (остальные — статич. подписи)
        ai.append(("intro", _strip(subs[0])))
    for i, p in enumerate(re.findall(r'<div class="tag[^"]*">.*?</div>\s*<p>(.*?)</p>', doc, re.S)):
        ai.append((f"insight[{i}]", _strip(p)))
    m = re.search(r'font-size: 11pt; line-height: 1\.7; color: var\(--ink\);">(.*?)</div>', doc, re.S)
    if m:
        ai.append(("ai_notes", _strip(m.group(1))))
    return ai


async def _gen(order: dict, diagnoses: list, stop: list) -> str:
    from worker import _generate_natural_html
    print(f"[gen] {order['dog_name']} ({order['breed']}, {order['weight_kg']}кг, "
          f"{order['condition']}) diet={order['diet_type']} stop={stop} diagn={diagnoses}")
    path = await _generate_natural_html(order, diagnoses, stop)
    print(f"[gen] HTML: {path} ({os.path.getsize(path)} bytes)\n")
    return path


def run(idx: int) -> int:
    p = PROFILES[idx]
    order = _order_from_profile(p, idx)
    diagnoses = list(p.get("diagnoses", []))
    stop = list(p.get("stop_products", []))

    html_path = asyncio.run(_gen(order, diagnoses, stop))
    doc = open(html_path, encoding="utf-8").read()

    # --- Аудит ИИ-текста (числа + стоп в кормовом контексте) ---
    ai = _extract_ai(doc)
    print("=" * 70)
    print("ТЕКСТ ИИ (дословно) + страж")
    print("=" * 70)
    ai_bad = 0
    for label, text in ai:
        issues = audit_ai_text(text, stop)
        if issues:
            ai_bad += 1
        mark = "ЧИСТО" if not issues else "‼ НАРУШЕНИЕ"
        print(f"\n--- {label} :: {mark} ---")
        print(text)
        for it in issues:
            print("   →", it)

    # --- Контент-чеки по ПОЛНОМУ тексту (регресс-стражи) ---
    full = _visible_text(doc)
    print("\n" + "=" * 70)
    print("КОНТЕНТ-ЧЕКИ (полный текст отчёта)")
    print("=" * 70)
    content_bad = 0

    # Протёк = стоп-продукт в «кормовом» контексте (без маркера исключения рядом).
    # Законное «исключите говядину» — не протёк (та же логика, что в check_ai_text).
    leaks = []
    for s in stop:
        fed = [f for f in _stop_forms(s) if f in full and not _is_excluded_context(full, f)]
        if fed:
            leaks.append(f"{s}→{','.join(fed)}")
    if stop:
        ok = not leaks
        content_bad += 0 if ok else 1
        print(f"[{'+' if ok else '!'}] Стоп-лист в полном тексте (кормовой контекст): "
              f"{'чисто' if ok else 'ПРОТЁК ' + '; '.join(leaks)}")

    zero = re.findall(r"\b0\s*(?:мл|капсул\w*|шт|таблет\w*|г)\b", full)
    ok = not zero
    content_bad += 0 if ok else 1
    print(f"[{'+' if ok else '!'}] Нет нулевых доз: {'ок' if ok else zero[:5]}")

    # Эффективный Ca:P (после добавки кальция) — в здоровом коридоре 1.1-2.0.
    from calculator import DietCalculator, DogProfile
    dog = DogProfile(name=p["name"], breed=p["breed"], age_months=p["age_months"],
        sex=p["sex"], neutered=p["neutered"], weight_kg=p["weight_kg"], current_food="dry",
        condition=p["condition"], activity=p["activity"], diagnoses=diagnoses,
        stool=p.get("stool", "good"), diet_type=p["diet_type"],
        budget=p.get("budget", "market"), stop_products=stop)
    res = DietCalculator().calculate(dog)
    eff = res.ca_p_ratio_effective
    ok = 1.1 <= eff <= 2.0
    content_bad += 0 if ok else 1
    print(f"[{'+' if ok else '!'}] Ca:P эффективный в коридоре: еда={res.ca_p_ratio} → "
          f"с добавкой={eff} {'ок' if ok else 'ВНЕ 1.1-2.0'}")

    print("\n" + "=" * 70)
    print(f"ИТОГ {p['name']}: ИИ-секций={len(ai)} нарушений_ИИ={ai_bad} | "
          f"контент-провалов={content_bad}")
    print("=" * 70)
    return 0 if (ai_bad == 0 and content_bad == 0) else 1


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] == "--list":
        for i, p in enumerate(PROFILES):
            print(f"{i:2} {p['diet_type']:7} {p['name']:10} {p['breed'][:20]:20} "
                  f"{p['weight_kg']}кг {p.get('condition',''):8} "
                  f"стоп={p.get('stop_products') or '—'} диагн={p.get('diagnoses') or '—'}")
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    return run(int(sys.argv[1]))


if __name__ == "__main__":
    sys.exit(main())
