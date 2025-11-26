# TeX

## Donald Knuth

Donald Knuth is an American mathematician and computer scientist, born in 1938.
He is widely regarded as one of the great pioneers of algorithmics and theoretical computer science. Beyond pure algorithms, he cared deeply about how mathematics and computer science are communicated -- elegant notation, crisp printing, clear layout. Thus, to support his own writing (notably of his magnum opus The Art of Computer Programming), he decided to build a better typesetting system from scratch, one tailored for math and scientific texts.

## Origins & Motivation

In the late 1970s, typesetting was shifting: older "hot-metal" composition methods gave way to phototypesetting. When the second edition of The Art of Computer Programming was being re-set under the new technology, Knuth saw proofs of the text -- and was horrified by the ugliness and loss of typographic quality.
Frustrated, he resolved to create his own system -- a digital typesetting engine that gave precise control over layout, spacing, and especially the complex demands of mathematical formulae.
Thus began TeX. The project started around 1977; by 1978 a first version was running.
Knuth’s vision was not just about pretty printing: he wanted a stable, precise system that would produce **consistent output forever** -- so that technical documents would remain readable and reproducible decades later.

## Versioning of TeX -- Why π?

After a few years of development (first version around 1978, then a major rewrite as TeX82 released in 1982), the design of TeX was deemed complete and "frozen" around version 3.0 (in 1989).
Rather than increment major version numbers as new features, Knuth opted for a quirky, symbolic versioning: after 3.0, every subsequent bug-fix release adds another digit to the decimal expansion, so the version number asymptotically approaches the mathematical constant π.
As of now, the version of TeX is **3.141592653** (the cursed geekiest of version numbers).
This reflects Knuth’s philosophy: TeX is stable, mature, its core doesn’t need new features -- only maintenance to keep it consistent and bug-free.

Knuth reportedly joked that after his death, when no more bug-fixes remain, the final version "will be" exactly π -- meaning that any residual quirks or "bugs" will simply be features.

## Pronunciation

The name "TeX" comes from the Greek root τεχ- (tékʰnē) meaning "art, craft, technique" -- fitting for a typesetting system deeply rooted in the art of typesetting. Because the "X" in TeX is really the Greek letter chi (Χ), the "proper" pronunciation is something like "tekh" (with a voiceless velar fricative -- like the "ch" in German or Scottish "loch").

Over time, many users found plain TeX a bit "low-level" and hard to use directly. This led to the rise of higher-level macro systems like LaTeX (and later others), which made it easier to write large documents, papers, theses -- without wrestling directly with spacing, boxes, etc.

Despite these newer systems, the core TeX engine and its philosophy remain influential. Many scientific, mathematical, and academic publications still rely on TeX (or macro layers over it) because nothing else matches its combination of precision, stability, and typographic quality.
