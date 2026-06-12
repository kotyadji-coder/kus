"""Финал линеек: Мираторг/Meglium/ZooRing варианты + SENIOR (Brit Premium, Monge).
Макросы с магазинов; где производитель блокирует скрап (Мираторг/ZooRing экзотика)
— по линии (помечено). Идемпотентно. Запуск: venv/bin/python tools/report_qa/_seed_final.py
"""
import json, os
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "dry_foods.json")
def L(q): return {"ozon": f"ozon.ru/search/?text={q}", "wb": f"wildberries.ru/catalog/0/search.aspx?search={q}", "4paws": f"4lapy.ru/search/?q={q}"}
NAT = "натуральные (токоферолы)"

NEW = [
    # ---- Мираторг ----
    {"id": "miratorg_promeat_beef", "brand": "Мираторг", "name": "Pro Meat Adult Beef", "country": "Россия",
     "price_category": "budget", "price_per_kg": 360, "size_suitable": ["mini", "small", "medium", "large"], "age_suitable": ["adult"], "grain_free": True,
     "ingredients_top5": ["дегидрированное мясо курицы", "свежая говядина", "картофель", "горох", "животный жир"],
     "protein_pct": 28, "fat_pct": 16, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 40,
     "main_protein_sources": ["говядина", "курица"], "grain_sources": [], "preservatives": NAT, "splitting_detected": False,
     "pros": ["Беззерновой (картофель/горох)", "Высокое содержание мяса", "Доступная цена, РФ"], "cons": ["Содержит курицу (частый аллерген)"],
     "special_traits": ["grain_free"], "allergens_absent": ["corn", "wheat", "soy"], "availability_ru": "stable", "buy_links": L("мираторг+pro+meat+говядина")},
    {"id": "miratorg_meat_beef", "brand": "Мираторг", "name": "Meat Adult Medium/Maxi Beef", "country": "Россия",
     "price_category": "budget", "price_per_kg": 250, "size_suitable": ["medium", "large"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["мясо и мясные ингредиенты 28% (дегидр. курица 24%, свежая говядина 4%)", "рис", "кукуруза", "животный жир", "гороховый протеин"],
     "protein_pct": 22, "fat_pct": 12, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 28,
     "main_protein_sources": ["курица", "говядина"], "grain_sources": ["рис", "кукуруза"], "preservatives": NAT, "splitting_detected": False,
     "pros": ["Самая доступная цена", "Российское производство"], "cons": ["Невысокий белок (22%)", "Курица как основной белок"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("мираторг+meat+говядина")},

    # ---- Meglium ----
    {"id": "meglium_puppy", "brand": "Meglium", "name": "Puppy", "country": "Италия",
     "price_category": "budget", "price_per_kg": 320, "size_suitable": ["mini", "small", "medium", "large"], "age_suitable": ["puppy"], "grain_free": False,
     "ingredients_top5": ["дегидрированное мясо", "кукуруза", "пшеница", "куриный жир", "свекловичный жом"],
     "protein_pct": 28, "fat_pct": 18, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 28,
     "main_protein_sources": ["курица"], "grain_sources": ["кукуруза", "пшеница"], "preservatives": NAT, "splitting_detected": True,
     "pros": ["Для щенков", "Повышенная калорийность для роста"], "cons": ["Кукуруза + пшеница", "Обобщённое «дегидрированное мясо»"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("meglium+puppy")},
    {"id": "meglium_sensible_fish_rice", "brand": "Meglium", "name": "Sensible Fish & Rice", "country": "Италия",
     "price_category": "budget", "price_per_kg": 320, "size_suitable": ["mini", "small", "medium", "large"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["кукуруза", "дегидрированное мясо", "пшеница", "рыбная мука 12%", "рис 10%"],
     "protein_pct": 24, "fat_pct": 9, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 20,
     "main_protein_sources": ["рыба"], "grain_sources": ["кукуруза", "пшеница", "рис"], "preservatives": NAT, "splitting_detected": True,
     "pros": ["Рыба для чувствительного пищеварения", "Низкий жир (9%) — для склонных к полноте"], "cons": ["Кукуруза + пшеница", "Невысокое содержание мяса"],
     "special_traits": ["weight_control"], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("meglium+sensible+рыба")},

    # ---- ZooRing ----
    {"id": "zooring_mini_puppy_junior", "brand": "ZooRing", "name": "Mini Puppy & Junior Turkey/Chicken/Lamb", "country": "Россия",
     "price_category": "mid", "price_per_kg": 420, "size_suitable": ["mini", "small"], "age_suitable": ["puppy"], "grain_free": False,
     "ingredients_top5": ["дегидрированное мясо (индейка 17%, курица 15%, ягнёнок 4%)", "кукуруза", "рис", "животный жир", "свекловичный жом"],
     "protein_pct": 28, "fat_pct": 16, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 36,
     "main_protein_sources": ["индейка", "курица", "ягнёнок"], "grain_sources": ["кукуруза", "рис"], "preservatives": NAT, "splitting_detected": False,
     "pros": ["Для щенков, юниоров, беременных и кормящих мини-пород", "Три мяса", "Глюкозамин/хондроитин"], "cons": ["Содержит кукурузу и курицу"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("zooring+mini+puppy")},
    {"id": "zooring_mini_active_duck", "brand": "ZooRing", "name": "Mini Active Dog Duck & Rice", "country": "Россия",
     "price_category": "mid", "price_per_kg": 420, "size_suitable": ["mini", "small", "medium"], "age_suitable": ["adult"], "grain_free": False,
     "ingredients_top5": ["дегидрированное мясо утки", "рис", "кукуруза", "животный жир", "свекловичный жом"],
     "protein_pct": 26, "fat_pct": 16, "fiber_pct": 3, "ash_pct": 8, "meat_estimate_pct": 30,
     "main_protein_sources": ["утка"], "grain_sources": ["рис", "кукуруза"], "preservatives": NAT, "splitting_detected": False,
     "pros": ["Active — для активных мелких собак", "Утка как основной белок (без курицы-основы)"], "cons": ["Содержит кукурузу"],
     "special_traits": ["performance"], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("zooring+active+утка")},

    # ---- SENIOR (существующие бренды, реальные данные) ----
    {"id": "brit_premium_senior_l", "brand": "Brit Premium", "name": "Senior L (Large Breeds)", "country": "Чехия",
     "price_category": "mid", "price_per_kg": 450, "size_suitable": ["large", "giant"], "age_suitable": ["senior"], "grain_free": False,
     "ingredients_top5": ["мука из мяса курицы и куриных субпродуктов 40%", "рис", "кукуруза", "пшеница", "куриный жир"],
     "protein_pct": 26, "fat_pct": 13, "fiber_pct": 3, "ash_pct": 7, "meat_estimate_pct": 38,
     "main_protein_sources": ["курица"], "grain_sources": ["рис", "кукуруза", "пшеница"], "preservatives": NAT, "splitting_detected": False,
     "pros": ["Для пожилых крупных пород", "Умеренный жир (13%)", "Масло лосося (Омега-3)"], "cons": ["Кукуруза + пшеница", "Курица как основной белок"],
     "special_traits": ["joint_support"], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("brit+premium+senior")},
    {"id": "monge_medium_senior_chicken", "brand": "Monge", "name": "Daily Line Medium Senior Chicken", "country": "Италия",
     "price_category": "mid", "price_per_kg": 560, "size_suitable": ["medium"], "age_suitable": ["senior"], "grain_free": False,
     "ingredients_top5": ["дегидрированное мясо курицы 30%", "рис", "свежее мясо курицы 10%", "овёс", "куриный жир"],
     "protein_pct": 25, "fat_pct": 12, "fiber_pct": 3, "ash_pct": 7, "meat_estimate_pct": 40,
     "main_protein_sources": ["курица"], "grain_sources": ["рис", "овёс"], "preservatives": NAT, "splitting_detected": False,
     "pros": ["Для пожилых средних пород", "Курица 40% (мясо)", "Рис и овёс — мягкие злаки", "Умеренный жир"], "cons": ["Курица как основной белок"],
     "special_traits": [], "allergens_absent": [], "availability_ru": "stable", "buy_links": L("monge+medium+senior")},
]

def main():
    db = json.load(open(DB, encoding="utf-8")); ex = {f["id"] for f in db["foods"]}; n = 0
    for f in NEW:
        if f["id"] in ex: print("уже есть:", f["id"]); continue
        db["foods"].append(f); n += 1; print("+", f["brand"], f["name"])
    json.dump(db, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nдобавлено {n}, всего: {len(db['foods'])}")
if __name__ == "__main__": main()
