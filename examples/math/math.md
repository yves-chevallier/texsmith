# Inline Math

You can include inline math expressions using the standard LaTeX delimiters `\( ... \)` or `$ ... $` :

```markdown
The quadratic formula is given by \(x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}\) 
or $x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$.
```

Rendered as:

> The quadratic formula is given by \(x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}\) 
> or $x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$.

## Block Math

The Schrödinger equation in a non-relativistic case is written as:

$$
\imath \hbar \frac{\partial}{\partial t} \Psi(\mathbf{r},t) =
\left[ -\frac{\hbar^2}{2m} \nabla^2 + V(\mathbf{r},t) \right] \Psi(\mathbf{r},t)
$$

And the set of Maxwell's equations in differential form. The magnetic flux $\eqref{eq:max2}$ through any closed surface is zero, this implies that there are no magnetic monopoles.

$$
\begin{align}
\nabla \cdot \vec{E} &= \frac{\rho}{\varepsilon_0} \quad &&\text{Gauss Law}\\[4pt]
\nabla \cdot \vec{B} &= 0 \quad &&\text{Gauss's law for electricity} \label{eq:max2}\\[4pt]
\nabla \times \vec{E} &= -\,\frac{\partial \vec{B}}{\partial t} 
    \quad &&\text{Faraday's law}\\[4pt]
\nabla \times \vec{B} &= \mu_0 \vec{J} + \mu_0 \varepsilon_0 
    \frac{\partial \vec{E}}{\partial t}
\quad &&\text{Ampère-Maxwell law}
\end{align}
$$