"""
Fragments are reusable pieces of LaTeX code that can be combined to create
complex documents. This module provides the base class for all fragments and
registers them for easy access.

Each fragment should inherit from the `Fragment` base class and implement the
`render` method, which returns the LaTeX code as a string.

Fragments are used by templates to extend their functionality and provide
modular components that can be reused across different documents.

- Bibliography: Fragments for managing references and citations.
- Callouts: Fragments for highlighting important information.
- Code Listings: Fragments for including source code with syntax highlighting.
- Glossary: Fragments for defining terms and acronyms.
- Typesetting: Fragments for custom formatting and layout.
- Geometry: Fragments for setting page dimensions and margins.
- etc.

"""
