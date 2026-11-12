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
  series-soft: "#C07D93"
  shell-good: "#9BC75A"
  shell-crit: "#FF6A5E"
  shell-warn: "#F0A93B"
typography:
  title:
    fontFamily: "Zilla Slab, ui-serif, Georgia, serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1
  figure-hero:
    fontFamily: "Zilla Slab, ui-serif, Georgia, serif"
    fontSize: "2.5rem"
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: "-0.01em"
  figure:
    fontFamily: "Zilla Slab, ui-serif, Georgia, serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.05
  section:
    fontFamily: "Libre Franklin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
  body:
    fontFamily: "Libre Franklin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Libre Franklin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.85rem"
    fontWeight: 600
  meta:
    fontFamily: "Libre Franklin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
  cond-label:
    fontFamily: "Zilla Slab, ui-serif, Georgia, serif"
    fontSize: "0.75rem"
    fontWeight: 700
    letterSpacing: "0.03em"
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
    padding: "14px 16px"
  ticket-stub:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "16px 16px 14px"
  evidence-tag:
    backgroundColor: "{colors.sunken}"
    textColor: "{colors.ink}"
    rounded: "{rounded.tick}"
    padding: "2px 8px"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "16px"
  agent-dock:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    width: "clamp(360px, 28vw, 420px)"
  agent-fab:
    backgroundColor: "{colors.wine}"
    textColor: "#FFFFFF"
    rounded: "{rounded.card}"
    height: "48px"
    padding: "0 16px"
    typography: "{typography.label}"
  ask-agent-button:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "4px 8px"
    typography: "{typography.label}"
  filter-bar:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    height: "80px"
  agent-ask-field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    height: "40px"
    padding: "0 12px"
    typography: "{typography.label}"
  share-menu:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    width: "20rem"
    padding: "6px"
---

# Design System: Central de Operações

## Overview

**Creative North Star: "A comanda na fila"**

The console borrows the grammar of the delivery apps its operators already use every day: cool neutral greys, firm sans type, 8px corners, one red that means something. It adds a world of its own taken from the restaurant counter: the thermal **comanda** a store prints when an order arrives. Every alert in the current recorte is a comanda hung on a rail, numbered, tagged by category and severity, with the action printed on it. One comanda is open at a time, in a wide band under the rail; the open one also marks its evidence on the KPI or chart that proves it.

The shell is a wine band, not red: it gives the product a recognisable colour field without borrowing any delivery brand's identity, and keeps red free to mean "critical". Data series are drawn in a wine ramp, so the charts belong to the same world as the shell.

**Key Characteristics:**
- Cool grey field (`field`) with white surfaces; layers separate by tone and hairline, never by shadow.
- Wine shell band on every theme; signals on the band use their own `shell-*` tokens.
- Libre Franklin for reading; Zilla Slab only as the stamp voice: caps for the comanda's identity (`Nº 01 · SLA`, the rail title, the evidence tag), headline figures and the product name.
- Tabular figures on numbers that align or change (figures, deltas, table cells), not on prose; headline numbers in Zilla Slab (`figure`).
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

Two families, both from Google Fonts. **Libre Franklin** (`wght` 400–700) sets all reading text, labels, controls and charts. **Zilla Slab** (500, 600, 700) is the stamp voice, used only on headline figures (`figure`), the comanda identity (`cond`) and the product name in the band (`font-slab`). Never on running text, labels or tables. `cond` keeps its name for compatibility; it now means the stamp voice (Zilla Slab caps), not a narrow cut.

### Scale
Six steps, as `@theme` tokens in `global.css`; no `text-[x.xxrem]` outside them: `text-meta` 0.75 · `text-aux` 0.85 · `text-body` 0.95 · `text-lead` 1.125 · `text-figure` 1.5 · `text-hero` 2.5rem. Panel titles use `text-base`.

