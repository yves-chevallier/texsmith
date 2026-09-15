#set document(
title: "Versioning",
)
#set page(
paper: "a4",
margin: 2.5cm,
numbering: none,
footer: context {
if counter(page).final().first() > 1 {
align(center)[#counter(page).get().first()]
}
},
)
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#set par(justify: true)
#show heading: set block(above: 1.8em, below: 1.0em)
#set heading(numbering: "1.1")

#align(center)[
#text(size: 1.8em, weight: "bold")[Versioning]]
#v(1.5em)

#ts-callout-style.update("fancy")

TeXSmith follows #link("https://semver.org/spec/v2.0.0.html")[Semantic Versioning 2.0.0]. Each release version is identified by a three-part number: `MAJOR.MINOR.PATCH`. We will therefore ensure that no breaking changes are introduced in minor or patch releases.

However, versions prior to `1.0.0` are considered initial development releases, and as such, the public API may change at any time without notice. Users are advised to expect potential breaking changes when upgrading between pre-1.0.0 versions. As we are not yet near a stable release, TeXSmith is not recommended for production use at this time. Testing and feedback from early adopters are highly appreciated to help us improve the tool.
