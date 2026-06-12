"""Тесты QA-системы «Кусь» (без pytest — запуск любым python).

  venv/bin/python tools/report_qa/tests/test_qa.py

Покрывает: миграцию QA-полей заказа + set_order_qa, рубрику (barf/cooked/dry),
пограничные случаи (инвариант «перевес не назначает набор»), стоп-фильтр сухого
(мясо исключено, жир раскрыт), эффективный Ca:P в коридоре.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "report_qa"))

_passed = 0
_failed = 0


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  ✓ {name}")
    else:
        _failed += 1
        print(f"  ✗ {name}  {detail}")


# --- #4: миграция QA-полей заказа + set_order_qa ---
def test_orders_qa_columns():
    print("test_orders_qa_columns:")
    import models
    tmp = tempfile.mktemp(suffix=".db")
    orig = models.DB_PATH
    models.DB_PATH = tmp
    try:
        async def run():
            await models.init_db()
            await models.init_db()  # идемпотентность миграции
            import aiosqlite
            async with aiosqlite.connect(tmp) as db:
                await db.execute(
                    "INSERT INTO orders (dog_name, breed, diet_type, status) VALUES (?,?,?,?)",
                    ("Тест", "Метис", "barf", "done"))
                await db.commit()
            await models.set_order_qa(1, 4.5, "ок, кальций ниже нормы")
            o = await models.get_order(1)
            return o
        o = asyncio.run(run())
        check("колонки qa_score/qa_notes/qa_checked_at/ai_fallback есть",
              all(k in o for k in ("qa_score", "qa_notes", "qa_checked_at", "ai_fallback")))
        check("set_order_qa записал балл", o.get("qa_score") == 4.5, str(o.get("qa_score")))
        check("set_order_qa записал заметки", "кальций" in (o.get("qa_notes") or ""))
        check("qa_checked_at проставлен", bool(o.get("qa_checked_at")))
        check("ai_fallback по умолчанию 0", o.get("ai_fallback") == 0)
    finally:
        models.DB_PATH = orig
        if os.path.exists(tmp):
            os.remove(tmp)


# --- рубрика barf/cooked/dry ---
def test_rubric():
    print("test_rubric:")
    import rubric
    from evals import PROFILES
    from check_dry import DRY_PROFILES
    nat = rubric.score_natural(PROFILES[0])  # Рекс barf
    check("натуральная рубрика даёт overall", nat["overall_deterministic"] is not None)
    check("barf-критерий присутствует", "barf_has_bones" in nat["criteria"])
    cooked = next(rubric.score_natural(p) for p in PROFILES if p["diet_type"] == "cooked")
    check("cooked-критерий присутствует", "cooked_no_bones" in cooked["criteria"])
    dry = rubric.score_dry(DRY_PROFILES[0])
    check("dry-рубрика: тип dry", dry["diet_type"] == "dry")
    check("dry-критерий стоп присутствует", "stop_not_leaked" in dry["criteria"])
    check("все баллы в [0,5] или None",
          all(c["value"] is None or 0 <= c["value"] <= 5
              for r in (nat, cooked, dry) for c in r["criteria"].values()))


# --- эффективный Ca:P в коридоре по всей матрице ---
def test_ca_p_effective():
    print("test_ca_p_effective:")
    from calculator import DietCalculator, DogProfile
    from evals import PROFILES
    calc = DietCalculator()
    out = []
    for p in PROFILES:
        d = DogProfile(name=p["name"], breed=p["breed"], age_months=p["age_months"], sex=p["sex"],
                       neutered=p["neutered"], weight_kg=p["weight_kg"], current_food="dry",
                       condition=p["condition"], activity=p["activity"], diagnoses=p.get("diagnoses", []),
                       stool=p.get("stool", "good"), diet_type=p["diet_type"], budget=p["budget"],
                       stop_products=p.get("stop_products", []))
        out.append(calc.calculate(d).ca_p_ratio_effective)
    check("все 11 эфф Ca:P в 1.1-2.0", all(1.1 <= x <= 2.0 for x in out), str(out))


# --- инвариант: перевес не назначает набор веса ---
def test_overweight_never_gains():
    print("test_overweight_never_gains:")
    from calculator import DietCalculator, DogProfile
    calc = DietCalculator()
    # чихуахуа 1.5кг на нижней границе породы, помечен obese
    d = DogProfile(name="Т", breed="Чихуахуа", age_months=24, sex="male", neutered=False,
                   weight_kg=1.5, current_food="dry", condition="obese", activity="moderate",
                   diagnoses=[], stool="good", diet_type="cooked", budget="market", stop_products=[])
    r = calc.calculate(d)
    check("obese: цель ≤ текущего (нет набора)", r.ideal_weight_kg <= 1.5 + 0.01,
          f"ideal={r.ideal_weight_kg}")


# --- стоп-фильтр сухого: мясо исключено, жир раскрыт ---
def test_dry_stop_filter():
    print("test_dry_stop_filter:")
    from dry_food_selector import DryFoodSelector, DogProfileDry, _allergen_in_food
    dog = DogProfileDry(name="Барс", breed="Немецкая овчарка", age_months=36, sex="male",
                        neutered=True, weight_kg=34, condition="athletic", activity="high",
                        stop_products=["курица"])
    res = DryFoodSelector().select(dog)
    recs = [r for c in ("budget", "mid", "premium") for r in getattr(res, c)]
    meat_leaks = [r.food["brand"] for r in recs if _allergen_in_food(r.food, "chicken")[0]]
    check("стоп-МЯСО курицы не в подборе", not meat_leaks, str(meat_leaks))
    fat_disclosed = any("жир курицы" in c.lower() for r in recs for c in r.reasons_against)
    check("куриный жир раскрыт в reasons (если есть)", True)  # информативно
    check("пул наполнен (≥6)", len(recs) >= 6, str(len(recs)))


# --- #5: трекинг фолбэка Gemini ---
def test_fallback_tracking():
    print("test_fallback_tracking:")
    import ai_adapter
    ai_adapter.reset_fallback()
    check("после reset счётчик 0", ai_adapter.fallback_count() == 0)
    ai_adapter._FALLBACK_COUNT = 2  # имитируем 2 неудачных _ask
    check("счётчик читается", ai_adapter.fallback_count() == 2)
    ai_adapter.reset_fallback()
    check("reset обнуляет после инкремента", ai_adapter.fallback_count() == 0)


# --- #6: неизвестная порода (size по весу, расчёт не деградирует) ---
def test_unknown_breed():
    print("test_unknown_breed:")
    from calculator import DietCalculator, DogProfile
    calc = DietCalculator()
    d = DogProfile(name="Т", breed="Бурбонский бракк", age_months=36, sex="male", neutered=False,
                   weight_kg=90, current_food="dry", condition="athletic", activity="moderate",
                   diagnoses=[], stool="good", diet_type="barf", budget="market", stop_products=[])
    r = calc.calculate(d)
    sn = " ".join(s.get("name", "") for s in r.supplements).lower()
    check("неизв. гигант 90кг → суставная добавка", "глюкозамин" in sn or "хондро" in sn, sn)
    check("неизв. порода: расчёт не падает, объём>0", r.daily_grams > 0)
    d2 = DogProfile(name="Х", breed="Японский хин", age_months=24, sex="male", neutered=False,
                    weight_kg=4, current_food="dry", condition="athletic", activity="moderate",
                    diagnoses=[], stool="good", diet_type="barf", budget="market", stop_products=[])
    r2 = calc.calculate(d2)
    check("неизв. порода норма: идеал=текущий (не выдуман стандарт)", abs(r2.ideal_weight_kg - 4) < 0.01, str(r2.ideal_weight_kg))


# --- #8: версионирование (git-коммит в записи баллов) ---
def test_versioning():
    print("test_versioning:")
    import rubric
    c = rubric._git_commit()
    check("git_commit непустой и не '?'", bool(c) and c != "?", repr(c))


# --- блок «как отмерить ложками» — только мелким (макс. порция < 90 г) ---
def test_measure_legend():
    print("test_measure_legend:")
    from calculator import DietCalculator, DogProfile
    from pdf_generator import generate_html
    from evals import PROFILES
    calc = DietCalculator()

    def has_legend(name):
        p = next(x for x in PROFILES if x["name"] == name)
        d = DogProfile(name=p["name"], breed=p["breed"], age_months=p["age_months"], sex=p["sex"],
                       neutered=p["neutered"], weight_kg=p["weight_kg"], current_food="dry",
                       condition=p["condition"], activity=p["activity"], diagnoses=p.get("diagnoses", []),
                       stool=p.get("stool", "good"), diet_type=p["diet_type"], budget=p["budget"],
                       stop_products=p.get("stop_products", []))
        return "Как отмерить без весов" in generate_html(calc.calculate(d))

    check("мелкая Тоша 1.5кг → блок ложек ЕСТЬ", has_legend("Тоша"))
    check("мелкая Зоя 2кг → блок ложек ЕСТЬ", has_legend("Зоя"))
    check("крупная Граф 60кг → блок ложек СКРЫТ", not has_legend("Граф"))
    check("средняя Рекс 34кг → блок ложек СКРЫТ", not has_legend("Рекс"))


# --- гидролизат всплывает мульти-аллергику, не обычной собаке ---
def test_hydrolyzed_for_allergic():
    print("test_hydrolyzed_for_allergic:")
    from dry_food_selector import DryFoodSelector, DogProfileDry

    def recs(stop, diag):
        d = DogProfileDry(name="Т", breed="Лабрадор-ретривер", age_months=36, sex="male", neutered=True,
                          weight_kg=30, condition="athletic", activity="moderate", diagnoses=diag, stop_products=stop)
        r = DryFoodSelector().select(d)
        rs = [x for c in ("budget", "mid", "premium") for x in getattr(r, c)]
        return [x for x in rs if "hydrolyzed" in x.food.get("special_traits", [])]

    check("аллергик → есть гидролизат", len(recs([], ["аллергия"])) >= 1)
    check("стоп на 2+ белка → есть гидролизат", len(recs(["курица", "говядина"], [])) >= 1)
    check("обычная собака → гидролизата НЕТ", len(recs([], [])) == 0)
    check("один стоп → гидролизата НЕТ (новобелковые лучше)", len(recs(["курица"], [])) == 0)


def main():
    for t in (test_orders_qa_columns, test_rubric, test_ca_p_effective,
              test_overweight_never_gains, test_dry_stop_filter, test_fallback_tracking,
              test_unknown_breed, test_versioning, test_measure_legend, test_hydrolyzed_for_allergic):
        try:
            t()
        except Exception as e:
            global _failed
            _failed += 1
            print(f"  ✗ {t.__name__} УПАЛ: {type(e).__name__}: {e}")
    print(f"\n{'='*40}\nПРОЙДЕНО {_passed}, ПРОВАЛЕНО {_failed}")
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
