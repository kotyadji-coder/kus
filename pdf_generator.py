"""
Генерация PDF-файла с рационом собаки.
Использует WeasyPrint (HTML -> PDF).
"""

import os
import base64
import io
from datetime import date
from calculator import DietResult, DietCalculator, DogProfile
from declension import decline_name

try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False


def _generate_qr_b64(url: str) -> str:
    """Генерирует QR-код как base64 PNG."""
    try:
        import qrcode
        qr = qrcode.make(url, box_size=4, border=2)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return ""

DIET_TYPE_LABELS = {"barf": "BARF (сырое)", "cooked": "Термообработка\u00a0(варка)"}
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
    is_female = dog.sex == "female"
    pronoun_he = "она" if is_female else "он"
    pronoun_him = "её" if is_female else "его"
    verb_refused = "отказалась" if is_female else "отказался"
    adj_active = "активна" if is_female else "активен"

    # QR-код на бота
    qr_b64 = _generate_qr_b64("https://t.me/doggifood_bot")
    qr_img = f'<img src="data:image/png;base64,{qr_b64}" alt="QR" style="width:22mm;height:22mm;">' if qr_b64 else ''

    # Склонения клички
    name = dog.name  # именительный
    name_g = decline_name(dog.name, "gent")  # родительный (кого? Барона)
    name_d = decline_name(dog.name, "datv")  # дательный (кому? Барону)
    name_a = decline_name(dog.name, "accs")  # винительный (кого? Барона)

    # Сезонная пометка
    _season = dog.season
    if _season == "default":
        _m = date.today().month
        _season = "winter" if _m in (11, 12, 1, 2, 3) else "summer" if _m in (6, 7, 8) else "default"
    season_note = ""
    if _season == "winter":
        season_note = " Учтена зимняя корректировка (+10% калорий)."
    elif _season == "summer":
        season_note = " Учтена летняя корректировка (−5% калорий)."
    pregnancy_note = ""
    if dog.pregnant:
        pregnancy_note = " Рацион увеличен с учётом беременности."
    elif dog.lactating:
        pregnancy_note = " Рацион увеличен с учётом лактации."

    # Count total pages: cover + summary + menu pages + shopping + supplements + transition + memo + [ai analysis] + disclaimer
    menu_days = result.weekly_menu
    menu_page1 = menu_days[:4]
    menu_page2 = menu_days[4:]

    ai_analysis_html = getattr(result, 'ai_analysis', '') or ''
    has_ai_analysis = bool(ai_analysis_html)

    # Split AI analysis into blocks for 2 pages (3 blocks each)
    ai_blocks_page1 = ""
    ai_blocks_page2 = ""
    if has_ai_analysis:
        import re
        # Split by finding each <div class="insight" ...> ... </div> block
        # Use a simple approach: split on the opening tag
        parts = re.split(r'(?=<div class="insight")', ai_analysis_html)
        blocks = [p.strip() for p in parts if p.strip().startswith('<div class="insight"')]

        if len(blocks) >= 4:
            mid = (len(blocks) + 1) // 2  # ceil division
            ai_blocks_page1 = '\n'.join(blocks[:mid])
            ai_blocks_page2 = '\n'.join(blocks[mid:])
        else:
            ai_blocks_page1 = ai_analysis_html
            ai_blocks_page2 = ""

    total_pages = (12 if ai_blocks_page2 else 11) if has_ai_analysis else 10

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
        distribution_rows += f'<div class="group-row"><span class="sw" style="background:{color};display:inline-block;width:10px;height:10px;border-radius:3px;vertical-align:middle;margin-right:6px;"></span><span class="nm">{label}</span> <span class="g" style="float:right;">{g_display}</span></div>\n'
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

    # --- Puppy recalc note ---
    if getattr(result, 'puppy_next_recalc', ''):
        result.warnings.append(result.puppy_next_recalc)

    # --- Cooking tips (for cooked diet) ---
    cooking_html = ""
    if getattr(result, 'cooking_tips', []):
        tips = "".join(f"<li>{t}</li>" for t in result.cooking_tips)
        cooking_html = f'<div class="warn" style="background: var(--primary-softer); border-left-color: var(--primary);"><div class="ico"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4M6.34 6.34l2.83 2.83M2 12h4m-.34 5.66l2.83-2.83M12 18v4m3.66-6.17l2.83 2.83M18 12h4m-6.17-3.66l2.83-2.83"/></svg></div><div><strong>Советы по приготовлению</strong><ul style="margin:4px 0 0;padding-left:18px;font-size:9pt;line-height:1.5;">{tips}</ul></div></div>'

    # --- Warnings ---
    warnings_html = ""
    for w in result.warnings:
        warnings_html += f'<div class="warn">⚠ {w}</div>\n'

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

    def _menu_table(days_list):
        rows = []
        for i in range(0, len(days_list), 2):
            left = _menu_card(days_list[i])
            right = _menu_card(days_list[i+1]) if i+1 < len(days_list) else ''
            rows.append(f'<tr><td>{left}</td><td>{right}</td></tr>')
        return '\n'.join(rows)

    menu_page1_html = _menu_table(menu_page1)
    menu_page2_html = _menu_table(menu_page2)

    # Week summary card
    total_week_grams = sum(
        sum(p.grams for p in d.morning) + sum(p.grams for p in d.evening)
        for d in menu_days
    )
    week_summary = f'''<div class="day" style="background: var(--bg-soft); border-style: dashed;">
      <div class="day-head"><div class="day-name" style="color:var(--ink);">Итого&nbsp;за&nbsp;неделю</div></div>
      <table style="width:100%;font-size:9.5pt;border-collapse:collapse;">
        <tr><td style="color:var(--ink-soft);padding:2px 0;">Общий вес рациона</td><td style="font-weight:700;text-align:right;padding:2px 0;">≈&nbsp;{total_week_grams/1000:.2f}&nbsp;кг</td></tr>
        <tr><td style="color:var(--ink-soft);padding:2px 0;">Кормлений в день</td><td style="font-weight:700;text-align:right;padding:2px 0;">{result.meals_per_day}</td></tr>
      </table>
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

    shop_groups_list = []
    for group_key, items in shopping_by_group.items():
        css_cls = SHOP_GROUP_CSS.get(group_key, "eggs")
        group_label = GROUP_LABELS.get(group_key, group_key)
        items_html = ""
        for pname, grams, pid in sorted(items, key=lambda x: -x[1]):
            g_str = _fmt_egg_or_grams(grams, pid, pname)
            items_html += f'<div class="shop-item"><div class="check"></div><div class="nm">{pname}</div><div class="g">{g_str}</div></div>\n'
        shop_groups_list.append(f'''<div class="shop-group {css_cls}">
      <h4><span>{group_label}</span></h4>
      {items_html}
    </div>''')

    # Build 2-column table from shop groups
    shopping_rows = ""
    for i in range(0, len(shop_groups_list), 2):
        left = shop_groups_list[i]
        right = shop_groups_list[i+1] if i+1 < len(shop_groups_list) else ''
        shopping_rows += f'<tr><td>{left}</td><td>{right}</td></tr>\n'
    shopping_html = shopping_rows

    # --- Supplements ---
    supp_cards = ""
    for s in result.supplements:
        supp_cards += f'''<div class="supp">
      <div class="head">
        <span class="name">{s['name']}</span>
        <span class="freq">{s.get('frequency', '')}</span>
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
    for i in range(0, len(FORBIDDEN_FOODS), 2):
        left = FORBIDDEN_FOODS[i]
        right = FORBIDDEN_FOODS[i+1] if i+1 < len(FORBIDDEN_FOODS) else None
        danger_rows += '<tr>'
        danger_rows += f'<td><span class="nm">✕ {left[0]}</span><br/><span class="why">{left[1]}</span></td>'
        if right:
            danger_rows += f'<td><span class="nm">✕ {right[0]}</span><br/><span class="why">{right[1]}</span></td>'
        else:
            danger_rows += '<td></td>'
        danger_rows += '</tr>\n'

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
.page-head .logo {{ display: inline-block; }}
.page-head .logo .mark {{
  width: 22px; height: 22px;
  border-radius: 6px;
  background: var(--primary);
  color: #fff;
  display: inline-block;
  text-align: center;
  line-height: 22px;
  vertical-align: middle;
  margin-right: 6px;
}}
.page-head .logo .mark svg {{ vertical-align: middle; }}
.page-head .logo .name {{
  font-weight: 800;
  font-size: 16px;
  color: var(--primary);
  letter-spacing: -0.02em;
  vertical-align: middle;
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
  display: inline-block;
  margin-top: 8mm;
  padding: 8px 16px;
  background: var(--accent);
  color: #fff;
  font-weight: 700;
  font-size: 9.5pt;
  border-radius: 100px;
  white-space: nowrap;
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
  width: 100%;
  border-collapse: separate;
  border-spacing: 3mm;
  margin-bottom: 6mm;
}}
.metric {{
  background: var(--bg-soft);
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 4mm;
  width: 25%;
  vertical-align: top;
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
  width: 100%;
  border-collapse: separate;
  border-spacing: 4mm 0;
  margin-bottom: 5mm;
}}
.summary-grid > tbody > tr > td:first-child {{ width: 58%; }}
.summary-grid > tbody > tr > td:last-child {{ width: 42%; vertical-align: top; }}

