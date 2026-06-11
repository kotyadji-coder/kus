"""W3 — пограничные случаи (детерминированно, без Gemini).

Матрица 11 профилей — happy path. Реальные клиенты грязнее: неизвестная порода,
абсурдный вес, мульти-диагноз, беременность+лактация, нулевой возраст, грязный
текст стопов. Гоняем калькулятор (и парсер стопов) по краям и проверяем
ИНВАРИАНТЫ: не падает + значения вменяемы (не 0/отрицательные/абсурдные дозы,
Ca:P в коридоре, объём правдоподобен, кормлений ≥1).

Запуск:  venv/bin/python tools/report_qa/check_edge.py
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from calculator import DietCalculator, DogProfile  # noqa: E402

# Каждый кейс: (описание, kwargs для DogProfile)
BASE = dict(name="Тест", breed="Метис", age_months=24, sex="male", neutered=False,
            weight_kg=15, current_food="dry", condition="athletic", activity="moderate",
            diagnoses=[], stool="good", diet_type="barf", budget="market", stop_products=[])


def case(desc, **kw):
    d = dict(BASE); d.update(kw); return (desc, d)


EDGE_CASES = [
    case("неизвестная порода (японский хин), норма", breed="Японский хин", weight_kg=4),
    case("неизвестная порода + перевес (цель похудения?)", breed="Японский хин", weight_kg=6, condition="chubby"),
    case("кроха 0.5 кг", breed="Чихуахуа", weight_kg=0.5, age_months=18),
    case("гигант 120 кг", breed="Метис", weight_kg=120, condition="athletic"),
    case("вес 0 (битый ввод)", weight_kg=0),
    case("возраст 0 (новорождённый)", age_months=0, weight_kg=1),
    case("щенок гигантской породы 3 мес", breed="Немецкий дог", age_months=3, weight_kg=12),
    case("мульти-диагноз: панкреатит+гастрит+аллергия+мкб",
         diagnoses=["панкреатит", "гастрит", "аллергия", "мкб"]),
    case("беременность И лактация одновременно", sex="female", neutered=False,
         pregnant=True, lactating=True, weight_kg=20),
    case("obese кроха 1.5 кг варёнка", breed="Чихуахуа", weight_kg=1.5, condition="obese", diet_type="cooked"),
    case("все мясо в стопе (курица+говядина+индейка+рыба+свинина)",
         stop_products=["курица", "говядина", "индейка", "рыба", "свинина"]),
    case("неизвестная гигантская порода, obese", breed="Тибетский мастиф", weight_kg=90, condition="obese"),
]


def check_invariants(dog: DogProfile, r) -> list[str]:
    bad = []
    if dog.weight_kg > 0 and r.ideal_weight_kg <= 0:
        bad.append(f"idealweight={r.ideal_weight_kg} (≤0 при вводе {dog.weight_kg})")
    if r.rer_kcal < 0 or r.mer_kcal < 0:
        bad.append(f"ккал отриц: rer={r.rer_kcal} mer={r.mer_kcal}")
    if dog.weight_kg > 0 and r.daily_grams <= 0:
        bad.append(f"daily_grams={r.daily_grams} (≤0)")
    if r.meals_per_day < 1:
        bad.append(f"кормлений {r.meals_per_day} (<1)")
    if r.ideal_weight_kg > 0 and r.daily_grams > 0:
        pct = r.daily_grams / (r.ideal_weight_kg * 1000) * 100
        if not (0.5 <= pct <= 12):
            bad.append(f"объём {pct:.1f}% идеала (абсурд)")
    # цель НАБОРА для перевеса — баг (равенство допустимо: конфликт вес=породный мин)
    if dog.condition in ("chubby", "obese") and dog.weight_kg > 0 and r.ideal_weight_kg > dog.weight_kg + 0.01:
        bad.append(f"перевес, но цель {r.ideal_weight_kg} > текущий {dog.weight_kg} (назначен НАБОР)")
    # дозы добавок: ровно ноль или отрицательная (не «3.0» — ноль после точки не в счёт)
    for s in r.supplements:
        d = str(s.get("dosage", ""))
        if re.search(r"(?<![\d.,])(0(?:[.,]0+)?|-\d+(?:[.,]\d+)?)\s*(мг|мл|г|капсул\w*|табл\w*|шт|ч\.?\s*л)", d):
            bad.append(f"подозрит. доза {s.get('name')}: «{d}»")
    # Ca:P эффективный
    if r.supplements and r.p_total_mg > 0:
        if not (1.0 <= r.ca_p_ratio_effective <= 2.2):
            bad.append(f"эфф Ca:P={r.ca_p_ratio_effective} вне 1.0-2.2")
    return bad


def main() -> int:
    calc = DietCalculator()
    all_ok = True
    print("# QA · пограничные случаи (натуралка, калькулятор)\n")
    for desc, kw in EDGE_CASES:
        try:
            dog = DogProfile(**kw)
            r = calc.calculate(dog)
        except Exception as e:
            all_ok = False
            print(f"💥 CRASH  {desc}\n          {type(e).__name__}: {e}")
            continue
        bad = check_invariants(dog, r)
        if bad:
            all_ok = False
            print(f"🔴 FAIL  {desc}")
            print(f"         идеал={r.ideal_weight_kg} объём={r.daily_grams}г Ca:P={r.ca_p_ratio_effective} кормл={r.meals_per_day}")
            for b in bad:
                print(f"         → {b}")
        else:
            print(f"✅ OK    {desc}  (идеал={r.ideal_weight_kg} объём={r.daily_grams}г Ca:P={r.ca_p_ratio_effective})")
    print("\n" + ("ВСЕ ГРАНИЦЫ OK" if all_ok else "ЕСТЬ ПРОБЛЕМЫ НА ГРАНИЦАХ"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
