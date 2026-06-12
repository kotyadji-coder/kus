"""Полная линейка Award (точные макросы с магазинов holistic-shop/valta/korma55).
Идемпотентно. Запуск: venv/bin/python tools/report_qa/_seed_award.py
"""
import json, os
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "dry_foods.json")
def L(q): return {"ozon": f"ozon.ru/search/?text={q}", "wb": f"wildberries.ru/catalog/0/search.aspx?search={q}", "4paws": f"4lapy.ru/search/?q={q}"}

NEW = [
    {"id": "award_adult_all_beef_chicken", "brand": "Award", "name": "Adult All Breeds Beef & Chicken",
     "country": "Россия", "price_category": "mid", "price_per_kg": 470,
     "size_suitable": ["mini", "small", "medium", "large"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["дегидрированное мясо курицы 25%", "дегидрированное мясо говядины 8%", "рис", "овёс", "зелёная чечевица"],
     "protein_pct": 25, "fat_pct": 14, "fiber_pct": 3, "ash_pct": 7, "meat_estimate_pct": 33,
     "main_protein_sources": ["курица", "говядина"], "grain_sources": ["рис", "овёс"],
     "preservatives": "натуральные (токоферолы)", "splitting_detected": False,
     "pros": ["Курица 25% + говядина 8% указаны", "Глюкозамин/хондроитин для суставов", "Рис и овёс — мягкие злаки"],
     "cons": ["Содержит курицу/говядину (частые аллергены)"],
     "special_traits": ["joint_support"], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("award+говядина+курица")},

    {"id": "award_adult_small_lamb_turkey", "brand": "Award", "name": "Adult Small Breeds Lamb & Turkey",
     "country": "Россия", "price_category": "mid", "price_per_kg": 500,
     "size_suitable": ["mini", "small"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["дегидрированное мясо ягнёнка", "дегидрированное мясо индейки", "рис", "овёс", "зелёная чечевица"],
     "protein_pct": 26, "fat_pct": 17, "fiber_pct": 3, "ash_pct": 7, "meat_estimate_pct": 30,
     "main_protein_sources": ["ягнёнок", "индейка"], "grain_sources": ["рис", "овёс"],
     "preservatives": "натуральные (токоферолы)", "splitting_detected": False,
     "pros": ["Ягнёнок + индейка — без курицы/говядины", "Для мелких пород", "Рис и овёс"],
     "cons": ["Калорийный (жир 17%) — следить за весом малоактивных"],
     "special_traits": ["hypoallergenic"], "allergens_absent": ["chicken", "beef"], "availability_ru": "stable", "buy_links": L("award+мелких+ягнёнок+индейка")},

    {"id": "award_hypo_pork", "brand": "Award", "name": "HYPO Adult All Breeds Pork",
     "country": "Россия", "price_category": "premium", "price_per_kg": 560,
     "size_suitable": ["mini", "small", "medium", "large"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["рис", "дегидрированное мясо свинины 28%", "овёс", "жир животный (свиной)", "зелёная чечевица"],
     "protein_pct": 26, "fat_pct": 13, "fiber_pct": 2, "ash_pct": 6, "meat_estimate_pct": 28,
     "main_protein_sources": ["свинина"], "grain_sources": ["рис", "овёс"],
     "preservatives": "натуральные (токоферолы)", "splitting_detected": False,
     "pros": ["Свинина — новый (необычный) белок, моно-протеин", "Гипоаллергенный, без курицы/говядины/ягнёнка/рыбы", "Брусника/груша/розмарин"],
     "cons": ["Лечебно-профилактический — при аллергии на свинину не подходит"],
     "special_traits": ["hypoallergenic", "single_protein"], "allergens_absent": ["chicken", "beef", "lamb", "fish"], "availability_ru": "stable", "buy_links": L("award+hypo+свинина")},

    {"id": "award_puppy_turkey_chicken", "brand": "Award", "name": "Puppy / Pregnant & Lactating Turkey & Chicken",
     "country": "Россия", "price_category": "mid", "price_per_kg": 520,
     "size_suitable": ["small", "medium"], "age_suitable": ["puppy"], "grain_free": False,
     "ingredients_top5": ["дегидрированное мясо индейки 25%", "дегидрированное мясо курицы 10%", "рис", "жир животный (свиной, куриный)", "овёс"],
     "protein_pct": 29, "fat_pct": 19, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 35,
     "main_protein_sources": ["индейка", "курица"], "grain_sources": ["рис", "овёс"],
     "preservatives": "натуральные (токоферолы)", "splitting_detected": False,
     "pros": ["Для щенков, беременных и кормящих сук", "Индейка 25% + курица 10%, мясо 35%", "Высокая калорийность для роста/лактации"],
     "cons": ["Содержит курицу (частый аллерген)"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("award+щенки+индейка+курица")},
]

def main():
    db = json.load(open(DB, encoding="utf-8")); ex = {f["id"] for f in db["foods"]}; n = 0
    for f in NEW:
        if f["id"] in ex: print("уже есть:", f["id"]); continue
        db["foods"].append(f); n += 1; print("+", f["brand"], f["name"])
    json.dump(db, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nдобавлено {n}, всего: {len(db['foods'])}")

if __name__ == "__main__": main()
