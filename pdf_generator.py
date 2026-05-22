"""
Генерация PDF-файла с рационом собаки.
Использует WeasyPrint (HTML -> PDF).
"""

import os
from datetime import date
from calculator import DietResult, DietCalculator, DogProfile
from declension import decline_name

try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False


DIET_TYPE_LABELS = {"barf": "BARF (сырое)", "cooked": "Термообработка (варка)"}
CONDITION_LABELS = {"thin": "Недовес", "athletic": "Норма", "chubby": "Лёгкий перевес", "obese": "Ожирение"}
ACTIVITY_LABELS = {"lazy": "Низкая", "moderate": "Средняя", "high": "Высокая", "puppy": "Щенок"}
GROUP_LABELS = {
    "muscle_meat": "Мясо мускульное",
    "raw_meaty_bones": "Сырые мясные кости",
    "organs": "Субпродукты (органы)",
    "vegetables": "Овощи и зелень",
    "dairy": "Кисломолочные продукты",
    "eggs": "Яйца",
    "fish": "Рыба",
    "oils_supplements": "Масла и добавки",
}

FORBIDDEN_FOODS = [
    ("Шоколад, кофе, какао", "Теобромин — яд для собак"),
    ("Виноград, изюм", "Вызывают почечную недостаточность"),
    ("Лук, чеснок", "Разрушают эритроциты"),
    ("Авокадо", "Персин токсичен для собак"),
    ("Ксилит (сахарозаменитель)", "Резкое падение сахара, печёночная недостаточность"),
    ("Трубчатые кости птицы (варёные!)", "Осколки перфорируют ЖКТ"),
    ("Солёное, копчёное, жареное", "Нагрузка на почки и печень"),
    ("Хлеб, сдоба, макароны", "Пустые калории, брожение в ЖКТ"),
    ("Грибы", "Тяжело перевариваются, некоторые токсичны"),
    ("Орехи макадамия", "Токсичны для собак"),
]


def _fmt_age(age_months: int) -> str:
    if age_months < 12:
        return f"{age_months} мес."
    years = age_months // 12
    months = age_months % 12
    return f"{years} г." + (f" {months} мес." if months else "")


def _fmt_grams(grams: float) -> str:
    if grams >= 1000:
        return f"{grams/1000:.1f} кг"
    return f"{int(grams)} г"


# Вес одного яйца для пересчёта граммов → штук
EGG_PIECE_GRAMS = {
    "chicken_egg": 60,
    "quail_egg": 10,
}


def _is_egg(product_id: str = "", product_name: str = "") -> bool:
    return product_id in EGG_PIECE_GRAMS or "яйц" in product_name.lower()


def _egg_piece_weight(product_id: str = "", product_name: str = "") -> int:
    if product_id in EGG_PIECE_GRAMS:
        return EGG_PIECE_GRAMS[product_id]
    if "перепел" in product_name.lower():
        return 10
    return 60  # куриное по умолчанию


def _fmt_egg_or_grams(grams: float, product_id: str = "", product_name: str = "") -> str:
    """Форматирует количество: яйца в штуках, остальное в граммах."""
    if _is_egg(product_id, product_name):
        piece = _egg_piece_weight(product_id, product_name)
        count = max(1, round(grams / piece))
        return f"{count} шт."
    return _fmt_grams(grams)


# SVG icons used throughout the PDF
_SVG_PAW = '<svg width="{w}" height="{w}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="9" r="1.6"/><circle cx="10" cy="6" r="1.6"/><circle cx="14" cy="6" r="1.6"/><circle cx="18" cy="9" r="1.6"/><path d="M8.5 14c0-2 1.6-3.5 3.5-3.5s3.5 1.5 3.5 3.5c0 1.6 1 2.2 1 3.5 0 1.4-1.2 2-2.6 2-1 0-1.4-.5-1.9-.5s-.9.5-1.9.5C8.7 19.5 7.5 18.9 7.5 17.5c0-1.3 1-1.9 1-3.5z"/></svg>'
_SVG_CHECK = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>'
_SVG_X = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M6 6l12 12M6 18L18 6"/></svg>'
_SVG_WARN = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>'
_SVG_FISH = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12c2-4 5-6 9-6s7 2 9 6c-2 4-5 6-9 6s-7-2-9-6z"/><circle cx="15" cy="11" r="0.8" fill="currentColor"/><path d="M3 12l-2 2M3 12l-2-2"/></svg>'

# Color map for distribution groups
GROUP_COLORS = {
    "muscle_meat": "#055ba9",
    "raw_meaty_bones": "#f59e0b",
    "organs": "#b91c1c",
    "vegetables": "#16a34a",
    "dairy": "#0ea5e9",
    "eggs": "#a855f7",
    "fish": "#0369a1",
    "oils_supplements": "#64748b",
}

SHOP_GROUP_CSS = {
    "muscle_meat": "meat",
    "raw_meaty_bones": "bones",
    "organs": "organs",
    "vegetables": "veg",
    "dairy": "dairy",
    "eggs": "eggs",
    "fish": "eggs",
    "oils_supplements": "eggs",
}

FISH_DAYS = {"Среда", "Суббота"}


def _page_head(meta_text: str) -> str:
    return f'''<div class="page-head">
    <div class="logo">
      <span class="mark">{_SVG_PAW.format(w=16)}</span>
      <span class="name">Кусь</span>
    </div>
    <div class="meta">{meta_text}</div>
  </div>'''


def _page_foot(num: int, total: int, doc_id: str) -> str:
    return f'<div class="page-foot">стр. <strong>{num}</strong> / {total} · Кусь · {doc_id}</div>'