### Hierarchy
- **Title** `text-figure`/700 in Zilla Slab, normal tracking: product name in the band.
- **Figure hero** `text-hero`/600 in Zilla Slab (`figure`): the three operation KPIs.
- **Figure** `text-figure`/600 in Zilla Slab (`figure`): volume KPIs inline with their label.
- **Section** 1rem/600: panel titles; ticket titles `text-lead`/600.
- **Body** `text-body`/400, 1.6 line height; **Label** `text-aux`/600, sentence case: KPI labels, table headers, "Ação", footer headings.
- **Cond** `text-meta`/700 in Zilla Slab, uppercase, 0.03em tracking, lining figures: comanda identity only.

### Weights
400 text · 500 controls only (buttons, tabs, chips, inputs) · 600 panel titles, labels and headline figures · 700 the product name and the cond comanda head.

### Named Rules
**The One Body Rule.** Tables use one text size; header rank comes from weight and colour, never from a bigger size.

**The Comanda Caps Rule.** Stamp-voice caps (`cond`, Zilla Slab) belong to the comanda's identity. A KPI, a table header or a footer heading is a label in sentence case; caps everywhere is the generic dashboard voice this world refuses.

## Layout

Max width 1440px, 24px side padding (16px under `sm`), 20px gutters. The page reads top-down at full width: comanda rail → KPIs → trend → stages | heatmap → stores → ranking → orders. The rail sits first because the action is the product; KPIs follow as the context the comandas cite. From `lg` the KPI block is two tracks (`minmax(0,3fr) minmax(15rem,1fr)`): the three operation heroes on the left, the three volume figures stacked in one column on the right at the same height. Charts and tables follow full width or in pairs. The agent is not a grid track: it is one fixed panel outside `main` (see Agent panel). Every grid track is `minmax(0, 1fr)` so truncated text never widens the page.

The ranking keeps its row filter in a sticky right column (24px button, 44px below `lg`), so the drill stays on screen while the table scrolls sideways. A rate or median the backend marks as small-sample (`low_sample`, `volume_low_sample`) prints muted with a dotted underline and sorts to the end of its column in both directions; the panel hint says so when such rows exist.

## Elevation & Depth

Flat. Depth comes from layer tone: the open comanda and its rail ticket are pure surface, the other rail tickets are surface at 60% over the field. The filter bar is the only sticky layer, at every width, separated by a hairline. The agent panel floats over the page only in its float mode (1024–1279px), outlined in ink instead of shadowed.

### Named Rules
**The No Shadow Rule.** No box-shadows anywhere, including tooltips and dialogs.

## Shapes

`tick` 4px for inner controls (segmented items, checkboxes, table frames); `card` 8px for panels, tiles, buttons and the comanda body. The comanda's top edge is a row of 5px half-holes (CSS mask), its header sits over a 1.5px dashed rule.

## Components

### Mark
The mark is "Carimbo Nº": the `Nº` drawn in one stroke inside a receipt whose bottom edge is perforated. It draws in `currentColor` on the wine band, beside the product name, and its favicon is `#F2E6EA` on a wine square (`#3D0B1F`, 6px corners). Keep it still: no animation, no pulse. Don't put it on a coloured rounded tile in the header, and don't bring back the radar or orbit mark.

### Buttons
- **Primary** (`btn-primary`): crit fill, white text. One on the page: the open comanda's drill-down.
- **Ink** (`btn-ink`): ink fill; secondary commitments such as the agent's Enviar, Filtrar estas lojas and the trend zoom.
- **Ghost** (`btn-ghost`): surface with rule border; everything else, including Mais filtros, Compartilhar, the mobile sheet's Exportar, each Perguntar and Nova conversa.
- **Wine FAB** (`agent-fab`): the only wine-filled button. It is the agent's opener below `lg`, in the thumb zone: a 48px square with the Bot icon only (the name lives in its accessible label), so it covers as little of the open comanda and the KPIs as possible. Its status dot sits in the top-right corner. It hides while the sheet is open.

