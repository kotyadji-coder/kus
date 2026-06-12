"""Разовый сид: добавляет популярные на маркетплейсах бренды в dry_foods.json.
Протеин/мясо/состав/злаки — из данных производителей/обзоров (веб). Жир/зола/
клетчатка/цена где источник не дал точно — разумная оценка для класса (помечено).
Идемпотентно по id. Запуск: venv/bin/python tools/report_qa/_seed_brands.py
"""
import json
import os

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "dry_foods.json")


def L(q):
    return {"ozon": f"ozon.ru/search/?text={q}", "wb": f"wildberries.ru/catalog/0/search.aspx?search={q}",
            "4paws": f"4lapy.ru/search/?q={q}"}


NEW = [
    {"id": "gemon_hp_adult_chicken_rice", "brand": "Gemon", "name": "High Premium Adult All Breeds Chicken & Rice",
     "country": "Италия", "price_category": "budget", "price_per_kg": 360,
     "size_suitable": ["mini", "small", "medium", "large"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["злаки", "мясо и продукты животного происхождения 30% (свежая курица 15%)",
                          "масла и жиры", "свекловичный жом", "пивные дрожжи"],
     "protein_pct": 27, "fat_pct": 15, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 30,
     "main_protein_sources": ["курица"], "grain_sources": ["рис", "кукуруза"],
     "preservatives": "натуральные (токоферолы)", "splitting_detected": True,
     "pros": ["Свежая курица 15% указана", "Доступная цена", "Стабильные поставки в РФ"],
     "cons": ["Злаки на первом месте", "Обобщённые «мясо и продукты животного происхождения»"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("gemon+adult")},

    {"id": "meglium_adult_gold_beef", "brand": "Meglium", "name": "Adult Gold Beef",
     "country": "Италия", "price_category": "budget", "price_per_kg": 290,
     "size_suitable": ["mini", "small", "medium", "large"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["дегидрированное мясо (говядина 16%, курица 15%)", "кукуруза", "пшеница",
                          "кукурузная мука", "куриный жир"],
     "protein_pct": 24, "fat_pct": 12, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 31,
     "main_protein_sources": ["говядина", "курица"], "grain_sources": ["кукуруза", "пшеница"],
     "preservatives": "натуральные (токоферолы)", "splitting_detected": True,
     "pros": ["Два мяса с процентами (говядина 16%, курица 15%)", "Доступная цена"],
     "cons": ["Кукуруза + пшеница + кукурузная мука (splitting)", "Высокая зольность"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("meglium+adult")},

    {"id": "rodnye_korma_adult", "brand": "Родные корма", "name": "Взрослые собаки всех пород",
     "country": "Россия", "price_category": "budget", "price_per_kg": 300,
     "size_suitable": ["mini", "small", "medium", "large"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["мясные ингредиенты 27% (курица 19%, говядина 8%)", "маис", "пшеница",
                          "животный жир", "гидролизат мясных белков"],
     "protein_pct": 24, "fat_pct": 12, "fiber_pct": 3, "ash_pct": 7, "meat_estimate_pct": 27,
     "main_protein_sources": ["курица", "говядина"], "grain_sources": ["кукуруза", "пшеница"],
     "preservatives": "натуральные (токоферолы)", "splitting_detected": True,
     "pros": ["Курица 19% + говядина 8% указаны", "Российское производство, доступная цена"],
     "cons": ["Маис + пшеница", "Гидролизат мясных белков как усилитель"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("родные+корма+собак")},

    {"id": "award_adult_medium_turkey_chicken", "brand": "Award", "name": "Adult Medium Turkey & Chicken",
     "country": "Россия", "price_category": "mid", "price_per_kg": 480,
     "size_suitable": ["small", "medium"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["дегидрированное мясо курицы 18%", "дегидрированное мясо индейки 11%", "рис",
                          "овёс", "зелёная чечевица"],
     "protein_pct": 24, "fat_pct": 15, "fiber_pct": 3, "ash_pct": 7, "meat_estimate_pct": 29,
     "main_protein_sources": ["курица", "индейка"], "grain_sources": ["рис", "овёс"],
     "preservatives": "натуральные (токоферолы)", "splitting_detected": False,
     "pros": ["Два мяса с процентами, мясо на первом месте", "Рис и овёс — мягкие злаки", "Российский суперпремиум"],
     "cons": ["Содержит курицу (частый аллерген)"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("award+собак+индейка")},

    {"id": "miratorg_promeat_lamb_potato", "brand": "Мираторг", "name": "Pro Meat Adult Lamb & Potato",
     "country": "Россия", "price_category": "budget", "price_per_kg": 360,
     "size_suitable": ["mini", "small", "medium", "large"], "age_suitable": ["adult"], "grain_free": True,
     "ingredients_top5": ["дегидрированное мясо курицы 27%", "свежая ягнятина 13%", "картофель", "горох", "животный жир"],
     "protein_pct": 28, "fat_pct": 17, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 40,
     "main_protein_sources": ["ягнёнок", "курица"], "grain_sources": [],
     "preservatives": "натуральные (токоферолы)", "splitting_detected": False,
     "pros": ["Мясо 40% (курица 27% + ягнятина 13%)", "Беззерновой (картофель/горох)", "Доступная цена, РФ"],
     "cons": ["Содержит курицу (частый аллерген)"],
     "special_traits": ["grain_free"], "allergens_absent": ["corn", "wheat", "soy"],
     "availability_ru": "stable", "buy_links": L("мираторг+pro+meat")},

    {"id": "jarvi_adult_medium_large", "brand": "Jarvi", "name": "Adult Medium & Large Breeds",
     "country": "Россия", "price_category": "mid", "price_per_kg": 540,
     "size_suitable": ["medium", "large"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["дегидрированное мясо курицы 15%", "дегидрированное мясо индейки 12%",
                          "дегидрированное мясо говядины 8%", "рис", "животный жир"],
     "protein_pct": 26, "fat_pct": 17, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 35,
     "main_protein_sources": ["курица", "индейка", "говядина"], "grain_sources": ["рис"],
     "preservatives": "натуральные (токоферолы)", "splitting_detected": False,
     "pros": ["Три мяса с процентами", "Рыбий жир (Омега-3)", "Холистик, РФ"],
     "cons": ["Содержит курицу/говядину (частые аллергены)"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("jarvi+собак")},

    {"id": "zooring_original_veal_rice", "brand": "ZooRing", "name": "Original Formula Veal & Rice",
     "country": "Россия", "price_category": "mid", "price_per_kg": 400,
     "size_suitable": ["mini", "small", "medium", "large"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["обезвоженное мясо и мясные ингредиенты 33% (телятина, птица)", "рис", "кукуруза",
                          "пшеничные отруби", "животный жир"],
     "protein_pct": 24, "fat_pct": 13, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 33,
     "main_protein_sources": ["телятина", "птица"], "grain_sources": ["рис", "кукуруза", "пшеница"],
     "preservatives": "натуральные (токоферолы)", "splitting_detected": True,
     "pros": ["Мясо 33% (телятина — основа)", "Российское производство"],
     "cons": ["Рис + кукуруза + пшеничные отруби", "Обобщённые «мясные ингредиенты»"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("zooring+собак")},
]


def main():
    db = json.load(open(DB, encoding="utf-8"))
    existing = {f["id"] for f in db["foods"]}
    added = 0
    for f in NEW:
        if f["id"] in existing:
            print(f"уже есть: {f['id']}")
            continue
        db["foods"].append(f)
        added += 1
        print(f"+ {f['brand']} {f['name']}")
    json.dump(db, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nдобавлено {added}, всего кормов: {len(db['foods'])}")


if __name__ == "__main__":
    main()
