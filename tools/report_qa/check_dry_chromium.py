"""Проверка пагинации сухого отчёта движком Chromium (а НЕ WeasyPrint).

Клиент сохраняет PDF кнопкой «Печать» — это Chromium (page.pdf), и он
пагинирует иначе, чем WeasyPrint. Поэтому инвариант «логических секций ==
физических страниц» нужно проверять именно тем движком, которым печатает клиент.

Это Chromium-аналог tools/measure_dry.py. Для каждого профиля evals.PROFILES:
  1. selector.select(dog)               — детерминированно, без Gemini
  2. (опц.) подставляем AI-текст        — чтобы высота карточек была боевой
  3. generate_dry_food_html(result)     — собираем HTML
  4. Chromium page.pdf -> считаем стр.  — физические страницы
  5. сверяем с числом <section class="page"> (логические секции)

OVERFLOW = физических > логических: какая-то секция не влезла в A4 и вытекла,
утащив футер в середину следующего листа.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pypdfium2 as pdfium  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from dry_food_selector import DryFoodSelector, DogProfileDry, generate_dry_food_html  # noqa: E402
from evals import PROFILES  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# Реалистичный по длине AI-текст «Чем подходит»: в боевом отчёте сюда попадает
# 2-3 предложения от Gemini. Пустой ai_analysis даёт фолбэк на reasons_for[0]
# (короче) -> карточки ниже -> ложно-оптимистичная пагинация. Подставляем текст
# типичной длины, чтобы высота карточек совпадала с боевой.
FAKE_AI = (
    "Сбалансированный состав с понятными источниками белка и умеренной "
    "жирностью — хороший выбор под этот профиль. Реальное мясо стоит первым "
    "в списке, наполнители без дешёвых злаков, поэтому пищеварение остаётся "
    "стабильным даже при чувствительном ЖКТ."
)


def _logical_sections(html: str) -> int:
    return len(re.findall(r'<section class="page', html))


def _physical_pages_chromium(html_path: str) -> int:
    file_url = "file://" + os.path.abspath(html_path)
    base_dir = os.path.dirname(os.path.abspath(html_path))
    pdf_path = html_path.rsplit(".", 1)[0] + "_print.pdf"
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        try:
            ctx = browser.new_context(base_url="file://" + base_dir + "/")
            page = ctx.new_page()
            page.goto(file_url, wait_until="networkidle", timeout=30000)
            page.emulate_media(media="print")
            page.pdf(path=pdf_path, format="A4", print_background=True,
                     prefer_css_page_size=True)
            ctx.close()
        finally:
            browser.close()
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        return len(pdf)
    finally:
        pdf.close()


def main(inject_ai: bool = True):
    os.makedirs(OUT_DIR, exist_ok=True)
    selector = DryFoodSelector()
    all_ok = True
    for prof in PROFILES:
        dog = DogProfileDry(
            name=prof["name"], breed=prof["breed"], age_months=prof["age_months"],
            sex=prof["sex"], neutered=prof["neutered"], weight_kg=prof["weight_kg"],
            condition=prof["condition"], activity=prof["activity"],
            diagnoses=prof.get("diagnoses", []), stool="good",
            stop_products=prof.get("stop_products", []),
        )
        result = selector.select(dog)
        if inject_ai:
            for rec in result.budget + result.mid + result.premium:
                rec.ai_analysis = FAKE_AI

        html = generate_dry_food_html(result)
        html_path = os.path.join(OUT_DIR, f"chk_{prof['name']}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        logical = _logical_sections(html)
        physical = _physical_pages_chromium(html_path)
        status = "OK" if physical == logical else "OVERFLOW"
        if physical != logical:
            all_ok = False
        print(f"{status:9} {prof['name']:8} {prof['breed']:24} "
              f"{prof['weight_kg']:>5}кг  лог={logical} физ={physical}")

    print("\n" + ("ВСЕ ПРОФИЛИ OK (Chromium) — секции == страницы"
                  if all_ok else "ЕСТЬ ПЕРЕПОЛНЕНИЯ В CHROMIUM"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(inject_ai="--no-ai" not in sys.argv))
