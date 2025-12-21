# Glossary

In online documentation, a glossary doesn't make much sense because you can
search for terms directly and you have hyperlinks. However, in printed documents, a
glossary can be very useful to provide definitions of terms used in the text.

TeXSmith adds support for glossaries through the `glossary` extension, which
allows you to define glossary entries in your Markdown files and generate a
glossary section in the output document.

The fragment is automatically included when needed:

- If you use acronyms or abbreviations.
- If you define glossary entries using the `glossary` directive.