def generate_html(result: DietResult) -> str:
    dog = result.dog
    today = date.today().strftime("%d.%m.%Y")
    age_text = _fmt_age(dog.age_months)
    sex_text = "мальчик" if dog.sex == "male" else "девочка"
    doc_id = f"Рацион {dog.name}"
    weight_diff = round(dog.weight_kg - result.ideal_weight_kg, 1)

    # Склонения клички
    name = dog.name  # именительный
    name_g = decline_name(dog.name, "gent")  # родительный (кого? Барона)
    name_d = decline_name(dog.name, "datv")  # дательный (кому? Барону)
    name_a = decline_name(dog.name, "accs")  # винительный (кого? Барона)

    # Count total pages: cover + summary + menu pages + shopping + supplements + transition + memo + disclaimer
    menu_days = result.weekly_menu
    menu_page1 = menu_days[:4]
    menu_page2 = menu_days[4:]
    total_pages = 9  # fixed layout like the design

    # --- Distribution rows + stacked bar ---
    dist_items = [(g, grams) for g, grams in result.distribution.items() if grams > 0]
    total_grams = sum(g for _, g in dist_items)

    distribution_rows = ""
    stack_spans = ""
    for group, grams in dist_items:
        label = GROUP_LABELS.get(group, group)
        color = GROUP_COLORS.get(group, "#64748b")
        pct = (grams / total_grams * 100) if total_grams > 0 else 0
        if group == "eggs":
            # Яйца дают 2-3 раза в неделю, не каждый день
            # Считаем сколько штук в неделю (daily * 7 / вес_яйца)
            weekly_grams = grams * 7
            egg_count = max(1, round(weekly_grams / 60))
            g_display = f"{egg_count} шт./нед."
        else:
            g_display = f"{int(grams)} г"
        distribution_rows += f'<div class="group-row"><span class="sw" style="background:{color}"></span><span class="nm">{label}</span><span class="g">{g_display}</span></div>\n'
        stack_spans += f'<span style="background:{color}; width:{pct:.1f}%"></span>'

    # Pie chart conic gradient
    pie_segments = []
    cumulative = 0
    dominant_group = ""
    dominant_pct = 0
    for group, grams in dist_items:
        color = GROUP_COLORS.get(group, "#64748b")
        pct = (grams / total_grams * 100) if total_grams > 0 else 0
        pie_segments.append(f"{color} {cumulative:.1f}% {cumulative + pct:.1f}%")
        if pct > dominant_pct:
            dominant_pct = pct
            dominant_group = GROUP_LABELS.get(group, group).split()[0].lower()
        cumulative += pct
    pie_gradient = ", ".join(pie_segments)

    # --- Warnings ---
    warnings_html = ""
    for w in result.warnings:
        warnings_html += f'''<div class="warn">
      <div class="ico">{_SVG_WARN}</div>
      <div>{w}</div>
    </div>\n'''

    # --- Menu cards builder ---
    def _menu_card(day_menu) -> str:
        is_fish = day_menu.day_name in FISH_DAYS
        cls = ' special' if is_fish else ''
        morning_total = sum(p.grams for p in day_menu.morning)
        evening_total = sum(p.grams for p in day_menu.evening)
        day_total = int(morning_total + evening_total)

        tag = f'<div class="day-tag">{day_total} г</div>'
        if is_fish:
            tag = f'<div class="day-tag fish">{_SVG_FISH} Рыбный день</div>'

        morning_items = ""
        for p in day_menu.morning:
            if p.grams > 0:
                g_str = _fmt_egg_or_grams(p.grams, p.product_id, p.product_name)
                morning_items += f'<div class="item"><span class="nm">{p.product_name}</span><span class="leader"></span><span class="g">{g_str}</span></div>\n'

        evening_items = ""
        for p in day_menu.evening:
            if p.grams > 0:
                g_str = _fmt_egg_or_grams(p.grams, p.product_id, p.product_name)
                evening_items += f'<div class="item"><span class="nm">{p.product_name}</span><span class="leader"></span><span class="g">{g_str}</span></div>\n'

        return f'''<div class="day{cls}">
      <div class="day-head"><div class="day-name">{day_menu.day_name}</div>{tag}</div>
      <div class="meal-block">
        <div class="meal-time"><span class="dot"></span> Утро</div>
        {morning_items}
      </div>
      <div class="meal-block">
        <div class="meal-time evening"><span class="dot"></span> Вечер</div>
        {evening_items}
      </div>
    </div>'''

    menu_page1_html = "\n".join(_menu_card(d) for d in menu_page1)
    menu_page2_html = "\n".join(_menu_card(d) for d in menu_page2)

    # Week summary card
    total_week_grams = sum(
        sum(p.grams for p in d.morning) + sum(p.grams for p in d.evening)
        for d in menu_days
    )
    week_summary = f'''<div class="day" style="background: var(--bg-soft); border-style: dashed;">
      <div class="day-head"><div class="day-name" style="color:var(--ink);">Итого за неделю</div></div>
      <div style="display:grid; grid-template-columns: 1fr auto; gap: 6px; font-size: 9.5pt;">
        <div style="color:var(--ink-soft);">Общий вес рациона</div><div style="font-weight:700;">≈ {total_week_grams/1000:.2f} кг</div>
        <div style="color:var(--ink-soft);">Кормлений в день</div><div style="font-weight:700;">{result.meals_per_day}</div>
      </div>
    </div>'''

    # --- Shopping list ---
    shopping = {}
    for day_menu in result.weekly_menu:
        for portion in day_menu.morning + day_menu.evening:
            if portion.product_name not in shopping:
                shopping[portion.product_name] = {"grams": 0, "group": portion.group, "product_id": portion.product_id}
            shopping[portion.product_name]["grams"] += portion.grams

    shopping_by_group = {}
    for pname, info in shopping.items():
        g = info["group"]
        if g not in shopping_by_group:
            shopping_by_group[g] = []
        shopping_by_group[g].append((pname, int(info["grams"]), info["product_id"]))

    shopping_html = ""
    for group_key, items in shopping_by_group.items():
        css_cls = SHOP_GROUP_CSS.get(group_key, "eggs")
        group_label = GROUP_LABELS.get(group_key, group_key)
        items_html = ""
        for pname, grams, pid in sorted(items, key=lambda x: -x[1]):
            g_str = _fmt_egg_or_grams(grams, pid, pname)
            items_html += f'<div class="shop-item"><div class="check"></div><div class="nm">{pname}</div><div class="g">{g_str}</div></div>\n'
        shopping_html += f'''<div class="shop-group {css_cls}">
      <h4><span>{group_label}</span></h4>
      {items_html}
    </div>\n'''

    # --- Supplements ---
    supp_cards = ""
    for i, s in enumerate(result.supplements):
        full_cls = " full" if i == len(result.supplements) - 1 and len(result.supplements) % 2 == 1 else ""
        if full_cls:
            supp_cards += f'''<div class="supp{full_cls}">
      <div class="left">
        <div class="head" style="margin-bottom: 3mm;">
          <div class="ico"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"/><path d="M9 12l2 2 4-4"/></svg></div>
          <div>
            <div class="name">{s['name']}</div>
            <div class="freq">{s.get('frequency', '')}</div>
          </div>
        </div>
        <div class="note" style="font-size: 10pt;">{s.get('notes', '')}</div>
      </div>
      <div class="dose" style="text-align:right; white-space: nowrap;">{s['dosage']}</div>
    </div>\n'''
        else:
            supp_cards += f'''<div class="supp">
      <div class="head">
        <div class="ico"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"/><path d="M9 12l2 2 4-4"/></svg></div>
        <div>
          <div class="name">{s['name']}</div>
          <div class="freq">{s.get('frequency', '')}</div>
        </div>
      </div>
      <div class="dose">{s['dosage']}</div>
      <div class="note">{s.get('notes', '')}</div>
    </div>\n'''

    # --- Transition timeline ---
    transition_steps = ""
    for i, step in enumerate(result.transition_plan):
        if "note" in step:
            continue
        is_final = (i == len(result.transition_plan) - 1) or (i == len([s for s in result.transition_plan if "note" not in s]) - 1)
        final_cls = " final" if is_final else ""
        transition_steps += f'''<div class="tl-step{final_cls}">
      <div class="row1">
        <span class="days-badge">Дни {step['days']}</span>
        <span class="step-name">{step['title']}</span>
      </div>
      <div class="step-text">{step['desc']}</div>
    </div>\n'''

    # Transition warning
    transition_note = ""
    for step in result.transition_plan:
        if "note" in step:
            transition_note = step["note"]
            break

    # --- Forbidden foods ---
    danger_rows = ""
    for food, reason in FORBIDDEN_FOODS:
        danger_rows += f'<div class="danger-row"><div class="x">{_SVG_X}</div><div><div class="nm">{food}</div><div class="why">{reason}</div></div></div>\n'

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8" />
<title>Кусь · Индивидуальный рацион · {dog.name}</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
<style>
:root {{
  --primary: #055ba9;
  --primary-dark: #04467f;
  --primary-soft: #e6f0fa;
  --primary-softer: #f3f8fd;
  --accent: #f59e0b;
  --accent-deep: #d97706;
  --accent-soft: #fef3c7;
  --ink: #0b1726;
  --ink-soft: #475569;
  --ink-light: #94a3b8;
  --border: #e2e8f0;
  --border-soft: #eef2f7;
  --bg: #ffffff;
  --bg-soft: #f7f9fc;
  --bg-warm: #fdfbf7;
  --green: #16a34a;
  --green-soft: #dcfce7;
  --red: #dc2626;
  --red-soft: #fee2e2;
  --pink-soft: #fde8ec;
  --blue-soft: #e0f2fe;
  --yellow-soft: #fef3c7;
}}