.group-table {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 5mm 6mm;
}}
.group-table h4 {{ margin-bottom: 4mm; font-size: 10pt; text-transform: uppercase; letter-spacing: 0.1em; color: var(--ink-soft); }}

.group-row {{
  padding: 4px 0;
  border-bottom: 1px dashed var(--border-soft);
  font-size: 9.5pt;
  line-height: 1.4;
}}
.group-row:last-child {{ border-bottom: none; }}
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

.warn-grid {{ margin-top: 3mm; }}
.warn {{
  background: var(--yellow-soft);
  border-left: 3px solid var(--accent);
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 8.5pt;
  color: var(--ink);
  margin-bottom: 2mm;
  line-height: 1.4;
  page-break-inside: avoid;
}}

/* ===== PAGES 3-4 — Weekly menu ========================================== */
.menu-grid {{
  width: 100%;
  border-collapse: separate;
  border-spacing: 2mm;
}}
.menu-grid td {{ width: 50%; vertical-align: top; }}
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
  width: 100%;
  border-collapse: separate;
  border-spacing: 2mm;
}}
.shop-grid td {{ width: 50%; vertical-align: top; }}
.shop-group {{
  border-radius: 10px;
  padding: 4mm;
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
  padding: 3px 0;
  font-size: 9.5pt;
  border-bottom: 1px dashed rgba(11,23,38,0.08);
  line-height: 1.4;
}}
.shop-item:last-child {{ border-bottom: none; }}
.shop-item .check {{
  width: 11px; height: 11px;
  border: 1.5px solid var(--ink-soft);
  border-radius: 3px;
  background: rgba(255,255,255,0.6);
  display: inline-block;
  vertical-align: middle;
  margin-right: 6px;
}}
.shop-item .nm {{ color: var(--ink); }}
.shop-item .g {{ font-weight: 700; font-feature-settings: "tnum"; float: right; }}

