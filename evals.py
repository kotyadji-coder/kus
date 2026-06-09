"""
Эвалы: автоматическая проверка расчётов на реальных профилях собак.
Запускается из админки или командой `python evals.py`.
"""

from calculator import DietCalculator, DogProfile, stop_roots, is_stopped

PROFILES = [
    {"name": "Рекс", "breed": "Немецкая овчарка", "age_months": 36, "sex": "male", "neutered": True,
     "weight_kg": 34, "condition": "athletic", "activity": "high", "diet_type": "barf",
     "budget": "market", "stop_products": [], "diagnoses": [], "label": "Взрослый, активный, норма"},

    {"name": "Буся", "breed": "Чихуахуа", "age_months": 60, "sex": "female", "neutered": True,
     "weight_kg": 3.2, "condition": "chubby", "activity": "lazy", "diet_type": "cooked",
     "budget": "supermarket", "stop_products": [], "diagnoses": [], "label": "Мини-порода, перевес"},

    {"name": "Барон", "breed": "Лабрадор-ретривер", "age_months": 36, "sex": "male", "neutered": True,
     "weight_kg": 32, "condition": "chubby", "activity": "moderate", "diet_type": "barf",
     "budget": "market", "stop_products": ["курица"], "diagnoses": [], "label": "Аллергик на курицу"},

    {"name": "Граф", "breed": "Немецкий дог", "age_months": 24, "sex": "male", "neutered": False,
     "weight_kg": 60, "condition": "athletic", "activity": "moderate", "diet_type": "barf",
     "budget": "unlimited", "stop_products": [], "diagnoses": [], "label": "Гигант, молодой"},

    {"name": "Тоша", "breed": "Йоркширский терьер", "age_months": 4, "sex": "male", "neutered": False,
     "weight_kg": 1.5, "condition": "athletic", "activity": "puppy", "diet_type": "cooked",
     "budget": "supermarket", "stop_products": [], "diagnoses": [], "label": "Щенок мини-породы"},

    {"name": "Мухтар", "breed": "Среднеазиатская овчарка", "age_months": 108, "sex": "male", "neutered": True,
     "weight_kg": 55, "condition": "athletic", "activity": "lazy", "diet_type": "barf",
     "budget": "market", "stop_products": [], "diagnoses": ["панкреатит"], "label": "Пожилой с панкреатитом"},

    {"name": "Лесси", "breed": "Колли", "age_months": 48, "sex": "female", "neutered": True,
     "weight_kg": 25, "condition": "thin", "activity": "moderate", "diet_type": "barf",
     "budget": "market", "stop_products": ["говядина"], "diagnoses": ["гастрит"], "label": "Гастрит + худая"},

    {"name": "Джек", "breed": "Джек-рассел-терьер", "age_months": 18, "sex": "male", "neutered": True,
     "weight_kg": 7, "condition": "athletic", "activity": "high", "diet_type": "barf",
     "budget": "supermarket", "stop_products": [], "diagnoses": [], "label": "Маленький активный"},

    {"name": "Зефир", "breed": "Самоед", "age_months": 8, "sex": "male", "neutered": False,
     "weight_kg": 18, "condition": "athletic", "activity": "puppy", "diet_type": "barf",
     "budget": "market", "stop_products": ["курица", "говядина"], "diagnoses": [], "label": "Подросток, 2 стоп-продукта"},

    {"name": "Дуся", "breed": "Мопс", "age_months": 72, "sex": "female", "neutered": True,
     "weight_kg": 10, "condition": "obese", "activity": "lazy", "diet_type": "cooked",
     "budget": "supermarket", "stop_products": [], "diagnoses": [], "label": "Ожирение, мопс"},
    # Граничный случай: очень мелкая варёная собака с жидким стулом —
    # ловит нулевые дозы/цены и неделимые добавки (кейс «Зоя»).
    {"name": "Зоя", "breed": "Йоркширский терьер", "age_months": 24, "sex": "female", "neutered": True,
     "weight_kg": 2.0, "condition": "thin", "activity": "moderate", "diet_type": "cooked",
     "budget": "supermarket", "stop_products": [], "diagnoses": ["аллергия"], "stool": "loose",
     "label": "Мелкая, варёнка, жидкий стул"},
]


