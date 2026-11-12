---
target: frontend/src/pages/index.astro
total_score: 29
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
target_fingerprint: "sha256:744f9c6f2b182b76135a1a2e39f91f5e6460b1a88d15f89a8a7bb179b8eb5369"
target_path: "C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
timestamp: 2026-11-12T10-26-13Z
slug: frontend-src-pages-index-astro
---
Method: dual-agent (A: Grok 4.7 high, "Crítica A: revisão de design" · B: Grok 4.7 medium, "Crítica B: detector e navegador"). Parent re-measured light-theme contrast and the hub select.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Hub value clipped in the select ("Hub Co…"); KPI labels slide under the sticky bar |
| 2 | Match System / Real World | 3 | Ciclo has no verdict word; unknown hub shown as "1 selecionado" |
| 3 | User Control and Freedom | 3 | Unknown hub id sticks as an empty recorte |
| 4 | Consistency and Standards | 3 | Mobile "Comandas · 4" vs rail "· 5" (agent comanda not counted) |
| 5 | Error Prevention | 2 | `hub=99999` accepted and zeroes the console |
| 6 | Recognition Rather Than Recall | 3 | Selected hub must be read from the chip, not the control |
| 7 | Flexibility and Efficiency | 3 | Sort headers have no `aria-sort`; no page jump in orders |
| 8 | Aesthetic and Minimalist Design | 3 | Filter row (9 controls) and 6-wide rail compete with the open comanda |
| 9 | Error Recovery | 3 | Invalid segment explained well; unknown hub diagnosed as "Nenhum pedido" |
| 10 | Help and Documentation | 3 | Glossary and footer rules exist; glossary targets are 18px tall |
| **Total** | | **29/40** | **Good** |

## Design Specificity Verdict

**LLM assessment**: authored for this product. The open comanda (perforation, Nº, severity by shape, inverted Ação block) and one recorte driving chips, URL, KPIs, agent header and answer are specific. The lower half (trend, heatmap, scatter, ranking, 12-column orders) is a competent category stack.

**Deterministic scan**: 4 findings, one rule (`border-accent-on-rounded`) at `filters/PeriodPresets.tsx:34,166` and `ui/Panel.tsx:275,288`. All false positives: bottom border on a top-only radius (sliding segment indicator). In-page scan: `cramped-padding` on the dataset pill in the header; `nested-cards` on the two table scrollers inside panels; page-level `gradient-text`, `bounce-easing` (cubic-bezier(0.34, 1.36, 0.64, 1)), `marquee` ("shimmer-band"); `flat-type-hierarchy` (body 13.6 / h2 16 / h3 18) appeared in one scan only.

**Measured**: no horizontal document scroll at 320/768/1280. 11 Tab stops before the first comanda, all 27 stops with a 2px outline. 0 unnamed buttons, heading outline without skips, landmarks present. Dark theme: 0 contrast failures (lowest 5.37 on the Ação block). Light theme: the sub-agent's failures were a mid-transition artifact after toggling in a hidden tab; on a fresh light load labels are #666 on #fff/#f5f5f5 and values #1a1a1a on #fff. Rail stubs Nº 02–06 sit at 4.55:1. At 320, 95 of 129 interactive elements are under 44×44, including 12×12 sort buttons and 18px-tall glossary terms.

**Visual overlays**: injection succeeded in the sub-agent's tab, but that tab is no longer listed, so no reliable user-visible overlay is available.

## Overall Impression

The first viewport does the job: one comanda, one action. The biggest opportunity is the filter bar, which cannot show the hub it just filtered by.

## What's Working

- The comanda is a real object, and focus returns correctly on collapse and on Esc from the agent.
- One recorte everywhere: hub 22 + March became chip, period segment, KPI comparison and the agent's scope line.
- KPI verdict line: "Crítico · 10,6 p.p. abaixo da rede · −2,9 p.p." answers "is it off?" without a chart.

## Priority Issues

- **[P1] Hub select cannot show the hub.** At 1280 the value span is 33px wide for a 109px name (re-measured by the parent); still clipped at 1440. The 352px agent ask control takes the room. Fix: drop the inner label when the value overflows, and collapse the ask control to "Agente" before a place name truncates. Command: /impeccable layout.
- **[P1] Unknown hub id treated as a real empty recorte.** `/?hub=99999` keeps a chip "ID 99999", "1 selecionado", and "Nenhum pedido neste recorte". Invalid segment already gets the right notice. Fix: drop ids absent from the hub list with the same notice. Command: /impeccable harden.
- **[P1] At 320 the recorte summary and the filter sheet hide the slice.** Summary span 46px for 204px of text; "Comandas · 4" disagrees with the rail's 5 (`MobileRecorte.tsx:22-23`); sheet footer covers Segmento and chips; date segment reads "01/…". Fix: summary full width, Comandas on its own line, pad the sheet scroll by the footer height. Command: /impeccable adapt. (Sub-agent observation; not re-measured by the parent.)
- **[P2] Stale agent comanda survives a recorte change.** On an empty range and on hub 99999 the only open comanda was "SLA 74,2% no Color Shopping", above the empty-state sentence. Fix: comandas whose scope differs from the URL leave the rail and stay in the agent log. Command: /impeccable harden.
- **[P2] Ciclo has no verdict.** Network card shows "hubs de 31,7 a 180,5 min" with no word; at 768 the delta ellipsizes to "+3,…". The task asks whether prep is off. Deliberate today (no target for the median). Fix: either a verdict from the slow-hub alert rule, or truncate the reference before the delta. Command: /impeccable clarify.

## Persona Red Flags

**Alex (power user)**: reads the hub from the chip because the select is clipped; sort works but is silent (`OrdersTable.tsx:360-366`); orders load 200 of 1.074 with no jump; "Aprofundando com o modelo…" after the action is already printed.

**Sam (keyboard + screen reader)**: skip links, outlines and Esc return all work; sort direction not exposed; hub control's accessible name is full while the visible text is clipped; full Tab traversal was computed, not driven with real key presses.

**Recruiter, 3 minutes**: the first screen works; the proving number (74,2% Crítico) is below the fold at 1280 and its label slides under the sticky bar; "API (Swagger)" in the header is a portfolio tell; scrolling on ends in a methodology footer.

## Minor Observations

- Ignore notice says the accepted segment is "good"; footer and product say "goods".
- 12×12 sort buttons in the ranking; glossary terms 18px tall; "API (Swagger)" 32px tall below lg.
- At 768 the agent FAB covers the ticket-médio footnote; "Ticket mé…" clipped.
- Export from the 320 sheet opens a second dialog over the sheet.
- Rail heading uses the stamp caps reserved in DESIGN.md for the comanda identity.
- `impeccable live-server --background` exited immediately on this machine.
- Glossary popover and Ctrl K were not confirmed with real input.

## Questions to Consider

- If the open comanda already names person, hub and hour, what else belongs in the first three minutes?
- Should a hub id that matches nothing be a filter, or a typo the console refuses?
- What would the ciclo card say if it had to use the same three words as SLA?
