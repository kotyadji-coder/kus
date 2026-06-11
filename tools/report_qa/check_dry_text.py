"""W2-добор — сверка ЧИСЕЛ в ИИ-тексте сухого корма с карточкой (нужен Gemini).

В отличие от натуралки, в тексте сухого числа РАЗРЕШЕНЫ (% мяса/белка, цена), но
ОБЯЗАНЫ совпадать с карточкой корма — ИИ не должен выдумывать или путать цифры.
Для выборки рекомендованных кормов зовём generate_dry_food_analysis и проверяем,
что каждое число из текста есть в карточке (meat/protein/fat/ash %, цена) или это
вес собаки. Чужое число = 🔴 (галлюцинация/расхождение).

Запуск:  venv/bin/python tools/report_qa/check_dry_text.py [N_кормов]
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dry_food_selector import DryFoodSelector, DogProfileDry  # noqa: E402
from ai_adapter import generate_dry_food_analysis  # noqa: E402

DOG = {"name": "Барс", "breed": "Немецкая овчарка", "age_months": 36, "sex": "male",
       "neutered": True, "weight_kg": 34, "condition": "athletic", "activity": "high",
       "diagnoses": [], "stool": "good", "stop_products": []}


def _card_numbers(food: dict, dog_w) -> set[int]:
    """Числа, которые ИИ ВПРАВЕ назвать: показатели карточки + вес собаки."""
    nums = set()
    for fld in ("protein_pct", "fat_pct", "ash_pct", "fiber_pct", "meat_estimate_pct", "price_per_kg"):
        v = food.get(fld)
        if isinstance(v, (int, float)):
            nums.add(int(round(v)))
    nums.add(int(round(dog_w)))
    return nums


def _text_numbers(text: str) -> list[int]:
    """Числа из текста (проценты, цена, голые) — кандидаты на сверку."""
    return [int(n) for n in re.findall(r"\d+", text)]


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    dog = DogProfileDry(name=DOG["name"], breed=DOG["breed"], age_months=DOG["age_months"],
                        sex=DOG["sex"], neutered=DOG["neutered"], weight_kg=DOG["weight_kg"],
                        condition=DOG["condition"], activity=DOG["activity"],
                        diagnoses=DOG["diagnoses"], stop_products=DOG["stop_products"])
    res = DryFoodSelector().select(dog)
    recs = [r for c in ("budget", "mid", "premium") for r in getattr(res, c)][:n]
    print(f"# QA · числа в ИИ-тексте сухого ({len(recs)} кормов, боевой Gemini)\n")
    bad = 0
    for rec in recs:
        food = rec.food
        allowed = _card_numbers(food, dog.weight_kg)
        text = generate_dry_food_analysis(food, DOG)
        found = _text_numbers(text)
        # допускаем точное совпадение ИЛИ ±1 (округление «~55%»)
        mism = [x for x in found if not any(abs(x - a) <= 1 for a in allowed) and x > 3]
        tag = f"{food.get('brand')} {food.get('name')}"
        if mism:
            bad += 1
            print(f"🔴 {tag}")
            print(f"   карточка: мясо~{food.get('meat_estimate_pct')}% белок{food.get('protein_pct')}% жир{food.get('fat_pct')}% зола{food.get('ash_pct')}% цена{food.get('price_per_kg')}")
            print(f"   числа вне карточки: {mism}")
            print(f"   текст: {text}")
        else:
            print(f"✅ {tag} — числа из карточки ({found or 'нет чисел'})")
            print(f"   «{text}»")
    print("\n" + ("ВСЕ ЧИСЛА ИЗ КАРТОЧЕК" if not bad else f"РАСХОЖДЕНИЙ: {bad}"))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
