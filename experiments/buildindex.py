#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_index_precis.py — Génère un index JSON de haute précision depuis un fichier Markdown.
- Candidats = groupes nominaux (noun phrases) uniquement (POS constraints)
- Lemmatisation (FR/EN) via spaCy, dé-accentuation et normalisation
- Stopwords FR+EN + stoplist projet (stop_terms.txt) si présent
- Filtre PMI pour bigrammes/trigrammes
- Boost titres/légendes, bonus annotations `terme`{index, text="Affiché"}
- Écrit le JSON sur stdout

Dépendances:
    pip install markdown-it-py beautifulsoup4 spacy langdetect
    python -m spacy download en_core_web_sm
    python -m spacy download fr_core_news_sm
"""

import sys, re, os, json, math, unicodedata
from pathlib import Path
from collections import defaultdict, Counter
from typing import List, Tuple, Dict, Set

# --- tierces ---
try:
    import markdown_it
    from bs4 import BeautifulSoup
except Exception:
    sys.stderr.write("Installe 'markdown-it-py' et 'beautifulsoup4'\n")
    raise

# langue
try:
    from langdetect import detect
except Exception:
    detect = None

# spaCy
import spacy
NLP_CACHE = {}

def get_nlp(lang_hint: str):
    """Charge un pipeline spaCy FR/EN selon hint, avec fallback."""
    if lang_hint in NLP_CACHE:
        return NLP_CACHE[lang_hint]
    names = []
    if lang_hint.startswith("fr"):
        names = ["fr_core_news_sm", "en_core_web_sm"]
    else:
        names = ["en_core_web_sm", "fr_core_news_sm"]
    nlp = None
    for name in names:
        try:
            nlp = spacy.load(name, disable=["ner", "textcat"])
            break
        except Exception:
            continue
    if nlp is None:
        sys.stderr.write("Aucun modèle spaCy FR/EN trouvé. `python -m spacy download en_core_web_sm`\n")
        raise SystemExit(1)
    NLP_CACHE[lang_hint] = nlp
    return nlp

# --- util ---
TOKEN_ALPHA_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")
FIG_RE = re.compile(r'(?i)\bfig(?:ure)?\b[ \t]*[:#\-\u00A0]*\s*([0-9][\d\.\-]*)?')

FR_STOPWORDS = set("""
au aux avec ce ces dans de des du elle en et eux il je la le leur lui ma mais me même mes moi mon ne nos notre nous on ou par pas pour qu que qui sa se ses son sur ta te tes toi ton tu un une vos votre vous c d j l à m n s t y été étée étés étées étant étais était étions étiez étaient être eût fut furent éta fûmes fûtes eûtes eûmes eût eussent aient aurait aurais aura aurez aurons avons avez avaient avait avais avais ai as a ont suis es est sommes êtes sont serai seras sera serons serez seraient serais serait seraient étais étions étiez étaient étais était serions seriez seraient avais avait avions aviez avaient aurais aurait aurions auriez auraient ayant ayant eu avoir ceci cela ça çà ça-même chacun chacune chaque quelque quelques lequel laquelle lesquels lesquelles dont où
""".split())
EN_STOPWORDS = set("""
a an and are as at be been being by for from has have having he her hers him his how i if in into is it its itself just me more most my myself no nor not of on once only or other our ours ourselves out over own same she should so some such than that the their theirs them themselves then there these they this those through to too under until up very was we were what when where which while who whom why with you your yours yourself yourselves
""".split())

def load_stoplist_file() -> Set[str]:
    p = Path("stop_terms.txt")
    if p.exists():
        terms = [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip() and not l.strip().startswith("#")]
        return set(terms)
    return set()

USER_STOPLIST = set(map(lambda s: s.lower(), load_stoplist_file()))

def deaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def normalize_text(s: str) -> str:
    s = s.strip().lower()
    s = deaccent(s)
    s = re.sub(r"[\s\-]+", " ", s)
    return s

def slugify(s: str) -> str:
    s = normalize_text(s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r"\s+", "-", s).strip("-")

def remove_fenced_code(md_text: str) -> str:
    return re.sub(r"```.*?```", "", md_text, flags=re.S)

def replace_index_annotations(md_text: str) -> str:
    """
    `terme`{index, text="Affiché"} -> <span class="idx" data-key="terme" data-text="Affiché">Affiché</span>
    """
    pattern = re.compile(r"`([^`]+?)`\{index(?:,\s*text=\"([^\"]+)\")?\}")
    def _repl(m):
        term = m.group(1)
        disp = m.group(2) or term
        return f'<span class="idx" data-key="{term}" data-text="{disp}">{disp}</span>'
    return pattern.sub(_repl, md_text)

def detect_language(text: str) -> str:
    if detect:
        try:
            code = detect(text)
            return "fr" if code.startswith("fr") else "en"
        except Exception:
            return "en"
    return "en"

def extract_blocks_from_markdown(md_text: str):
    md_engine = markdown_it.MarkdownIt("commonmark").enable("table")
    html = md_engine.render(md_text)
    soup = BeautifulSoup(html, "html.parser")
    blocks = []
    heading = None
    anchor = None
    char_cursor = 0
    for tag in soup.find_all(["h1","h2","h3","h4","p","li","figcaption"]):
        is_heading = tag.name.startswith("h")
        if is_heading:
            heading = tag.get_text(" ", strip=True)
            anchor = slugify(heading) if heading else None
        text = tag.get_text(" ", strip=True)
        if text:
            blocks.append({
                "heading": heading,
                "anchor": anchor,
                "text": text,
                "char_start": char_cursor,
                "is_heading": is_heading,
                "is_caption": tag.name == "figcaption" or bool(FIG_RE.search(text))
            })
            char_cursor += len(text) + 1
    return soup, blocks

# --- candidats par POS ---
DISALLOWED_POS = {"AUX","VERB","PRON","DET","ADP","CCONJ","SCONJ","PART","INTJ","PUNCT","SYM","NUM"}

def noun_phrase_candidates(nlp, text: str, max_len: int = 6) -> List[Tuple[str, List[str], List[str]]]:
    """
    Renvoie des candidats (surface, lemmas, pos) en respectant:
    - contient au moins un NOUN/PROPN
    - ne commence/termine pas par POS interdit
    - longueur <= max_len
    """
    doc = nlp(text)
    cands = []

    # 1) noun_chunks si dispo (même sans parser, certains modèles les fournissent via heuristiques)
    if hasattr(doc, "noun_chunks"):
        chunks = []
        if hasattr(doc, "noun_chunks"):
            try:
                # convertir en liste pour forcer l'évaluation et capturer E029 si pas de parser
                chunks = list(doc.noun_chunks)
            except Exception:
                chunks = []
        if chunks:
            for nc in chunks:
                toks = [t for t in nc if TOKEN_ALPHA_RE.search(t.text)]
                if not toks:
                    continue
                if len(toks) > max_len:
                    continue
                pos_set = {t.pos_ for t in toks}
                if "NOUN" not in pos_set and "PROPN" not in pos_set:
                    continue
                if toks[0].pos_ in DISALLOWED_POS or toks[-1].pos_ in DISALLOWED_POS:
                    continue
                surface = " ".join(t.text for t in toks)
                lemmas = [t.lemma_.lower() for t in toks]
                pos = [t.pos_ for t in toks]
                cands.append((surface, lemmas, pos))

    # 2) fallback par motif POS (séquences autorisées)
    i = 0
    while i < len(doc):
        if doc[i].pos_ in {"NOUN","PROPN","ADJ"} and TOKEN_ALPHA_RE.search(doc[i].text):
            j = i
            kept = []
            while j < len(doc) and doc[j].pos_ in {"NOUN","PROPN","ADJ"} and TOKEN_ALPHA_RE.search(doc[j].text):
                kept.append(doc[j])
                j += 1
            if kept and len(kept) <= max_len:
                pos_set = {t.pos_ for t in kept}
                if "NOUN" in pos_set or "PROPN" in pos_set:
                    if kept[0].pos_ not in DISALLOWED_POS and kept[-1].pos_ not in DISALLOWED_POS:
                        surface = " ".join(t.text for t in kept)
                        lemmas = [t.lemma_.lower() for t in kept]
                        pos = [t.pos_ for t in kept]
                        cands.append((surface, lemmas, pos))
            i = j
        else:
            i += 1
    return cands

# --- PMI ---
def compute_pmi(term_tokens: List[str], unigram_counts: Counter, total_tokens: int) -> float:
    """
    PMI moyen adjacent pour bigrammes/trigrammes (tokens déjà normalisés).
    """
    if len(term_tokens) == 1 or total_tokens == 0:
        return 0.0
    def prob(tok): return unigram_counts[tok] / total_tokens if unigram_counts[tok] else 1e-12
    pairs = list(zip(term_tokens, term_tokens[1:]))
    # estimation naïve: P(xy) ~= min(P(x), P(y)) / 5  (borne prudente)
    # on préfère un critère discriminant simple: somme log(P(xy)/(P(x)P(y))) avec P(xy) ~ min(Px,Py)/K
    pmi_vals = []
    for a,b in pairs:
        px, py = prob(a), prob(b)
        pxy = min(px, py) / 5.0
        pmi = math.log((pxy / (px*py)) + 1e-12)
        pmi_vals.append(pmi)
    return sum(pmi_vals) / len(pmi_vals)

# --- pipeline principal ---
def build_index_precise(path: str, md_text: str):
    # annotations et nettoyage
    md_text = replace_index_annotations(md_text)
    md_text_clean = remove_fenced_code(md_text)

    # blocs
    soup, blocks = extract_blocks_from_markdown(md_text_clean)
    full_text = "\n".join(b["text"] for b in blocks)

    # langue
    lang = detect_language(full_text[:2000])
    nlp = get_nlp(lang)
    STOP = FR_STOPWORDS | EN_STOPWORDS | USER_STOPLIST

    # occurrences forcées
    forced = []
    for span in soup.select(".idx"):
        disp = span.get("data-text") or span.get_text(strip=True)
        key = span.get("data-key") or disp
        forced.append((key, disp))

    # stats globales
    unigram_counts = Counter()
    total_unigrams = 0

    term_data = defaultdict(lambda: {
        "raw_forms": Counter(),
        "occurrences": [],
        "forced": 0,
        "len_tokens": 0
    })

    total_chars = sum(len(b["text"]) + 1 for b in blocks) or 1
    processed_chars = 0

    # passe 1: unigrames pour PMI
    for b in blocks:
        doc = nlp(b["text"])
        for t in doc:
            if not TOKEN_ALPHA_RE.search(t.text):
                continue
            lem = t.lemma_.lower()
            if lem in STOP or t.pos_ in DISALLOWED_POS:
                continue
            unigram_counts[lem] += 1
            total_unigrams += 1

    # passe 2: candidats NP
    for b in blocks:
        heading_boost = 1.6 if b["is_heading"] else 1.0
        caption_boost = 1.4 if b["is_caption"] else 1.0
        early_ratio = processed_chars / total_chars
        early_boost = 1.25 if early_ratio < 0.25 else (1.12 if early_ratio < 0.5 else 1.0)

        cands = noun_phrase_candidates(nlp, b["text"], max_len=6)
        for surface, lemmas, pos in cands:
            # filtrages supplémentaires
            norm_surface = normalize_text(surface)
            if any(l in STOP for l in lemmas):
                continue
            # longueur minimale en lettres
            if len(norm_surface) < 3:
                continue

            # clé canonique = lemmas normalisés
            lem_norm = [normalize_text(l) for l in lemmas if TOKEN_ALPHA_RE.search(l)]
            if not lem_norm:
                continue
            key = " ".join(lem_norm)

            # score local
            length_bonus = 1.0 + (0.10 if len(lem_norm) == 2 else (0.18 if len(lem_norm) >= 3 else 0.0))
            weight = heading_boost * caption_boost * early_boost * length_bonus

            term_data[key]["raw_forms"][surface] += 1
            term_data[key]["occurrences"].append({
                "heading": b["heading"],
                "anchor": b["anchor"],
                "pos": b["char_start"],
                "snippet": (b["text"][:160] + "…") if len(b["text"]) > 160 else b["text"],
                "weight": round(weight, 3)
            })
            term_data[key]["len_tokens"] = max(term_data[key]["len_tokens"], len(lem_norm))

        processed_chars += len(b["text"]) + 1

    # intégrer les entrées forcées (bonus + garantie)
    for key, disp in forced:
        lem = normalize_text(key)
        term_data[lem]["raw_forms"][disp] += 1
        term_data[lem]["forced"] += 1
        term_data[lem]["occurrences"].append({
            "heading": None,
            "anchor": None,
            "pos": 0,
            "snippet": disp,
            "weight": 1.8
        })
        term_data[lem]["len_tokens"] = max(term_data[lem]["len_tokens"], len(lem.split()))

    # scoring global + PMI filter
    entries = []
    for key, data in term_data.items():
        occ = len(data["occurrences"])
        if occ == 0:
            continue

        toks = key.split()
        # Filtrage agressif des unigrams trop faibles (sauf forcés ou en titre)
        if len(toks) == 1 and data["forced"] == 0:
            # doit apparaître au moins 4 fois OU avoir des occurrences en titre/caption
            has_boosted = any(o["weight"] >= 1.4 for o in data["occurrences"])
            if (sum(data["raw_forms"].values()) < 4) and not has_boosted:
                continue

        # PMI pour >1 token
        pmi = compute_pmi(toks, unigram_counts, total_unigrams) if len(toks) > 1 else 0.0
        # seuil PMI (écarte collocations faibles)
        if len(toks) == 2 and pmi < 0.2 and data["forced"] == 0:
            continue
        if len(toks) >= 3 and pmi < 0.0 and data["forced"] == 0:
            continue

        # fréquence log
        freq = sum(data["raw_forms"].values())
        freq_score = math.log1p(freq) / 4.0  # ~[0..1]

        # poids moyen (titres/captions/early)
        avg_w = sum(o["weight"] for o in data["occurrences"]) / occ

        # longueur bonus
        len_bonus = 0.0
        if len(toks) == 2:
            len_bonus = 0.08
        elif len(toks) >= 3:
            len_bonus = 0.15

        forced_bonus = 0.18 if data["forced"] > 0 else 0.0

        final = 0.55*freq_score + 0.25*(pmi/2.0 + 0.5 if len(toks)>1 else 0.0) + 0.20*(avg_w/2.0) + len_bonus + forced_bonus
        final = max(0.0, min(1.0, final))

        display = data["raw_forms"].most_common(1)[0][0]
        variants = [w for w,_ in data["raw_forms"].most_common(5) if w != display]

        # compactage occurrences
        occs_sorted = sorted(
            data["occurrences"],
            key=lambda o: (o["weight"]),
            reverse=True
        )[:10]

        entries.append({
            "term": display,
            "lemma": key,               # forme canonique = lemmas
            "variants": variants,
            "score": round(final, 4),
            "docs": [{
                "path": os.fspath(Path(path).resolve()),
                "occurrences": occs_sorted
            }]
        })

    # tri par score puis alpha (stable)
    entries.sort(key=lambda e: (-e["score"], e["lemma"]))
    return entries

# --- CLI ---
def main(argv):
    if len(argv) < 2 or argv[1] in ("-h","--help"):
        sys.stderr.write("Usage: python build_index_precis.py <fichier.md>\n")
        sys.exit(2)

    in_path = argv[1]
    if in_path == "-":
        md_text = sys.stdin.read()
        source_path = "(stdin)"
    else:
        p = Path(in_path)
        if not p.exists():
            sys.stderr.write(f"Fichier introuvable: {in_path}\n")
            sys.exit(1)
        md_text = p.read_text(encoding="utf-8")
        source_path = str(p)

    entries = build_index_precise(source_path, md_text)
    json.dump(entries, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")

if __name__ == "__main__":
    main(sys.argv)
