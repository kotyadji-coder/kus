"""Generate PNG screenshots of each PDF page for landing preview."""
import re
import os

from calculator import DietCalculator, DogProfile
from pdf_generator import generate_html

calc = DietCalculator()
dog = DogProfile(
    name="Барон", breed="Лабрадор-ретривер", age_months=36, sex="male",
    neutered=True, weight_kg=32, current_food="dry", condition="chubby",
    activity="moderate", diagnoses=[], stool="good", diet_type="barf",
    budget="market", stop_products=["курица"],
)
result = calc.calculate(dog)
html = generate_html(result)

pages = re.findall(r'<section class="page.*?</section>', html, re.DOTALL)
print(f"Found {len(pages)} pages")

css_match = re.search(r'<style>(.*?)</style>', html, re.DOTALL)
css = css_match.group(1) if css_match else ""

from weasyprint import HTML as WpHTML
from pdf2image import convert_from_bytes

out_dir = os.path.join(os.path.dirname(__file__), "static", "pdf-pages")
os.makedirs(out_dir, exist_ok=True)

PAGE_LABELS = [
    "Обложка",
    "Сводка рациона",
    "Меню: Пн — Чт",
    "Меню: Пт — Вс",
    "Список покупок",
    "Витамины и добавки",
    "Схема перевода",
    "Памятка",
    "Контакты",
]

# Generate full PDF from all pages
full_html = f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>{css}
html,body {{ background:#fff; margin:0; padding:0; }}
.toolbar {{ display:none; }}
</style></head><body>{''.join(pages)}</body></html>"""

print("Generating PDF...")
pdf_bytes = WpHTML(string=full_html).write_pdf()
print(f"PDF: {len(pdf_bytes)//1024} KB")

print("Converting to PNG...")
images = convert_from_bytes(pdf_bytes, dpi=150)
print(f"Got {len(images)} pages")

for i, img in enumerate(images):
    path = os.path.join(out_dir, f"page_{i+1}.png")
    img.save(path, "PNG", optimize=True)
    size = os.path.getsize(path) // 1024
    label = PAGE_LABELS[i] if i < len(PAGE_LABELS) else f"Стр. {i+1}"
    print(f"  Page {i+1}: {label} — {size} KB")

print(f"\nDone! {len(images)} pages saved to {out_dir}")
