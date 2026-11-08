---
name: Central de Operações
description: Warm paper ops console — porcelain field, kraft slips, burnt-chili signal.
colors:
  burnt-chili: "#C2410C"
  chili-deep: "#7C2D12"
  warm-porcelain: "#FFFBF7"
  kraft-wash: "#F3EBE3"
  sand-rule: "#E7D8C9"
  stone-ink: "#1C1917"
  warm-stone: "#78716C"
typography:
  headline:
    fontFamily: "Source Sans Pro, sans-serif"
    fontSize: "1.55rem"
    fontWeight: 700
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Source Sans Pro, sans-serif"
    fontSize: "15px"
    fontWeight: 600
  body:
    fontFamily: "Source Sans Pro, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
  label:
    fontFamily: "Source Sans Pro, sans-serif"
    fontSize: "0.92rem"
    fontWeight: 400
rounded:
  clip: "2px"
  fold: "6px"
spacing:
  sm: "16px"
  md: "0.9rem"
  lg: "1.4rem"
  xl: "3rem"
components:
  metric-card:
    backgroundColor: "{colors.kraft-wash}"
    textColor: "{colors.stone-ink}"
    rounded: "{rounded.clip}"
    padding: "0.7rem 0.9rem"
  button-primary:
    backgroundColor: "{colors.burnt-chili}"
    textColor: "{colors.warm-porcelain}"
    rounded: "{rounded.fold}"
    typography: "{typography.label}"
  button-primary-hover:
    backgroundColor: "{colors.chili-deep}"
    textColor: "{colors.warm-porcelain}"
  button-ghost:
    backgroundColor: "{colors.kraft-wash}"
    textColor: "{colors.stone-ink}"
    rounded: "{rounded.fold}"
    typography: "{typography.label}"
  hint:
    textColor: "{colors.warm-stone}"
    typography: "{typography.label}"
  chart-plot:
    backgroundColor: "{colors.warm-porcelain}"
    textColor: "{colors.stone-ink}"
---

# Design System: Central de Operações

> **Implementação atual (v2):** os tokens abaixo vivem em `frontend/src/styles/global.css` como variáveis CSS mapeadas para o Tailwind (`bg-paper`, `bg-kraft`, `border-rule`, `text-ink`, `text-muted`, `text-chili`…), com um tema escuro equivalente (`[data-theme="dark"]`). Gráficos são ECharts e leem os mesmos tokens. Menções a Streamlit e Plotly neste documento descrevem a v1 e valem como intenção visual: trocar "Plotly" por "ECharts", "sidebar" por "barra de recorte" e `st.dialog` pela seção do agente.

## Overview

**Creative North Star: "The Praça Briefing Desk"**

This is a paper ops desk at a Brazilian praça, not a marketing kitchen and not a SaaS command center. The field is warm porcelain; the sidebar and KPI slips are kraft wash; the only loud mark is burnt chili, used like a stamp on a briefing — a left rail, a heat scale, a primary action — never a page fill. Numbers, recorte, and the next action sit closer to the visitor than any chrome.

The mood is dry, quiet, and dense enough to scan in two minutes. Hierarchy is size and ink weight, not color noise. Charts sit on the same porcelain as the page, with sand rules instead of grid theater. Depth is tonal: porcelain against kraft, a 1px sand rule, a 3px chili rail. No drop shadows. Confirmed refusals: neon SaaS dashboards, glassmorphism, purple AI-agent chrome, iFood red/magenta or official identity, food-stock photography as decoration, emojis, display serifs, and pill-shaped controls.

**Key Characteristics:**

- Porcelain canvas, kraft slips, sand rules — paper, not glass
- Burnt chili as the sole signal color (stamp, heat, primary action)
- Flat by default: no shadows; depth is layered stock
- One sans (Source Sans Pro); size does the hierarchy
- Clipped, clerical components; paper-fold corners (6px) on new chrome
- Independent of iFood wordmark, logo, and official visual identity

## Colors

Warm paper neutrals carry the field. Burnt chili is the only chromatic voice; darker chili and stone inks exist to grade heat and series, not to add a second brand color.

### Primary

- **Burnt Chili** (`burnt-chili`): Streamlit `primaryColor`, KPI left rail, GMV line, ranking/rating/cancel bars, and the hot end of heat scales. Use it when something must be *acted on* or *is the series that matters*. It is a stamp, not a fill.

