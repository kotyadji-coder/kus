"""Рендер сухого отчёта через WeasyPrint и проверка переполнения секций.

Логических секций <section class="page"> должно быть ровно столько же, сколько
физических страниц PDF. Если физических больше — какая-то секция переполнилась
(карточки не уместились в A4). Прогон по всем тест-профилям evals.PROFILES.
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dry_food_selector import DryFoodSelector, DogProfileDry, generate_dry_food_html
from evals import PROFILES
from weasyprint import HTML as WpHTML

selector = DryFoodSelector()
all_ok = True

for p in PROFILES:
    dog = DogProfileDry(
        name=p["name"], breed=p["breed"], age_months=p["age_months"],
        sex=p["sex"], neutered=p["neutered"], weight_kg=p["weight_kg"],
        condition=p["condition"], activity=p["activity"],
        diagnoses=p.get("diagnoses", []), stool="good",
        stop_products=p.get("stop_products", []),
    )
    result = selector.select(dog)
    html = generate_dry_food_html(result)

    n_logical = len(re.findall(r'<section class="page', html))
    n_physical = len(WpHTML(string=html).render().pages)

    # Одинокий хвост: страница-категория, на которой лишь 1 карточка корма,
    # хотя в категории кормов больше одного.
    lonely = 0
    by_cat = {}
    for blk in re.findall(r'(Категория (\d+) / 3)(.*?)(?=Категория \d+ / 3|\Z)', html, re.DOTALL):
        cat = blk[1]
        cards_here = len(re.findall(r'class="food"', blk[2]))
        by_cat.setdefault(cat, []).append(cards_here)
    for cat, counts in by_cat.items():
        total = sum(counts)
        if total > 1 and any(c == 1 for c in counts):
            lonely += 1

    overflow = n_physical != n_logical
    status = "OVERFLOW" if overflow else ("LONELY" if lonely else "OK")
    if overflow or lonely:
        all_ok = False
    print(f"{status:9} {p['name']:8} {p['breed']:24} "
          f"{p['weight_kg']:>5}кг  лог={n_logical} физ={n_physical} "
          f"кат={ {c: by_cat[c] for c in sorted(by_cat)} }")

print("\n" + ("ВСЕ ПРОФИЛИ OK — переполнений нет" if all_ok
              else "ЕСТЬ ПЕРЕПОЛНЕНИЯ — карточки не влезают"))
sys.exit(0 if all_ok else 1)
