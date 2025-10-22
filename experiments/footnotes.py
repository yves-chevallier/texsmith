import xml.etree.ElementTree as etree
from types import MethodType

import markdown
from markdown.extensions import Extension

# ---- On réutilise l’extension officielle plutôt que de la recopier ----------
from markdown.extensions.footnotes import FootnoteExtension


class MissingFootnotes(Extension):
    def __init__(self, **kwargs):
        # Config minimale et neutre
        self.config = {
            'element': ['footnote-missing', 'Nom du tag inséré pour une note manquante.'],
            'text_template': ['{id}', 'Texte affiché pour une note manquante. Peut contenir {id}.'],
            'css_class': ['', 'Classe CSS optionnelle pour la balise (et son lien).'],
            'link_to_list': [False, "Si True, crée un <a href='#fn:ID'> même s'il n'existe pas."],
            'data_attribute': ['data-footnote-id', "Nom de l’attribut stockant l’identifiant manquant. Laisser vide pour désactiver."],
        }
        super().__init__(**kwargs)
        self._footnotes_ext = None
        self._patched_pattern = False
        self.missing_ids: set[str] = set()

    # -- utilitaire : retrouver l’extension footnotes existante (SSOT) ----------
    def _get_footnotes_ext(self, md):
        if self._footnotes_ext is not None:
            return self._footnotes_ext
        for ext in getattr(md, 'registeredExtensions', []):
            if isinstance(ext, FootnoteExtension):
                self._footnotes_ext = ext
                break
        return self._footnotes_ext

    def reset(self):
        # Markdown appelle reset() avant chaque conversion
        self.missing_ids.clear()

    def extendMarkdown(self, md):
        md.registerExtension(self)

        if self._patched_pattern:
            return

        pattern = self._find_footnote_pattern(md)
        if pattern is None:
            raise RuntimeError(
                "MissingFootnotes nécessite que l'extension 'footnotes' soit chargée avant."
            )

        original_handle = pattern.handleMatch
        extension = self

        def patched_handle(self_pattern, match, data):
            # On délègue d’abord au comportement officiel
            result = original_handle(match, data)
            if result and result[0] is not None:
                return result

            fid = match.group(1)
            extension.missing_ids.add(fid)
            node = extension._build_missing_node(fid, self_pattern)
            return node, match.start(0), match.end(0)

        pattern.handleMatch = MethodType(patched_handle, pattern)
        self._patched_pattern = True

    def _find_footnote_pattern(self, md):
        patterns = getattr(md.inlinePatterns, 'items', None)
        if callable(patterns):
            for name, pattern in md.inlinePatterns.items():
                if name == 'footnote':
                    return pattern
        else:
            try:
                return md.inlinePatterns['footnote']
            except KeyError:
                return None
        return None

    def _build_missing_node(self, fid, pattern):
        tag_name = self.getConfig('element')
        node = etree.Element(tag_name)

        css_class = self.getConfig('css_class')
        if css_class:
            node.set('class', css_class)

        data_attr = self.getConfig('data_attribute')
        if data_attr:
            node.set(data_attr, fid)

        text = self.getConfig('text_template').format(id=fid)
        if self.getConfig('link_to_list'):
            footnote_ext = self._get_footnotes_ext(pattern.md)
            separator = footnote_ext.get_separator() if footnote_ext else ':'
            anchor = etree.SubElement(node, 'a')
            if css_class:
                anchor.set('class', css_class)
            anchor.set('href', f"#fn{separator}{fid}")
            anchor.text = text
        else:
            node.text = text

        return node


# ----------------------- Démonstration ----------------------------------------
if __name__ == "__main__":
    import textwrap

    TEST_MD = textwrap.dedent(
        """\
        Foobar @<citekey> is a cheese [^citekey], and chocolate [^chocolate].

        [^citekey]: This is the bibliography entry for citekey.
        """
    ).strip()

    md = markdown.Markdown(
        extensions=[
            'footnotes',
            MissingFootnotes(
                element='footnote-missing',
                text_template='{id}',
                css_class='',
                link_to_list=False,
            ),
        ],
        output_format="html5",
    )

    html = md.convert(TEST_MD)

    # Les IDs manquants sont disponibles si tu veux logger/alerter
    for ext in md.registeredExtensions:
        if isinstance(ext, MissingFootnotes):
            print("Missing footnotes:", sorted(ext.missing_ids))

    print(html)
