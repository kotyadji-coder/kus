"""Разовый сид: добавляет гидролизатные вет-диеты в data/dry_foods.json.
Макросы — из гарантированного анализа производителей (см. ROADMAP/коммит).
meat_estimate и price — оценка (помечено). Идемпотентно по id.
Запуск: venv/bin/python tools/report_qa/_seed_foods.py
"""
import json
import os

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "dry_foods.json")


def _links(q):
    return {"ozon": f"ozon.ru/search/?text={q}", "wb": f"wildberries.ru/catalog/0/search.aspx?search={q}",
            "4paws": f"4lapy.ru/search/?q={q}"}


NEW = [
    {
        "id": "royal_canin_anallergenic", "brand": "Royal Canin", "name": "Veterinary Anallergenic",
        "country": "Франция", "price_category": "premium", "price_per_kg": 1450,
        "size_suitable": ["mini", "small", "medium", "large"], "age_suitable": ["adult"], "grain_free": False,
        "ingredients_top5": ["кукурузный крахмал", "гидролизат пера (низкомолекулярный)", "кокосовое масло",
                             "соевое масло", "свекловичный жом"],
        "protein_pct": 18, "fat_pct": 16, "fiber_pct": 2, "ash_pct": 7, "meat_estimate_pct": 20,
        "main_protein_sources": ["гидролизат пера"], "grain_sources": ["кукуруза"],
        "preservatives": "натуральные (токоферолы)", "splitting_detected": False,
        "pros": ["Гидролизат пера — белок расщеплён до олигопептидов, не распознаётся иммунитетом",
                 "Для собак с аллергией сразу на несколько белков", "Назначается при тяжёлой пищевой аллергии/атопии"],
        "cons": ["Лечебная диета — давать по назначению ветврача", "Высокая цена", "Содержит кукурузный крахмал"],
        "special_traits": ["hypoallergenic", "hydrolyzed"],
        "allergens_absent": ["chicken", "beef", "lamb", "fish", "wheat"],
        "availability_ru": "stable", "buy_links": _links("royal+canin+anallergenic"),
    },
    {
        "id": "proplan_vet_ha_hydrolyzed", "brand": "Pro Plan Veterinary", "name": "HA Hydrolyzed Canine",
        "country": "США/Италия", "price_category": "premium", "price_per_kg": 1150,
        "size_suitable": ["mini", "small", "medium", "large"], "age_suitable": ["puppy", "adult", "senior"], "grain_free": False,
        "ingredients_top5": ["кукурузный крахмал", "гидролизат изолята соевого белка", "кокосовое масло",
                             "рапсовое масло", "целлюлоза"],
        "protein_pct": 18, "fat_pct": 9, "fiber_pct": 4, "ash_pct": 7, "meat_estimate_pct": 12,
        "main_protein_sources": ["гидролизат сои"], "grain_sources": ["кукуруза"],
        "preservatives": "TBHQ", "splitting_detected": False,
        "pros": ["Гидролизованный соевый белок — гипоаллергенный", "Все стадии жизни", "МСТ (кокосовое масло)"],
        "cons": ["Лечебная диета — по назначению ветврача", "Растительный белок (соя)", "Содержит кукурузный крахмал"],
        "special_traits": ["hypoallergenic", "hydrolyzed"],
        "allergens_absent": ["chicken", "beef", "lamb", "fish", "wheat"],
        "availability_ru": "unstable", "buy_links": _links("pro+plan+ha+hydrolyzed"),
    },
    {
        "id": "hills_zd_hydrolyzed", "brand": "Hills", "name": "Prescription Diet z/d Food Sensitivities",
        "country": "США/Нидерланды", "price_category": "premium", "price_per_kg": 1150,
        "size_suitable": ["mini", "small", "medium", "large"], "age_suitable": ["adult"], "grain_free": False,
        "ingredients_top5": ["кукурузный крахмал", "гидролизат куриной печени", "гидролизат курицы",
                             "молотая скорлупа пекана", "целлюлоза"],
        "protein_pct": 15, "fat_pct": 11, "fiber_pct": 8, "ash_pct": 7, "meat_estimate_pct": 20,
        "main_protein_sources": ["гидролизат курицы"], "grain_sources": ["кукуруза"],
        "preservatives": "натуральные (токоферолы)", "splitting_detected": False,
        "pros": ["Сильно гидролизованный белок — не распознаётся иммунитетом", "Омега-3/6 для кожи",
                 "Для пищевой аллергии и непереносимости"],
        "cons": ["Лечебная диета — по назначению ветврача", "Высокая клетчатка", "Содержит кукурузный крахмал"],
        "special_traits": ["hypoallergenic", "hydrolyzed", "skin_coat"],
        "allergens_absent": ["chicken", "beef", "lamb", "fish", "wheat", "soy"],
        "availability_ru": "unstable", "buy_links": _links("hills+z%2Fd"),
    },
    {
        "id": "farmina_vetlife_ultrahypo", "brand": "Farmina Vet Life", "name": "UltraHypo Canine",
        "country": "Италия", "price_category": "premium", "price_per_kg": 1050,
        "size_suitable": ["mini", "small", "medium", "large"], "age_suitable": ["adult"], "grain_free": False,
        "ingredients_top5": ["рисовый крахмал", "гидролизат рыбного белка", "рыбий жир",
                             "хлорид калия", "карбонат кальция"],
        "protein_pct": 18, "fat_pct": 15, "fiber_pct": 1, "ash_pct": 5, "meat_estimate_pct": 22,
        "main_protein_sources": ["гидролизат рыбы"], "grain_sources": ["рис"],
        "preservatives": "натуральные (токоферолы)", "splitting_detected": False,
        "pros": ["Гидролизат рыбы + рисовый крахмал — без кукурузы/пшеницы/сои",
                 "Моно-белок, элиминационная диета", "Высокие Омега-3 (рыбий жир)"],
        "cons": ["Лечебная диета — по назначению ветврача", "Высокая цена"],
        "special_traits": ["hypoallergenic", "hydrolyzed", "grain_free"],
        "allergens_absent": ["chicken", "beef", "lamb", "fish", "corn", "wheat", "soy"],
        "availability_ru": "stable", "buy_links": _links("farmina+vet+life+ultrahypo"),
    },
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
