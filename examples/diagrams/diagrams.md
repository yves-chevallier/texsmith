---
press:
  subtitle: "An Overview of drawio and mermaid diagram integration"
  paper:
    margin: 2cm
---
# Diagram Integration

You can embed Draw.io or Mermaid diagrams directly in Markdown. This keeps
technical documentation close to the visuals it describes, and the package
takes care of converting each diagram to an image that the final LaTeX
document can reference automatically.

## Draw.io Diagram

![Euclidean GCD](pgcd.drawio){width=60%}

/// caption
Euclidean algorithm for the greatest common divisor
///

## Mermaid Diagram

```mermaid {width=80%}
%% Vegetable harvesting algorithm
flowchart LR
    start(Start) --> pick[Dig up]
    pick --> if{Cabbages?}
    if --No--> step[Move forward one step]
    step --> pick
    if --Yes--> stop(End)
```
