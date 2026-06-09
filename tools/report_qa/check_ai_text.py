"""Детерминированный аудит ТЕКСТА от Gemini: ИИ не имеет права писать числа и
стоп-продукты — числа (дозы/граммы/цены) авторитетны из calculator, ИИ даёт
только нарратив (см. правило small-dog-edge-cases / stop-list-aware-templates).

`audit_ai_text(text, stop_products)` — чистая функция, работает на любой строке
ИИ-текста. Это «дешёвый страж» уровня 1: ловит запрещённые числа и стоп-продукты
ДО того, как тратиться на оценку качества прозы (уровень 2 — ИИ-судья/человек).

ВАЖНО: проверять есть что только когда Gemini реально подключён и вернул текст.
Сейчас в этом окружении ключа/креды нет (_ask()→None) → отчёты идут на фолбэке,
ИИ-текста для аудита не существует. Функция готова к моменту подключения ИИ.

Запуск самотеста:  venv/bin/python tools/report_qa/check_ai_text.py
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from calculator import stop_roots, is_stopped  # noqa: E402

# Единицы измерения — числа рядом с ними почти наверняка доза/граммовка/цена.
_UNITS = r"г|гр|грамм\w*|мл|ккал|кал|руб\w*|₽|%|кг|капсул\w*|таблет\w*|шт|порц\w*|ст\.?\s*л|ч\.?\s*л"
_QTY_RE = re.compile(rf"\d+[.,]?\d*\s*(?:{_UNITS})\b", re.I)
# Голые многозначные числа (29.9, 600) — тоже подозрительно для нарратива.
_BARE_NUM_RE = re.compile(r"(?<!\w)\d{2,}(?:[.,]\d+)?(?!\w)")
# Названия нутриентов с цифрами — разрешены (не количества).
_ALLOW = re.compile(r"омега[\s-]?[36]|b\s?1?\d|d\s?3|k\s?2|ca\s?:?\s?p", re.I)

# Стоп-продукт в свободном тексте — курируемые видимые формы (как в check_natural).
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


def _stop_forms(stop_product: str) -> list[str]:
    key = stop_product.strip().lower()
    return STOP_DISPLAY.get(key) or list(stop_roots([key])) or [key]


def audit_ai_text(text: str, stop_products: list[str] | None = None) -> list[str]:
    """Возвращает список нарушений в ИИ-тексте (пустой = чисто)."""
    if not text:
        return []
    low = text.lower()
    masked = _ALLOW.sub("·", low)  # вырезаем разрешённые нутриенты перед поиском чисел
    issues: list[str] = []

    qty = _QTY_RE.findall(masked)
    if qty:
        issues.append(f"числа с единицами (запрещены ИИ): {qty[:5]}")
    bare = [n for n in _BARE_NUM_RE.findall(masked)]
    if bare:
        issues.append(f"голые числа (подозрительно): {bare[:5]}")
    for s in (stop_products or []):
        hits = [f for f in _stop_forms(s) if f in low]
        if hits:
            issues.append(f"стоп-продукт «{s}» в тексте: {hits}")
    return issues


# --- Самотест на синтетике (Gemini тут не нужен) -----------------------------
_SELFTEST = [
    ("Барон — крепкий лабрадор, любит активные прогулки. Сбалансированный рацион "
     "поддержит его форму, а омега-3 — блеск шерсти.", [], True),
    ("Давайте 50 г курицы утром и 2 капсулы рыбьего жира.", ["курица"], False),
    ("Рацион рассчитан на целевой вес 29.9 кг и разделён на 2 кормления.", [], False),
    ("Говядина прекрасно подойдёт как основной источник белка.", ["говядина"], False),
]


def _selftest() -> int:
    ok = True
    for text, stop, should_pass in _SELFTEST:
        issues = audit_ai_text(text, stop)
        passed = not issues
        mark = "OK " if passed == should_pass else "ОШИБКА ТЕСТА"
        if passed != should_pass:
            ok = False
        print(f"[{mark}] ожидали={'чисто' if should_pass else 'нарушения'} | "
              f"получили={issues or 'чисто'}\n      «{text[:60]}…»")
    print("\n" + ("САМОТЕСТ ПРОЙДЕН" if ok else "САМОТЕСТ ПРОВАЛЕН"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_selftest())
