"""W1 — система ОЦЕНОК отчётов «Кусь» (детерминированный слой), РАЗНЫЕ рубрики по
типу рациона: barf / cooked / dry. Баллы 0-5 по критериям + общий, история в
scores/<дата>.json — тренд и регрессии. Субъективное (ценность/связность/
безопасность советов, для сухого — точность чисел против карточки) оценивает
LLM-судья (skills/nightly_qa.md), дописывает в тот же json (value=None = ждёт).

Шкала: 5 отлично · 3-4 ок с замечанием · 1-2 плохо · 0 провал · None не оценено.

CLI:
  venv/bin/python tools/report_qa/rubric.py          # вся матрица (натуралка) + dry-профили
  venv/bin/python tools/report_qa/rubric.py nat <i>   # один натуральный профиль
  venv/bin/python tools/report_qa/rubric.py dry <i>   # один сухой профиль
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from calculator import DietCalculator, DogProfile  # noqa: E402
from evals import PROFILES  # noqa: E402
from check_ai_text import audit_ai_text  # noqa: E402
from dry_food_selector import DryFoodSelector, DogProfileDry, _allergen_in_food, STOP_TO_ALLERGEN  # noqa: E402
from check_dry import DRY_PROFILES  # noqa: E402

SCORES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scores")
MSK = timezone(timedelta(hours=3))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Субъективные критерии — общие, их выставляет LLM-судья.
SUBJECTIVE = ("value_usefulness", "no_duplication", "safety", "profile_match")


# ===================== НАТУРАЛКА (barf / cooked) =====================

def _mk_dog(p: dict) -> DogProfile:
    return DogProfile(
        name=p["name"], breed=p["breed"], age_months=p["age_months"], sex=p["sex"],
        neutered=p["neutered"], weight_kg=p["weight_kg"], current_food="dry",
        condition=p["condition"], activity=p["activity"], diagnoses=p.get("diagnoses", []),
        stool=p.get("stool", "good"), diet_type=p["diet_type"],
        budget=p.get("budget", "market"), stop_products=p.get("stop_products", []))


def _c_target_weight(dog, r):
    cur, ideal = dog.weight_kg, r.ideal_weight_kg
    if dog.condition in ("chubby", "obese"):
        return (5, f"перевес → цель {ideal} ≤ {cur}") if ideal <= cur + 0.01 else (0, f"перевес, но цель {ideal} > {cur}")
    if dog.condition == "thin":
        return (5, f"худой → цель {ideal} > {cur}") if ideal > cur + 0.01 else (0, f"худой, но цель {ideal} ≤ {cur}")
    ok = abs(ideal - cur) <= max(0.2, cur * 0.05)
    return (5, f"норма → {ideal}≈{cur}") if ok else (2, f"норма, цель {ideal}≠{cur}")


def _c_ca_p(dog, r):
    e = r.ca_p_ratio_effective
    if 1.2 <= e <= 2.0: return 5, f"эфф Ca:P={e}"
    if 1.1 <= e < 1.2 or 2.0 < e <= 2.2: return 3, f"эфф Ca:P={e} на границе"
    return 0, f"эфф Ca:P={e} ВНЕ 1.1-2.0"


def _c_dose(dog, r):
    if not r.supplements: return 0, "добавок нет"
    for s in r.supplements:
        if re.search(r"(?<![\d.,])(0(?:[.,]0+)?|-\d)\s*(мг|мл|г|капсул|табл|шт|ч\.?\s*л)", str(s.get("dosage", ""))):
            return 0, f"нулевая/отриц. доза: {s.get('name')}"
    return 5, f"{len(r.supplements)} добавок, доз без нулей"


def _c_grams(dog, r):
    pct = r.daily_grams / (r.ideal_weight_kg * 1000) * 100 if r.ideal_weight_kg else 0
    lo, hi = (2.0, 6.5) if r.ideal_weight_kg < 5 else (2.0, 4.0)
    return (5, f"{r.daily_grams}г={pct:.1f}%идеала") if lo <= pct <= hi else (2, f"{pct:.1f}%идеала — пограничн.")


def _c_diag(dog, r):
    diag = [d.lower() for d in dog.diagnoses]
    if not diag: return 5, "диагнозов нет"
    notes, bad = [], False
    tot = max(1, sum(r.distribution.values()))
    if any("панкреат" in d for d in diag):
        op = r.distribution.get("organs", 0) / tot * 100
        ok = op <= 9; bad |= not ok
        notes.append(f"панкреатит: субпрод. {op:.0f}% {'сниж.' if ok else 'НЕ сниж.!'}")
    if any("гастрит" in d for d in diag):
        ok = any("гастрит" in w.lower() for w in r.warnings); bad |= not ok
        notes.append(f"гастрит: warning {'есть' if ok else 'НЕТ!'}")
    return (2 if bad else 5, "; ".join(notes) or "учтены")


def _c_barf_bones(dog, r):
    bones = r.distribution.get("raw_meaty_bones", 0)
    if bones > 0:
        return 5, "кости в рационе (источник Ca)"
    # При гастрите кости намеренно убираются (мягкая пища), кальций компенсирует.
    gastritis = any("гастрит" in d.lower() for d in dog.diagnoses)
    has_ca = any("Кальци" in s.get("name", "") for s in r.supplements)
    if gastritis and has_ca:
        return 5, "кости убраны (гастрит), кальций компенсирует"
    return 1, "barf без костей без обоснования (!)"


def _c_cooked_nobones(dog, r):
    bones = r.distribution.get("raw_meaty_bones", 0)
    has_ca = any("Кальци" in s.get("name", "") for s in r.supplements)
    if bones > 0: return 0, "варёнка с костями (!)"
    return (5, "без костей + кальций назначен") if has_ca else (1, "варёнка без костей и БЕЗ кальция (!)")


NAT_SHARED = {"target_weight": _c_target_weight, "ca_p_effective": _c_ca_p,
              "dose_sanity": _c_dose, "daily_grams": _c_grams, "diagnosis_reflected": _c_diag}
NAT_BARF = {"barf_has_bones": _c_barf_bones}
NAT_COOKED = {"cooked_no_bones": _c_cooked_nobones}


def _extract_ai(html: str) -> dict:
    def strip(t):
        t = re.sub(r"<br\s*/?>", " ", t); t = re.sub(r"<[^>]+>", " ", t)
        return re.sub(r"\s+", " ", t).strip()
    subs = re.findall(r'<p class="section-sub">(.*?)</p>', html, re.S)
    ins = re.findall(r'<div class="tag[^"]*">.*?</div>\s*<p>(.*?)</p>', html, re.S)
    notes = re.search(r'font-size: 11pt; line-height: 1\.7; color: var\(--ink\);">(.*?)</div>', html, re.S)
    return {"intro": strip(subs[0]) if subs else "", "insights": [strip(x) for x in ins],
            "notes": strip(notes.group(1)) if notes else ""}


def _nat_text_criteria(ai, stop):
    blocks = [b for b in [ai["intro"]] + ai["insights"] + [ai["notes"]] if b]
    out = {}
    n_num = sum(1 for b in blocks if any("числ" in i for i in audit_ai_text(b, stop)))
    out["no_numbers"] = (5 if n_num == 0 else max(0, 5 - n_num * 2), "цифр нет" if not n_num else f"{n_num} секций с цифрами")
    n_stop = sum(1 for b in blocks if any("стоп-продукт" in i for i in audit_ai_text(b, stop)))
    out["stop_handled"] = (5 if n_stop == 0 else 0, "стоп чисто/исключён" if not n_stop else f"{n_stop} секций кормят стоп")
    out["completeness"] = (5 if len(ai["insights"]) == 6 else max(0, 5 - abs(6 - len(ai["insights"]))), f"{len(ai['insights'])} блоков (ждём 6)")
    return out


def score_natural(p, html_path=None):
    dog = _mk_dog(p); r = DietCalculator().calculate(dog)
    crit = dict(NAT_SHARED); crit.update(NAT_BARF if dog.diet_type == "barf" else NAT_COOKED)
    scores = {k: dict(zip(("value", "note"), fn(dog, r))) for k, fn in crit.items()}
    if html_path and os.path.exists(html_path):
        for k, (v, n) in _nat_text_criteria(_extract_ai(open(html_path, encoding="utf-8").read()), p.get("stop_products", [])).items():
            scores[k] = {"value": v, "note": n}
    for k in SUBJECTIVE:
        scores[k] = {"value": None, "note": "ждёт LLM-судью"}
    return _finalize(p["name"], p["diet_type"], scores)


# ===================== СУХОЙ КОРМ (dry) =====================

def score_dry(p):
    dog = DogProfileDry(
        name=p["name"], breed=p["breed"], age_months=p["age_months"], sex=p["sex"],
        neutered=p["neutered"], weight_kg=p["weight_kg"], condition=p["condition"],
        activity=p["activity"], diagnoses=p.get("diagnoses", []),
        stool=p.get("stool", "good"), stop_products=p.get("stop_products", []))
    res = DryFoodSelector().select(dog)
    recs = [r for c in ("budget", "mid", "premium") for r in getattr(res, c)]
    scores = {}
    # 1. стоп-МЯСО не протекло (жир допустим)
    meat_leak = []
    for s in dog.stop_products:
        tok = STOP_TO_ALLERGEN.get(s.lower())
        for rec in recs:
            meat, _f = _allergen_in_food(rec.food, tok) if tok else ([], [])
            if meat: meat_leak.append(f"{rec.food['brand']}:{meat}")
    scores["stop_not_leaked"] = {"value": 5 if not meat_leak else 0,
                                 "note": "стоп-мясо не в подборе" if not meat_leak else f"ПРОТЁК {meat_leak[:3]}"}
    # 2. аллергику нет частого аллергена (мясо)
    is_allergic = any("аллерг" in d.lower() for d in dog.diagnoses)
    allerg_leak = []
    if is_allergic:
        for rec in recs:
            absent = set(rec.food.get("allergens_absent", []))
            for tok in ("chicken", "beef", "corn", "wheat", "soy"):
                if tok in absent:
                    continue  # производитель гарантирует отсутствие белка
                meat, _f = _allergen_in_food(rec.food, tok)  # жир не считаем (без белка)
                if meat:
                    allerg_leak.append(f"{rec.food['brand']}:{tok}")
    scores["allergen_handled"] = {"value": 5 if not allerg_leak else 0,
                                  "note": "n/a" if not is_allergic else ("аллергены не в подборе" if not allerg_leak else f"ПРОТЁК {allerg_leak[:3]}")}
    # 3. карточки полны (% мяса/белок/цена)
    missing = [f"{rec.food['brand']}:{fld}" for rec in recs for fld in ("protein_pct", "meat_estimate_pct", "price_per_kg") if not rec.food.get(fld)]
    scores["composition_complete"] = {"value": 5 if not missing else 2, "note": "карточки полны" if not missing else f"пусто: {missing[:3]}"}
    # 4. пул наполнен (цель 9, пустые категории — минус)
    n = len(recs)
    scores["pool_filled"] = {"value": 5 if n >= 9 else (3 if n >= 6 else 1),
                             "note": f"подобрано {n}/9" + (f", пусто: {res.empty_categories}" if res.empty_categories else "")}
    # субъективное: ценность текста + ТОЧНОСТЬ ЧИСЕЛ против карточки (числа в сухом разрешены)
    for k in ("value_usefulness", "composition_accuracy", "safety"):
        scores[k] = {"value": None, "note": "ждёт LLM-судью"}
    return _finalize(p["name"], "dry", scores)


# ===================== общее =====================

def _git_commit() -> str:
    """Короткий хэш текущего коммита — версия кода, давшая эти баллы (для W8:
    падение балла атрибутируется конкретной правке)."""
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "?"


def _finalize(name, diet, scores):
    graded = [s["value"] for s in scores.values() if s["value"] is not None]
    overall = round(sum(graded) / len(graded), 2) if graded else None
    return {"name": name, "diet_type": diet, "overall_deterministic": overall, "criteria": scores}


def _print(res):
    flag = "" if (res["overall_deterministic"] or 0) >= 4.5 else "  ⚠"
    print(f"{res['name']:8} {res['diet_type']:7} балл={res['overall_deterministic']}{flag}")
    for k, v in res["criteria"].items():
        if v["value"] is not None and v["value"] < 5:
            print(f"     [{v['value']}] {k}: {v['note']}")


def main() -> int:
    os.makedirs(SCORES_DIR, exist_ok=True)
    args = sys.argv[1:]
    results = []
    if args and args[0] == "dry":
        idxs = [int(args[1])] if len(args) > 1 else range(len(DRY_PROFILES))
        results = [score_dry(DRY_PROFILES[i]) for i in idxs]
    elif args and args[0] == "nat":
        idxs = [int(args[1])] if len(args) > 1 else range(len(PROFILES))
        results = [score_natural(PROFILES[i], os.path.join(ROOT, "output", f"order_{990100+i}_natural.html")) for i in idxs]
    else:
        for i, p in enumerate(PROFILES):
            results.append(score_natural(p, os.path.join(ROOT, "output", f"order_{990100+i}_natural.html")))
        for p in DRY_PROFILES:
            results.append(score_dry(p))
    for res in results:
        _print(res)
    now = datetime.now(MSK)
    stamp = now.strftime("%Y-%m-%d")
    commit = _git_commit()
    with open(os.path.join(SCORES_DIR, f"{stamp}.json"), "w", encoding="utf-8") as f:
        json.dump({"date": stamp, "ts": now.strftime("%Y-%m-%d %H:%M"), "git_commit": commit,
                   "results": results}, f, ensure_ascii=False, indent=2)
    print(f"\nИстория: scores/{stamp}.json  ({len(results)} профилей, код {commit})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
