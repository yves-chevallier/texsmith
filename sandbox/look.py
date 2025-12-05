import json


class FontSelector:
    def __init__(self, db_path="noto_coverage_db.json"):
        # Chargement de la base
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                self.db = json.load(f)
        except FileNotFoundError:
            print(f"Erreur : Le fichier {db_path} est introuvable.")
            self.db = []

    def get_candidates(self, char):
        """Récupère TOUTES les fonts qui supportent le caractère."""
        code = ord(char)
        candidates = []
        for entry in self.db:
            for start, end in entry["ranges"]:
                if start <= code <= end:
                    candidates.append(entry["family"])
                    break
        return candidates

    def calculate_score(self, font_name):
        """
        Attribue un score à une font pour déterminer sa pertinence
        comme police de corps de texte standard.
        """
        score = 0
        name_lower = font_name.lower()

        # --- BONUS ---
        # On veut du standard lisible
        if "noto sans" in name_lower:
            score += 100
        elif "noto serif" in name_lower:
            score += 80  # Serif est un bon second choix

        # Pour les emojis, on préfère la couleur
        if "color emoji" in name_lower:
            score += 150

        # --- MALUS ---
        # On évite les styles spécifiques sauf nécessité
        if "ui" in name_lower:
            score -= 20  # Moins lisible en long texte
        if "display" in name_lower:
            score -= 30  # Trop gros/gras
        if "mono" in name_lower:
            score -= 40  # Chasse fixe

        # Styles régionaux ou calligraphiques spécifiques
        # Si on cherche de l'Arabe générique, on ne veut pas de Nastaliq (style persan/urdu)
        # ni de Kufi (géométrique) par défaut.
        decorative_keywords = ["nastaliq", "kufi", "naskh", "signwriting", "handwriting"]
        for kw in decorative_keywords:
            if kw in name_lower:
                score -= 50

        # Pénalité de longueur :
        # "Noto Sans Arabic" (court) est souvent plus générique que "Noto Sans Arabic ExtraCondensed"
        score -= len(font_name)

        return score

    def best_font_for_char(self, char):
        candidates = self.get_candidates(char)

        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0]

        # On trie les candidats par score décroissant
        # On utilise une liste de tuples (font_name, score) pour le debug si besoin
        ranked_candidates = sorted(candidates, key=self.calculate_score, reverse=True)

        # Le premier est le meilleur
        return ranked_candidates[0]


# --- DÉMONSTRATION ---

selector = FontSelector()

# Liste de caractères pièges
test_chars = [
    ("A", "Latin Simple"),
    ("€", "Symbole Euro"),
    ("﷽", "Arabe (Basmala)"),
    ("🐍", "Emoji"),
    ("अ", "Devanagari (Hindi)"),
    ("ト", "Katakana (Japonais)"),
]

print(f"{'CHAR':<5} | {'CATEGORY':<20} | {'BEST FONT (RESULTAT)'}")
print("-" * 70)

for char, cat in test_chars:
    best = selector.best_font_for_char(char)
    # Pour le debug, on peut aussi voir les candidats rejetés :
    # candidates = selector.get_candidates(char)
    # print(f"Candidats pour {char}: {candidates}")
    print(f"{char:<5} | {cat:<20} | {best}")
