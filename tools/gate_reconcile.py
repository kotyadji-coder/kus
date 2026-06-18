"""Ворота: на ВСЕХ эталонных профилях НИ ОДНОГО провала инвариантов согласования.
Отдельно от evals.py, потому что у эвалов есть «мягкие» провалы калибровки (перевес/
щенок) — они допустимы; жёсткие инварианты сводка↔меню↔покупки — нет. Exit 1 при провале."""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculator import DietCalculator, DogProfile
import pdf_generator
from reconcile import violations
from evals import PROFILES

calc = DietCalculator()
bad = []
for p in PROFILES:
    dog = DogProfile(
        name=p["name"], breed=p["breed"], age_months=p["age_months"], sex=p["sex"],
        neutered=p["neutered"], weight_kg=p["weight_kg"], current_food="dry",
        condition=p["condition"], activity=p["activity"], diagnoses=p.get("diagnoses", []),
        stool=p.get("stool", "good"), diet_type=p["diet_type"], budget=p["budget"],
        stop_products=p.get("stop_products", []), pregnant=p.get("pregnant", False),
        lactating=p.get("lactating", False), season="neutral",
    )
    res = calc.calculate(dog)
    v = violations(res, pdf_generator.generate_html(res))
    if v:
        bad.append((p["name"], v))

if bad:
    print(f"✗ Инварианты согласования провалены у {len(bad)} профилей:")
    for name, v in bad:
        print(f"    [{name}] " + "; ".join(f"{x['key']}: {x['detail']}" for x in v))
    sys.exit(1)
print(f"✓ Согласование: {len(PROFILES)}/{len(PROFILES)} профилей чисты")
sys.exit(0)
