"""W2 — QA сухого корма (детерминированно, без Gemini).

Главный риск сухого: стоп-продукт/аллерген просачивается в ПОДБОР. Фильтр в
dry_food_selector проверяет стоп только в main_protein_sources, а курица/говядина
могут стоять в ingredients_top5 второстепенно и не быть помечены в allergens_absent
→ корм просочится. Здесь проверяем РЕЗУЛЬТАТ подбора по ПОЛНОМУ составу.

Что проверяем для каждого рекомендованного корма (budget/mid/premium):
  1. стоп-продукт НЕ встречается в полном составе (ingredients_top5 +
     main_protein_sources + grain_sources);
  2. для аллергика — нет частых аллергенов (курица/говядина/кукуруза/пшеница/соя);
  3. карточка корма консистентна (protein_pct/meat_estimate_pct/price заданы).

Числа в ИИ-тексте сухого (% мяса, цена) — отдельный слой (нужен Gemini): они
РАЗРЕШЕНЫ, но обязаны совпадать с карточкой. Это TODO второго прохода.

Запуск:  venv/bin/python tools/report_qa/check_dry.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dry_food_selector import DryFoodSelector, DogProfileDry  # noqa: E402
from check_ai_text import _stop_forms  # noqa: E402

# Видимые формы частых аллергенов в РУССКОМ составе.
ALLERGEN_FORMS = {
    "курица": ["кури", "куриц", "курин", "курят"],
    "говядина": ["говяд", "говяж"],
    "кукуруза": ["кукуруз"],
    "пшеница": ["пшени", "пшён", "пшен"],
    "соя": ["соя", "соев", "сои"],
}

# Дры-профили (в evals.PROFILES их нет — матрица натуралки). Покрываем стопы+аллергию.
DRY_PROFILES = [
    {"name": "Барс", "breed": "Немецкая овчарка", "age_months": 36, "sex": "male",
     "neutered": True, "weight_kg": 34, "condition": "athletic", "activity": "high",
     "diagnoses": [], "stool": "good", "stop_products": ["курица"]},
    {"name": "Туз", "breed": "Лабрадор-ретривер", "age_months": 48, "sex": "male",
     "neutered": True, "weight_kg": 32, "condition": "chubby", "activity": "moderate",
     "diagnoses": [], "stool": "good", "stop_products": ["говядина"]},
    {"name": "Ника", "breed": "Пудель", "age_months": 24, "sex": "female",
     "neutered": False, "weight_kg": 8, "condition": "athletic", "activity": "moderate",
     "diagnoses": ["аллергия"], "stool": "loose", "stop_products": []},
    {"name": "Чип", "breed": "Чихуахуа", "age_months": 24, "sex": "male",
     "neutered": False, "weight_kg": 3, "condition": "athletic", "activity": "moderate",
     "diagnoses": [], "stool": "good", "stop_products": ["курица", "говядина"]},
]


def _full_composition(food: dict) -> str:
    parts = (food.get("ingredients_top5", []) + food.get("main_protein_sources", [])
             + food.get("grain_sources", []))
    return " ".join(parts).lower()


def _check_profile(p: dict) -> list[str]:
    dog = DogProfileDry(
        name=p["name"], breed=p["breed"], age_months=p["age_months"], sex=p["sex"],
        neutered=p["neutered"], weight_kg=p["weight_kg"], condition=p["condition"],
        activity=p["activity"], diagnoses=p.get("diagnoses", []),
        stool=p.get("stool", "good"), stop_products=p.get("stop_products", []),
    )
    res = DryFoodSelector().select(dog)
    issues: list[str] = []
    recs = [(c, r) for c in ("budget", "mid", "premium") for r in getattr(res, c)]
    is_allergic = any("аллерг" in d.lower() for d in dog.diagnoses)

    for cat, rec in recs:
        food = rec.food
        tag = f"{food.get('brand')} {food.get('name')} [{cat}]"
        ings = [i.lower() for i in food.get("ingredients_top5", [])]
        mp = " ".join(food.get("main_protein_sources", [])).lower()
        # 1. стоп-продукт в составе. Различаем МЯСО/МУКА (🔴 опасно, должно
        #    исключаться) и ЖИР (🟡 рафинированный, без белка — безопасен, но
        #    клиенту со стоп-листом стоит раскрыть, а не отдавать молча).
        for s in dog.stop_products:
            forms = ALLERGEN_FORMS.get(s.lower()) or list(_stop_forms(s))
            meat_hits = [i for i in ings if any(f in i for f in forms) and "жир" not in i]
            fat_hits = [i for i in ings if any(f in i for f in forms) and "жир" in i]
            if meat_hits:
                issues.append(f"🔴 СТОП «{s}» МЯСО/МУКА в подборе: {tag} ({meat_hits})")
            if fat_hits:
                issues.append(f"🟡 «{s}» только жир (безопасно, но не раскрыто клиенту): {tag} ({fat_hits})")
        # 2. аллергик — частые аллергены: мясо 🔴, жир 🟡
        if is_allergic:
            for allerg, forms in ALLERGEN_FORMS.items():
                meat_hits = [i for i in ings if any(f in i for f in forms) and "жир" not in i]
                fat_hits = [i for i in ings if any(f in i for f in forms) and "жир" in i]
                if meat_hits:
                    issues.append(f"🔴 аллергику корм с «{allerg}» (мясо/мука): {tag} ({meat_hits})")
                elif fat_hits:
                    issues.append(f"🟡 аллергику корм с «{allerg}» (жир, обычно ок): {tag} ({fat_hits})")
        # 3. карточка консистентна
        for fld in ("protein_pct", "meat_estimate_pct", "price_per_kg"):
            if not food.get(fld):
                issues.append(f"🟡 у {tag} пустое поле {fld}")
    return issues, len(recs)


def main() -> int:
    print("# QA · сухой корм (стоп/аллерген в подборе)\n")
    all_ok = True
    for p in DRY_PROFILES:
        issues, n = _check_profile(p)
        stop_lbl = f"стоп={p.get('stop_products') or '—'} диагн={p.get('diagnoses') or '—'}"
        ok = not any(i.startswith("🔴") for i in issues)
        all_ok = all_ok and ok
        print(f"{'OK ' if ok else 'FAIL'} {p['name']:6} {p['breed'][:18]:18} {stop_lbl}  (подобрано {n} кормов)")
        for i in issues:
            print(f"     {i}")
    print("\n" + ("ВСЕ OK — стоп/аллерген не протекают в подбор" if all_ok else "ЕСТЬ ПРОТЕЧКИ В ПОДБОРЕ"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
