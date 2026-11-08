---
name: Central de Operações
description: Comanda ops console — cool grey field, wine shell band, alerts as printed order tickets.
colors:
  field: "#ECECEC"
  surface: "#FFFFFF"
  sunken: "#F5F5F5"
  sunken-strong: "#E8E8E8"
  rule: "#DCDCDC"
  ink: "#1A1A1A"
  muted: "#666666"
  crit: "#D92B20"
  crit-deep: "#A51E16"
  crit-soft: "#FBE1DE"
  warn: "#946000"
  good: "#46700F"
  wine: "#3D0B1F"
  wine-raised: "#5A1730"
  on-wine: "#F1DBE3"
  series: "#7A1E3D"
  series-deep: "#4A0F25"
  series-soft: "#E7B3C4"
  shell-good: "#9BC75A"
  shell-crit: "#FF6A5E"
  shell-warn: "#F0A93B"
typography:
  title:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.4rem"
    fontWeight: 700
    lineHeight: 1.2
  figure-hero:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "2.6rem"
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: "-0.01em"
  figure:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.45rem"
    fontWeight: 700
    lineHeight: 1.05
  section:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
  body:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.9rem"
    fontWeight: 400
  cond-label:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 700
    letterSpacing: "0.04em"
rounded:
  tick: "4px"
  card: "8px"
spacing:
  gutter: "20px"
  page-x: "24px"
  ticket-x: "20px"
components:
  button-primary:
    backgroundColor: "{colors.crit}"
    textColor: "#FFFFFF"
    rounded: "{rounded.card}"
    padding: "6px 12px"
    typography: "{typography.label}"
  button-primary-hover:
    backgroundColor: "{colors.crit-deep}"
  button-ink:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
    rounded: "{rounded.card}"
    padding: "6px 12px"
  button-ghost:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "6px 12px"
  button-ghost-hover:
    backgroundColor: "{colors.sunken}"
  shell-band:
    backgroundColor: "{colors.wine}"
    textColor: "{colors.on-wine}"
    height: "64px"
  kpi-cell:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    padding: "14px 16px 12px"
    typography: "{typography.figure-hero}"
  ticket:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "20px 20px 16px"
  ticket-action:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
    rounded: "{rounded.card}"
    padding: "12px 14px"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "16px"
---

# Design System: Central de Operações

## Overview

**Creative North Star: "A comanda na fila"**

The console borrows the grammar of the delivery apps its operators already use every day: cool neutral greys, firm sans type, 8px corners, one red that means something. It adds a world of its own taken from the restaurant counter: the thermal **comanda** a store prints when an order arrives. Every alert in the current recorte is a comanda in a queue, numbered, tagged by category and severity, with the action printed at its foot. One comanda is open at a time; the rest wait, summarised.

The shell is a wine band, not red: it gives the product a recognisable colour field without borrowing any delivery brand's identity, and keeps red free to mean "critical". Data series are drawn in a wine ramp, so the charts belong to the same world as the shell.

**Key Characteristics:**
- Cool grey field (`field`) with white surfaces; layers separate by tone and hairline, never by shadow.
- Wine shell band on every theme; signals on the band use their own `shell-*` tokens.
- Archivo with a width axis: normal width for reading, condensed caps only for short labels and comanda headers.
- Tabular figures everywhere; headline numbers in a narrow bold cut (`figure`).
- Red (`crit`) reserved for critical severity and the one primary action in view.

## Colors

### Primary
- **Crit** `#D92B20` (dark `#FF5D50`): critical severity marks, worsening deltas, the primary action button. Hover `crit-deep`.

### Secondary
- **Wine** `#3D0B1F` (dark `#26060F`): the shell band. `wine-raised` for hover/active inside it, `on-wine` for its text.
- **Series** `#7A1E3D` (dark `#E0789A`): the data colour. Ordered ramps use `series-deep` → `series` → `series-soft`.

### Neutral
- **Field** `#ECECEC`, **Surface** `#FFFFFF`, **Sunken** `#F5F5F5` / `sunken-strong` `#E8E8E8`, **Rule** `#DCDCDC`, **Ink** `#1A1A1A`, **Muted** `#666666`. Dark theme mirrors them (`#111111`, `#1B1B1B`, `#232323`, `#353535`, `#F2F2F2`, `#A6A6A6`).
- **Warn** `#946000` and **Good** `#46700F` carry state only.

### Named Rules
**The One Red Rule.** Red marks what is critical or what the operator should press next. Active filters, selected tabs, focus rings and icons use ink, never red.

**The Wine Data Rule.** A chart series is wine unless it encodes state. Volume, heat and stage ramps are never red.

## Typography

One family, **Archivo** (Google Fonts, `wdth` 62–125, `wght` 400–800).

### Hierarchy
- **Title** 1.4rem/700 at 88% width: product name in the band.
- **Figure hero** 2.6rem/700 at 80% width: the three operation KPIs.
- **Figure** 1.45rem/700 at 80% width: volume KPIs inline with their label.
- **Section** 1rem/600: panel titles; ticket titles at 1.08rem/600.
- **Body** 0.95rem/400, 1.6 line height; **Label** 0.9rem muted.
- **Cond label** 0.78rem/700, uppercase, 72% width, 0.04em tracking: KPI labels, comanda headers, table headers, footer headings.

