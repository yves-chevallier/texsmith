# Equations

In Markdown, there is no standard way to number equations or to reference them. However, with the help of the `pymdownx.arithmatex` extension, we can achieve this functionality. Artimatex preserves LaTeX math syntax within Markdown and allows for equation with labels.

```md
The equation for the elastic modulus $E$ as a function of temperature $T$ and strain rate $\dot{\varepsilon}$ [](#eq:em) gives the modulus.

$$
\begin{equation}\label{eq:em}
M = \frac{1}{E(T, \dot{\varepsilon})}
\end{equation}
$$
```