* {{ box-sizing: border-box; }}

html, body {{
  margin: 0; padding: 0;
  background: #e6e9ef;
  font-family: "Golos Text", system-ui, sans-serif;
  color: var(--ink);
  font-size: 11pt;
  line-height: 1.45;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}}

/* ===== Print toolbar ====================================== */
.toolbar {{
  position: fixed;
  top: 16px; right: 16px;
  z-index: 100;
  display: flex; gap: 8px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 8px;
  box-shadow: 0 12px 30px -12px rgba(11,23,38,0.25);
}}
.toolbar button {{
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  background: var(--primary);
  color: #fff;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}}
.toolbar .hint {{
  font-size: 11px;
  color: var(--ink-light);
  align-self: center;
  padding: 0 6px;
}}

/* ===== A4 page ========================================================== */
.page {{
  width: 210mm;
  min-height: 297mm;
  margin: 16px auto;
  background: #fff;
  position: relative;
  padding: 18mm 16mm 14mm;
  box-sizing: border-box;
  box-shadow: 0 12px 32px -16px rgba(11,23,38,0.25);
  overflow: hidden;
  page-break-after: always;
  break-after: page;
  zoom: var(--page-zoom, 1);
}}
.page:last-of-type {{ page-break-after: auto; }}

.page-foot {{
  position: absolute;
  left: 0; right: 0; bottom: 8mm;
  text-align: center;
  font-size: 8pt;
  color: var(--ink-light);
  letter-spacing: 0.05em;
}}
.page-foot strong {{ color: var(--ink-soft); font-weight: 600; }}

.page-head {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8mm;
  padding-bottom: 5mm;
  border-bottom: 1px solid var(--border-soft);
}}
.page-head .logo {{ display: inline-flex; align-items: center; gap: 8px; }}
.page-head .logo .mark {{
  width: 26px; height: 26px;
  border-radius: 8px;
  background: var(--primary);
  color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
}}
.page-head .logo .name {{
  font-weight: 800;
  font-size: 16px;
  color: var(--primary);
  letter-spacing: -0.02em;
}}
.page-head .meta {{
  font-size: 9pt;
  color: var(--ink-light);
}}
.page-head .meta strong {{ color: var(--ink-soft); font-weight: 600; }}

/* ===== Common typography ================================================ */
h1, h2, h3, h4 {{ margin: 0; letter-spacing: -0.02em; color: var(--ink); }}
h1 {{ font-size: 34pt; font-weight: 800; line-height: 1.02; letter-spacing: -0.035em; }}
h2 {{ font-size: 22pt; font-weight: 700; line-height: 1.1; }}
h3 {{ font-size: 14pt; font-weight: 700; }}
h4 {{ font-size: 11pt; font-weight: 700; }}
p {{ margin: 0; }}
.eyebrow {{
  display: inline-block;
  font-size: 9pt;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--primary);
  background: var(--primary-soft);
  padding: 5px 12px;
  border-radius: 100px;
}}
.section-title {{
  font-size: 18pt;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--ink);
  margin-bottom: 4mm;
}}
.section-sub {{
  font-size: 10pt;
  color: var(--ink-soft);
  margin-bottom: 6mm;
  max-width: 145mm;
}}

/* ===== PAGE 1 — Cover =================================================== */
.cover {{ padding: 0; }}
.cover .top-bar {{
  height: 6mm;
  background: linear-gradient(90deg, var(--primary) 0%, var(--primary) 55%, var(--accent) 100%);
}}
.cover-inner {{ padding: 14mm 16mm 14mm; }}
.cover-head {{
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 18mm;
}}
.cover-head .logo .name {{ font-size: 22px; }}
.cover-head .logo .mark {{ width: 34px; height: 34px; border-radius: 10px; }}
.cover-head .doc-id {{
  text-align: right;
  font-size: 9pt;
  color: var(--ink-light);
  line-height: 1.6;
}}
.cover-head .doc-id .label {{
  display: inline-block;
  font-size: 8pt;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--primary);
  background: var(--primary-soft);
  padding: 4px 10px;
  border-radius: 100px;
  margin-bottom: 6px;
}}

.cover-title-block {{ max-width: 130mm; }}
.cover-title-block .kicker {{
  font-size: 11pt;
  color: var(--ink-soft);
  font-weight: 500;
  margin-bottom: 6mm;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}}
.cover-title-block .kicker .dot {{
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--accent);
}}
.cover-title-block .dog-name {{
  font-size: 56pt;
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 0.95;
  color: var(--primary);
  margin: 4mm 0 6mm;
}}
.cover-title-block .breed {{
  font-size: 14pt;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 4mm;
}}
.cover-stats {{
  display: inline-flex;
  align-items: center;
  gap: 10mm;
  font-size: 11pt;
  color: var(--ink-soft);
}}
.cover-stats .stat strong {{ font-size: 14pt; font-weight: 700; color: var(--ink); }}
.cover-stats .divider {{ width: 1px; height: 24px; background: var(--border); }}

