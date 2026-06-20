"""
Единый источник истины для инвариантов СОГЛАСОВАНИЯ отчёта (сводка ↔ меню ↔
список покупок). Один и тот же набор проверок используют:
  - evals.py        — витрина в админке (15 эталонных профилей),
  - tools/fuzz.py    — ночной фаззинг случайных профилей,
  - tools/snapshot.py — golden-снапшоты (заморозка дизайна/чисел),
  - tools/canary.py  — проверка, что детектор вообще живой.

Принцип «храповика»: каждый найденный баг превращается в инвариант ЗДЕСЬ и больше
не может вернуться молча. Дублировать проверки нельзя — только добавлять сюда.
"""

import re

# Группы, которых по дизайну нет в меню (показаны на странице добавок).
MENU_EXEMPT_GROUPS = {"oils_supplements"}

GROUP_RU = {
    "muscle_meat": "мясо", "raw_meaty_bones": "кости", "organs": "субпродукты",
    "vegetables": "овощи", "dairy": "кисломолочка", "eggs": "яйца",
    "fish": "рыба", "oils_supplements": "масла",
}

_FRAC = {"¼": 0.25, "½": 0.5, "¾": 0.75}


def parse_frac(s: str) -> float:
    """«9¼» → 9.25, «½» → 0.5, «2» → 2.0."""
    total, digits = 0.0, ""
    for ch in s.strip():
        if ch.isdigit():
            digits += ch
        elif ch in _FRAC:
            total += _FRAC[ch]
    if digits:
        total += int(digits)
    return total


def _day_slots(day):
    """Все слоты дня по порядку: Утро, День, Полдник, Вечер.
    afternoon (Полдник) — 4-е кормление щенков <4 мес; getattr для старых снимков."""
    return (day.morning, getattr(day, 'midday', []),
            getattr(day, 'afternoon', []), day.evening)


def _menu_group_grams(result) -> dict:
    out = {}
    for d in result.weekly_menu:
        for grp in _day_slots(d):
            for p in grp:
                out[p.group] = out.get(p.group, 0) + p.grams
    return out


