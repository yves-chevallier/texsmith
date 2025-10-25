"""Configuration models used by the LaTeX renderer.

CommonConfig:
    build_dir (Path | None): Répertoire de base pour les artefacts LaTeX.
        Fournissez un chemin (absolu ou relatif au projet) pour changer
        l'emplacement global d'export. Les livres héritent de cette valeur
        lorsqu'ils n'en définissent pas.
    save_html (bool): Conserve l'export HTML intermédiaire à côté du PDF.
        Activez cette option pour inspecter ou déboguer le rendu HTML produit
        avant la compilation LaTeX.
    mermaid_config (Path | None): Fichier de configuration Mermaid.
        Référencez un fichier `.json` ou `.mermaid` pour injecter des options
        personnalisées lors de la conversion des diagrammes.
    project_dir (Path | None): Répertoire racine du projet MkDocs.
        Sert de base pour résoudre les chemins sources, notamment lors de la
        copie de fichiers additionnels.
    language (str | None): Code de langue BCP 47 utilisé par LaTeX.
        Renseignez-le pour contrôler l'hyphénation, les traductions internes
        et la localisation des métadonnées.

CoverConfig:
    name (str): Identifiant du gabarit de couverture à appliquer.
        Utilisez une valeur déclarée dans vos modèles de couverture.
    color (str | None): Couleur principale du gabarit.
        Fixez-la pour harmoniser la palette de la couverture ou conserver
        la valeur par défaut du template.
    logo (str | None): Ressource logo à afficher.
        Fournissez un chemin relatif au projet pour insérer un logo spécifique.

BookConfig:
    root (str | None): Titre de navigation servant de point de départ du livre.
        Spécifiez-le si la section racine diffère de la première page MkDocs.
    title (str | None): Titre du livre.
        Laissez vide pour utiliser `site_name` ou fournissez un intitulé dédié.
    subtitle (str | None): Sous-titre affiché sur la couverture et dans les
        métadonnées.
    author (str | None): Auteur principal du livre.
        Peut être multi-auteurs en utilisant une chaîne formatée.
    year (int | None): Année de publication.
        Renseignez-la pour figer la date si `site_date` n'est pas défini.
    email (str | None): Adresse de contact affichée dans les credits.
    folder (Path | None): Dossier de sortie pour le livre.
        Par défaut, un slug du titre est utilisé ; spécifiez un chemin pour
        contrôler précisément la destination.
    frontmatter (list[str]): Titres de sections forcées en front matter.
        Listez les titres MkDocs à déplacer avant la matière principale.
    backmatter (list[str]): Titres de sections placées en annexes.
        Listez les titres MkDocs à déplacer après la matière principale.
    base_level (int): Niveau de base des titres.
        Ajustez ce niveau pour aligner la numérotation avec le gabarit LaTeX.
    copy_files (dict[str, str]): Correspondance de fichiers supplémentaires.
        Chaque clé est un motif glob relatif au projet ; la valeur indique où
        copier les fichiers dans le dossier de sortie.
    index_is_foreword (bool): Traite la page `index` comme avant-propos.
        Activez-le pour retirer la numérotation de cette page d'ouverture.
    drop_title_index (bool): Supprime le titre de la page `index` lorsqu'elle
        est considérée comme avant-propos.
    cover (CoverConfig): Paramètres de la couverture du livre.

LaTeXConfig:
    enabled (bool): Active ou désactive la génération LaTeX.
        Mettez `False` pour conserver la configuration sans lancer l'export.
    books (list[BookConfig]): Ensemble des livres à produire.
        Ajoutez une entrée par livre souhaité ; hérite de CommonConfig.
    clean_assets (bool): Nettoie les artefacts obsolètes dans `build_dir`.
        Laissez actif pour éviter l'accumulation de ressources inutilisées.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from slugify import slugify


class CommonConfig(BaseModel):
    """Common configuration propagated to each book."""

    model_config = ConfigDict(extra="forbid")

    build_dir: Path | None = None
    save_html: bool = False
    mermaid_config: Path | None = None
    project_dir: Path | None = None
    language: str | None = None


class CoverConfig(BaseModel):
    """Metadata used to render book covers."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="default", description="Cover template name")
    color: str | None = Field(default="black", description="Primary color")
    logo: str | None = Field(default=None, description="Logo path")


class BookConfig(CommonConfig):
    """Configuration for an individual book."""

    root: str | None = None
    title: str | None = None
    subtitle: str | None = None
    author: str | None = None
    year: int | None = None
    email: str | None = None
    folder: Path | None = None
    frontmatter: list[str] = Field(default_factory=list)
    backmatter: list[str] = Field(default_factory=list)
    base_level: int = -2
    copy_files: dict[str, str] = Field(default_factory=dict)
    index_is_foreword: bool = False
    drop_title_index: bool = False
    cover: CoverConfig = Field(default_factory=CoverConfig)

    @model_validator(mode="after")
    def set_folder(self) -> BookConfig:
        """Populate the output folder from the book title when missing."""
        if self.folder is None and self.title:
            self.folder = Path(slugify(self.title, separator="-"))
        return self


class LaTeXConfig(CommonConfig):
    """Configuration for LaTeX taken from ``mkdocs.yml``."""

    enabled: bool = True
    books: list[BookConfig] = Field(default_factory=lambda: [BookConfig()])
    clean_assets: bool = True

    @model_validator(mode="after")
    def propagate(self) -> LaTeXConfig:
        """Propagate common values to nested book configurations."""
        to_propagate = (
            "build_dir",
            "mermaid_config",
            "save_html",
            "project_dir",
            "language",
        )
        for book in self.books:
            for key in to_propagate:
                if getattr(book, key) is None:
                    setattr(book, key, getattr(self, key))
        return self

    def add_extra(self, **extra_data: Any) -> None:
        """Allow consumers to attach additional attributes at runtime."""
        for key, value in extra_data.items():
            object.__setattr__(self, key, value)
