"""Панель QA: статистика, оценки, рекомендации. Читает историю scores/<дата>.json
и рендерит самодостаточный HTML (инлайн-CSS, без шаблонов). Монтируется в app.py
как /admin/qa под verify_admin (данные остаются на 5.42).

CLI для локального просмотра:  venv/bin/python tools/report_qa/dashboard.py > /tmp/qa.html
"""
from __future__ import annotations

import glob
import html
import json
import os

SCORES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scores")


def _load_history() -> list[dict]:
    """Все прогоны по возрастанию даты."""
    out = []
    for path in sorted(glob.glob(os.path.join(SCORES_DIR, "*.json"))):
        try:
            out.append(json.load(open(path, encoding="utf-8")))
        except Exception:
            continue
    return out


def _color(v) -> str:
    if v is None:
        return "#9ca3af"
    if v >= 4.5:
        return "#16a34a"
    if v >= 3.5:
        return "#ca8a04"
    return "#dc2626"


def render_dashboard_html() -> str:
    hist = _load_history()
    if not hist:
        return "<html><body style='font-family:sans-serif;padding:40px'><h2>QA-панель «Кусь»</h2><p>Истории оценок пока нет. Запустите <code>rubric.py</code>.</p></body></html>"

    latest = hist[-1]
    results = latest.get("results", [])

    # средние по типу рациона
    by_diet: dict[str, list[float]] = {}
    for r in results:
        if r.get("overall_deterministic") is not None:
            by_diet.setdefault(r["diet_type"], []).append(r["overall_deterministic"])
    diet_avg = {d: round(sum(v) / len(v), 2) for d, v in by_diet.items()}

    # тренд: средний общий балл по датам
    trend = []
    for run in hist:
        vals = [r["overall_deterministic"] for r in run.get("results", []) if r.get("overall_deterministic") is not None]
        if vals:
            trend.append((run.get("date", "?"), round(sum(vals) / len(vals), 2)))

    # рекомендации: все критерии < 5 в последнем прогоне
    recs = []
    for r in results:
        for k, c in r.get("criteria", {}).items():
            if c.get("value") is not None and c["value"] < 5:
                recs.append((r["name"], r["diet_type"], k, c["value"], c.get("note", "")))

    n_judged = sum(1 for r in results for c in r.get("criteria", {}).values() if c.get("value") is None)

    def esc(x):
        return html.escape(str(x))

    rows = []
    for r in results:
        ov = r.get("overall_deterministic")
        crit_bad = "; ".join(f"{k}={c['value']}" for k, c in r.get("criteria", {}).items()
                             if c.get("value") is not None and c["value"] < 5) or "—"
        rows.append(
            f"<tr><td>{esc(r['name'])}</td><td>{esc(r['diet_type'])}</td>"
            f"<td style='text-align:center;font-weight:700;color:{_color(ov)}'>{ov if ov is not None else '—'}</td>"
            f"<td style='font-size:13px;color:#555'>{esc(crit_bad)}</td></tr>")

    diet_cards = "".join(
        f"<div style='flex:1;min-width:120px;background:#fff;border-radius:10px;padding:14px;box-shadow:0 1px 4px #0001'>"
        f"<div style='font-size:13px;color:#777'>{esc(d)}</div>"
        f"<div style='font-size:28px;font-weight:800;color:{_color(a)}'>{a}</div></div>"
        for d, a in sorted(diet_avg.items()))

    trend_txt = " · ".join(f"{esc(d)}: <b style='color:{_color(a)}'>{a}</b>" for d, a in trend[-10:])

    rec_items = "".join(
        f"<li><b>{esc(nm)}</b> <span style='color:#888'>({esc(dt)})</span> — "
        f"<span style='color:{_color(v)}'>[{v}]</span> {esc(k)}: {esc(note)}</li>"
        for nm, dt, k, v, note in recs) or "<li style='color:#16a34a'>Замечаний нет — всё ≥5 ✅</li>"

    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>QA-панель · Кусь</title></head>
<body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f3f4f6;margin:0;padding:24px;color:#111">
<div style="max-width:980px;margin:0 auto">
  <h1 style="margin:0 0 4px">🐕 QA-панель «Кусь»</h1>
  <div style="color:#777;margin-bottom:18px">Последний прогон: <b>{esc(latest.get('date','?'))}</b> · {len(results)} профилей · детерминированные баллы (субъективных, ждущих ИИ-судью: {n_judged})</div>

  <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px">{diet_cards}</div>

  <div style="background:#fff;border-radius:10px;padding:14px 16px;margin-bottom:20px;box-shadow:0 1px 4px #0001">
    <div style="font-size:13px;color:#777;margin-bottom:6px">Тренд среднего балла</div>
    <div style="font-size:14px">{trend_txt}</div>
  </div>

  <h2 style="font-size:18px;margin:0 0 8px">Оценки по профилям</h2>
  <table style="width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 4px #0001">
    <thead><tr style="background:#111;color:#fff;text-align:left">
      <th style="padding:10px">Собака</th><th style="padding:10px">Тип</th>
      <th style="padding:10px;text-align:center">Балл</th><th style="padding:10px">Замечания</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>

  <h2 style="font-size:18px;margin:22px 0 8px">Рекомендации (критерии &lt;5)</h2>
  <ul style="background:#fff;border-radius:10px;padding:14px 30px;box-shadow:0 1px 4px #0001;line-height:1.7">{rec_items}</ul>

  <div style="color:#aaa;font-size:12px;margin-top:18px">Источник: tools/report_qa/scores/ · ⬜ серое = ждёт ИИ-судью · 🟢 ≥4.5 · 🟡 ≥3.5 · 🔴 &lt;3.5</div>
</div></body></html>"""


if __name__ == "__main__":
    print(render_dashboard_html())
