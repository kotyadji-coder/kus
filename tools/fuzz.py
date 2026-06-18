"""
Фаззинг расчёта: генерим случайных собак по всей сетке параметров и гоняем
инварианты согласования (reconcile.py). Баги живут в углах, которые человек не
перечислил в эталонных профилях — фаззер их ищет «снова и снова».

  python tools/fuzz.py            # 300 профилей, seed=1 (воспроизводимо)
  python tools/fuzz.py 1000 7     # 1000 профилей, seed=7

Exit 1 при любом нарушении (для ночного крона/алерта). Каждое нарушение печатается
с ПОЛНЫМИ параметрами — чтобы воспроизвести и превратить в постоянный профиль/инвариант.
"""
import sys, os, json, random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculator import DietCalculator, DogProfile
import pdf_generator
from reconcile import violations

# Породы с реалистичным диапазоном взрослого веса (кг). Фаззер берёт вес ИЗ
# диапазона породы, а не 1-95 наугад: иначе генерятся химеры (7-кг сенбернар,
# 48-кг мопс), и ночь алертит на нарушения, которых в жизни не бывает.
BREED_WEIGHT = {
    "Немецкая овчарка": (22, 40), "Чихуахуа": (1.5, 3), "Лабрадор-ретривер": (25, 36),
    "Немецкий дог": (45, 90), "Йоркширский терьер": (2, 3.5), "Среднеазиатская овчарка": (40, 80),
    "Мопс": (6, 9), "Такса": (4, 9), "Сенбернар": (55, 90), "Метис": (4, 40),
    "Шпиц": (1.5, 3.5), "Бигль": (9, 14), "Ротвейлер": (35, 60), "Той-терьер": (1.5, 3),
}
BREEDS = list(BREED_WEIGHT)
CONDITIONS = ["thin", "athletic", "chubby", "obese"]
ADULT_ACTIVITIES = ["lazy", "moderate", "high"]
DIETS = ["barf", "cooked"]
BUDGETS = ["supermarket", "market", "unlimited"]
SEASONS = ["winter", "summer", "neutral"]
MEATS = ["курица", "говядина", "индейка", "рыба", "баранина"]
DIAGS = [[], [], [], ["аллергия"], ["гастрит"], ["панкреатит"], ["аллергия", "гастрит"]]


def random_profile(rnd: random.Random) -> dict:
    sex = rnd.choice(["male", "female"])
    nstops = rnd.choices([0, 1, 2, 3], weights=[5, 3, 2, 1])[0]
    breed = rnd.choice(BREEDS)
    age = rnd.choice([2, 3, 4, 5, 7, 10, 14, 18, 24, 36, 60, 96, 132])

    lo, hi = BREED_WEIGHT[breed]
    weight = rnd.uniform(lo, hi)
    if age < 12:                       # щенок ещё не набрал взрослый вес
        weight *= max(0.25, min(1.0, age / 12))
    weight = round(weight, 1)

    # «puppy»-активность согласована с возрастом; взрослым — обычная активность
    activity = "puppy" if age < 12 else rnd.choice(ADULT_ACTIVITIES)
    pregnant = sex == "female" and age >= 12 and rnd.random() < 0.1
    lactating = sex == "female" and age >= 12 and not pregnant and rnd.random() < 0.1
    return {
        "name": "Фz", "breed": breed, "age_months": age,
        "sex": sex, "neutered": rnd.random() < 0.5, "weight_kg": weight,
        "condition": rnd.choice(CONDITIONS), "activity": activity,
        "diet_type": rnd.choice(DIETS), "budget": rnd.choice(BUDGETS),
        "stop_products": rnd.sample(MEATS, nstops),
        "diagnoses": rnd.choice(DIAGS),
        "pregnant": pregnant, "lactating": lactating,
        "season": rnd.choice(SEASONS),
    }


def run(n: int, seed: int) -> list[dict]:
    rnd = random.Random(seed)
    calc = DietCalculator()
    found = []
    for i in range(n):
        p = random_profile(rnd)
        dog = DogProfile(
            name=p["name"], breed=p["breed"], age_months=p["age_months"], sex=p["sex"],
            neutered=p["neutered"], weight_kg=p["weight_kg"], current_food="dry",
            condition=p["condition"], activity=p["activity"], diagnoses=p["diagnoses"],
            stool="good", diet_type=p["diet_type"], budget=p["budget"],
            stop_products=p["stop_products"], pregnant=p["pregnant"],
            lactating=p["lactating"], season=p["season"],
        )
        try:
            res = calc.calculate(dog)
            html = pdf_generator.generate_html(res)
            viol = violations(res, html)
        except Exception as e:
            viol = [{"key": "ИСКЛЮЧЕНИЕ", "detail": f"{type(e).__name__}: {e}"}]
        if viol:
            found.append({"profile": p, "violations": viol})
    return found


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    found = run(n, seed)
    print(f"Фаззинг: {n} профилей (seed={seed}), нарушений: {len(found)}")
    for f in found[:40]:
        keys = ", ".join(v["key"] for v in f["violations"])
        print(f"\n✗ [{keys}]")
        for v in f["violations"]:
            print(f"    {v['key']}: {v['detail']}")
        print(f"    repro: {json.dumps(f['profile'], ensure_ascii=False)}")
    if len(found) > 40:
        print(f"\n… ещё {len(found) - 40} нарушений")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
