"""Бесплатные детерминированные контент-чеки натурального отчёта (без Gemini).

`pdf_generator.generate_html(result)` детерминирован — AI-нарратив инжектится
отдельно (worker), без него идёт фолбэк-текст. Значит контент HTML можно
проверять бесплатно. Важно: именно в HTML-ТЕКСТЕ (обучающие хардкод-шаблоны),
а НЕ в меню, жил баг со стоп-листом (fix 7fd0a68) — меню фильтровалось, а блок
«Правила BARF» советовал куриные кости. Поэтому это прежде всего РЕГРЕСС-СТРАЖ
того класса багов, плюс дозы/добавки/Ca:P.

Что НЕ проверяем: пагинацию натуралки. Честная высота страниц зависит от длины
реального AI-текста (фолбэк короче → ложно-оптимистично) — это слой платной
матрицы. Сам движок печати уже покрыт check_dry_chromium.py.

Запуск:  venv/bin/python tools/report_qa/check_natural.py
"""
from __future__ import annotations

import html as _html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from calculator import DietCalculator, DogProfile, stop_roots  # noqa: E402
from pdf_generator import generate_html  # noqa: E402
from evals import PROFILES  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# Видимые формы стоп-продукта в тексте (для регресс-стража). Корни матчинга из
# calculator рассчитаны на ИМЕНА продуктов в БД; в свободном тексте слова другие
# («куриные», «куриц»), поэтому здесь — курируемый список форм. Для продукта вне
# карты берём корень из calculator.stop_roots как фолбэк.
STOP_DISPLAY = {
    "курица": ["кури", "куриц", "курят", "курин"],
    "говядина": ["говяд", "говяж"],
    "свинина": ["свин"],
    "баранина": ["баран", "барань"],
    "утка": ["утин", "утк", "утя"],
    "кролик": ["кролик", "кролич"],
    "индейка": ["индей", "индюш"],
    "лосось": ["лосос"],
    "минтай": ["минтай"],
}


def _visible_text(html: str) -> str:
    """HTML -> видимый текст в нижнем регистре (без <style>/<script> и тегов)."""
    html = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = _html.unescape(text)
    return re.sub(r"\s+", " ", text).lower()


def _stop_forms(stop_product: str) -> list[str]:
    key = stop_product.strip().lower()
    if key in STOP_DISPLAY:
        return STOP_DISPLAY[key]
    # фолбэк: корень из единого источника правды
    return list(stop_roots([key])) or [key]


def _check_profile(dog: DogProfile, result) -> list[tuple[str, bool, str]]:
    html = generate_html(result)
    text = _visible_text(html)
    checks: list[tuple[str, bool, str]] = []

    # 1. Регресс-страж: стоп-продукт не протёк в текст (меню/закупка/обучалка)
    leaks = []
    for s in dog.stop_products:
        hits = [f for f in _stop_forms(s) if f in text]
        if hits:
            leaks.append(f"{s}→{','.join(hits)}")
    if dog.stop_products:
        checks.append(("Стоп-лист в тексте", not leaks,
                       "чисто" if not leaks else "ПРОТЁК: " + "; ".join(leaks)))

    # 2. Нет «0» для ненулевых доз/порций (страж мелких собак)
    zero = re.findall(r"\b0\s*(?:мл|капсул\w*|шт|таблет\w*|г)\b", text)
    checks.append(("Нет нулевых доз", not zero,
                   "ок" if not zero else f"найдено: {zero[:5]}"))

    # 3. Добавки отрендерены
    supp_ok = bool(result.supplements) and "добавк" in text
    checks.append(("Добавки в отчёте", supp_ok,
                   f"{len(result.supplements)} добавок" if supp_ok else "блок добавок пуст/не отрендерен"))

    # 4. Ca:P показан и совпадает с расчётом
    cap = f"{result.ca_p_ratio:.2f}".rstrip("0").rstrip(".")
    cap_full = f"{result.ca_p_ratio:.2f}"
    cap_ok = (cap in text) or (cap_full in text) or ("ca:p" in text) or ("ca/p" in text)
    checks.append(("Ca:P показан", cap_ok,
                   f"Ca:P={result.ca_p_ratio}" if cap_ok else "значение Ca:P не найдено в тексте"))

    return checks


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    calc = DietCalculator()
    md = ["# QA · контент натуралки (детерминированно, без Gemini)", ""]
    all_ok = True

    for prof in PROFILES:
        if prof["diet_type"] not in ("barf", "cooked"):
            continue
        dog = DogProfile(
            name=prof["name"], breed=prof["breed"], age_months=prof["age_months"],
            sex=prof["sex"], neutered=prof["neutered"], weight_kg=prof["weight_kg"],
            current_food="dry", condition=prof["condition"], activity=prof["activity"],
            diagnoses=prof.get("diagnoses", []), stool=prof.get("stool", "good"),
            diet_type=prof["diet_type"], budget=prof["budget"],
            stop_products=prof.get("stop_products", []),
        )
        result = calc.calculate(dog)
        checks = _check_profile(dog, result)
        prof_ok = all(ok for _, ok, _ in checks)
        all_ok = all_ok and prof_ok

        stop_lbl = f"стоп={prof.get('stop_products') or '—'}"
        head = f"{'OK ' if prof_ok else 'FAIL'} {prof['name']:8} {prof['diet_type']:7} {stop_lbl}"
        print(head)
        md.append(f"### {'✅' if prof_ok else '🔴'} {prof['name']} · {prof['diet_type']} · {stop_lbl}")
        for title, ok, detail in checks:
            mark = "+" if ok else "!"
            print(f"    [{mark}] {title}: {detail}")
            md.append(f"- {'✅' if ok else '🔴'} **{title}**: {detail}")
        md.append("")

    verdict = "ВСЕ ПРОФИЛИ OK (контент натуралки)" if all_ok else "ЕСТЬ ПРОВАЛЫ В КОНТЕНТЕ"
    print("\n" + verdict)
    md.insert(1, f"_{verdict}_\n")
    report = os.path.join(OUT_DIR, "QA_natural_content.md")
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"Отчёт: {report}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