### Secondary

- **Chili Deep** (`chili-deep`): Dark stop on the volume heatmap and the deep end of the Plotly colorway. Use it to intensify chili, never as a second accent family.

### Neutral

- **Warm Porcelain** (`warm-porcelain`): Page background and Plotly `plot_bgcolor`. The briefing sheet.
- **Kraft Wash** (`kraft-wash`): Sidebar and KPI card fill (`secondaryBackgroundColor`). Recorte rail and metric slips.
- **Sand Rule** (`sand-rule`): KPI hairline, chart grid and axis line, “pedidos” bars under a chili GMV line. Rules and quiet series, not text.
- **Stone Ink** (`stone-ink`): Body text, chart titles, metric values (`textColor`).
- **Warm Stone** (`warm-stone`): Metric labels, recorte hint, axis ticks, empty-chart annotation. Secondary copy only.

Plotly categorical colorway (not separate brand roles): Burnt Chili, `#9A3412`, `#B45309`, `#A16207`, `#44403C`, `#57534E`, `#D97706`, Chili Deep, `#CA8A04`, `#292524`. Heatmap continuous: Porcelain → `#FDBA74` → Burnt Chili → Chili Deep. Delivery-time continuous: `#FED7AA` → Burnt Chili.

**The One Chili Rule.** Burnt chili is the only loud color. It marks signal (rail, heat, primary action, the series that matters). Porcelain and kraft carry the field. Do not introduce a second accent family (teal, purple, iFood magenta, electric orange).

## Typography

**Display Font:** none — this system has no display face
**Body Font:** Source Sans Pro (with sans-serif), Streamlit `font = "sans serif"`
**Label/Mono Font:** same sans; no decorative mono

**Character:** One clerical sans. Tight headline tracking, muted labels, no serif contrast, no type as ornament. The pairing is a briefing, not a magazine.

### Hierarchy

- **Headline** (700, 1.55rem, letter-spacing -0.02em): Page title only (`h1` “Central de Operações”).
- **Title** (600, 15px): Plotly chart titles, left-aligned, Stone Ink. Streamlit subheaders (Alertas, Visão do recorte, Agente) sit in this band.
- **Body** (400, 1rem): Captions, alert copy, chat. Comfortable Streamlit default; do not drop body below this on the main stage.
- **Label** (400, 0.92rem): Recorte hint, metric labels, suggested-prompt buttons. Warm Stone when the label is supporting.

Chart body type is 12px Stone Ink with Warm Stone ticks — a Plotly-only step under Label, not a second UI font.

**The Briefing Type Rule.** One sans. Hierarchy is size and weight, never a second family. No display serif, no uppercase tracking as decoration, no mono except real data/code (which this product does not surface in the UI).

## Layout

Wide Streamlit canvas, sidebar expanded. The main `.block-container` caps at 1400px, with 1.4rem top padding and 5rem bottom padding (room for the Agente FAB). The Recorte sidebar is the left rail; the stage reading order is title → recorte chips (with Limpar) → alerts → hero KPI trio (tempo, nota, cancelamento) → volume trio (pedidos, GMV, ticket) → three tabs (Tendência 1.35/1, Ranking 1.2/1 with piores notas leading GMV, Operação three equal columns). The agent is a chili stamp FAB, bottom-right, opening an `st.dialog` (not an in-page column). Chart default height is 360px (ranking 420px); Plotly margins 16/16/48/16. Density is operate-mode: scan, don’t stroll. Empty recorte stops the stage after the warning and the Limpar exit — do not leave a hollow chart grid. The FAB remains available.

**The Recorte Rail Rule.** Sidebar is Kraft Wash; the main stage is Warm Porcelain. Do not invert, do not paint the whole app chili. Keep six KPI slips: a hero row of three operational stamps, then a volume row of three. Do not collapse them into a dense table unless the recorte itself is empty.

## Elevation & Depth

No drop shadows. Depth is stacked paper: porcelain field, kraft slips, a 1px sand rule, a 3px chili rail on KPIs. Plotly paper is transparent so charts sit on the page stock; the plot area is porcelain. Hover labels are white sheets, not lifted cards. Streamlit alerts (error / warning / success) are framework banners — they are semantic, not extra elevation.