### Filter bar
The desktop bar (`lg` and up) has two rows with separate jobs. Row 1 defines the recorte: its controls are 40px tall, with `card` corners and a 1px border. Row 2 shows the recorte itself and is 32px tall, growing only if the chips wrap. The bar is 80px in all: row 1, 8px, row 2. Controls in one group sit 8px apart, and groups sit 16px apart.
- **Período**: one segmented control, "Tudo | 30 dias | 7 dias | Datas", with one sliding indicator. **Datas**, its fourth segment, opens a popover with the same component and motion as Mais filtros, anchored left. The popover holds Início and Fim as two 40px fields, each opening the pt-BR calendar. Once a range is chosen, the segment shows it ("01/03 – 15/03", "desde 01/03", "até 15/03") and the indicator sits on it. In the mobile sheet, Datas expands the two fields inline below the control instead, at 44px each.
- **Cidade**, **Hub** and **Loja**: equal-width selects with the label inline and muted inside the box ("Cidade  Curitiba ▾"). An active select takes an ink border.
- **Mais filtros**: sized to its text, with the active count after it ("Mais filtros · 2"). It takes an ink border when any extra filter is active.
- After a 1px vertical rule at the right end of row 1: the agent's ask field (see Agent panel).
- **Row 2**: the chips of the active filters, or one line saying the recorte is complete when there are none; a quiet "Limpar recorte" text button; and, at the right, the ghost **Compartilhar ▾** menu. Its items are Copiar link, Pedidos em CSV, Copiar briefing (Markdown) and PDF da tela, each with a series-coloured icon and a one-line muted description. The copy actions confirm in place: the icon cross-fades to a check in `good`, the label changes, and the menu stays open.

Exportar is no longer on the desktop bar. The Export dialog opens only from the mobile sheet's footer, and CSV is in Compartilhar.

### Inputs / Fields
Filter selects are 40px surface boxes (44px below `lg`) with the label inline and muted before the value; an active filter gets an ink border. Selected options use an ink checkbox. From `lg` up, Período, Cidade, Hub and Loja stay visible; Segmento, Canal and Modal live in the "Mais filtros" popover, which floats over the page instead of pushing it down. Below `lg` the bar collapses to one recorte summary ("Recorte · N / Rio de Janeiro · Editar") that opens a bottom sheet with every control (Período and Lugar open; Segmento, Canal and Modal folded under "Pedido", which opens by itself when one of them is in use), plus a "Comandas · N / X críticas" shortcut to the queue. Every active value also shows as a removable chip.

No native dropdown or calendar ships: their open state is the operating system's, with square corners and no tokens. Single choices (Quebrar por) use `Select`, dates use `DatePicker`; both open the same floating panel as the filter menus (`card` corners, rule border, surface, no shadow, same open/close motion). The calendar is pt-BR (dd/mm/aaaa, week from Sunday), day cells are `tick`, the chosen day is ink and the rest of the range a sunken tint. Below `lg` it opens in flow instead of floating, so the bottom sheet never clips it.

Table outliers (No prazo abaixo do recorte, cancelamento acima, ciclo fora do SLA) are flagged by the backend and drawn in ink with weight and an arrow mark, never in red: red stays with the comandas.

### Navigation
The wine band holds product name, subtitle, the API (Swagger) link, API status dot and the theme toggle. The agent does not live here: it opens from the filter bar, the mobile FAB or Ctrl K. Below `sm` the band is one 56px row: name, status dot (label kept for screen readers) and theme toggle; subtitle and API link hide. Below `lg` every control in the page is at least 44px tall.