.shop-tip {{
  margin-top: 3mm;
  background: var(--primary);
  color: #fff;
  border-radius: 10px;
  padding: 4mm 5mm;
  font-size: 9pt;
  display: flex; gap: 10px;
  align-items: flex-start;
  font-size: 10pt;
  line-height: 1.55;
}}
.shop-tip strong {{ display: block; font-weight: 700; margin-bottom: 2px; }}

/* ===== PAGE 6 — Supplements ============================================= */
.supp-grid {{
  margin: 0;
}}
.supp {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  padding: 3.5mm 5mm;
  margin-bottom: 2.5mm;
  page-break-inside: avoid;
  break-inside: avoid;
}}
.supp .head .name {{ font-size: 10.5pt; font-weight: 700; color: var(--ink); display: inline; }}
.supp .head .freq {{ font-size: 8pt; color: var(--ink-light); display: inline; margin-left: 6px; }}
.supp .dose {{
  font-size: 13pt;
  font-weight: 800;
  color: var(--primary);
  letter-spacing: -0.03em;
  line-height: 1;
  margin: 2mm 0 1mm;
}}
.supp .note {{ font-size: 8.5pt; color: var(--ink-soft); line-height: 1.4; }}

/* ===== PAGE 7 — Transition timeline ===================================== */
.timeline {{ position: relative; padding-left: 18mm; margin-top: 3mm; }}
.timeline::before {{
  content: ""; position: absolute;
  left: 8mm; top: 4mm; bottom: 4mm;
  width: 2px; background: var(--border);
}}
.tl-step {{
  position: relative;
  margin-bottom: 3mm;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  padding: 3.5mm 5mm;
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
  font-size: 11pt;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.01em;
}}
.tl-step .step-text {{ font-size: 9pt; color: var(--ink-soft); line-height: 1.45; }}

