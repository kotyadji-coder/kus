"""
Рендер HTML-отчёта тремя способами, как его видит клиент:
  1. десктоп-экран   (viewport 1280) -> *_desktop.png  (full page)
  2. мобильный экран (viewport 390)  -> *_mobile.png   (full page, проверка @media 820px)
  3. печать браузера (print media)   -> *_print.pdf + постраничные *_print_pN.png

Печать делается Chromium'ом (page.pdf), а не WeasyPrint — это то, что реально
получает клиент кнопкой «Печать / Сохранить PDF». PDF растеризуем в PNG через
pypdfium2, чтобы агент мог осмотреть каждую страницу глазами.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import pypdfium2 as pdfium
from playwright.sync_api import sync_playwright

DESKTOP_WIDTH = 1280
MOBILE_WIDTH = 390
RASTER_SCALE = 2.0  # масштаб растеризации PDF (чёткость для осмотра текста)


@dataclass
class RenderResult:
    html_path: str
    desktop_png: str | None = None
    mobile_png: str | None = None
    print_pdf: str | None = None
    print_pngs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _rasterize_pdf(pdf_path: str, out_prefix: str, scale: float = RASTER_SCALE) -> list[str]:
    pngs: list[str] = []
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            bitmap = page.render(scale=scale)
            pil = bitmap.to_pil()
            out = f"{out_prefix}_print_p{i + 1}.png"
            pil.save(out)
            pngs.append(out)
    finally:
        pdf.close()
    return pngs


def render_report(html_path: str, out_prefix: str) -> RenderResult:
    """Снимает все три состояния. out_prefix — путь без расширения."""
    res = RenderResult(html_path=html_path)
    file_url = "file://" + os.path.abspath(html_path)
    base_dir = os.path.dirname(os.path.abspath(html_path))

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        try:
            # --- desktop screen ---
            try:
                ctx = browser.new_context(viewport={"width": DESKTOP_WIDTH, "height": 1000},
                                          device_scale_factor=2, base_url="file://" + base_dir + "/")
                page = ctx.new_page()
                page.goto(file_url, wait_until="networkidle", timeout=30000)
                page.emulate_media(media="screen")
                out = f"{out_prefix}_desktop.png"
                page.screenshot(path=out, full_page=True)
                res.desktop_png = out
                ctx.close()
            except Exception as e:
                res.errors.append(f"desktop: {e}")

            # --- mobile screen ---
            try:
                ctx = browser.new_context(viewport={"width": MOBILE_WIDTH, "height": 844},
                                          device_scale_factor=2, is_mobile=True,
                                          base_url="file://" + base_dir + "/")
                page = ctx.new_page()
                page.goto(file_url, wait_until="networkidle", timeout=30000)
                page.emulate_media(media="screen")
                out = f"{out_prefix}_mobile.png"
                page.screenshot(path=out, full_page=True)
                res.mobile_png = out
                ctx.close()
            except Exception as e:
                res.errors.append(f"mobile: {e}")

            # --- print PDF (browser engine) ---
            try:
                ctx = browser.new_context(base_url="file://" + base_dir + "/")
                page = ctx.new_page()
                page.goto(file_url, wait_until="networkidle", timeout=30000)
                page.emulate_media(media="print")
                pdf_out = f"{out_prefix}_print.pdf"
                page.pdf(path=pdf_out, format="A4", print_background=True,
                         prefer_css_page_size=True)
                res.print_pdf = pdf_out
                ctx.close()
                res.print_pngs = _rasterize_pdf(pdf_out, out_prefix)
            except Exception as e:
                res.errors.append(f"print: {e}")
        finally:
            browser.close()
    return res


if __name__ == "__main__":
    import sys
    r = render_report(sys.argv[1], sys.argv[2])
    print(r)
