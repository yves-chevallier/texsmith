# Index

This document demonstrates the index generation with TeXSmith. You can nest, format and create multiple index entries for terms.

Use the hashtag syntax `#[term]` to inject index entries without altering the visible text.

```markdown
#[a] One level index entry in default index
#[a][b][c](registry) Three levels nesting in the registry index
#[*a*] Formatted index entry in default index
#[**a**] Bold formatted index entry in default index
#[***a***] Bold italic formatted index entry in default index
#[a] #[b] Multiple index entries in one place
```

When built with default template (article) the indices will automatically be placed at the end of the document if there are any index entries.

## Granny Smith

A tart apple variety often used in baking and cooking. Known for its bright green skin and crisp texture.
#[Granny Smith] #[apple]

{latex}[\clearpage]

## Fuji

A sweet and juicy apple variety that originated in Japan. It has a dense flesh and a balanced flavor.

#[Fuji] #[apple] #[*juicy*]

{latex}[\clearpage]

## Honeycrisp

A popular apple variety known for its crisp texture and sweet-tart flavor. It has a distinctive red and yellow skin.

#[Honeycrisp] #[apple]
