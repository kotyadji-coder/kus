"""Расширение линеек Gemon/Jarvi/Родные корма — точные макросы с магазинов/Monge.
Идемпотентно. Запуск: venv/bin/python tools/report_qa/_seed_lineups.py
"""
import json, os
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "dry_foods.json")
def L(q): return {"ozon": f"ozon.ru/search/?text={q}", "wb": f"wildberries.ru/catalog/0/search.aspx?search={q}", "4paws": f"4lapy.ru/search/?q={q}"}
NAT = "натуральные (токоферолы)"

NEW = [
    # ---- Gemon (Италия, budget) ----
    {"id": "gemon_mini_adult_chicken", "brand": "Gemon", "name": "High Premium Mini Adult Chicken & Rice", "country": "Италия",
     "price_category": "budget", "price_per_kg": 380, "size_suitable": ["mini", "small"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["злаки", "мясо и продукты животного происхождения (свежая курица)", "масла и жиры", "свекловичный жом", "пивные дрожжи"],
     "protein_pct": 26, "fat_pct": 13, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 28,
     "main_protein_sources": ["курица"], "grain_sources": ["рис", "кукуруза"], "preservatives": NAT, "splitting_detected": True,
     "pros": ["Для мелких пород", "Свежая курица", "Доступная цена"], "cons": ["Злаки на первом месте"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("gemon+mini+adult")},
    {"id": "gemon_mini_puppy_junior", "brand": "Gemon", "name": "High Premium Mini Puppy & Junior Chicken & Turkey", "country": "Италия",
     "price_category": "budget", "price_per_kg": 400, "size_suitable": ["mini", "small"], "age_suitable": ["puppy"], "grain_free": False,
     "ingredients_top5": ["злаки", "мясо и продукты животного происхождения (курица, индейка)", "масла и жиры", "свекловичный жом", "рыбий жир"],
     "protein_pct": 29, "fat_pct": 15, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 30,
     "main_protein_sources": ["курица", "индейка"], "grain_sources": ["рис", "кукуруза"], "preservatives": NAT, "splitting_detected": True,
     "pros": ["Для щенков и юниоров мелких пород", "Повышенная калорийность для роста"], "cons": ["Злаки на первом месте"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("gemon+mini+puppy")},
    {"id": "gemon_medium_lamb_rice", "brand": "Gemon", "name": "High Premium Medium Adult Lamb & Rice", "country": "Италия",
     "price_category": "budget", "price_per_kg": 360, "size_suitable": ["medium", "large"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["злаки", "мясо и продукты животного происхождения (свежий ягнёнок)", "масла и жиры", "свекловичный жом", "пивные дрожжи"],
     "protein_pct": 25, "fat_pct": 13, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 28,
     "main_protein_sources": ["ягнёнок"], "grain_sources": ["рис"], "preservatives": NAT, "splitting_detected": True,
     "pros": ["Ягнёнок — без курицы как основного белка", "Один злак (рис)"], "cons": ["Злаки на первом месте"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("gemon+medium+lamb")},
    {"id": "gemon_performance", "brand": "Gemon", "name": "High Premium Performance All Breeds Adult", "country": "Италия",
     "price_category": "budget", "price_per_kg": 380, "size_suitable": ["medium", "large"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["злаки", "мясо и продукты животного происхождения 30% (свежая курица 15%)", "масла и жиры", "свекловичный жом", "пивные дрожжи"],
     "protein_pct": 27, "fat_pct": 15, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 30,
     "main_protein_sources": ["курица"], "grain_sources": ["рис", "кукуруза"], "preservatives": NAT, "splitting_detected": True,
     "pros": ["Performance — для активных и рабочих собак (повышенная энергия)", "Свежая курица 15%"], "cons": ["Злаки на первом месте"],
     "special_traits": ["performance"], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("gemon+performance")},

    # ---- Jarvi (Россия, mid) ----
    {"id": "jarvi_small_chicken_turkey_beef", "brand": "Jarvi", "name": "Adult Small Breeds Chicken/Turkey/Beef", "country": "Россия",
     "price_category": "mid", "price_per_kg": 560, "size_suitable": ["mini", "small"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["дегидрированное мясо курицы 15%", "дегидрированное мясо индейки 10%", "дегидрированное мясо говядины 10%", "рис", "ячмень"],
     "protein_pct": 28, "fat_pct": 17, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 35,
     "main_protein_sources": ["курица", "индейка", "говядина"], "grain_sources": ["рис", "ячмень"], "preservatives": NAT, "splitting_detected": False,
     "pros": ["Три мяса с процентами", "Для мелких пород", "Рыбий жир (Омега-3)"], "cons": ["Содержит курицу/говядину"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("jarvi+мелких+говядина")},
    {"id": "jarvi_puppy_small_lamb", "brand": "Jarvi", "name": "Puppy Small Breeds Lamb", "country": "Россия",
     "price_category": "mid", "price_per_kg": 580, "size_suitable": ["mini", "small"], "age_suitable": ["puppy"], "grain_free": False,
     "ingredients_top5": ["дегидрированное мясо курицы 15%", "дегидрированное мясо индейки 12%", "дегидрированное мясо говядины 8%", "гидролизат белка ягнёнка 4%", "рис"],
     "protein_pct": 29, "fat_pct": 18, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 35,
     "main_protein_sources": ["курица", "индейка", "говядина", "ягнёнок"], "grain_sources": ["рис", "кукуруза", "овёс"], "preservatives": NAT, "splitting_detected": False,
     "pros": ["Для щенков мелких пород", "Глюкозамин/хондроитин", "Омега-3 для развития"], "cons": ["Содержит курицу/говядину"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("jarvi+щенков+ягнёнок")},
    {"id": "jarvi_sensitive_lamb", "brand": "Jarvi", "name": "Adult Small Sensitive Lamb (Monoprotein)", "country": "Россия",
     "price_category": "mid", "price_per_kg": 600, "size_suitable": ["mini", "small"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["дегидрированное мясо ягнёнка", "рис", "ячмень", "жир (источник омега)", "рыбий жир"],
     "protein_pct": 26, "fat_pct": 15, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 30,
     "main_protein_sources": ["ягнёнок"], "grain_sources": ["рис", "ячмень"], "preservatives": NAT, "splitting_detected": False,
     "pros": ["Моно-белок ягнёнок — для чувствительного пищеварения", "Без курицы/говядины"], "cons": ["Один белок — при аллергии на ягнёнка не подходит"],
     "special_traits": ["hypoallergenic", "single_protein"], "allergens_absent": ["chicken", "beef"], "availability_ru": "stable", "buy_links": L("jarvi+сенситив+ягнёнок")},

    # ---- Родные корма (Россия, budget) ----
    {"id": "rodnye_korma_beef", "brand": "Родные корма", "name": "Взрослые собаки, говядина с овощами", "country": "Россия",
     "price_category": "budget", "price_per_kg": 300, "size_suitable": ["mini", "small", "medium", "large"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["мясные ингредиенты (говядина 14%, курица 8%)", "маис", "пшеница", "животный жир", "гидролизат мясных белков"],
     "protein_pct": 22, "fat_pct": 10, "fiber_pct": 3, "ash_pct": 7, "meat_estimate_pct": 22,
     "main_protein_sources": ["говядина", "курица"], "grain_sources": ["кукуруза", "пшеница"], "preservatives": NAT, "splitting_detected": True,
     "pros": ["Говядина 14% + курица 8%", "Доступная цена, РФ"], "cons": ["Маис + пшеница", "Невысокий белок (22%)"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("родные+корма+говядина")},
]

def main():
    db = json.load(open(DB, encoding="utf-8")); ex = {f["id"] for f in db["foods"]}; n = 0
    for f in NEW:
        if f["id"] in ex: print("уже есть:", f["id"]); continue
        db["foods"].append(f); n += 1; print("+", f["brand"], f["name"])
    json.dump(db, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nдобавлено {n}, всего: {len(db['foods'])}")
if __name__ == "__main__": main()