.cover-badge {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 8mm;
  padding: 8px 16px;
  background: var(--accent);
  color: #fff;
  font-weight: 700;
  font-size: 10pt;
  border-radius: 100px;
  letter-spacing: -0.005em;
}}
.cover-badge .dot {{ width: 8px; height: 8px; border-radius: 50%; background: #fff; }}

.cover-photo {{
  margin-top: 10mm;
  border-radius: 14px;
  overflow: hidden;
  height: 60mm;
  background: linear-gradient(135deg, var(--primary-soft), var(--bg-warm));
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ink-light);
  font-size: 10pt;
}}
.cover-photo img {{
  width: 100%; height: 100%; object-fit: cover; display: block;
}}
.cover-photo .float-card {{
  position: absolute;
  left: 8mm; bottom: 8mm;
  background: rgba(255,255,255,0.96);
  backdrop-filter: blur(8px);
  border-radius: 12px;
  padding: 10px 14px;
  display: flex; align-items: center; gap: 10px;
  box-shadow: 0 12px 30px -12px rgba(11,23,38,0.25);
}}
.cover-photo .float-card .ico {{
  width: 32px; height: 32px;
  border-radius: 8px;
  background: var(--primary-soft);
  color: var(--primary);
  display: flex; align-items: center; justify-content: center;
}}
.cover-photo .float-card .label {{ font-size: 8pt; color: var(--ink-soft); }}
.cover-photo .float-card .val {{ font-size: 11pt; font-weight: 700; color: var(--ink); }}

.cover-footer {{
  position: absolute;
  left: 16mm; right: 16mm; bottom: 12mm;
  display: flex; justify-content: space-between; align-items: center;
  font-size: 8.5pt;
  color: var(--ink-light);
  border-top: 1px solid var(--border-soft);
  padding-top: 5mm;
}}

/* ===== PAGE 2 — Summary ================================================= */
.metric-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4mm;
  margin-bottom: 8mm;
}}
.metric {{
  background: var(--bg-soft);
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 5mm;
}}
.metric .lbl {{
  font-size: 8pt;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--ink-soft);
  margin-bottom: 3mm;
}}
.metric .val {{
  font-size: 22pt;
  font-weight: 800;
  letter-spacing: -0.035em;
  color: var(--ink);
  line-height: 1;
}}
.metric .val .unit {{ font-size: 11pt; font-weight: 600; color: var(--ink-soft); margin-left: 4px; }}
.metric .sub {{ font-size: 8.5pt; color: var(--ink-light); margin-top: 2mm; }}

.summary-grid {{
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 6mm;
  margin-bottom: 6mm;
}}

.group-table {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 5mm 6mm;
}}
.group-table h4 {{ margin-bottom: 4mm; font-size: 10pt; text-transform: uppercase; letter-spacing: 0.1em; color: var(--ink-soft); }}

.group-row {{
  display: grid;
  grid-template-columns: 16px 1fr auto;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
  border-bottom: 1px dashed var(--border-soft);
  font-size: 10pt;
}}
.group-row:last-child {{ border-bottom: none; }}
.group-row .sw {{ width: 10px; height: 10px; border-radius: 3px; }}
.group-row .nm {{ color: var(--ink); }}
.group-row .g {{ font-weight: 700; font-feature-settings: "tnum"; }}

.stack {{
  display: flex;
  height: 22px;
  border-radius: 6px;
  overflow: hidden;
  margin: 4mm 0;
  border: 1px solid var(--border-soft);
}}
.stack span {{ display: block; height: 100%; }}

.pie-card {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 5mm;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}}
.pie {{
  width: 38mm; height: 38mm;
  border-radius: 50%;
  background: conic-gradient({pie_gradient});
  position: relative;
  display: flex; align-items: center; justify-content: center;
}}
.pie::after {{
  content: ""; position: absolute; inset: 24%;
  background: #fff; border-radius: 50%;
}}
.pie .center {{
  position: relative;
  z-index: 1;
  text-align: center;
  font-size: 9pt;
  font-weight: 600;
  color: var(--ink-soft);
}}
.pie .center strong {{ display: block; font-size: 16pt; color: var(--ink); font-weight: 800; }}

.warn-grid {{ display: grid; gap: 3mm; }}
.warn {{
  display: flex; gap: 10px; align-items: flex-start;
  background: var(--yellow-soft);
  border-left: 3px solid var(--accent);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 9.5pt;
  color: var(--ink);
}}
.warn .ico {{
  flex: 0 0 auto;
  width: 22px; height: 22px;
  border-radius: 6px;
  background: var(--accent);
  color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
  margin-top: -1px;
}}

/* ===== PAGES 3-4 — Weekly menu ========================================== */
.menu-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 3mm;
}}
.day {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 4mm 4.5mm;
  display: flex; flex-direction: column;
  page-break-inside: avoid;
  break-inside: avoid;
}}
.day.special {{ border-color: var(--primary); background: var(--primary-softer); }}
.day-head {{
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 2mm;
}}
.day-name {{
  font-size: 12pt;
  font-weight: 700;
  color: var(--primary);
  letter-spacing: -0.01em;
}}
.day-tag {{
  font-size: 7.5pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  padding: 3px 8px;
  border-radius: 100px;
  background: var(--bg-soft);
  color: var(--ink-soft);
  display: inline-flex; align-items: center; gap: 4px;
}}
.day-tag.fish {{ background: #dbeafe; color: #1e3a8a; }}

.meal-block + .meal-block {{ margin-top: 2mm; padding-top: 2mm; border-top: 1px dashed var(--border-soft); }}
.meal-time {{
  font-size: 7.5pt;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--ink-light);
  margin-bottom: 1.5mm;
  display: flex; align-items: center; gap: 6px;
}}
.meal-time .dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--accent); }}
.meal-time.evening .dot {{ background: var(--primary); }}

.item {{
  display: flex; align-items: baseline;
  font-size: 9pt;
  padding: 1px 0;
  gap: 6px;
  line-height: 1.35;
}}
.item .nm {{ color: var(--ink); }}
.item .leader {{ flex: 1; border-bottom: 1px dotted var(--ink-light); margin: 0 2px; transform: translateY(-3px); }}
.item .g {{ font-weight: 600; font-feature-settings: "tnum"; color: var(--ink); white-space: nowrap; }}

