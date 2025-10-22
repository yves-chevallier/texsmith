#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
index_to_latex_lines.py — Convertit un index.json (du script 1) en lignes style index LaTeX.

Sortie (texte par défaut) :
  terme_dans_le_texte , terme_dans_l'index , p. 2, 5, 7 ; fig. 1.2, 3

Heuristiques :
- Page = floor(pos / CHARS_PER_PAGE) + 1  (par défaut CHARS_PER_PAGE = 1200)
- Figure détectée si:
    * heading/snippet matchent /(fig(?:ure)?)\s*[:#\s]*([\d][\d\.\-]*)?/i
    * ou anchor contient "fig" ou "figure"
  => on affiche "fig. <num>" si le numéro est détecté, sinon "fig@<anchor>" ou "fig".

Options:
    --chars-per-page N   (int, défaut 1200)
    --format text|csv    (défaut text)
    <input>              chemin du JSON ou "-" pour stdin
"""

import argparse
import json
import re
import sys
import unicodedata


FIG_RE = re.compile(r"(?i)\bfig(?:ure)?\b[ \t]*[:#\-\u00A0]*\s*([0-9][\d\.\-]*)?")


def deaccent(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def normalize_term(s: str) -> str:
    s = (s or "").strip().lower()
    s = deaccent(s)
    return re.sub(r"\s+", " ", s)


def detect_fig_labels(heading: str, snippet: str, anchor: str):
    """
    Renvoie un set de labels de figure détectés (ex: {"1.2"} ou {"fig@installation"}).
    """
    labels = set()
    for txt in (heading or "", snippet or ""):
        m = FIG_RE.search(txt)
        if m:
            num = (m.group(1) or "").strip()
            if num:
                labels.add(num)
            else:
                labels.add("fig")
    if anchor and re.search(r"(?i)\bfig(?:ure)?\b", anchor):
        labels.add(f"@{anchor}")
    return labels


def compute_page(pos: int, cpp: int) -> int:
    if pos is None:
        return 1
    if pos < 0:
        pos = 0
    return (pos // cpp) + 1


def load_entries(path: str):
    if path == "-":
        return json.load(sys.stdin)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("input", nargs="?", default="-")
    ap.add_argument("--chars-per-page", type=int, default=1200)
    ap.add_argument("--format", choices=["text", "csv"], default="text")
    ap.add_argument("-h", "--help", action="help", help="Afficher l'aide et quitter")
    args = ap.parse_args()

    try:
        data = load_entries(args.input)
    except Exception as e:
        sys.stderr.write(f"Erreur: impossible de lire le JSON '{args.input}': {e}\n")
        sys.exit(1)

    # data est une liste d'entrées {term, lemma, variants, score, docs:[{path, occurrences:[...] }]}
    rows = []

    for entry in data:
        term_display = entry.get("term") or ""
        index_term = entry.get("lemma") or normalize_term(term_display) or ""
        # Agrège pages/figures sur tous les documents présents (même si en pratique 1)
        pages = set()
        figs = set()

        for doc in entry.get("docs", []):
            occs = doc.get("occurrences", []) or []
            for o in occs:
                pos = o.get("pos", 0)
                pnum = compute_page(int(pos), args.chars_per_page)
                pages.add(pnum)

                # Figures ?
                heading = o.get("heading")
                snippet = o.get("snippet")
                anchor = o.get("anchor")
                for lbl in detect_fig_labels(heading, snippet, anchor):
                    figs.add(lbl)

        # Format pages
        pages_list = sorted(pages)
        pages_str = ", ".join(f"{p}" for p in pages_list) if pages_list else ""

        # Format figures
        if figs:
            # sépare les numéros "propres" des ancres "@..." et de "fig" générique
            num_like = sorted(
                [x for x in figs if x and x[0].isdigit()],
                key=lambda s: [
                    int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)
                ],
            )
            at_like = sorted([x[1:] for x in figs if x.startswith("@")])
            generic = ["fig"] if "fig" in figs else []
            fig_parts = []
            if num_like:
                fig_parts.append("fig. " + ", ".join(num_like))
            if at_like:
                fig_parts.append("fig@" + ", ".join(at_like))
            if generic and not num_like and not at_like:
                fig_parts.append("fig.")
            figures_str = " ; " + " ; ".join(fig_parts)
        else:
            figures_str = ""

        # Ligne
        if args.format == "csv":
            # CSV simple, échapper basique
            def q(s):
                return '"' + (s or "").replace('"', '""') + '"'

            rows.append(
                f"{q(term_display)},{q(index_term)},{q(('p. ' + pages_str if pages_str else '') + figures_str)}"
            )
        else:
            # Texte
            left = term_display
            mid = index_term
            right_parts = []
            if pages_str:
                right_parts.append("p. " + pages_str)
            if figures_str:
                right_parts.append(figures_str.strip())
            right = " ; ".join(right_parts)
            rows.append(f"{left} , {mid} , {right}")

    # Tri alphabétique par clé d'index (insensible aux accents/casse)
    rows_sorted = sorted(
        rows,
        key=lambda line: normalize_term(line.split(",")[1] if "," in line else line),
    )

    for line in rows_sorted:
        sys.stdout.write(line.rstrip() + "\n")


if __name__ == "__main__":
    main()
