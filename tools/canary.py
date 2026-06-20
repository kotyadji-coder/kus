"""
Канарейка — «кто проверяет проверяющего». Намеренно ломаем отчёт каждым известным
багом и убеждаемся, что детектор (reconcile.py) его ЛОВИТ. Если канарейка «жива»
(баг не пойман) — сломан сам детектор, а не рацион. Плюс проверяем, что на ЧИСТОМ
отчёте ложных срабатываний нет.

  python tools/canary.py   # exit 0 — детектор живой; exit 1 — детектор ослеп

Это то, что делает систему самопроверяемой: ночной прогон канарейки доказывает,
что зелёные эвалы означают «багов нет», а не «детектор молчит».
"""
import sys, os, copy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculator import DietCalculator, DogProfile
import pdf_generator
from reconcile import reconciliation_checks, violations


def _base():
    dog = DogProfile(name="Граф", breed="Немецкий дог", age_months=48, sex="male",
                     neutered=False, weight_kg=60.0, current_food="dry", condition="athletic",
                     activity="moderate", diagnoses=[], stool="good", diet_type="barf",
                     budget="market", stop_products=[], season="neutral")
    res = DietCalculator().calculate(dog)
    return res, pdf_generator.generate_html(res)


def _failed(checks, key):
    return any(c["key"] == key and c["status"] == "fail" for c in checks)


def main():
    res, html = _base()
    misses = []  # инъекции, которые детектор НЕ поймал

    # 0. Чистый отчёт — ложных срабатываний быть не должно.
    if violations(res, html):
        misses.append(f"ложное срабатывание на чистом отчёте: {[v['key'] for v in violations(res, html)]}")

    # 1. Баг слотов: меню рисует не столько слотов, сколько кормлений.
    r1 = copy.deepcopy(res)
    r1.meals_per_day += 1
    if not _failed(reconciliation_checks(r1, None), "Слоты = кормления"):
        misses.append("не пойман баг слотов (меню ≠ кормлений)")

    # 2. Группа в сводке, но не в меню (как было с субпродуктами под стоп-листом).
    r2 = copy.deepcopy(res)
    r2.distribution["phantom_group"] = 500
    if not _failed(reconciliation_checks(r2, None), "Группы сводки = меню"):
        misses.append("не пойман баг выпавшей группы")

    # 3. Единица яйца: сводка ≠ список покупок (перепелиное 10г vs хардкод 60г).
    bad_egg = ('<span class="nm">Яйца</span> <span class="g" style="float:right;">3 шт./нед.</span>'
               '<td class="nm">Яйцо перепелиное</td><td class="g" style="padding-left:8px;">17 шт.</td>')
    if not _failed(reconciliation_checks(res, bad_egg), "Яйцо: сводка = покупки"):
        misses.append("не пойман баг единицы яйца")

    # 4. Нулевая порция в отчёте.
    if not _failed(reconciliation_checks(res, html + '<span class="g">0 г</span>'), "Нет нулей / ложки уместны"):
        misses.append("не пойман баг нулевой порции")

    # 5. Зазор «суточная норма ≠ сумма групп» (как было 565 г vs 520 г).
    r5 = copy.deepcopy(res)
    r5.daily_grams = int(r5.daily_grams * 1.3)  # норма раздута, группы не тронуты
    if not _failed(reconciliation_checks(r5, None), "Норма = сумма групп"):
        misses.append("не пойман зазор норма ≠ сумма групп")

    if misses:
        print("✗ ДЕТЕКТОР ОСЛЕП — не поймал инъекции:")
        for m in misses:
            print(f"    - {m}")
        return 1
    print("✓ Канарейка жива: детектор ловит все 5 инъекций, ложных срабатываний нет")
    return 0


if __name__ == "__main__":
    sys.exit(main())
