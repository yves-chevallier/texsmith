# Math Extension

The undisputed standard for writing mathematical notation is the LaTeX syntax, as implemented by the MathJax and Arithmatex extensions.

## Inline Math

You can include inline math expressions using the standard LaTeX delimiters `\( ... \)` or `$ ... $` :

```markdown
The quadratic formula is given by \(x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}\) 
or $x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$.
```

Rendered as:

> The quadratic formula is given by \(x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}\) 
> or $x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$.

!!! note 
    Do not add spaces between the dollar signs and the math content, as this will prevent proper rendering.

## Block Math

### Simple equations

The Schrödinger equation in a non-relativistic case is written as:

```latex
$$
\imath \hbar \frac{\partial}{\partial t} \Psi(\mathbf{r},t) =
\left[ -\frac{\hbar^2}{2m} \nabla^2 + V(\mathbf{r},t) \right] \Psi(\mathbf{r},t)
$$
```

$$
\imath \hbar \frac{\partial}{\partial t} \Psi(\mathbf{r},t) =
\left[ -\frac{\hbar^2}{2m} \nabla^2 + V(\mathbf{r},t) \right] \Psi(\mathbf{r},t)
$$

### Multiple equations

```latex
$$
\begin{align*}
\nabla \cdot \vec{E} &= \frac{\rho}{\varepsilon_0} \quad &&\text{Gauss Law}\\[4pt]
\nabla \cdot \vec{B} &= 0 \quad &&\text{Gauss's law for electricity}\\[4pt]
\nabla \times \vec{E} &= -\,\frac{\partial \vec{B}}{\partial t} 
    \quad &&\text{Faraday's law}\\[4pt]
\nabla \times \vec{B} &= \mu_0 \vec{J} + \mu_0 \varepsilon_0 
    \frac{\partial \vec{E}}{\partial t}
\quad &&\text{Ampère-Maxwell law}
\end{align*}
$$
```

$$
\begin{align*}
\nabla \cdot \vec{E} &= \frac{\rho}{\varepsilon_0} \quad &&\text{Gauss Law}\\[4pt]
\nabla \cdot \vec{B} &= 0 \quad &&\text{Gauss's law for electricity}\\[4pt]
\nabla \times \vec{E} &= -\,\frac{\partial \vec{B}}{\partial t} 
    \quad &&\text{Faraday's law}\\[4pt]
\nabla \times \vec{B} &= \mu_0 \vec{J} + \mu_0 \varepsilon_0 
    \frac{\partial \vec{E}}{\partial t}
\quad &&\text{Ampère-Maxwell law}
\end{align*}
$$

### Numbered equation

To number an equation use the `\begin{equation}` and `\end{equation}` commands. Here the example for the relativistic gravitational field equation:

```latex
The equation $\eqref{eq:gravity}$ describes the fundamental interaction of 
gravitation as a result of spacetime being curved by matter and energy.

$$
\begin{equation} \label{eq:gravity}
R_{\mu \nu} - \frac{1}{2} R g_{\mu \nu} + \Lambda g_{\mu \nu} = 
    \frac{8 \pi G}{c^4} T_{\mu \nu}
\end{equation}
$$
```

The equation $\eqref{eq:gravity}$ describes the fundamental interaction of gravitation as a result of spacetime being curved by matter and energy.

$$
\begin{equation} \label{eq:gravity}
R_{\mu \nu} - \frac{1}{2} R g_{\mu \nu} + \Lambda g_{\mu \nu} = \frac{8 \pi G}{c^4} T_{\mu \nu}
\end{equation}
$$

You can refer to numbered equations using the `\label{}` and place in Markdown `$\eqref{}$`.

In an aligned environment, you can number individual lines using the `\label{}` command:

```latex
As we see $\eqref{eq:max2}$, the magnetic flux through any closed surface is zero, 
this implies that there are no magnetic monopoles.

$$
\begin{align}
\oint_{\partial V} \vec{E} \cdot d\vec{S} &= \frac{Q_{\text{int}}}{\varepsilon_0} 
    \label{eq:max1} \\[6pt]
\oint_{\partial V} \vec{B} \cdot d\vec{S} &= 0 \label{eq:max2} \\[6pt]
\oint_{\partial S} \vec{E} \cdot d\vec{\ell} &= -\,\frac{d}{dt} \int_{S} \vec{B} 
    \cdot d\vec{S} \label{eq:max3} \\[6pt]
\oint_{\partial S} \vec{B} \cdot d\vec{\ell} &= \mu_0 I_{\text{int}} 
+ \mu_0 \varepsilon_0 \frac{d}{dt} \int_{S} \vec{E} \cdot d\vec{S} \label{eq:max4}
\end{align}
$$
```

As we see $\eqref{eq:max2}$, the magnetic flux through any closed surface is zero, this implies that there are no magnetic monopoles.

$$
\begin{align}
\oint_{\partial V} \vec{E} \cdot d\vec{S} &= \frac{Q_{\text{int}}}{\varepsilon_0} \label{eq:max1} \\[6pt]
\oint_{\partial V} \vec{B} \cdot d\vec{S} &= 0 \label{eq:max2} \\[6pt]
\oint_{\partial S} \vec{E} \cdot d\vec{\ell} &= -\,\frac{d}{dt} \int_{S} \vec{B} \cdot d\vec{S} \label{eq:max3} \\[6pt]
\oint_{\partial S} \vec{B} \cdot d\vec{\ell} &= \mu_0 I_{\text{int}} 
+ \mu_0 \varepsilon_0 \frac{d}{dt} \int_{S} \vec{E} \cdot d\vec{S} \label{eq:max4}
\end{align}
$$

## MkDocs Configuration

If used in MkDocs, ensure you have the following configuration to enable MathJax with equation numbering support:

```yaml
markdown_extensions:
  - pymdownx.arithmatex:
      generic: true
extra_javascript:
  - js/mathjax.js
  - https://unpkg.com/mathjax@3/es5/tex-mml-chtml.js
```

In the `js/mathjax.js` file, include the following MathJax configuration:

```javascript
window.MathJax = {
  tex: {
    inlineMath: [['\\(', '\\)']],
    displayMath: [['$$', '$$'], ['\\[', '\\]']],
    tags: 'ams',   
    packages: {'[+]': ['ams']}
  },
  options: {
    ignoreHtmlClass: '.*',
    processHtmlClass: 'arithmatex'
  }
};
```

## With LaTeX output

Here what the above examples would look when rendered with TeXSmith:

[![Math rendering](../assets/examples/equation.png)](../assets/examples/equation.pdf)