.tl-warn {{
  margin-top: 3mm;
  background: #fee2e2;
  border-left: 3px solid var(--red);
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 8.5pt;
  color: var(--ink);
  line-height: 1.4;
  page-break-inside: avoid;
}}

/* ===== PAGE 8 — Reminders =============================================== */
.memo-section {{ margin-bottom: 3mm; }}
.memo-section h3 {{
  font-size: 10pt;
  margin-bottom: 2mm;
  display: inline-block;
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

.danger-table {{
  width: 100%;
  border-collapse: separate;
  border-spacing: 1.5mm;
}}
.danger-table td {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 8pt;
  line-height: 1.35;
  vertical-align: top;
  width: 50%;
}}
.danger-table .nm {{ color: var(--red); font-weight: 600; }}
.danger-table .why {{ color: var(--ink-soft); }}

.check-table {{
  width: 100%;
  border-collapse: separate;
  border-spacing: 1.5mm;
}}
.check-table td {{
  background: var(--green-soft);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 8pt;
  line-height: 1.35;
  width: 50%;
  vertical-align: top;
}}
.check-table td strong {{ color: var(--green); font-weight: 700; }}
.check-table td span {{ color: var(--ink-soft); }}

.vet-table {{
  width: 100%;
  border-collapse: separate;
  border-spacing: 1.5mm;
}}
.vet-table td {{
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 8pt;
  line-height: 1.35;
  color: var(--ink);
  vertical-align: top;
  width: 50%;
}}

/* ===== AI Personalized Analysis (multi-page) ============================ */
.ai-analysis .insight {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 5mm 6mm;
  margin-bottom: 4mm;
  page-break-inside: avoid;
  break-inside: avoid;
}}
.ai-analysis .insight .tag {{
  display: inline-block;
  font-size: 8pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 3px 10px;
  border-radius: 6px;
  margin-bottom: 3mm;
}}
.ai-analysis .insight .tag.breed {{ background: var(--primary-softer); color: var(--primary); }}
.ai-analysis .insight .tag.health {{ background: #fef3c7; color: #92400e; }}
.ai-analysis .insight .tag.nutrition {{ background: #dcfce7; color: #166534; }}
.ai-analysis .insight .tag.lifestyle {{ background: #ede9fe; color: #5b21b6; }}
.ai-analysis .insight p {{ font-size: 10pt; line-height: 1.6; color: var(--ink); margin: 0; }}

/* ===== PAGE 10 — Disclaimer / contacts ================================== */
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
  margin-bottom: 4mm;
}}
.contact-grid table {{
  width: 100%;
  border-collapse: separate;
  border-spacing: 3mm 0;
}}
.contact-grid td {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 5mm;
  vertical-align: top;
  width: 50%;
}}
.contact-card .label {{ font-size: 8.5pt; color: var(--ink-light); text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600; }}
.contact-card .val {{ font-size: 13pt; font-weight: 700; color: var(--ink); letter-spacing: -0.01em; }}

.support-strip {{
  margin-top: 6mm;
  background: var(--primary);
  color: #fff;
  border-radius: 12px;
  padding: 6mm 8mm;
}}
.support-strip h3 {{ color: #fff; font-size: 16pt; margin-bottom: 3mm; }}
.support-strip p {{ font-size: 10pt; line-height: 1.5; color: rgba(255,255,255,0.85); }}

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
    zoom: 1 !important;
    padding: 18mm 16mm 14mm;
    box-sizing: border-box;
  }}
  .page:last-of-type {{ page-break-after: auto; }}
  .cover .top-bar, .cover-photo, .cover-badge, .metric, .pie, .stack span,
  .warn, .day.special, .shop-group, .shop-tip, .supp .head .ico,
  .tl-step::before, .tl-warn, .support-strip, .hero-rec,
  .check-row .v, .danger-row .x, .vet-row .ico, .ai-analysis .insight {{
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
  <p class="section-sub">{getattr(result, 'ai_intro', '') or f'Рассчитано на основе целевого веса {result.ideal_weight_kg} кг и {ACTIVITY_LABELS.get(dog.activity, "средней").lower()} активности. Поделено на {result.meals_per_day} кормления.{season_note}{pregnancy_note}'}</p>

  <table class="metric-grid">
    <tr>
    <td class="metric">
      <div class="lbl">Суточная норма</div>
      <div class="val">{int(result.daily_grams)}<span class="unit">г</span></div>
      <div class="sub">в {result.meals_per_day} порции</div>
    </td>
    <td class="metric">
      <div class="lbl">Калорийность</div>
      <div class="val">{int(result.mer_kcal)}<span class="unit">ккал</span></div>
      <div class="sub">≈&nbsp;{int(result.mer_kcal / result.ideal_weight_kg) if result.ideal_weight_kg > 0 else 0} ккал/кг</div>
    </td>
    <td class="metric">
      <div class="lbl">Кормлений</div>
      <div class="val">{result.meals_per_day}<span class="unit">раза</span></div>
      <div class="sub">утро · вечер</div>
    </td>
    <td class="metric">
      <div class="lbl">Целевой вес</div>
      <div class="val">{result.ideal_weight_kg}<span class="unit">кг</span></div>
      <div class="sub">{f"−{weight_diff} кг" if weight_diff > 0 else f"+{abs(weight_diff)} кг" if weight_diff < 0 else "в норме"}</div>
    </td>
    </tr>
  </table>

  <table class="summary-grid">
    <tr>
    <td>
      <div class="group-table">
        <h4>Распределение по группам · {int(total_grams)} г</h4>
        <div class="stack">
          {stack_spans}
        </div>
        {distribution_rows}
      </div>
    </td>
    <td>
      <div class="pie-card">
        <div class="pie">
          <div class="center"><strong>{int(dominant_pct)}%</strong>{dominant_group}</div>
        </div>
        <div style="font-size:8.5pt; color:var(--ink-soft); margin-top:3mm; text-align:center; line-height:1.4;">
          {DIET_TYPE_LABELS.get(dog.diet_type, dog.diet_type)}
        </div>
      </div>
    </td>
    </tr>
  </table>

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
  <p class="section-sub" style="margin-bottom: 4mm;">Каждый день — {result.meals_per_day} кормления. Вес продуктов указан до приготовления.</p>

  <table class="menu-grid">
    {menu_page1_html}
  </table>

  {_page_foot(3, total_pages, doc_id)}
</section>

<!-- ============================================================ -->
<!-- PAGE 4 — MENU DAYS 5-7                                        -->
<!-- ============================================================ -->
<section class="page">
  {_page_head("<strong>Меню на неделю</strong> · часть 2 из 2")}

  <div class="eyebrow">{menu_page2[0].day_name if menu_page2 else ""} — {menu_page2[-1].day_name if menu_page2 else ""}</div>
  <h2 class="section-title" style="margin-top: 3mm; margin-bottom: 2mm;">Меню на неделю</h2>

  <table class="menu-grid">
    {menu_page2_html}
    <tr><td colspan="2">{week_summary}</td></tr>
  </table>

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

  <table class="shop-grid">
    {shopping_html}
  </table>

  <div class="shop-tip">
    <div>
      <strong>{'Стоимость рациона: ≈' + str(int(round(result.cost_per_day / 50) * 50)) + ' руб/день · ≈' + str(int(round(result.cost_per_month / 500) * 500)) + ' руб/мес' if result.cost_per_day > 0 else 'Совет от Кусь'}</strong>
      {(result.meal_prep.get('tip', '') + ' Цены ориентировочные — зависят от региона и магазина.') if result.cost_per_day > 0 else 'Разделите мясо на порции сразу после покупки и заморозьте. Размораживайте в холодильнике 12 часов — не на столе.'}
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
    <strong style="display:block; margin-bottom:2px;">⚠ Если диарея — вернитесь на шаг назад</strong>
    {transition_note if transition_note else "Не паникуйте: ЖКТ настраивается на новый тип пищи 7–14 дней. Уменьшите порцию вдвое на сутки, затем продолжайте схему с предыдущего этапа."}
  </div>

  {_page_foot(7, total_pages, doc_id)}
</section>

<!-- ============================================================ -->
<!-- PAGE 8 — FEEDING GUIDE                                        -->
<!-- ============================================================ -->
<section class="page">
  {_page_head(f"<strong>{'Как варить' if dog.diet_type == 'cooked' else 'Как кормить BARF'}</strong>")}

  <div class="eyebrow">Руководство</div>
  <h2 class="section-title" style="margin-top: 4mm;">{'Правила приготовления' if dog.diet_type == 'cooked' else 'Правила сырого кормления (BARF)'}</h2>

  {'<div style="font-size:9.5pt;line-height:1.6;color:var(--ink);">' + chr(10) +
  '<p style="margin-bottom:3mm;"><strong>Мясо и субпродукты</strong> — варите 20–30 минут на слабом огне. Не солите, не добавляйте специи. Бульон можно добавить к порции — в нём полезные вещества.</p>' + chr(10) +
  '<p style="margin-bottom:3mm;"><strong>Печень</strong> — варите отдельно, не более 15 минут. Она быстро становится жёсткой и теряет витамины.</p>' + chr(10) +
  '<p style="margin-bottom:3mm;"><strong>Рыба</strong> — варите 10–15 минут. Обязательно проверьте на кости перед подачей. Используйте морскую рыбу (минтай, треска, горбуша).</p>' + chr(10) +
  '<p style="margin-bottom:3mm;"><strong>Овощи</strong> — добавляйте в последние 5–7 минут варки или давайте сырыми, натёртыми на мелкой тёрке. Тыква, кабачок, морковь, брокколи — лучший выбор.</p>' + chr(10) +
  '<p style="margin-bottom:3mm;"><strong>Яйца</strong> — варите всмятку (3–4 минуты). Белок усваивается лучше после термообработки, желток — наоборот.</p>' + chr(10) +
  '<p style="margin-bottom:3mm;"><strong>Кисломолочка</strong> — не варите! Кефир, творог, ряженка даются сырыми. Добавляйте утром, отдельно от мясного кормления.</p>' + chr(10) +
  '<p style="margin-bottom:5mm;"><strong>Хранение</strong> — готовую еду храните в холодильнике до 3 дней. Для удобства готовьте партию на 2–3 дня и замораживайте порционно. Размораживайте в холодильнике, не в микроволновке.</p>' + chr(10) +
  '<div style="background:var(--primary-softer);border-left:3px solid var(--primary);border-radius:8px;padding:8px 12px;font-size:9pt;">' + chr(10) +
  '<strong>Порядок кормления:</strong> Достаньте порцию → разогрейте до комнатной температуры → добавьте масло/добавки → подайте. Еда не должна быть горячей или холодной из холодильника.' + chr(10) +
  '</div></div>'
  if dog.diet_type == 'cooked' else
  '<div style="font-size:9.5pt;line-height:1.6;color:var(--ink);">' + chr(10) +
  '<p style="margin-bottom:3mm;"><strong>Мясо</strong> — давайте сырым, порезанным на куски по размеру пасти. Промороженное мясо (3+ дня в морозилке при −18°C) безопасно. Размораживайте в холодильнике 12 часов.</p>' + chr(10) +
  '<p style="margin-bottom:3mm;"><strong>Кости</strong> — только сырые мясные кости (куриные спинки, шеи, крылья). Никогда не давайте варёные кости — они раскалываются на острые осколки! Кости — это источник кальция, не игрушка.</p>' + chr(10) +
  '<p style="margin-bottom:3mm;"><strong>Субпродукты</strong> — печень, сердце, почки, рубец. Давайте сырыми. Печень — не более 5% рациона (богата витамином A). Рубец — зелёный (неочищенный) полезнее белого.</p>' + chr(10) +
  '<p style="margin-bottom:3mm;"><strong>Рыба</strong> — сырая морская рыба 2 раза в неделю. Речную рыбу давать нельзя (паразиты). Мелкую рыбу можно целиком, крупную — без головы и хребта.</p>' + chr(10) +
  '<p style="margin-bottom:3mm;"><strong>Овощи</strong> — сырые, измельчённые в блендере или натёртые на мелкой тёрке. Собаки не умеют переваривать целлюлозу — без измельчения овощи пройдут транзитом.</p>' + chr(10) +
  '<p style="margin-bottom:3mm;"><strong>Кисломолочка</strong> — кефир, творог, ряженка. Давайте утром, отдельно от мясного кормления.</p>' + chr(10) +
  '<p style="margin-bottom:5mm;"><strong>Хранение</strong> — разделите мясо на порции сразу после покупки и заморозьте. Размораживайте в холодильнике, не на столе и не в микроволновке.</p>' + chr(10) +
  '<div style="background:var(--primary-softer);border-left:3px solid var(--primary);border-radius:8px;padding:8px 12px;font-size:9pt;">' + chr(10) +
  '<strong>Порядок кормления:</strong> Достаньте порцию из холодильника за 20 минут до кормления → добавьте овощи, масло и добавки → подайте. Мясо должно быть комнатной температуры, не ледяным.' + chr(10) +
  '</div></div>'}

  {'<div style="margin-top: 5mm; background: var(--primary-softer); border-left: 3px solid var(--primary); border-radius: 8px; padding: 4mm 5mm; font-size: 9pt; line-height: 1.5; color: var(--ink);"><div style="font-size: 8pt; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--primary); margin-bottom: 2mm;">Персональные рекомендации</div>' + getattr(result, 'ai_notes', '').replace(chr(10), '<br/>') + '</div>' if getattr(result, 'ai_notes', '') else ''}

  {_page_foot(8, total_pages, doc_id)}
</section>

<!-- ============================================================ -->
<!-- PAGE 9 — REMINDERS                                            -->
<!-- ============================================================ -->
<section class="page">
  {_page_head("<strong>Памятка владельцу</strong>")}

  <div class="eyebrow">Памятка владельцу</div>
  <h2 class="section-title" style="margin-top: 3mm; margin-bottom: 2mm;">Запомнить и повесить на холодильник</h2>

  <div class="memo-section">
    <h3>Что НЕЛЬЗЯ давать собакам <span class="pill red">опасно</span></h3>
    <table class="danger-table">
      {danger_rows}
    </table>
  </div>

  <div class="memo-section">
    <h3>Как понять, что рацион подошёл <span class="pill green">через 2–4 недели</span></h3>
    <table class="check-table">
      <tr><td><strong>✓ Стул</strong> — <span>оформленный, 1–2 раза в день</span></td><td><strong>✓ Шерсть</strong> — <span>блестящая, меньше выпадает</span></td></tr>
      <tr><td><strong>✓ Энергия</strong> — <span>{adj_active} на прогулке, хорошо спит</span></td><td><strong>✓ Аппетит</strong> — <span>ест с удовольствием, миску вылизывает</span></td></tr>
      <tr><td><strong>✓ Вес</strong> — <span>стабилен или движется к целевому</span></td><td><strong>✓ Запах</strong> — <span>уходит из пасти и от кожи</span></td></tr>
    </table>
  </div>

  <div class="memo-section" style="margin-bottom: 0;">
    <h3>Когда срочно к ветеринару <span class="pill amber">не откладывайте</span></h3>
    <table class="vet-table">
      <tr>
        <td>⚠ Диарея или рвота более 24 часов</td>
        <td>⚠ Отказ от еды более суток</td>
      </tr>
      <tr>
        <td>⚠ Кровь в стуле или рвоте</td>
        <td>⚠ Сильный зуд или отёк морды</td>
      </tr>
      <tr>
        <td colspan="2">⚠ Внезапная вялость, апатия</td>
      </tr>
    </table>
  </div>

  {_page_foot(9, total_pages, doc_id)}
</section>

{f"""<!-- ============================================================ -->
<!-- PAGE 10 — AI ANALYSIS (part 1)                                -->
<!-- ============================================================ -->
<section class="page ai-analysis">
  {_page_head(f"<strong>{dog.name}</strong> · Персональный анализ")}

  <div class="eyebrow">Персональный анализ</div>
  <h2 class="section-title" style="margin-top: 4mm;">Рекомендации для {name_g}</h2>
  <p class="section-sub" style="font-size:10pt;">AI-анализ на основе ветеринарных стандартов NRC, FEDIAF и AAFCO. Система учитывает породные особенности, кондицию, заболевания и баланс нутриентов — и объясняет, почему рацион составлен именно так.</p>

  {ai_blocks_page1}

  {_page_foot(10, total_pages, doc_id)}
</section>""" if has_ai_analysis else ''}

{f"""<!-- ============================================================ -->
<!-- PAGE 11 — AI ANALYSIS (part 2)                                -->
<!-- ============================================================ -->
<section class="page ai-analysis">
  {_page_head(f"<strong>{dog.name}</strong> · Персональный анализ · продолжение")}

  {ai_blocks_page2}

  {_page_foot(11, total_pages, doc_id)}
</section>""" if has_ai_analysis and ai_blocks_page2 else ''}

<!-- ============================================================ -->
<!-- PAGE {11 if has_ai_analysis else 10} — DISCLAIMER + CONTACTS  -->
<!-- ============================================================ -->
<section class="page last-page">
  {_page_head("<strong>Дисклеймер и контакты</strong>")}

  <div class="eyebrow">Важно знать</div>
  <h2 class="section-title" style="margin-top: 4mm;">Несколько слов перед тем,<br/>как закроете PDF</h2>

  <div style="background:#fff;border:1px solid var(--border-soft);border-radius:12px;padding:5mm;margin-bottom:5mm;">
    <p style="font-size:9.5pt;line-height:1.55;color:var(--ink);font-style:italic;">Данный рацион рассчитан на основе общепринятых ветеринарных норм <strong>NRC&nbsp;2006</strong>, <strong>FEDIAF</strong> и <strong>AAFCO</strong>. Он не заменяет очную консультацию ветеринарного врача. При наличии хронических заболеваний обязательно согласуйте рацион с лечащим ветеринаром.</p>
  </div>

  <h3 style="font-size: 11pt; margin-bottom: 3mm;">Связь с нами</h3>
  <table style="width:100%;border-collapse:separate;border-spacing:3mm 0;margin-bottom:5mm;">
    <tr>
      <td style="background:#fff;border:1px solid var(--border-soft);border-radius:10px;padding:4mm 5mm;width:50%;vertical-align:top;">
        <div style="font-size:8pt;color:var(--ink-light);text-transform:uppercase;letter-spacing:0.1em;font-weight:600;margin-bottom:2mm;">Telegram</div>
        <div style="font-size:12pt;font-weight:700;color:var(--ink);">@doggifood_bot</div>
      </td>
      <td style="background:#fff;border:1px solid var(--border-soft);border-radius:10px;padding:4mm 5mm;width:50%;vertical-align:top;">
        <div style="font-size:8pt;color:var(--ink-light);text-transform:uppercase;letter-spacing:0.1em;font-weight:600;margin-bottom:2mm;">Сайт</div>
        <div style="font-size:12pt;font-weight:700;color:var(--ink);">kus.dogfine.ru</div>
      </td>
    </tr>
  </table>

  <div class="support-strip">
    <h3 style="font-size:14pt;">7 дней бесплатной поддержки</h3>
    <p style="font-size:9.5pt;">Стул не такой? {name} {verb_refused}? Не уверены, нормальна ли реакция? Напишите в Telegram-бот — ответим за 15 минут в рабочее время.</p>
  </div>

  <div class="bye">
    Спасибо, что доверили нам здоровье {name_g} ♥<br/>
    © 2026 Кусь · Doggi · kus.dogfine.ru
  </div>

  {_page_foot(total_pages, total_pages, doc_id)}
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