### Comanda (signature component)
The alert rail. **Rail tickets** hang side by side (`auto-cols minmax(12rem,1fr)`, 15rem under `sm`), scrolling sideways with snap when they don't fit: severity mark + `Nº 01 · CATEGORIA` in cond caps, then the title in two lines. A chevron at the right of the head says the ticket opens; it flips (`scaleY(-1)`, `--duration-fast`, symmetric) while its comanda is open. The severity word is left to the open band; on the rail the mark carries it. An ink bar under the rail marks the open ticket and slides between tickets (`--duration-fast`, `--ease-smooth-out`, symmetric like tabs); it fades out on collapse. When tickets are cut off at the right edge, the queue header shows "mais N" (ink, underlined, chevron), which scrolls the rail one page; it disappears when nothing is hidden ahead. Once the rail has scrolled, "voltar" (same style, chevron left) sits before it and scrolls one page back. Below `lg` the body of the open band (not its head row) keeps a 56px gutter on the right, so the agent's floating button never covers the Ação block or the comanda text. Hovering (or focusing) a closed ticket previews that lane with a `rule` bar, lifts the paper to full `surface` and the title and chevron to full ink (`--duration-quick`). Clicking the open ticket again collapses it.
The **open band** is a full-width comanda under the rail, never a popover: header with severity word and Recolher, then two columns from `lg` — title, detail and the actions (drill-down primary, Ver no gráfico and Perguntar ao agente ghost) on the left, the **Ação** block in inverted ink on the right. Under `lg` the Ação block comes first. Severity is a shape as well as a colour: filled dot (crítico), hollow ring (atenção), dash (observar). Printed, every rail ticket carries its action.
Motion: each new recorte reprints the rail, tickets unfolding in order (40ms stagger, six steps max, 280ms each) and the band last; switching comanda reprints the band (280ms, `cubic-bezier(0.16, 1, 0.3, 1)`). Opening from collapsed and collapsing animate the band's height as an accordion (`grid-template-rows: 0fr ↔ 1fr`, `--duration-fast`, `--ease-smooth-out`, symmetric, with a fade and `--blur-small` on the content), so the KPIs below glide instead of jumping. All of it is skipped under reduced motion.

### Evidence mark
Each alert names its evidence (backend `Evidence`: a KPI card, the stages chart by hub, the heatmap by hours, the store scatter by store or hub). While the comanda is open, that view marks it without touching the recorte: a KPI card gets a 2px inset ink outline; charts keep the evidence at full strength and drop everything else to ~20–30% opacity, with axis labels of the evidence in bold ink; the heatmap and scatter switch to the alert's metric. The view also shows a tag — severity mark + `Comanda Nº 02` in cond caps + the title, on sunken — that enters with `--duration-fast` and `--distance-micro`. Ver no gráfico scrolls to the chart's anchor in the static shell (the islands hydrate on view) and corrects the landing once scrolling ends.

### Agent panel
One panel node (`#agente`, `AgentDock`) holds the conversation at every width. It is the same node across modes, so a question in progress survives a resize. The mode follows the viewport:
- **Dock** (≥ 1280px): fixed right column, `clamp(360px, 28vw, 420px)` wide. The page gets right padding equal to the column, so nothing is covered. Only a 1px rule separates them.
- **Float** (1024–1279px): non-modal panel under the sticky filter bar, top-right, with a 1px ink border. The page stays scrollable and clickable.
- **Sheet** (< 1024px): full-screen modal. The rest of the page is inert and does not scroll.

Openers. Every opener prefills the question and never sends it; the operator reviews and presses Enviar.
- **Agent ask field** (`AgentAskButton`) at the right end of the filter bar's first row, after a 1px rule, from `xl` up. Between `lg` and `xl` the first row has no room for it: it moves to the right end of the second row, after Compartilhar, at 32px ("Agente" + shortcut), and the bar stays two rows (80px). It is styled like a question field: wine (`series`) border, Bot icon, "Pergunte sobre este recorte…" in muted text and a `Ctrl K` / `⌘K` hint. Clicking it or pressing the shortcut toggles the panel. Typing a character while it is focused opens the panel with that character already in the input. Where the bar is narrower than 72rem (dock open, or windows under about 1200px) it shrinks to "Agente" and drops the hint. With the panel open it reads "Conversa aberta" and is filled `sunken`. Its status dot sits inside it. The shortcut works from anywhere and is ignored while another dialog is open.
- **Perguntar** (`AskAgentButton`, ghost) as the last action of each chart and table panel, and in each comanda's footer beside the drill-down.
- **Wine FAB** on mobile (see Buttons).

