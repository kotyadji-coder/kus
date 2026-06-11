"""W1 — система ОЦЕНОК отчётов «Кусь» (детерминированный слой).

Превращает критерии QA-агента в баллы 0-5 по критериям + общий балл, пишет
историю в scores/<дата>.json — чтобы видеть тренд и ловить регрессии
(«улучшаться от расчёта к расчёту»). Образец — avito eval_results/action_items.

Здесь — ТОЛЬКО объективные, детерминированные критерии (без Gemini): их можно
гонять дёшево хоть каждую ночь. Субъективные (ценность текста, связность,
безопасность советов) оценивает LLM-судья отдельным скиллом — он дописывает свои
баллы в тот же json. Поля судьи помечены value=None («ждёт агента»).

Шкала: 5 отлично · 3-4 ок с замечанием · 1-2 плохо · 0 провал · None не оценивалось.

CLI:
  venv/bin/python tools/report_qa/rubric.py            # все профили матрицы
  venv/bin/python tools/report_qa/rubric.py <idx>      # один профиль
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from calculator import DietCalculator, DogProfile  # noqa: E402
from evals import PROFILES  # noqa: E402
from check_ai_text import audit_ai_text  # noqa: E402

SCORES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scores")
MSK = timezone(timedelta(hours=3))


def _mk_dog(p: dict) -> DogProfile:
    return DogProfile(
        name=p["name"], breed=p["breed"], age_months=p["age_months"], sex=p["sex"],
        neutered=p["neutered"], weight_kg=p["weight_kg"], current_food="dry",
        condition=p["condition"], activity=p["activity"], diagnoses=p.get("diagnoses", []),
        stool=p.get("stool", "good"), diet_type=p["diet_type"],
        budget=p.get("budget", "market"), stop_products=p.get("stop_products", []),
    )


# --- Объективные критерии: каждый возвращает (балл 0-5, пояснение) ----------

def _c_target_weight(dog, r) -> tuple[int, str]:
    cur, ideal = dog.weight_kg, r.ideal_weight_kg
    if dog.condition in ("chubby", "obese"):
        ok = ideal < cur - 0.05
        return (5 if ok else 0, f"перевес → цель {ideal} {'<' if ok else '≥(!)'} текущий {cur}")
    if dog.condition == "thin":
        ok = ideal > cur + 0.05
        return (5 if ok else 0, f"худой → цель {ideal} {'>' if ok else '≤(!)'} текущий {cur}")
    ok = abs(ideal - cur) <= max(0.2, cur * 0.05)
    return (5 if ok else 2, f"норма → цель {ideal} ≈ текущий {cur}" if ok else f"норма, но цель {ideal} ≠ {cur}")


def _c_ca_p(dog, r) -> tuple[int, str]:
    eff = r.ca_p_ratio_effective
    if 1.2 <= eff <= 2.0:
        return 5, f"эфф Ca:P={eff} (еда {r.ca_p_ratio})"
    if 1.1 <= eff < 1.2 or 2.0 < eff <= 2.2:
        return 3, f"эфф Ca:P={eff} на границе"
    return 0, f"эфф Ca:P={eff} ВНЕ коридора 1.1-2.0"


def _c_dose_sanity(dog, r) -> tuple[int, str]:
    if not r.supplements:
        return 0, "добавок нет"
    for s in r.supplements:
        d = str(s.get("dosage", ""))
        if re.search(r"\b0\s*(мг|мл|капсул|табл|шт|г)\b", d):
            return 0, f"нулевая доза: {s.get('name')}"
    return 5, f"{len(r.supplements)} добавок, доз без нулей"


def _c_daily_grams(dog, r) -> tuple[int, str]:
    pct = r.daily_grams / (r.ideal_weight_kg * 1000) * 100
    lo, hi = (2.0, 6.5) if r.ideal_weight_kg < 5 else (2.0, 4.0)  # крохам можно выше
    ok = lo <= pct <= hi
    return (5 if ok else 1, f"{r.daily_grams}г = {pct:.1f}% идеала ({'норма' if ok else 'подозрительно'})")


def _c_diagnosis(dog, r) -> tuple[int, str]:
    diag = [d.lower() for d in dog.diagnoses]
    if not diag:
        return 5, "диагнозов нет (n/a)"
    notes = []
    if any("панкреат" in d for d in diag):
        organs_pct = r.distribution.get("organs", 0) / max(1, sum(r.distribution.values())) * 100
        notes.append(f"панкреатит: субпродукты {organs_pct:.0f}% {'(снижены)' if organs_pct <= 9 else '(НЕ снижены!)'}")
    if any("гастрит" in d for d in diag):
        has_w = any("гастрит" in w.lower() for w in r.warnings)
        notes.append(f"гастрит: спец-предупреждение {'есть' if has_w else 'НЕТ(!)'} , кормлений {r.meals_per_day}")
    bad = any("НЕ" in n or "НЕТ" in n for n in notes)
    return (2 if bad else 5, "; ".join(notes) or "диагнозы учтены")


CALC_CRITERIA = {
    "target_weight": _c_target_weight,
    "ca_p_effective": _c_ca_p,
    "dose_sanity": _c_dose_sanity,
    "daily_grams": _c_daily_grams,
    "diagnosis_reflected": _c_diagnosis,
}


def _extract_ai(html: str) -> dict:
    def strip(t):
        t = re.sub(r"<br\s*/?>", " ", t); t = re.sub(r"<[^>]+>", " ", t)
        return re.sub(r"\s+", " ", t).strip()
    subs = re.findall(r'<p class="section-sub">(.*?)</p>', html, re.S)
    insights = re.findall(r'<div class="tag[^"]*">.*?</div>\s*<p>(.*?)</p>', html, re.S)
    notes = re.search(r'font-size: 11pt; line-height: 1\.7; color: var\(--ink\);">(.*?)</div>', html, re.S)
    return {
        "intro": strip(subs[0]) if subs else "",
        "insights": [strip(x) for x in insights],
        "notes": strip(notes.group(1)) if notes else "",
    }


def _text_criteria(ai: dict, stop: list) -> dict:
    """Детерминированные текстовые критерии (если HTML с ИИ есть)."""
    blocks = [ai["intro"]] + ai["insights"] + [ai["notes"]]
    blocks = [b for b in blocks if b]
    out = {}
    num_issues = sum(1 for b in blocks if any("числ" in i for i in audit_ai_text(b, stop)))
    out["no_numbers"] = (5 if num_issues == 0 else max(0, 5 - num_issues * 2),
                         "цифр нет" if num_issues == 0 else f"{num_issues} секций с цифрами")
    stop_issues = sum(1 for b in blocks if any("стоп-продукт" in i for i in audit_ai_text(b, stop)))
    out["stop_handled"] = (5 if stop_issues == 0 else 0,
                           "стоп чисто/исключён" if stop_issues == 0 else f"{stop_issues} секций кормят стоп")
    n_ins = len(ai["insights"])
    out["completeness"] = (5 if n_ins == 6 else max(0, 5 - abs(6 - n_ins)),
                           f"{n_ins} блоков анализа (ждём 6)")
    return out


def score_profile(p: dict, html_path: str | None = None) -> dict:
    dog = _mk_dog(p)
    r = DietCalculator().calculate(dog)
    scores = {}
    for key, fn in CALC_CRITERIA.items():
        val, note = fn(dog, r)
        scores[key] = {"value": val, "note": note}
    # текстовые — только если есть готовый HTML с ИИ
    if html_path and os.path.exists(html_path):
        ai = _extract_ai(open(html_path, encoding="utf-8").read())
        for key, (val, note) in _text_criteria(ai, p.get("stop_products", [])).items():
            scores[key] = {"value": val, "note": note}
    # субъективные — ждут LLM-судью
    for key in ("value_usefulness", "no_duplication", "safety", "profile_match"):
        scores[key] = {"value": None, "note": "ждёт LLM-судью"}

    graded = [s["value"] for s in scores.values() if s["value"] is not None]
    overall = round(sum(graded) / len(graded), 2) if graded else None
    return {"name": p["name"], "diet_type": p["diet_type"], "overall_deterministic": overall,
            "criteria": scores}


def main() -> int:
    os.makedirs(SCORES_DIR, exist_ok=True)
    idxs = [int(sys.argv[1])] if len(sys.argv) > 1 else range(len(PROFILES))
    results = []
    for i in idxs:
        p = PROFILES[i]
        html = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "output", f"order_{990100 + i}_natural.html")
        res = score_profile(p, html if os.path.exists(html) else None)
        results.append(res)
        flag = "" if (res["overall_deterministic"] or 0) >= 4.5 else "  ⚠"
        print(f"{res['name']:8} {res['diet_type']:7} балл={res['overall_deterministic']}{flag}")
        for k, v in res["criteria"].items():
            if v["value"] is not None and v["value"] < 5:
                print(f"     [{v['value']}] {k}: {v['note']}")
    stamp = datetime.now(MSK).strftime("%Y-%m-%d")
    path = os.path.join(SCORES_DIR, f"{stamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"date": stamp, "results": results}, f, ensure_ascii=False, indent=2)
    print(f"\nИстория: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