### Named Rules
**The One Body Rule.** Tables use one text size; header rank comes from condensed caps and weight, never from a bigger size.

**The Short Caps Rule.** Condensed caps only on labels of a few words. Sentences are never set condensed.

## Layout

Max width 1440px, 24px side padding (16px under `sm`), 20px gutters. Desktop first viewport: a two-column grid, KPIs and agent on the left, the comanda queue (340–440px) on the right spanning both rows. Under `lg` the order is KPIs → comandas → agent. Charts and tables follow full width or in pairs. Every grid track is `minmax(0, 1fr)` so truncated text never widens the page.

## Elevation & Depth

Flat. Depth comes from layer tone: open comanda is pure surface, queued comandas are surface at 70% over the field. The filter bar is the only sticky layer, at every width, separated by a hairline.

### Named Rules
**The No Shadow Rule.** No box-shadows anywhere, including tooltips and dialogs.

## Shapes

`tick` 4px for inner controls (segmented items, checkboxes, table frames); `card` 8px for panels, tiles, buttons and the comanda body. The comanda's top edge is a row of 5px half-holes (CSS mask), its header sits over a 1.5px dashed rule.

## Components

### Buttons
- **Primary** (`btn-primary`): crit fill, white text. One on the page: the open comanda's drill-down.
- **Ink** (`btn-ink`): ink fill; secondary commitments such as Exportar, the agent's Enviar, Filtrar estas lojas and the trend zoom.
- **Ghost** (`btn-ghost`): surface with rule border; everything else.

### Inputs / Fields
Filter selects are surface boxes with a small label over the value; an active filter gets an ink border. Selected options use an ink checkbox. From `lg` up, Período, Cidade, Hub and Loja stay visible; Segmento, Canal and Modal live in the "Mais filtros" popover, which floats over the page instead of pushing it down. Below `lg` the bar collapses to one recorte summary ("Recorte · N / Rio de Janeiro · Editar") that opens a bottom sheet with every control, plus a "Comandas · N / X críticas" shortcut to the queue. Every active value also shows as a removable chip.

Table outliers (No prazo abaixo do recorte, cancelamento acima, ciclo fora do SLA) are flagged by the backend and drawn in ink with weight and an arrow mark, never in red: red stays with the comandas.

### Navigation
The wine band holds product name, recorte summary, anchor links (Perguntar ao agente, API), API status dot and the theme toggle.

### Comanda (signature component)
The alert queue. Header: severity mark + `Nº 01 · CATEGORIA` in cond caps, severity word on the right in its state colour. Body: title, detail, then the **Ação** block in inverted ink. Footer: drill-down (primary) and Perguntar ao agente (ghost). Severity is a shape as well as a colour: filled dot (crítico), hollow ring (atenção), dash (observar). Motion: each new recorte reprints the queue, comandas unfolding top-down in order (40ms stagger, six steps max, 280ms each); opening one unfolds it over 280ms (`cubic-bezier(0.16, 1, 0.3, 1)`); collapsing folds it up in 160ms (`cubic-bezier(0.7, 0, 0.84, 0)`). All of it is skipped under reduced motion.

### Motion
Tokens live in `:root` (`--duration-*`, `--ease-*`, `--distance-*`, `--scale-*`, `--blur-*`, the transitions.dev scale); pick by usage, not by the nearest number. Closing is faster than opening, never delayed, and drops distance and blur. Only transform, opacity, filter and clip-path animate, and every motion has a reduced-motion path (instant or opacity only). The comanda reprint is the one authored moment; everything else is quiet and functional:
- Menus (MultiSelect, Mais filtros): open 250ms from scale 0.97, close 150ms to 0.99, `--ease-smooth-out`.
- Export dialog: open 250ms from scale 0.96, close 150ms; backdrop fades with it. Mobile recorte sheet: rises in 400ms, drops in 350ms.
- Segmented controls and the period presets: one indicator slides between options in 250ms.
- Values that change with the recorte (KPI figures, comanda counts) cross-fade only the changed digits, rising or falling with the value; never on first paint.
- Content replacing a skeleton fades in from a 2px blur over 400ms, once. Icon swaps (theme, copy link) cross-fade with blur in 250ms.
- The agent's wait is a shimmer over "Consultando o recorte…"; its answer rises 4px into place in 250ms.

### KPI grid
Three operation cells joined by 1px rule gaps, each with cond label, figure, delta, a daily trail drawn in ink from the recorte's own time series, and a muted footnote. Volume KPIs sit in one tile below, inline.

## Do's and Don'ts

### Do:
- Do keep every number tabular and every alert closed by an action.
- Do use the wine ramp for data and ink for neutral emphasis.
- Do encode severity by shape and colour together.

### Don't:
- Don't use red for selection, focus, filters or decorative icons.
- Don't put the comanda picket or condensed caps on anything that isn't an alert ticket or a short label.
- Don't add shadows, coloured side stripes on cards, or eyebrow labels above headings.
- Don't use any delivery company's wordmark, logo, brand red or proprietary typeface.