Status sits on the opener as an 8px dot in series wine. It pulses while the agent consults the recorte and stays solid when an answer arrives with the panel closed. It is never red: red stays for critical and the primary action.

The header names the panel and shows the live recorte as removable chips, because filters can change mid-conversation. The "recorte mudou" divider in the log stays. The conversation persists across open and close and in the tab's sessionStorage (last 40 messages). Esc closes the panel and returns focus to the opener.

### Motion
Tokens live in `:root` (`--duration-*`, `--ease-*`, `--distance-*`, `--scale-*`, `--blur-*`, the transitions.dev scale); pick by usage, not by the nearest number. Closing is faster than opening, never delayed, and drops distance and blur. Only transform, opacity, filter and clip-path animate, and every motion has a reduced-motion path (instant or opacity only). The comanda reprint is the one authored moment; everything else is quiet and functional:
- Menus (MultiSelect, Mais filtros, Datas, Compartilhar): open 250ms from scale 0.97, close 150ms to 0.99, `--ease-smooth-out`. The popovers scale from their trigger's corner: top right for Mais filtros and Compartilhar, top left for Datas.
- Agent panel: dock reveals from 12px right with opacity (no blur: a full-height column would repaint too much), 400ms open, 350ms close. Float opens like Mais filtros, from 0.97 over 250ms, and closes to 0.99 over 150ms. Sheet rises in 400ms and drops in 350ms. The opener's status dot pops in over 500ms on `--ease-bounce` (entrances only) and pulses linearly while the agent consults.
- Export dialog: open 250ms from scale 0.96, close 150ms; backdrop fades with it. Mobile recorte sheet: rises in 400ms, drops in 350ms.
- Segmented controls and the period presets: one indicator slides between options in 250ms, and on the period control it also slides onto Datas once a range is chosen.
- Values that change with the recorte (KPI figures, comanda counts) cross-fade only the changed digits, rising or falling with the value; never on first paint.
- Content replacing a skeleton fades in from a 2px blur over 400ms, once. Icon swaps (theme, copy link) cross-fade with blur in 250ms.
- The agent's wait is a shimmer over "Consultando o recorte…"; its answer rises 4px into place in 250ms.

### KPI grid
Three operation cells joined by 1px rule gaps, each with a sentence-case label, figure, one status line, a daily trail in series wine, and a muted footnote that wraps, never truncates. The status line leads with the verdict (Dentro, Atenção, Crítico — dash in `good`, hollow ring in `warn`, filled dot in `crit`) and the reference, then the previous-period delta when it exists. Nothing in it truncates: the part that does not fit beside the rest drops whole to a second line. A hairline marks the network value on the trail only when that value already sits inside the series scale. When the backend flags the measured base as small (`low_sample`), SLA and ciclo keep their figure and swap the status line for a `warn` note ("base: 20 entregas · amostra pequena"). Volume KPIs sit in one tile below, inline, and swap their delta for "amostra pequena" when either period has fewer than 100 orders.

## Do's and Don'ts

### Do:
- Do keep every aligned or changing number tabular and every alert closed by an action.
- Do use the wine ramp for data and ink for neutral emphasis.
- Do encode severity by shape and colour together.
- Do prefill the agent's question from a chart or comanda and leave sending to the operator.

### Don't:
- Don't use red for selection, focus, filters or decorative icons.
- Don't put the comanda's perforated edge or stamp-voice caps on anything that isn't the comanda itself.
- Don't set running text, labels or tables in Zilla Slab, and don't bring back a condensed cut: Libre Franklin has one width.
- Don't add shadows, coloured side stripes on cards, or eyebrow labels above headings.
- Don't use any delivery company's wordmark, logo, brand red or proprietary typeface.
- Don't put the agent panel back in the grid, or give its float mode a shadow.
