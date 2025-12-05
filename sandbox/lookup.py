import bisect
import json
import os
import pickle
from collections import defaultdict


class NotoLookup:
    def __init__(
        self,
        db_path="noto_coverage_db.json",
        cache_path="noto_lookup.pkl",
        classes_path="ucharclasses.json",
        verbose=False,
    ):
        self.db_path = db_path
        self.cache_path = cache_path
        self.classes_path = classes_path
        self.verbose = verbose
        self._data = None
        self._classes_index = ([], [])
        self.found_codepoints = {}  # Cache for found characters and their best font
        self._load_data()
        self._load_classes()

    def _load_data(self):
        """
        Charge les données depuis le cache pkl si possible, sinon depuis le JSON.
        Le cache est regénéré si le JSON est plus récent.
        """
        cache_exists = os.path.exists(self.cache_path)
        db_mtime = os.path.getmtime(self.db_path) if os.path.exists(self.db_path) else 0
        cache_mtime = os.path.getmtime(self.cache_path) if cache_exists else 0

        if cache_exists and cache_mtime > db_mtime:
            if self.verbose:
                print("Loading from cache...")
            with open(self.cache_path, "rb") as f:
                self._data = pickle.load(f)
            return

        if self.verbose:
            print("Building from JSON database...")
        self._build_from_json()

    def _build_from_json(self):
        """
        Construit la structure de données optimisée à partir du JSON et la sauvegarde dans le cache.
        """
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                db = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error reading {self.db_path}: {e}")
            self._data = ([], [], {})
            return

        font_map = {font_data["family"]: i for i, font_data in enumerate(db)}
        font_indices = {i: name for name, i in font_map.items()}

        all_ranges = []
        for font_data in db:
            font_index = font_map[font_data["family"]]
            for start, end in font_data["ranges"]:
                all_ranges.append((start, end, font_index))

        all_ranges.sort(key=lambda x: x[0])

        starts = [r[0] for r in all_ranges]
        ranges_meta = [(r[1], r[2]) for r in all_ranges]

        self._data = (starts, ranges_meta, font_indices)

        try:
            with open(self.cache_path, "wb") as f:
                pickle.dump(self._data, f)
            if self.verbose:
                print(f"Cache saved to {self.cache_path}")
        except IOError as e:
            if self.verbose:
                print(f"Error saving cache to {self.cache_path}: {e}")

    # --- ucharclasses helpers -------------------------------------------------
    def _load_classes(self):
        """Charge le mapping classe Unicode -> ranges pour pouvoir remonter le script."""
        try:
            with open(self.classes_path, "r", encoding="utf-8") as f:
                classes = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._classes_index = ([], [])
            return

        ranges = []
        for entry in classes:
            start = entry.get("start")
            end = entry.get("end")
            name = entry.get("name")
            if start is None or end is None or name is None:
                continue
            ranges.append((int(start), int(end), str(name)))

        ranges.sort(key=lambda r: r[0])
        starts = [r[0] for r in ranges]
        meta = [(r[1], r[2]) for r in ranges]
        self._classes_index = (starts, meta)

    def _class_for_codepoint(self, codepoint: int) -> str | None:
        """Retourne la classe ucharclasses pour un codepoint, ou None."""
        starts, meta = self._classes_index
        if not starts:
            return None
        idx = bisect.bisect_right(starts, codepoint)
        if idx == 0:
            return None
        # candidate just before idx
        end, name = meta[idx - 1]
        if codepoint <= end:
            return name
        return None

    # --- Recherche de fonts ---------------------------------------------------
    def get_candidates(self, char):
        """Récupère toutes les fonts qui supportent le caractère en utilisant la recherche binaire."""
        if not self._data or not self._data[0]:
            return []

        starts, ranges_meta, font_indices = self._data
        code = ord(char)

        # Trouve le point d'insertion pour le codepoint dans la liste triée des départs.
        # C'est l'index du premier range qui commence APRÈS notre codepoint.
        # Les ranges qui pourraient contenir notre codepoint sont donc avant cet index.
        idx = bisect.bisect_right(starts, code)

        candidates = []
        # On vérifie tous les ranges qui commencent avant ou au même endroit que `code`
        for i in range(idx):
            # La condition `starts[i] <= code` est implicite grâce au bisect.
            # On doit juste vérifier si on est avant la fin du range.
            end, font_index = ranges_meta[i]
            if code <= end:
                candidates.append(font_indices[font_index])

        return list(set(candidates))  # Retourne les fonts uniques

    def _calculate_score(self, font_name):
        """
        Attribue un score à une font. On préfère les fonts non-bitmap pour les emojis.
        """
        score = 0
        name_lower = font_name.lower()

        # Priorité aux polices noir et blanc pour les emojis
        if "emoji" in name_lower:
            if "color" not in name_lower:
                score += 200  # Gros bonus pour les emojis N&B (Symbola, etc.)
            else:
                score -= 100  # Malus pour les emojis couleur (incompatibles LaTeX)

        if "sans" in name_lower and "cjk" not in name_lower:
            score += 100
        elif "serif" in name_lower and "cjk" not in name_lower:
            score += 80

        # CJK
        if "cjksc" in name_lower:
            score += 50  # Chinois simplifié
        if "cjkjp" in name_lower:
            score += 50  # Japonais
        if "cjkkr" in name_lower:
            score += 50  # Coréen

        # Malus pour les styles spécifiques
        if "mono" in name_lower:
            score -= 40
        if "display" in name_lower:
            score -= 30

        return score

    def best_font_for_char(self, char):
        """Choisit la meilleure font pour un caractère donné."""
        candidates = self.get_candidates(char)
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        ranked = sorted(candidates, key=self._calculate_score, reverse=True)
        return ranked[0]

    def lookup(self, text):
        """Analyse un texte, trouve la meilleure font pour chaque caractère et met à jour le cache interne."""
        for char in text:
            if char not in self.found_codepoints:
                best_font = self.best_font_for_char(char)
                # Même sans font trouvée, on enregistre le caractère pour remonter sa classe
                self.found_codepoints[char] = best_font

    def reset(self):
        """Réinitialise le cache interne des caractères trouvés."""
        self.found_codepoints = {}

    def summary(self):
        """Retourne un résumé des fonts nécessaires et des ranges couverts."""
        font_to_codepoints = defaultdict(list)
        for char, font in self.found_codepoints.items():
            font_to_codepoints[font].append(ord(char))

        output = {}
        for font, codepoints in font_to_codepoints.items():
            codepoints.sort()

            if not codepoints:
                continue

            # Fusionner les codepoints en ranges
            ranges = []
            start = end = codepoints[0]
            for code in codepoints[1:]:
                if code == end + 1:
                    end = code
                else:
                    ranges.append(
                        f"U+{start:04X}" if start == end else f"U+{start:04X}-U+{end:04X}"
                    )
                    start = end = code
            ranges.append(f"U+{start:04X}" if start == end else f"U+{start:04X}-U+{end:04X}")

            output[font] = ranges

        return output

    def get_classes(self):
        """
        Retourne un mapping {script: {"fonts": [...], "ranges": [...]}} basé sur les caractères trouvés.
        Les ranges sont fusionnés et formatés en U+XXXX ou U+XXXX-U+YYYY.
        """
        script_data = defaultdict(lambda: {"fonts": set(), "codepoints": []})
        for char, font in self.found_codepoints.items():
            code = ord(char)
            script = self._class_for_codepoint(code)
            if script is None and code <= 0x7F:
                # Ignore ASCII/control chars so they don't show up as Unknown
                continue
            script = script or "Unknown"
            entry = script_data[script]
            entry["fonts"].add(font)
            entry["codepoints"].append(code)

        def merge_ranges(codes):
            if not codes:
                return []
            codes = sorted(set(codes))
            merged = []
            start = end = codes[0]
            for c in codes[1:]:
                if c == end + 1:
                    end = c
                else:
                    merged.append(f"U+{start:04X}" if start == end else f"U+{start:04X}-U+{end:04X}")
                    start = end = c
            merged.append(f"U+{start:04X}" if start == end else f"U+{start:04X}-U+{end:04X}")
            return merged

        result = {}
        for script, info in script_data.items():
            result[script] = {
                "fonts": sorted(info["fonts"]),
                "ranges": merge_ranges(info["codepoints"]),
            }
        return result


# --- DÉMONSTRATION ---
if __name__ == "__main__":
    lookup = NotoLookup()
    if not lookup._data or not lookup._data[0]:
        print("Failed to load data, exiting.")
    else:
        print("\n--- Test de recherche ---")
        test_text = "Hello World! 👋 Bonjour. 汉字. 안녕하세요. こんにちは."

        print(f'Analyse du texte: "{test_text}"')
        lookup.lookup(test_text)

        print("\n--- Résumé pour fallback LaTeX (ucharclasses) ---")
        summary_data = lookup.summary()
        for font, ranges in summary_data.items():
            print(f"\nPolice: {font}")
            print(f"  Ranges: {', '.join(ranges)}")

        print("\n--- Test de caractères individuels ---")
        chars_to_test = {
            "A": "Latin",
            "€": "Euro",
            "🐍": "Emoji (serpent)",
            "汉": "Idéogramme Chinois",
            "안": "Syllabe Coréenne",
            "こ": "Hiragana Japonais",
        }
        for char, desc in chars_to_test.items():
            best = lookup.best_font_for_char(char)
            print(f"Meilleure font pour '{char}' ({desc}): {best}")