/* ===== PAGE 5 — Shopping list =========================================== */
.shop-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4mm;
}}
.shop-group {{
  border-radius: 12px;
  padding: 5mm;
  page-break-inside: avoid;
  break-inside: avoid;
}}
.shop-group.meat {{ background: var(--pink-soft); }}
.shop-group.bones {{ background: #fde2cf; }}
.shop-group.organs {{ background: #f4e1f3; }}
.shop-group.veg {{ background: var(--green-soft); }}
.shop-group.dairy {{ background: var(--blue-soft); }}
.shop-group.eggs {{ background: var(--yellow-soft); }}

.shop-group h4 {{
  display: flex; align-items: center; justify-content: space-between;
  font-size: 9pt;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 4mm;
  padding-bottom: 3mm;
  border-bottom: 1px solid rgba(11,23,38,0.08);
}}

.shop-item {{
  display: grid;
  grid-template-columns: 14px 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
  font-size: 10pt;
  border-bottom: 1px dashed rgba(11,23,38,0.08);
}}
.shop-item:last-child {{ border-bottom: none; }}
.shop-item .check {{
  width: 12px; height: 12px;
  border: 1.5px solid var(--ink-soft);
  border-radius: 3px;
  background: rgba(255,255,255,0.6);
}}
.shop-item .nm {{ color: var(--ink); }}
.shop-item .g {{ font-weight: 700; font-feature-settings: "tnum"; }}

.shop-tip {{
  margin-top: 5mm;
  background: var(--primary);
  color: #fff;
  border-radius: 12px;
  padding: 5mm 6mm;
  display: flex; gap: 10px;
  align-items: flex-start;
  font-size: 10pt;
  line-height: 1.55;
}}
.shop-tip strong {{ display: block; font-weight: 700; margin-bottom: 2px; }}

/* ===== PAGE 6 — Supplements ============================================= */
.supp-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4mm;
}}
.supp {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  padding: 6mm;
  display: flex; flex-direction: column;
  gap: 3mm;
}}
.supp .head {{ display: flex; align-items: center; gap: 10px; }}
.supp .head .ico {{
  width: 44px; height: 44px;
  border-radius: 12px;
  background: var(--primary-soft);
  color: var(--primary);
  display: inline-flex; align-items: center; justify-content: center;
}}
.supp .head .name {{ font-size: 13pt; font-weight: 700; color: var(--ink); }}
.supp .head .freq {{ font-size: 8.5pt; color: var(--ink-light); margin-top: 2px; }}
.supp .dose {{
  font-size: 20pt;
  font-weight: 800;
  color: var(--primary);
  letter-spacing: -0.03em;
  line-height: 1;
}}
.supp .note {{ font-size: 9.5pt; color: var(--ink-soft); line-height: 1.5; }}

.supp.full {{ grid-column: span 2; flex-direction: row; align-items: center; gap: 6mm; }}
.supp.full .left {{ flex: 1; }}

/* ===== PAGE 7 — Transition timeline ===================================== */
.timeline {{ position: relative; padding-left: 18mm; margin-top: 4mm; }}
.timeline::before {{
  content: ""; position: absolute;
  left: 8mm; top: 4mm; bottom: 4mm;
  width: 2px; background: var(--border);
}}
.tl-step {{
  position: relative;
  margin-bottom: 5mm;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 5mm 6mm;
  page-break-inside: avoid;
  break-inside: avoid;
}}
.tl-step:last-child {{ margin-bottom: 0; }}
.tl-step::before {{
  content: "";
  position: absolute;
  left: -10mm;
  top: 7mm;
  width: 14px; height: 14px;
  border-radius: 50%;
  background: var(--primary);
  border: 3px solid #fff;
  box-shadow: 0 0 0 2px var(--primary);
}}
.tl-step.final::before {{ background: var(--accent); box-shadow: 0 0 0 2px var(--accent); }}
.tl-step .row1 {{
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 2mm;
}}
.tl-step .days-badge {{
  font-size: 9pt;
  font-weight: 700;
  color: #fff;
  background: var(--primary);
  padding: 4px 10px;
  border-radius: 6px;
  letter-spacing: -0.01em;
}}
.tl-step.final .days-badge {{ background: var(--accent); }}
.tl-step .step-name {{
  font-size: 13pt;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.01em;
}}
.tl-step .step-text {{ font-size: 10pt; color: var(--ink-soft); line-height: 1.55; }}

.tl-warn {{
  margin-top: 4mm;
  background: #fee2e2;
  border-left: 3px solid var(--red);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 9.5pt;
  color: var(--ink);
  display: flex; gap: 10px; align-items: flex-start;
}}
.tl-warn .ico {{
  flex: 0 0 auto;
  width: 22px; height: 22px;
  border-radius: 6px;
  background: var(--red);
  color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
}}

/* ===== PAGE 8 — Reminders =============================================== */
.memo-section {{ margin-bottom: 6mm; }}
.memo-section h3 {{
  font-size: 12pt;
  margin-bottom: 4mm;
  display: inline-flex; align-items: center; gap: 8px;
}}
.memo-section h3 .pill {{
  font-size: 8pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  padding: 4px 10px;
  border-radius: 100px;
}}
.pill.red {{ background: var(--red-soft); color: var(--red); }}
.pill.green {{ background: var(--green-soft); color: var(--green); }}
.pill.amber {{ background: var(--accent-soft); color: var(--accent-deep); }}

.danger-grid {{
  display: grid; grid-template-columns: 1fr 1fr; gap: 3mm;
}}
.danger-row {{
  display: flex; gap: 10px; align-items: flex-start;
  padding: 8px 12px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  font-size: 9.5pt;
  line-height: 1.45;
}}
.danger-row .x {{
  flex: 0 0 auto;
  width: 22px; height: 22px;
  border-radius: 50%;
  background: var(--red-soft);
  color: var(--red);
  display: inline-flex; align-items: center; justify-content: center;
  margin-top: -1px;
}}
.danger-row .nm {{ color: var(--ink); font-weight: 600; }}
.danger-row .why {{ color: var(--ink-soft); font-weight: 400; }}

.check-grid {{
  display: grid; grid-template-columns: 1fr 1fr; gap: 3mm;
}}
.check-row {{
  display: flex; gap: 10px; align-items: flex-start;
  padding: 8px 12px;
  background: var(--green-soft);
  border-radius: 10px;
  font-size: 9.5pt;
  line-height: 1.45;
}}
.check-row .v {{
  flex: 0 0 auto;
  width: 22px; height: 22px;
  border-radius: 50%;
  background: var(--green);
  color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
}}
.check-row strong {{ color: var(--ink); font-weight: 700; display: block; }}
.check-row span {{ color: var(--ink-soft); }}

.vet-grid {{
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 3mm;
}}
.vet-row {{
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 10px;
  padding: 10px;
  font-size: 9pt;
  line-height: 1.4;
  color: var(--ink);
  display: flex; flex-direction: column; gap: 6px;
}}
.vet-row .ico {{
  width: 24px; height: 24px;
  border-radius: 6px;
  background: var(--accent);
  color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
}}

/* ===== PAGE 9 — Disclaimer / contacts =================================== */
.last-page {{ background: var(--bg-soft); }}
.disclaimer-card {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  padding: 8mm;
  margin-bottom: 6mm;
  position: relative;
}}
.disclaimer-card .quote {{
  position: absolute;
  top: -8px; left: 6mm;
  font-size: 36pt;
  font-weight: 800;
  color: var(--primary);
  line-height: 1;
}}
.disclaimer-card p {{
  font-size: 10.5pt;
  line-height: 1.6;
  color: var(--ink);
  font-style: italic;
  padding-left: 14mm;
}}
.contact-grid {{
  display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4mm;
}}
.contact-card {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 6mm;
  display: flex; flex-direction: column; gap: 4mm;
  align-items: flex-start;
}}
.contact-card .ico {{
  width: 44px; height: 44px;
  border-radius: 12px;
  background: var(--primary-soft);
  color: var(--primary);
  display: inline-flex; align-items: center; justify-content: center;
}}
.contact-card .label {{ font-size: 8.5pt; color: var(--ink-light); text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600; }}
.contact-card .val {{ font-size: 13pt; font-weight: 700; color: var(--ink); letter-spacing: -0.01em; }}