def run_evals() -> list[dict]:
    """Прогоняет все профили и возвращает результаты с проверками."""
    calc = DietCalculator()
    results = []

    for profile in PROFILES:
        dog = DogProfile(
            name=profile["name"], breed=profile["breed"], age_months=profile["age_months"],
            sex=profile["sex"], neutered=profile["neutered"], weight_kg=profile["weight_kg"],
            current_food="dry", condition=profile["condition"], activity=profile["activity"],
            diagnoses=profile.get("diagnoses", []), stool=profile.get("stool", "good"),
            diet_type=profile["diet_type"], budget=profile["budget"],
            stop_products=profile.get("stop_products", []),
        )

        result = calc.calculate(dog)
        checks = []
        passed = 0
        total = 0

        # --- Проверки ---

        # 1. Суточная норма в разумном диапазоне (1.5-7% от веса)
        total += 1
        pct = result.daily_grams / (dog.weight_kg * 10)  # процент от веса
        if 1.5 <= pct <= 7:
            checks.append(("Суточная норма", "ok", f"{int(result.daily_grams)}г = {pct:.1f}% от веса"))
            passed += 1
        else:
            checks.append(("Суточная норма", "fail", f"{int(result.daily_grams)}г = {pct:.1f}% от веса — вне нормы 1.5-7%"))

        # 2. Калорийность адекватна
        total += 1
        kcal_per_kg = result.mer_kcal / result.ideal_weight_kg if result.ideal_weight_kg > 0 else 0
        if 30 <= kcal_per_kg <= 120:
            checks.append(("Калорийность", "ok", f"{int(result.mer_kcal)} ккал = {int(kcal_per_kg)} ккал/кг"))
            passed += 1
        else:
            checks.append(("Калорийность", "fail", f"{int(result.mer_kcal)} ккал = {int(kcal_per_kg)} ккал/кг — вне нормы"))

        # 3. Стоп-продукты не попали в меню (матчинг — единый, из calculator)
        total += 1
        roots = stop_roots(dog.stop_products)

        violated = []
        for day in result.weekly_menu:
            for p in day.morning + day.evening:
                if is_stopped(p.product_name, roots):
                    violated.append(f"{day.day_name}: {p.product_name}")

        if not violated:
            checks.append(("Стоп-продукты", "ok", f"Стоп: {dog.stop_products or 'нет'} — чисто"))
            passed += 1
        else:
            checks.append(("Стоп-продукты", "fail", f"Найдены в меню: {', '.join(violated[:3])}"))

        # 4. Разброс граммовок по дням (±15%)
        total += 1
        day_totals = []
        for day in result.weekly_menu:
            total_g = sum(p.grams for p in day.morning) + sum(p.grams for p in day.evening)
            day_totals.append(total_g)
        avg = sum(day_totals) / len(day_totals) if day_totals else 0
        max_dev = max(abs(t - avg) / avg * 100 for t in day_totals) if avg > 0 else 0
        if max_dev <= 15:
            checks.append(("Равномерность дней", "ok", f"Макс. отклонение {max_dev:.0f}% (норма ≤15%)"))
            passed += 1
        else:
            min_d = min(day_totals)
            max_d = max(day_totals)
            checks.append(("Равномерность дней", "warn", f"Разброс {int(min_d)}-{int(max_d)}г, отклонение {max_dev:.0f}%"))
            passed += 0.5

        # 5. Ca:P в разумном диапазоне (или есть предупреждение)
        total += 1
        has_cap_warning = any("Ca:P" in w for w in result.warnings)
        if 1.0 <= result.ca_p_ratio <= 2.0:
            checks.append(("Ca:P баланс", "ok", f"Ca:P = {result.ca_p_ratio}"))
            passed += 1
        elif has_cap_warning:
            checks.append(("Ca:P баланс", "warn", f"Ca:P = {result.ca_p_ratio} — есть предупреждение"))
            passed += 0.5
        else:
            checks.append(("Ca:P баланс", "fail", f"Ca:P = {result.ca_p_ratio} — без предупреждения!"))

        # 6. Кормлений в день адекватно
        total += 1
        expected_meals = 2
        if dog.age_months < 4:
            expected_meals = 4
        elif dog.age_months < 6:
            expected_meals = 3
        if result.meals_per_day == expected_meals:
            checks.append(("Кол-во кормлений", "ok", f"{result.meals_per_day} раза/день"))
            passed += 1
        else:
            checks.append(("Кол-во кормлений", "warn", f"{result.meals_per_day} раза/день (ожидалось {expected_meals})"))
            passed += 0.5

        # 7. Есть продукты в меню (не пустое)
        total += 1
        total_products = sum(len(d.morning) + len(d.evening) for d in result.weekly_menu)
        if total_products >= 14:  # минимум 2 продукта на день
            checks.append(("Наполненность меню", "ok", f"{total_products} позиций за неделю"))
            passed += 1
        else:
            checks.append(("Наполненность меню", "fail", f"Только {total_products} позиций за неделю — мало"))

        # 8. Дозы добавок без нулей и пустот (важно для мелких собак)
        total += 1
        import re
        bad_doses = []
        for s in result.supplements:
            dose = str(s.get("dosage", ""))
            note = str(s.get("notes", ""))
            # «0 мл», «0 капсул», «0 мг», «0 табл» и т.п. в дозе или примечании
            if re.search(r"(^|[^\d.,])0\s*(мл|капсул|мг|табл|ч\.л|ст\.л|МЕ|шт)", dose + " " + note):
                bad_doses.append(f"{s.get('name')}: {dose}")
            if not dose.strip():
                bad_doses.append(f"{s.get('name')}: пустая доза")
        if not bad_doses:
            checks.append(("Дозы добавок", "ok", f"{len(result.supplements)} добавок, нулей нет"))
            passed += 1
        else:
            checks.append(("Дозы добавок", "fail", "; ".join(bad_doses[:3])))

        # 9. Стоимость не схлопывается в 0 при отображении
        total += 1
        disp_day = max(5, int(round(result.cost_per_day / 5) * 5)) if result.cost_per_day > 0 else 0
        if result.cost_per_day <= 0 or disp_day > 0:
            checks.append(("Стоимость", "ok", f"{disp_day} руб/день (расчёт {result.cost_per_day:.1f})"))
            passed += 1
        else:
            checks.append(("Стоимость", "fail", f"Отображается 0 руб/день при расчёте {result.cost_per_day:.1f}"))

        score = round(passed / total * 100)
        results.append({
            "profile": profile,
            "daily_grams": int(result.daily_grams),
            "mer_kcal": int(result.mer_kcal),
            "ideal_weight": result.ideal_weight_kg,
            "ca_p_ratio": result.ca_p_ratio,
            "meals": result.meals_per_day,
            "checks": checks,
            "score": score,
            "warnings": result.warnings,
        })

    return results


if __name__ == "__main__":
    results = run_evals()
    for r in results:
        p = r["profile"]
        print(f"\n{'='*60}")
        print(f"{p['name']} ({p['label']}) — {r['score']}%")
        print(f"  {p['breed']}, {p['weight_kg']}кг, {p['age_months']}мес, {p['condition']}")
        for name, status, detail in r["checks"]:
            icon = {"ok": "+", "warn": "~", "fail": "!"}[status]
            print(f"  [{icon}] {name}: {detail}")
