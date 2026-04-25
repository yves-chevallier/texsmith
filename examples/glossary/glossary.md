---
title: Structured glossary demo
language: english
toc: true
glossary:
  style: long
  groups:
    technical: Technical acronyms
    institutional: Institutional acronyms
  entries:
    API:
      group: technical
      description: Application Programming Interface
    HTTP:
      group: technical
      description: HyperText Transfer Protocol
    JSON:
      group: technical
      description: JavaScript Object Notation
    UN:
      group: institutional
      description: United Nations
    WHO:
      group: institutional
      description: World Health Organization
    DOI: Digital Object Identifier
---

# Introduction

This document showcases TeXSmith's structured glossary support. Definitions
live in the YAML front matter: each entry has a description and may be attached
to a group. TeXSmith renders, in declaration order, one table per group plus a
default table for entries that were left ungrouped.

# Technical acronyms

A REST API exchanges JSON messages over HTTP. The first occurrence of every
acronym — API, HTTP, JSON — is automatically replaced with `\acrshort{...}`,
without writing any `\gls{...}` by hand.

# Institutional acronyms

The UN coordinates international relief efforts; the WHO publishes its health
recommendations.

# Ungrouped acronym

A DOI uniquely identifies a scientific publication. With no group attached, it
is listed in the default acronym table.

# Mixing with the legacy syntax

The classic Markdown `*[KEY]: ...` syntax keeps working and merges with the
front-matter definitions.

NMR remains a cornerstone of modern molecular analysis.

*[NMR]: Nuclear Magnetic Resonance