.support-strip {{
  margin-top: 6mm;
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: #fff;
  border-radius: 16px;
  padding: 8mm 10mm;
  display: grid;
  grid-template-columns: 1fr;
  gap: 4mm;
}}
.support-strip h3 {{ color: #fff; font-size: 18pt; margin-bottom: 3mm; }}
.support-strip p {{ font-size: 11pt; line-height: 1.5; color: rgba(255,255,255,0.85); }}

.bye {{
  text-align: center;
  margin-top: 8mm;
  padding-top: 6mm;
  border-top: 1px solid var(--border-soft);
  font-size: 9pt;
  color: var(--ink-light);
}}

/* ===== Mobile scaling =================================================== */
@media (max-width: 820px) {{
  body {{ background: #eef0f4; }}
  .page {{
    margin: 10px auto;
    box-shadow: 0 6px 18px -8px rgba(11,23,38,0.25);
  }}
  .toolbar {{
    top: auto; right: 12px; bottom: 12px;
    padding: 6px;
    border-radius: 10px;
  }}
  .toolbar .hint {{ display: none; }}
  .toolbar button {{ padding: 9px 13px; font-size: 12px; }}
}}

/* ===== Print ============================================================ */
@page {{ size: A4 portrait; margin: 0; }}
@media print {{
  html, body {{ background: #fff; }}
  .toolbar {{ display: none !important; }}
  .page {{
    margin: 0;
    box-shadow: none;
    width: 210mm;
    height: 297mm;
    max-height: 297mm;
    overflow: hidden;
    zoom: 1 !important;
    padding: 18mm 16mm 14mm;
    box-sizing: border-box;
  }}
  .page:last-of-type {{ page-break-after: auto; }}
  .cover .top-bar, .cover-photo, .cover-badge, .metric, .pie, .stack span,
  .warn, .day.special, .shop-group, .shop-tip, .supp .head .ico,
  .tl-step::before, .tl-warn, .support-strip, .hero-rec,
  .check-row .v, .danger-row .x, .vet-row .ico {{
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
  }}
}}
</style>
</head>
<body>

<div class="toolbar">
  <span class="hint">A4 · {total_pages} страниц</span>
  <button onclick="window.print()">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9"></polyline><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>
    Печать / Сохранить PDF
  </button>
</div>

<script>
  (function () {{
    var PAGE_W_PX = 794;
    function fit() {{
      var vw = document.documentElement.clientWidth;
      var sidePad = 20;
      if (vw < PAGE_W_PX + sidePad * 2) {{
        var scale = Math.max(0.3, Math.min(1, (vw - sidePad) / PAGE_W_PX));
        document.documentElement.style.setProperty('--page-zoom', scale.toFixed(4));
      }} else {{
        document.documentElement.style.setProperty('--page-zoom', 1);
      }}
    }}
    fit();
    window.addEventListener('resize', fit);
    window.addEventListener('orientationchange', fit);
  }})();
</script>

<!-- ============================================================ -->
<!-- PAGE 1 — COVER                                                -->
<!-- ============================================================ -->
<section class="page cover">
  <div class="top-bar"></div>
  <div class="cover-inner">
    <div class="cover-head">
      <div class="logo">
        <span class="mark">{_SVG_PAW.format(w=20)}</span>
        <span class="name">Кусь</span>
      </div>
      <div class="doc-id">
        <div class="label">{doc_id}</div>
        <div>составлен {today}</div>
      </div>
    </div>

    <div class="cover-title-block">
      <div class="kicker"><span class="dot"></span> Индивидуальный рацион</div>
      <div class="dog-name">{dog.name}</div>
      <div class="breed">{dog.breed}</div>
      <div class="cover-stats">
        <div class="stat"><strong>{age_text}</strong><div style="font-size:9pt;color:var(--ink-light);">возраст</div></div>
        <div class="divider"></div>
        <div class="stat"><strong>{dog.weight_kg} кг</strong><div style="font-size:9pt;color:var(--ink-light);">текущий вес</div></div>
        <div class="divider"></div>
        <div class="stat"><strong>{sex_text}</strong><div style="font-size:9pt;color:var(--ink-light);">пол</div></div>
        <div class="divider"></div>
        <div class="stat"><strong>{ACTIVITY_LABELS.get(dog.activity, dog.activity)}</strong><div style="font-size:9pt;color:var(--ink-light);">активность</div></div>
      </div>
      <div style="margin-top: 6mm;">
        <span class="cover-badge"><span class="dot"></span>{DIET_TYPE_LABELS.get(dog.diet_type, dog.diet_type)}</span>
      </div>
    </div>

    <div class="cover-photo">
      {'<img src="data:image/png;base64,' + getattr(result, 'cover_image_b64', '') + '" alt="' + name + '">' if getattr(result, 'cover_image_b64', '') else '<span>Фото ' + name_g + '</span>'}
      <div class="float-card">
        <div class="ico">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>
        </div>
        <div>
          <div class="label">Целевой вес</div>
          <div class="val">{result.ideal_weight_kg} кг</div>
        </div>
      </div>
    </div>
  </div>
  <div class="cover-footer">
    <div>kus.dogfine.ru · @doggifood_bot</div>
    <div>Кусь · Подбор рациона для собак</div>
    <div>стр. 1 / {total_pages}</div>
  </div>
</section>

<!-- ============================================================ -->
<!-- PAGE 2 — SUMMARY                                              -->
<!-- ============================================================ -->
<section class="page">
  {_page_head(f"<strong>{dog.name}</strong> · {dog.breed}, {age_text}, {dog.weight_kg} кг · {doc_id}")}

  <div class="eyebrow">Сводка по рациону</div>
  <h2 class="section-title" style="margin-top: 4mm;">Что и сколько съедает {name} за день</h2>
  <p class="section-sub">{getattr(result, 'ai_intro', '') or f'Рассчитано на основе целевого веса {result.ideal_weight_kg} кг и {ACTIVITY_LABELS.get(dog.activity, "средней").lower()} активности. Поделено на {result.meals_per_day} кормления.'}</p>

  <div class="metric-grid">
    <div class="metric">
      <div class="lbl">Суточная норма</div>
      <div class="val">{int(result.daily_grams)}<span class="unit">г</span></div>
      <div class="sub">в {result.meals_per_day} порции</div>
    </div>
    <div class="metric">
      <div class="lbl">Калорийность</div>
      <div class="val">{int(result.mer_kcal)}<span class="unit">ккал</span></div>
      <div class="sub">≈ {int(result.mer_kcal / result.ideal_weight_kg) if result.ideal_weight_kg > 0 else 0} ккал/кг</div>
    </div>
    <div class="metric">
      <div class="lbl">Кормлений</div>
      <div class="val">{result.meals_per_day}<span class="unit">раза</span></div>
      <div class="sub">утро · вечер</div>
    </div>
    <div class="metric">
      <div class="lbl">Целевой вес</div>
      <div class="val">{result.ideal_weight_kg}<span class="unit">кг</span></div>
      <div class="sub">{f"−{weight_diff} кг" if weight_diff > 0 else f"+{abs(weight_diff)} кг" if weight_diff < 0 else "в норме"}</div>
    </div>
  </div>

  <div class="summary-grid">
    <div class="group-table">
      <h4>Распределение по группам · {int(total_grams)} г</h4>
      <div class="stack">
        {stack_spans}
      </div>
      {distribution_rows}
    </div>

    <div style="display:flex; flex-direction:column; gap:4mm;">
      <div class="pie-card">
        <div class="pie">
          <div class="center"><strong>{int(dominant_pct)}%</strong>{dominant_group}</div>
        </div>
        <div style="font-size:8.5pt; color:var(--ink-soft); margin-top:3mm; text-align:center; line-height:1.4;">
          {DIET_TYPE_LABELS.get(dog.diet_type, dog.diet_type)}
        </div>
      </div>
    </div>
  </div>

  <div class="warn-grid">
    {warnings_html}
  </div>

  {_page_foot(2, total_pages, doc_id)}
</section>

<!-- ============================================================ -->
<!-- PAGE 3 — MENU DAYS 1-4                                        -->
<!-- ============================================================ -->
<section class="page">
  {_page_head("<strong>Меню на неделю</strong> · часть 1 из 2")}

  <div class="eyebrow">{menu_page1[0].day_name if menu_page1 else ""} — {menu_page1[-1].day_name if menu_page1 else ""}</div>
  <h2 class="section-title" style="margin-top: 3mm; margin-bottom: 2mm;">Меню на неделю</h2>
  <p class="section-sub" style="margin-bottom: 4mm;">Каждый день — {result.meals_per_day} кормления. Граммовки указаны для миски «как есть».</p>

  <div class="menu-grid">
    {menu_page1_html}
  </div>

  {_page_foot(3, total_pages, doc_id)}
</section>

<!-- ============================================================ -->
<!-- PAGE 4 — MENU DAYS 5-7                                        -->
<!-- ============================================================ -->
<section class="page">
  {_page_head("<strong>Меню на неделю</strong> · часть 2 из 2")}

  <div class="eyebrow">{menu_page2[0].day_name if menu_page2 else ""} — {menu_page2[-1].day_name if menu_page2 else ""}</div>
  <h2 class="section-title" style="margin-top: 3mm; margin-bottom: 2mm;">Меню на неделю</h2>

  <div class="menu-grid">
    {menu_page2_html}
    {week_summary}
  </div>

  {_page_foot(4, total_pages, doc_id)}
</section>

<!-- ============================================================ -->
<!-- PAGE 5 — SHOPPING LIST                                        -->
<!-- ============================================================ -->
<section class="page">
  {_page_head("<strong>Список покупок</strong> · на неделю")}

  <div class="eyebrow">Чек-лист</div>
  <h2 class="section-title" style="margin-top: 4mm;">Список покупок на неделю</h2>
  <p class="section-sub">Распечатайте — и отмечайте по мере покупки. Все веса — на 7 дней для {name_g}.</p>

  <div class="shop-grid">
    {shopping_html}
  </div>

  <div class="shop-tip">
    <div>
      <strong>Совет от Кусь</strong>
      Разделите мясо на порции по 100–130&nbsp;г сразу после покупки и заморозьте. Размораживайте в холодильнике 12&nbsp;часов — не на столе. Кости давайте полу-размороженными.
    </div>
  </div>

  {_page_foot(5, total_pages, doc_id)}
</section>

<!-- ============================================================ -->
<!-- PAGE 6 — SUPPLEMENTS                                          -->
<!-- ============================================================ -->
<section class="page">
  {_page_head("<strong>Витамины и добавки</strong>")}

  <div class="eyebrow">Что добавлять каждый день</div>
  <h2 class="section-title" style="margin-top: 4mm;">Витамины и добавки</h2>
  <p class="section-sub">Дозировки рассчитаны под целевой вес {result.ideal_weight_kg} кг. Делите между кормлениями, если не указано иное.</p>

  <div class="supp-grid">
    {supp_cards}
  </div>

  {'<div style="margin-top: 6mm; background: var(--primary-softer); border-left: 3px solid var(--primary); border-radius: 8px; padding: 5mm 6mm; font-size: 9.5pt; line-height: 1.6; color: var(--ink);"><div style="font-size: 8pt; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--primary); margin-bottom: 3mm;">Персональные рекомендации</div>' + getattr(result, 'ai_notes', '').replace(chr(10), '<br/>') + '</div>' if getattr(result, 'ai_notes', '') else ''}

  {_page_foot(6, total_pages, doc_id)}
</section>

<!-- ============================================================ -->
<!-- PAGE 7 — TRANSITION                                           -->
<!-- ============================================================ -->
<section class="page">
  {_page_head("<strong>Перевод на новый рацион</strong>")}

  <div class="eyebrow">Схема перевода</div>
  <h2 class="section-title" style="margin-top: 4mm;">Как мягко перевести {name_a} на натуралку</h2>
  <p class="section-sub">Если {name} сейчас на сухом корме — не меняйте рацион за один день. Идите по этапам.</p>

  <div class="timeline">
    {transition_steps}
  </div>

  <div class="tl-warn">
    <div class="ico">{_SVG_WARN}</div>
    <div><strong style="display:block; font-weight:700; margin-bottom:2px;">Если диарея — вернитесь на шаг назад</strong>{transition_note if transition_note else "Не паникуйте: ЖКТ настраивается на новый тип пищи 7–14 дней. Уменьшите порцию вдвое на сутки, затем продолжайте схему с предыдущего этапа."}</div>
  </div>

  {_page_foot(7, total_pages, doc_id)}
</section>

<!-- ============================================================ -->
<!-- PAGE 8 — REMINDERS                                            -->
<!-- ============================================================ -->
<section class="page">
  {_page_head("<strong>Памятка владельцу</strong>")}

  <div class="eyebrow">Запомнить и распечатать на холодильник</div>
  <h2 class="section-title" style="margin-top: 4mm;">Памятка</h2>

  <div class="memo-section">
    <h3>Что НЕЛЬЗЯ давать собакам <span class="pill red">опасно</span></h3>
    <div class="danger-grid">
      {danger_rows}
    </div>
  </div>

  <div class="memo-section">
    <h3>Как понять, что рацион подошёл <span class="pill green">через 2–4 недели</span></h3>
    <div class="check-grid">
      <div class="check-row"><div class="v">{_SVG_CHECK}</div><div><strong>Стул</strong><span>оформленный, 1–2 раза в день</span></div></div>
      <div class="check-row"><div class="v">{_SVG_CHECK}</div><div><strong>Шерсть</strong><span>блестящая, меньше выпадает</span></div></div>
      <div class="check-row"><div class="v">{_SVG_CHECK}</div><div><strong>Энергия</strong><span>активна на прогулке, хорошо спит</span></div></div>
      <div class="check-row"><div class="v">{_SVG_CHECK}</div><div><strong>Аппетит</strong><span>ест с удовольствием, миску вылизывает</span></div></div>
      <div class="check-row"><div class="v">{_SVG_CHECK}</div><div><strong>Вес</strong><span>стабилен или движется к целевому</span></div></div>
      <div class="check-row"><div class="v">{_SVG_CHECK}</div><div><strong>Запах</strong><span>уходит из пасти и от кожи</span></div></div>
    </div>
  </div>

  <div class="memo-section" style="margin-bottom: 0;">
    <h3>Когда срочно к ветеринару <span class="pill amber">не откладывайте</span></h3>
    <div class="vet-grid">
      <div class="vet-row"><div class="ico">{_SVG_WARN}</div>Диарея или рвота более 24 часов</div>
      <div class="vet-row"><div class="ico">{_SVG_WARN}</div>Отказ от еды более суток</div>
      <div class="vet-row"><div class="ico">{_SVG_WARN}</div>Кровь в стуле или рвоте</div>
      <div class="vet-row"><div class="ico">{_SVG_WARN}</div>Сильный зуд или отёк морды</div>
      <div class="vet-row"><div class="ico">{_SVG_WARN}</div>Внезапная вялость, апатия</div>
    </div>
  </div>

  {_page_foot(8, total_pages, doc_id)}
</section>

<!-- ============================================================ -->
<!-- PAGE 9 — DISCLAIMER + CONTACTS                                -->
<!-- ============================================================ -->
<section class="page last-page">
  {_page_head("<strong>Дисклеймер и контакты</strong>")}

  <div class="eyebrow">Важно знать</div>
  <h2 class="section-title" style="margin-top: 4mm;">Несколько слов перед тем,<br/>как закроете PDF</h2>

  <div class="disclaimer-card">
    <div class="quote">«</div>
    <p>Данный рацион рассчитан на основе общепринятых ветеринарных норм <strong>NRC&nbsp;2006</strong>, <strong>FEDIAF</strong> и <strong>AAFCO</strong>. Он не заменяет очную консультацию ветеринарного врача. При наличии хронических заболеваний обязательно согласуйте рацион с лечащим ветеринаром.</p>
  </div>

  <h3 style="font-size: 12pt; margin-bottom: 4mm;">Связь с нами</h3>
  <div class="contact-grid">
    <div class="contact-card">
      <div class="ico">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l18-7-3 16-7-3-3 4v-5l10-9-12 7-3-2z"/></svg>
      </div>
      <div>
        <div class="label">Telegram-бот</div>
        <div class="val">@doggifood_bot</div>
      </div>
    </div>
    <div class="contact-card">
      <div class="ico">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18"/></svg>
      </div>
      <div>
        <div class="label">Сайт</div>
        <div class="val">kus.dogfine.ru</div>
      </div>
    </div>
  </div>

  <div class="support-strip">
    <div>
      <h3>7 дней бесплатной поддержки</h3>
      <p>Стул не такой? {name} отказался? Не уверены, нормальна ли реакция? Напишите в Telegram-бот — ответим за 15 минут в рабочее время.</p>
    </div>
  </div>

  <div class="bye">
    Спасибо, что доверили нам здоровье {name_g} ♥<br/>
    © 2026 Кусь · Doggi · kus.dogfine.ru
  </div>

  {_page_foot(9, total_pages, doc_id)}
</section>

</body>
</html>"""
    return html


def generate_pdf(result: DietResult, output_path: str = None) -> str:
    """Генерирует PDF и возвращает путь к файлу."""
    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(__file__),
            "output",
            f"ration_{result.dog.name}_{date.today().isoformat()}.pdf"
        )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    html_content = generate_html(result)

    if WEASYPRINT_AVAILABLE:
        HTML(string=html_content).write_pdf(output_path)
        print(f"PDF создан: {output_path}")
    else:
        # Сохраняем HTML как fallback
        html_path = output_path.replace(".pdf", ".html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"WeasyPrint не установлен. HTML сохранён: {html_path}")
        return html_path

    return output_path


# ---------------------------------------------------------------------------
# Тест
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    calc = DietCalculator()

    dog = DogProfile(
        name="Барон",
        breed="Лабрадор-ретривер",
        age_months=36,
        sex="male",
        neutered=True,
        weight_kg=32,
        current_food="dry",
        condition="chubby",
        activity="moderate",
        diagnoses=[],
        stool="good",
        diet_type="barf",
        budget="market",
        stop_products=["курица"],
    )

    result = calc.calculate(dog)
    path = generate_pdf(result)
    print(f"Готово: {path}")
