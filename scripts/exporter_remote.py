#!/usr/bin/env python3
"""
Exporter un fichier draw.io en SVG/PDF via la page d'export publique
https://app.diagrams.net/export3.html. Ne dépend pas des sources locales.

Dépendances :
  pip install playwright cairosvg
  playwright install chromium

Usage :
  python exporter_remote.py --input pgcd.drawio --svg pgcd.svg --pdf pgcd.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import subprocess
import sys
from playwright.sync_api import sync_playwright
from playwright._impl._errors import Error as PlaywrightError

EXPORT_URL = "https://app.diagrams.net/export3.html"


def render_svg(input_path: Path, svg_out: Path, embed_fonts: bool, theme: str) -> str:
    xml = input_path.read_text(encoding="utf-8")

    with sync_playwright() as p:
        browser = launch_chromium(p)
        page = browser.new_page(viewport={"width": 2400, "height": 1800})
        page.goto(EXPORT_URL)
        page.wait_for_function("() => typeof window.render === 'function'")

        # Wrap render to stash graph/data
        page.evaluate(
            """
(() => {
  const orig = window.render;
  window.render = function(data) {
    const g = orig.call(window, data);
    window.__lastGraph = g;
    window.__lastData = data;
    return g;
  };
})();
"""
        )

        payload = {
            "xml": xml,
            "format": "svg",
            "border": 0,
            "scale": 1,
            "w": 0,
            "h": 0,
            "extras": "{}",
            "embedXml": "1",
            "embedImages": "1",
            "embedFonts": "1" if embed_fonts else "0",
            "shadows": "1",
            "theme": theme,
        }

        page.evaluate("data => window.render(data)", payload)
        page.wait_for_selector("#LoadingComplete", state="attached", timeout=60_000)

        svg = page.evaluate(
            """
() => {
  const graph = window.__lastGraph;
  const data = window.__lastData || {};
  const done = document.getElementById('LoadingComplete');
  const scale = done ? parseFloat(done.getAttribute('scale')) || graph.view.scale || 1 : graph.view.scale || 1;
  let bg = graph.background;
  if (bg === mxConstants.NONE) bg = null;

  const svgRoot = graph.getSvg(bg, scale, data.border || 0, false, null,
    true, null, null, null, null, null, data.theme || 'auto');

  if (data.embedXml === '1') {
    svgRoot.setAttribute('content', data.xml);
  }

  const header = (Graph.xmlDeclaration || '') + '\\n' +
    (Graph.svgDoctype || '') + '\\n' +
    (Graph.svgFileComment || '');
  return header + '\\n' + mxUtils.getXml(svgRoot);
}
"""
        )

        svg_out.write_text(svg, encoding="utf-8")
        browser.close()
        return svg


def convert_to_pdf(svg_content: str, pdf_out: Path) -> None:
    # Utilise Chromium pour "imprimer" le SVG en PDF (rend texte/couleurs correctement)
    with sync_playwright() as p:
        browser = launch_chromium(p)
        page = browser.new_page()
        page.set_content(f"<html><body style='margin:0'>{svg_content}</body></html>")
        page.pdf(path=str(pdf_out), print_background=True)
        browser.close()


def launch_chromium(playwright, headless: bool = True):
    try:
        return playwright.chromium.launch(headless=headless)
    except PlaywrightError as e:
        msg = str(e)
        if "Executable doesn't exist" in msg or "Failed to launch" in msg:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"], check=True
            )
            return playwright.chromium.launch(headless=headless)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export draw.io -> SVG/PDF via remote export3.html.")
    parser.add_argument("--input", required=True, type=Path, help="Fichier .drawio à convertir")
    parser.add_argument("--svg", type=Path, help="Chemin de sortie SVG (défaut: <input>_export3.svg)")
    parser.add_argument("--pdf", type=Path, help="Chemin de sortie PDF (optionnel)")
    parser.add_argument("--embed-fonts", action="store_true", help="Embarque les fontes dans le SVG")
    parser.add_argument("--theme", default="auto", choices=["auto", "dark", "light"], help="Thème export (auto par défaut)")
    args = parser.parse_args(argv)

    if not args.input.exists():
        raise SystemExit(f"Fichier introuvable: {args.input}")

    svg_out = args.svg or args.input.with_name(args.input.stem + "_export3.svg")
    svg = render_svg(args.input, svg_out, args.embed_fonts, args.theme)
    print(f"Wrote SVG to {svg_out}")

    if args.pdf:
        convert_to_pdf(svg, args.pdf)
        print(f"Wrote PDF to {args.pdf}")


if __name__ == "__main__":
    main(sys.argv[1:])
