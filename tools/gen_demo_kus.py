"""Демо-генерация отчётов на выдуманных данных: йорк 2 кг и немецкий дог 70 кг.
Оба типа расчёта (натуралка barf + сухой корм) для каждой собаки. Запуск на 5.42."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from ai_adapter import parse_diagnoses, parse_stop_products, reset_fallback, fallback_count
from worker import _generate_natural_html, _generate_dry_food_html

DOGS = [
    dict(id="york", dog_name="Тиша", breed="Йоркширский терьер", age_months=36,
         sex="female", neutered=True, weight_kg=2.0, current_food="dry",
         condition="athletic", activity="moderate", stool="good",
         budget="market", diagnoses="", stop_products="", pregnant=False, lactating=False,
         telegram_user_id=None, email=None),
    dict(id="dane", dog_name="Граф", breed="Немецкий дог", age_months=48,
         sex="male", neutered=False, weight_kg=70.0, current_food="dry",
         condition="athletic", activity="moderate", stool="good",
         budget="market", diagnoses="", stop_products="", pregnant=False, lactating=False,
         telegram_user_id=None, email=None),
]

async def main():
    for d in DOGS:
        diagnoses = parse_diagnoses(d.get("diagnoses") or "")
        stop = parse_stop_products(d.get("stop_products") or "")
        reset_fallback()
        nat = await _generate_natural_html({**d, "diet_type": "barf"}, diagnoses, stop)
        dry = await _generate_dry_food_html({**d, "diet_type": "dry"}, diagnoses, stop)
        print(f"[{d['id']}] {d['dog_name']} ({d['breed']}, {d['weight_kg']}кг): "
              f"natural={os.path.basename(nat)} dry={os.path.basename(dry)} "
              f"gemini_fallbacks={fallback_count()}")

asyncio.run(main())
