#set document(
  title: "Inline Math",
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
#set math.equation(numbering: "(1)")
#set heading(numbering: "1.1")

#align(center)[
  #text(size: 1.8em, weight: "bold")[Inline Math]
]
#v(1.5em)

You can include inline math expressions using the standard LaTeX delimiters `\( ... \)` or `$ ... $` :

```markdown
The quadratic formula is given by \(x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}\)
or $x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$.
```

Rendered as:

#quote(block: true)[
  The quadratic formula is given by #mi(```x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}```)
  or #mi(```x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}```).
]

= Block Math

The Schrödinger equation in a non-relativistic case is written as:

#mitex(```\imath \hbar \frac{\partial}{\partial t} \Psi(\mathbf{r},t) =
\left[ -\frac{\hbar^2}{2m} \nabla^2 + V(\mathbf{r},t) \right] \Psi(\mathbf{r},t)```)

And the set of Maxwell's equations in differential form. The magnetic flux #ref(<eq:max2>) through any closed surface is zero, this implies that there are no magnetic monopoles.

#mitex(```\begin{align}
\nabla \cdot \vec{E} &= \frac{\rho}{\varepsilon_0} \quad &&\text{Gauss Law}\\[4pt]
\nabla \cdot \vec{B} &= 0 \quad &&\text{Gauss's law for electricity} \\[4pt]
\nabla \times \vec{E} &= -\,\frac{\partial \vec{B}}{\partial t}
    \quad &&\text{Faraday's law}\\[4pt]
\nabla \times \vec{B} &= \mu_0 \vec{J} + \mu_0 \varepsilon_0
    \frac{\partial \vec{E}}{\partial t}
\quad &&\text{Ampère-Maxwell law}
\end{align}```) <eq:max2>