**The Flat-By-Default Rule.** Surfaces are flat at rest and at hover. Never add ambient card shadows, glass blur, or a floating toolbar. If a control needs emphasis, use chili or a sand rule, not lift.

## Shapes

Form language is paper, not pills. Incumbent KPI chrome is clipped at 2px (`rounded.clip`) with a 1px sand border and a 3px chili left rail. New custom chrome uses a paper fold of 6px (`rounded.fold`) — the intended 4–6px step. Do not go to full Streamlit pills or iOS continuous corners. Charts are unrounded plot rectangles. Chili appears as a straight rail or a heat stop, never as a circular badge.

**The Paper Fold Rule.** Custom corners are 6px (paper fold) or 2px (legacy clip on KPI slips). Never pills, never 16px+ “card” rounding, never circular avatars as decoration.

## Components

Clipped and clerical: paper forms, chili as a left stamp, widgets that look like a briefing desk rather than a product site.

### Buttons

- **Shape:** Paper fold (6px). Not pills.
- **Primary:** Burnt Chili fill, Warm Porcelain text. Streamlit `primaryColor`. Hover darkens to Chili Deep.
- **Hover / Focus:** Darken chili; focus-visible is a 2px chili outline offset 2px, no glow.
- **Ghost / suggested prompts:** Kraft Wash fill, Stone Ink text, optional 1px Sand Rule. Full-width in their column. “Nova conversa” is this treatment, not primary.

### Cards / Containers

- **Corner Style:** 2px clip on KPI slips (incumbent); 6px fold on any new custom card
- **Background:** Kraft Wash for slips and sidebar; Warm Porcelain for the stage
- **Shadow Strategy:** none (see Elevation)
- **Border:** 1px Sand Rule; KPI slips add a 3px Burnt Chili left rail
- **Internal Padding:** 0.7rem 0.9rem on KPI slips

### Inputs / Fields

- **Style:** Streamlit native on Kraft Wash sidebar. Do not restyle into dark glass or heavy outlines.
- **Focus:** Framework focus; if customized, chili outline, not a glow ring.
- **Error / Disabled:** Empty recorte is a warning banner that stops the stage — not a red input border theater.

### Navigation

- Sidebar **Recorte** is the only nav: header + caption, then period / city / cuisine / restaurant / customer type / status. Tabs (Tendência, Ranking, Operação) are in-page, with chili as the active indicator via Streamlit primary. No top marketing bar.

### KPI slip (signature)

Kraft wash tile, 2px clip, 1px sand border, 3px chili left rail. Label in Warm Stone; value in Stone Ink. Six in a row. This is the product’s stamp — do not replace with gradient tiles, icons, or sparkline wallpaper.

### Chart frame (signature)

Transparent paper, porcelain plot, 15px left-aligned Stone Ink title, sand grid on Y only, Warm Stone ticks, chili (or the chili–stone colorway) for data. Mode bar off. Empty state is centered Warm Stone copy: “Sem dados no recorte.”

### Alerts

Streamlit semantic banners (`st.error` / `st.warning` / `st.success`), not custom chili cards. Title + detail + “Ação:” on one briefing block. Do not restyle them into toast stacks or icon tiles.

## Do's and Don'ts

### Do:

- **Do** keep Warm Porcelain as the stage and Kraft Wash as the Recorte rail and KPI slips.
- **Do** use Burnt Chili as a stamp: 3px left rail, heat stop, primary action, the series that matters.
- **Do** set Plotly paper transparent, plot porcelain, Y-grid sand, titles 15px Stone Ink, mode bar off.
- **Do** cap the stage at 1400px and keep six KPI slips: operação (tempo, nota, cancelamento) then volume.
- **Do** keep one sans (Source Sans Pro) and let size/weight rank the briefing.

### Don't:

- **Don't** use iFood red/magenta, wordmark, logo, or official visual identity.
- **Don't** add drop shadows, glassmorphism, neon SaaS chrome, or purple AI-agent styling.
- **Don't** fill backgrounds with chili or introduce a second accent family.
- **Don't** add a display serif, decorative mono, emojis, or food-stock photography as decoration.
- **Don't** pill-shape controls or round past the paper fold (6px) / clip (2px).
- **Don't** invent lift on hover to “make it feel premium.” Flat is the doctrine.