def reconciliation_checks(result, html=None) -> list[dict]:
    """Возвращает список проверок согласования: [{key, status, detail}].
    status ∈ {'ok','warn','fail'}. html опционален — без него рендер-проверки
    (яйцо, нули/ложки) пропускаются."""
    checks = []
    menu_g = _menu_group_grams(result)

    # 1. Слоты меню == «кормлений в день» (баг «3 кормления, 2 слота»)
    slot_bad = []
    for day in result.weekly_menu:
        slots = sum(1 for grp in _day_slots(day) if any(p.grams > 0 for p in grp))
        if slots != result.meals_per_day:
            slot_bad.append(f"{day.day_name}={slots}")
    checks.append({"key": "Слоты = кормления",
                   "status": "ok" if not slot_bad else "fail",
                   "detail": (f"каждый день {result.meals_per_day} слот(а)" if not slot_bad
                              else f"иначе: {', '.join(slot_bad[:3])} (ждали {result.meals_per_day})")})

    # 2. Каждая группа из сводки есть в меню (кроме масел)
    missing = [g for g, grams in result.distribution.items()
               if grams > 0 and g not in MENU_EXEMPT_GROUPS and menu_g.get(g, 0) <= 0]
    checks.append({"key": "Группы сводки = меню",
                   "status": "ok" if not missing else "fail",
                   "detail": ("все группы рациона есть в меню" if not missing
                              else f"в сводке есть, в меню нет: {', '.join(GROUP_RU.get(g, g) for g in missing)}")})

    # 3. Мясо + рыба в меню == мясной бюджет (рыбные дни заменяют мясо г-в-г).
    # Допуск двойной — процент ИЛИ абсолютный зазор округления. Меню округляет
    # КАЖДУЮ порцию до 10 г, поэтому систематическая ошибка ≈ 5 г × число мясных
    # порций за неделю. У мелких собак (порции 20-40 г) это легко даёт 18-19% —
    # и это не баг, а неизбежность округления. Поэтому абсолютный зазор считаем от
    # реального числа порций (самомасштабируется), а % оставляем как пол для крупных.
    meat_budget = result.distribution.get("muscle_meat", 0) * 7
    meat_menu = menu_g.get("muscle_meat", 0) + menu_g.get("fish", 0)
    if meat_budget > 0:
        n_meat = sum(1 for d in result.weekly_menu for grp in _day_slots(d)
                     for p in grp if p.group in ("muscle_meat", "fish") and p.grams > 0)
        round_slack = 5 * max(n_meat, 1)     # макс. систематический сдвиг округления, г/нед
        abs_dev = abs(meat_menu - meat_budget)
        dev = abs_dev / meat_budget * 100
        ok = dev <= 8 or abs_dev <= round_slack
        warn = dev <= 15 or abs_dev <= 1.5 * round_slack
        status = "ok" if ok else "warn" if warn else "fail"
        checks.append({"key": "Мясо+рыба = бюджет", "status": status,
                       "detail": f"{int(meat_menu)}г vs бюджет {int(meat_budget)}г/нед ({dev:.0f}%, зазор окр. ±{round_slack}г)"})
    else:
        checks.append({"key": "Мясо+рыба = бюджет", "status": "ok", "detail": "нет мясного бюджета"})

    # 3b. Суточная норма ≈ сумма групп распределения. Ловит зазор сводка↔состав
    # (как было 565 г норма vs 520 г по группам). Калькулятор сводит распределение
    # к round(daily_grams) (_calc_distribution: diff→muscle_meat), поэтому крупное
    # расхождение — баг, а не округление. Допуск держим узким: пол 12 г / 3%.
    norm = getattr(result, "daily_grams", 0) or 0
    groups_sum = sum(v for v in result.distribution.values() if v > 0)
    if norm > 0:
        dev = abs(norm - groups_sum)
        dev_pct = dev / norm * 100
        ok = dev <= max(12, 0.03 * norm)
        warn = dev <= max(20, 0.05 * norm)
        status = "ok" if ok else "warn" if warn else "fail"
        checks.append({"key": "Норма = сумма групп", "status": status,
                       "detail": f"норма {int(norm)}г vs группы {int(groups_sum)}г "
                                 f"(Δ{int(dev)}г, {dev_pct:.0f}%)"})
    else:
        checks.append({"key": "Норма = сумма групп", "status": "ok", "detail": "нет суточной нормы"})

    if html is None:
        return checks

    # 4. Яйцо: «X шт./нед.» в сводке == «Y шт.» в списке покупок (баг единицы яйца)
    mS = re.search(r'<span class="nm">Яйца</span> <span class="g"[^>]*>([0-9¼½¾]*)\s*шт\./нед', html)
    mH = re.search(r'class="nm">Яйцо[^<]*</td><td class="g"[^>]*>([0-9¼½¾]*)\s*шт\.', html)
    if mS and mH:
        S, H = parse_frac(mS.group(1)), parse_frac(mH.group(1))
        ok = abs(S - H) <= 0.3
        checks.append({"key": "Яйцо: сводка = покупки",
                       "status": "ok" if ok else "fail",
                       "detail": (f"{mS.group(1) or '0'} шт./нед = {mH.group(1)} шт." if ok
                                  else f"сводка {mS.group(1) or '0'} ≠ покупки {mH.group(1)} — единица яйца расходится")})
    else:
        checks.append({"key": "Яйцо: сводка = покупки", "status": "ok", "detail": "яйца в рационе отсутствуют"})

    # 5. Нет «0 г / 0 шт.»; легенда-ложки только при мелких порциях
    issues = []
    zeros = len(re.findall(r'>0 г<', html)) + len(re.findall(r'>0 шт', html))
    if zeros:
        issues.append(f"{zeros}×«0 г/шт»")
    max_portion = max((v for v in result.distribution.values() if v > 0), default=0)
    legend = "Как отмерить без весов" in html
    if max_portion < 90 and not legend:
        issues.append("нет легенды-ложек при мелких порциях")
    if max_portion >= 90 and legend:
        issues.append("легенда-ложки у крупной собаки (лишняя)")
    checks.append({"key": "Нет нулей / ложки уместны",
                   "status": "ok" if not issues else "fail",
                   "detail": (f"макс. порция {int(max_portion)}г, легенда {'есть' if legend else 'нет'}"
                              if not issues else "; ".join(issues))})
    return checks


def violations(result, html=None) -> list[dict]:
    """Только провалы (status == 'fail') — для фаззера/ворот/канарейки."""
    return [c for c in reconciliation_checks(result, html) if c["status"] == "fail"]
