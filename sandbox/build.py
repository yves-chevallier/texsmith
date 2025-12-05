import json
import urllib.request
import urllib.parse
import re
import time
import sys

# La source de vérité ultime (utilisée par le frontend de fonts.google.com)
# Elle contient TOUTES les polices, y compris les Noto.
GOOGLE_FONTS_METADATA_URL = "https://fonts.google.com/metadata/fonts"

# Source supplémentaire pour connaître les fichiers OTF disponibles par famille.
NOTOFONTS_STATE_URL = "https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/state.json"

# API CSS pour récupérer les ranges précis (le metadata donne des infos générales, le CSS donne la vérité technique)
GOOGLE_FONTS_CSS = "https://fonts.googleapis.com/css2?family={}&display=swap"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch_all_google_fonts_families():
    """
    Récupère la liste de TOUTES les familles Noto disponibles sur Google Fonts.
    """
    print(f"📥 Téléchargement des métadonnées globales depuis {GOOGLE_FONTS_METADATA_URL}...")

    try:
        req = urllib.request.Request(GOOGLE_FONTS_METADATA_URL, headers=HEADERS)
        with urllib.request.urlopen(req) as response:
            raw_data = response.read().decode("utf-8")

            # La réponse est protégée par un préfixe anti-XSSI du type `)]}'\n`
            # qu'il faut retirer avant json.loads.
            if raw_data.startswith(")]}'"):
                raw_data = raw_data.split("\n", 1)[1]

            data = json.loads(raw_data)

        # Le JSON contient une clé 'familyMetadataList' qui est une liste d'objets
        all_families = data.get("familyMetadataList", [])

        # On filtre pour ne garder que "Noto"
        noto_families = []
        for item in all_families:
            family_name = item["family"]
            if family_name.startswith("Noto "):
                noto_families.append(family_name)

        # Tri alphabétique
        noto_families.sort()

        print(f"✅ {len(noto_families)} familles Noto détectées (ex: {noto_families[:3]}).")
        return noto_families

    except Exception as e:
        print(f"❌ Erreur critique lors du fetch des métadonnées : {e}")
        sys.exit(1)


def _normalize_style(style: str) -> str | None:
    """Mappe un suffixe de fichier vers l'un des styles standards attendus."""
    cleaned = re.sub(r"[^a-z]", "", style.lower())
    mapping = {
        "regular": "regular",
        "italic": "italic",
        "bold": "bold",
        "bolditalic": "bolditalic",
    }
    return mapping.get(cleaned)


def fetch_otf_styles():
    """
    Récupère, pour chaque famille, la liste des styles OTF standards disponibles.
    Retourne un mapping {family_name|sanitized_name: {"styles": [...], "file_base": "...", "dir_base": "..."}}
    """
    print(f"📥 Téléchargement des informations de styles depuis {NOTOFONTS_STATE_URL}...")
    try:
        req = urllib.request.Request(NOTOFONTS_STATE_URL, headers=HEADERS)
        with urllib.request.urlopen(req) as response:
            raw_data = response.read().decode("utf-8")
        state = json.loads(raw_data)
    except Exception as e:
        print(f"⚠️ Impossible de récupérer les styles OTF : {e}")
        return {}

    styles_index = {}
    families_count = 0
    for entry in state.values():
        if not isinstance(entry, dict):
            continue
        for family_name, meta in entry.get("families", {}).items():
            styles = set()
            file_base = None
            for path in meta.get("files", []):
                if "/otf/" not in path:
                    continue
                filename = path.split("/")[-1]
                if not filename.lower().endswith(".otf"):
                    continue
                parts = path.split("/")
                dir_base = parts[1] if len(parts) > 1 else None
                base_part, sep, style_part = filename.rpartition("-")
                if not sep:
                    continue
                style_name = style_part.rsplit(".", 1)[0]
                normalized = _normalize_style(style_name)
                if normalized:
                    styles.add(normalized)
                if not file_base:
                    file_base = base_part

            if styles:
                families_count += 1
                entry_data = {
                    "styles": sorted(styles),
                    "file_base": file_base or "".join(ch for ch in family_name if ch.isalnum()),
                    "dir_base": dir_base or "".join(ch for ch in family_name if ch.isalnum()),
                }
                styles_index[family_name] = entry_data
                # Alias sans espaces ni signes pour faciliter les correspondances
                styles_index["".join(ch for ch in family_name if ch.isalnum())] = entry_data

    print(f"✅ Styles OTF extraits pour {families_count} familles.")
    return styles_index


def get_unicode_ranges(family_name):
    """Interroge l'API CSS pour avoir les ranges précis."""
    safe_name = urllib.parse.quote(family_name)
    url = GOOGLE_FONTS_CSS.format(safe_name)

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req) as response:
            css = response.read().decode("utf-8")

        # Extraction regex des ranges
        ranges = []
        matches = re.findall(r"unicode-range:\s*([^;]+);", css)
        for m in matches:
            # Nettoyage U+...
            parts = m.replace("unicode-range:", "").strip().split(",")
            for p in parts:
                p = p.strip().replace("U+", "")
                if "-" in p:
                    s, e = p.split("-")
                    ranges.append([int(s, 16), int(e, 16)])
                elif "?" in p:
                    pass  # On ignore les wildcards bizarres
                else:
                    v = int(p, 16)
                    ranges.append([v, v])
        return ranges
    except urllib.error.HTTPError as e:
        # 400 ou 404 : La font est listée mais peut-être pas dispo via cette API CSS (ex: icons)
        return None
    except Exception as e:
        print(f"Err sur {family_name}: {e}")
        return None


def build_database():
    # 1. Récupération de la liste fiable
    families = fetch_all_google_fonts_families()
    styles_index = fetch_otf_styles()

    db = []
    print(f"🚀 Démarrage du scan de couverture pour {len(families)} polices...")
    print("Cela va prendre environ 10-15 secondes...")

    count = 0
    for i, family in enumerate(families):
        ranges = get_unicode_ranges(family)

        if ranges:
            family_key = "".join(ch for ch in family if ch.isalnum())
            styles = styles_index.get(family) or styles_index.get(family_key) or {}
            entry = {
                "family": family,
                "ranges": ranges,
                "file_base": styles.get("file_base", family_key),
                "dir_base": styles.get("dir_base", family_key),
            }
            if styles.get("styles"):
                entry["otf_styles"] = styles["styles"]
            db.append(entry)
            count += 1
            # Petit feedback visuel sur la même ligne pour ne pas spammer
            sys.stdout.write(f"\rTraitement: {i + 1}/{len(families)} - {family} OK")
            sys.stdout.flush()
        else:
            sys.stdout.write(f"\rTraitement: {i + 1}/{len(families)} - {family} SKIP")
            sys.stdout.flush()

        # Pas de sleep nécessaire ici, l'API Google tient la charge, mais restons polis
        # time.sleep(0.01)

    # Sauvegarde
    with open("noto_coverage_db.json", "w", encoding="utf-8") as f:
        json.dump(db, f, separators=(",", ":"))  # Minified pour gagner de la place

    print(f"\n\n🎉 Terminé. {count} polices valides sauvegardées dans : noto_coverage_db.json")


if __name__ == "__main__":
    build_database()
