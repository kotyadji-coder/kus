"""
Golden-снапшоты отчётов: замораживают эталонный рендер 15 профилей (ключевые
числа + хеш разметки), чтобы дизайн и расчёты «не уезжали» незаметно.

  python tools/snapshot.py            # сверить с эталоном, exit 1 при расхождении
  python tools/snapshot.py --update   # одобрить текущее как новый эталон

Сезон пиннится ("neutral"), иначе зимой/летом калории сдвигаются и снапшот дрожит.
Эталон в tools/golden_snapshots.json — коммитится в репозиторий.
"""
import sys, os, json, hashlib, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculator import DietCalculator, DogProfile
import pdf_generator
from evals import PROFILES

GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_snapshots.json")


def _fingerprint(profile: dict) -> dict:
    dog = DogProfile(
        name=profile["name"], breed=profile["breed"], age_months=profile["age_months"],
        sex=profile["sex"], neutered=profile["neutered"], weight_kg=profile["weight_kg"],
        current_food="dry", condition=profile["condition"], activity=profile["activity"],
        diagnoses=profile.get("diagnoses", []), stool=profile.get("stool", "good"),
        diet_type=profile["diet_type"], budget=profile["budget"],
        stop_products=profile.get("stop_products", []),
        pregnant=profile.get("pregnant", False), lactating=profile.get("lactating", False),
        season="neutral",  # пин: убираем месячный дрейф калорий
    )
    res = DietCalculator().calculate(dog)
    html = pdf_generator.generate_html(res)
    # Нормализуем волатильное (дата) перед хешем разметки.
    norm = re.sub(r"\d{2}\.\d{2}\.\d{4}", "DATE", html)
    html_hash = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]

    shopping = {}
    day_totals = []
    for d in res.weekly_menu:
        tot = 0
        for p in (d.morning + getattr(d, 'midday', []) + getattr(d, 'afternoon', []) + d.evening):
            shopping[p.product_name] = shopping.get(p.product_name, 0) + int(p.grams)
            tot += p.grams
        day_totals.append(int(tot))

    return {
        "daily_grams": int(res.daily_grams),
        "mer_kcal": int(res.mer_kcal),
        "ideal_weight": res.ideal_weight_kg,
        "meals_per_day": res.meals_per_day,
        "ca_p_ratio": res.ca_p_ratio,
        "cost_per_day": int(res.cost_per_day),
        "distribution": {k: int(v) for k, v in sorted(res.distribution.items()) if v > 0},
        "day_totals": day_totals,
        "shopping": dict(sorted(shopping.items())),
        "supplements": [s.get("name") for s in res.supplements],
        "warnings_count": len(res.warnings),
        "html_len": len(html),
        "html_hash": html_hash,
    }


def build() -> dict:
    return {p["name"]: _fingerprint(p) for p in PROFILES}


def _diff(name: str, old: dict, new: dict) -> list[str]:
    out = []
    for k in sorted(set(old) | set(new)):
        if old.get(k) != new.get(k):
            out.append(f"  [{name}] {k}: {old.get(k)!r} → {new.get(k)!r}")
    return out


def main():
    update = "--update" in sys.argv
    current = build()
    if update:
        with open(GOLDEN, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2, sort_keys=True)
        print(f"✓ Эталон обновлён: {len(current)} профилей → {GOLDEN}")
        return 0

    if not os.path.exists(GOLDEN):
        print("✗ Нет эталона. Создайте: python tools/snapshot.py --update")
        return 1

    with open(GOLDEN, encoding="utf-8") as f:
        golden = json.load(f)

    diffs = []
    for name in sorted(set(golden) | set(current)):
        if name not in golden:
            diffs.append(f"  [{name}] НОВЫЙ профиль (нет в эталоне)")
        elif name not in current:
            diffs.append(f"  [{name}] ИСЧЕЗ из набора")
        else:
            diffs += _diff(name, golden[name], current[name])

    if diffs:
        print(f"✗ СНАПШОТ РАЗОШЁЛСЯ ({len(diffs)} расхождений) — отчёты/дизайн изменились:")
        print("\n".join(diffs))
        print("\nЕсли изменения ОЖИДАЕМЫ — одобрите: python tools/snapshot.py --update")
        return 1

    print(f"✓ Снапшот совпал: {len(current)} профилей без изменений")
    return 0


if __name__ == "__main__":
    sys.exit(main())
