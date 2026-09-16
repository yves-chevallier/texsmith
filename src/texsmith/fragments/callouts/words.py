"""The default title of a callout, in the languages the templates speak.

A callout written without a title prints its kind's word — ``\\begin{tscallout}
[kind=note]`` is a box titled *Note* — and that word is the document's, not
English. tmark's ``registries()["admonitions"]`` carries the English label of
every standard kind and nothing else, so the translations live here, keyed by
the BCP-47 primary subtag :func:`_map_bcp47_language` resolves a ``language:``
to (``french``, ``fr-CA`` and ``fr`` all land on ``fr``).

A language with no table falls back to English, and a kind a document
declares itself (``press.declare.admonitions``) carries its own ``name`` in
whatever language it was written in — which is the way to title a kind this
table does not know, or to overrule one it does.
"""

from __future__ import annotations

from collections.abc import Mapping

from texsmith.core.templates.languages import _map_bcp47_language


__all__ = ["CALLOUT_WORDS", "callout_words_for"]

#: ``language -> kind -> title``: the sixteen kinds of
#: ``tmark.registries()["admonitions"]`` plus the seven the callout styles
#: define on their own (``summary``, ``success``, ``caution``, ``failure``,
#: ``bug``, ``example``, ``quote``), which an author writes just as readily.
#: English is the fallback and lives in tmark's registry and in the styles,
#: not here.
CALLOUT_WORDS: Mapping[str, Mapping[str, str]] = {
    "fr": {
        "note": "Note",
        "tip": "Astuce",
        "warning": "Avertissement",
        "important": "Important",
        "danger": "Danger",
        "info": "Info",
        "hint": "Indice",
        "seealso": "Voir aussi",
        "question": "Question",
        "abstract": "Résumé",
        "theorem": "Théorème",
        "lemma": "Lemme",
        "corollary": "Corollaire",
        "proposition": "Proposition",
        "definition": "Définition",
        "proof": "Démonstration",
        "summary": "Résumé",
        "success": "Succès",
        "caution": "Attention",
        "failure": "Échec",
        "bug": "Bogue",
        "example": "Exemple",
        "quote": "Citation",
    },
    "de": {
        "note": "Notiz",
        "tip": "Tipp",
        "warning": "Warnung",
        "important": "Wichtig",
        "danger": "Gefahr",
        "info": "Info",
        "hint": "Hinweis",
        "seealso": "Siehe auch",
        "question": "Frage",
        "abstract": "Zusammenfassung",
        "theorem": "Satz",
        "lemma": "Lemma",
        "corollary": "Korollar",
        "proposition": "Proposition",
        "definition": "Definition",
        "proof": "Beweis",
        "summary": "Zusammenfassung",
        "success": "Erfolg",
        "caution": "Achtung",
        "failure": "Fehlschlag",
        "bug": "Fehler",
        "example": "Beispiel",
        "quote": "Zitat",
    },
    "es": {
        "note": "Nota",
        "tip": "Consejo",
        "warning": "Advertencia",
        "important": "Importante",
        "danger": "Peligro",
        "info": "Info",
        "hint": "Pista",
        "seealso": "Véase también",
        "question": "Pregunta",
        "abstract": "Resumen",
        "theorem": "Teorema",
        "lemma": "Lema",
        "corollary": "Corolario",
        "proposition": "Proposición",
        "definition": "Definición",
        "proof": "Demostración",
        "summary": "Resumen",
        "success": "Éxito",
        "caution": "Precaución",
        "failure": "Fallo",
        "bug": "Error",
        "example": "Ejemplo",
        "quote": "Cita",
    },
    "it": {
        "note": "Nota",
        "tip": "Suggerimento",
        "warning": "Avvertenza",
        "important": "Importante",
        "danger": "Pericolo",
        "info": "Info",
        "hint": "Indizio",
        "seealso": "Vedi anche",
        "question": "Domanda",
        "abstract": "Sommario",
        "theorem": "Teorema",
        "lemma": "Lemma",
        "corollary": "Corollario",
        "proposition": "Proposizione",
        "definition": "Definizione",
        "proof": "Dimostrazione",
        "summary": "Sommario",
        "success": "Successo",
        "caution": "Attenzione",
        "failure": "Fallimento",
        "bug": "Bug",
        "example": "Esempio",
        "quote": "Citazione",
    },
    "pt": {
        "note": "Nota",
        "tip": "Dica",
        "warning": "Aviso",
        "important": "Importante",
        "danger": "Perigo",
        "info": "Info",
        "hint": "Sugestão",
        "seealso": "Ver também",
        "question": "Pergunta",
        "abstract": "Resumo",
        "theorem": "Teorema",
        "lemma": "Lema",
        "corollary": "Corolário",
        "proposition": "Proposição",
        "definition": "Definição",
        "proof": "Demonstração",
        "summary": "Resumo",
        "success": "Sucesso",
        "caution": "Cuidado",
        "failure": "Falha",
        "bug": "Bug",
        "example": "Exemplo",
        "quote": "Citação",
    },
    "nl": {
        "note": "Notitie",
        "tip": "Tip",
        "warning": "Waarschuwing",
        "important": "Belangrijk",
        "danger": "Gevaar",
        "info": "Info",
        "hint": "Hint",
        "seealso": "Zie ook",
        "question": "Vraag",
        "abstract": "Samenvatting",
        "theorem": "Stelling",
        "lemma": "Lemma",
        "corollary": "Gevolg",
        "proposition": "Propositie",
        "definition": "Definitie",
        "proof": "Bewijs",
        "summary": "Samenvatting",
        "success": "Succes",
        "caution": "Let op",
        "failure": "Mislukking",
        "bug": "Bug",
        "example": "Voorbeeld",
        "quote": "Citaat",
    },
}


def callout_words_for(language: str | None) -> Mapping[str, str]:
    """The standard kinds' titles in ``language``; empty when English answers.

    ``language`` is whatever the template carries — a babel name
    (``french``), a tag (``fr-CA``) or a code (``fr``).
    """
    tag = _map_bcp47_language(language)
    if tag is None:
        return {}
    return CALLOUT_WORDS.get(tag, {})
