# Formal Letter

This template provides a unified structure to write letters for different coutries and languages. It exclusively relies on the KOMA-Script `scrlttr2` class and loads the appropriate national layout so the output complies with SN 010130 (Switzerland) or DIN 5008 (Germany). Invoke it through the CLI with `--template letter`. The supported versions are:

- English (UK)
- English (US)
- French (France or Switzerland via `fr-CH`)

## Attributes

- `cursive` (boolean): If true, the letter will be written in a cursive font style (modernline).
- `language` (string): Specifies the language of the letter. Supported values are `en-UK`, `en-US`, `fr-FR`, or `fr-CH`. Default is `en-UK`.
- `standard` (string): Selects the letter layout. Use `din`/`din5008` for DIN 5008 and `sn`, `sn-left`, or `sn-right` for SN 010130. Defaults to DIN for English locales and SN 010130 for French locales.
- `date` (string): The date to be displayed on the letter. If not provided, the current date will be used.
- `object` (string): The subject of the letter.
- `opening` (string): Optional override for the salutation inserted via `\opening{}`. If not provided, the Markdown document title (`# Heading`) is injected automatically.
- `closing` (string): Optional override for the closing formula inserted via `\closing{}`. Defaults to a locale-appropriate sentence (e.g. “Yours faithfully” for UK English).
- `signature` (string): Optional override for the signature block (defaults to the sender name). When `cursive` is enabled the Modernline font is used automatically.
- `fold_marks` (boolean): Enables the fold guide marks on the page header/edges. Defaults to `false`.
- `from` (object):
  - `name` (string): The name of the sender.
  - `address` (string): The address of the sender.
  - `city` (string): Optional location displayed next to the date (used as `\lieu{}` for French letters).
- `to` (object):
  - `name` (string): The name of the recipient.
  - `address` (string): The address of the recipient.

## Example Usage

```md
---
press:
  template: letter
  cursive: true
  language: fr-CH
  standard: sn
  date: 1928-12-23
  object: Invitation souper de Noël
  from:
    name: Madame Marie-Henriette Dupont
    address: 12, rue des Fleurs, 1204 Genève
    city: Genève
  to:
    name: Monsieur Jean-Marc Martin
    address:
      - 45, avenue des Champs
      - 75008 Paris
      - France
---
Mon très cher Monsieur Martin,

Il est des soirs où la solitude s’avance comme un spectre silencieux, effleurant les murailles de la demeure et glissant, perfide, jusqu’au cœur. Noël, jadis si empli de rires enfantins et de clameurs joyeuses, s’annonce cette année sous un voile de mélancolie. Mes enfants, ces oiseaux migrateurs, se sont envolés vers d’autres cieux ; et le deuil encore noir de mon cher défunt ne cesse de teinter mes jours d’une ombre discrète.

Aussi, permettez, cher Monsieur, qu’une audace presque inconsidérée me dicte ces lignes. Je me suis dit que peut-être -- par un bienveillant caprice du destin -- vous consentiriez à troubler ma solitude en acceptant de partager avec moi le souper de la Nativité.

Je me chargerai, de mes mains mêmes, de préparer un humble festin champêtre : une dinde dodue, élevée au jardin et répondant, avec une ingénuité touchante, au doux nom de Poulette. Elle sera escortée de quelques ortolans, mets délicat s’il en est, que j’aurai accommodés selon une recette d’antan dont j’ai gardé le secret.

Je n’ose espérer que la chaleur de mon foyer puisse égaler celle de votre esprit, ni que le parfum du vin chaud rivalise avec celui de votre présence. Mais si le cœur vous en dit, venez donc, cher ami ; et que la neige, complice de cette invitation, vous guide jusqu’à ma porte.
```
