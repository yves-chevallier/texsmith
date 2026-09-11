#set document(
  title: "Abbreviations",
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
  #text(size: 1.8em, weight: "bold")[Abbreviations]
]
#v(1.5em)

In modern chemical analysis, techniques like NMR, FTIR, and GC-MS are essential for identifying compounds, while methods such as HPLC and ICP-OES provide high-precision quantification of analytes across a wide range of matrices. Researchers often rely on computational tools like DFT and Molecular Dynamics to model reaction pathways and molecular behavior, supported by data from X-ray Diffraction for crystalline structure determination.

#v(1em)
#heading(numbering: none)[Acronyms]

/ DFT: Density Functional Theory
/ FTIR: Fourier Transform Infrared Spectroscopy
/ GC-MS: Gas Chromatography–Mass Spectrometry
/ HPLC: High-Performance Liquid Chromatography
/ ICP-OES: Inductively Coupled Plasma–Optical Emission Spectroscopy
/ NMR: Nuclear Magnetic Resonance
