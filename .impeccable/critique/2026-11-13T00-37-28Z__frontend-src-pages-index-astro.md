---
target: frontend/src/pages/index.astro
total_score: 28
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
target_fingerprint: "sha256:15815488a4ff7d87418519de223da17e5752c5d51896869c147799ff4a1c0924"
target_path: "C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
timestamp: 2026-11-13T00-37-28Z
slug: frontend-src-pages-index-astro
---
Method: dual-agent (A: ba493439192e4eeab010fe819e9184ee · B: 01e2ace4015dd6c3979b65e0eeb87f89)

### Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Strong API wake banner, `isPlaceholderData` dimming, live regions, and agent activity dot; however, `AgentAskButton` still reads `"Agente"` instead of `"Conversa aberta"` when docked at `1440px` (`AgentLauncher.tsx:78-81`), and `AgentChat` tucks LLM-upgrade progress under tall cards. |
| 2 | Match System / Real World | 3 | Fluent pt-BR ops briefing voice and physical comanda metaphor; minor gap where `OrdersTable` marks delayed rows with `↑` (`OrdersTable.tsx:66-71`) without a visible legend in the panel hint, and drilldown copy shifts from `"expedição"` (network-relative) to `"trânsito"` (stage median). |
| 3 | User Control and Freedom | 3 | Clear `Limpar recorte`, removable chips, `Nova conversa` + `"Desfazer"`, `Esc` stacking, and browser history sync; however, `Status` (`Concluído`/`Cancelado`) can only be toggled from `OrdersTable`'s column popover (`y ≈ 2764px`) or cleared via chips, and `TrendChart` zoom has no one-click undo. |
| 4 | Consistency and Standards | 2 | `AgentAskButton` shifts rows and shrinks (`40px → 32px`) when `AgentDock` opens at `1440px`; `AgentOpenBand` breaks the One Red Rule with `btn-primary`; `.ticket` perforated mask bleeds onto the empty state (`AlertsPanel.tsx:677`) and inside chat cards (`AgentComanda.tsx:48`); desktop `AgentChat` buttons (`25–28px`) and `BreakdownTable` row filters (`24px` without `.hit-target`) break sizing rules. |
| 5 | Error Prevention | 3 | Strong `DatePicker` bounds, `Cidade → Hub → Loja` cascade clearing, URL param validation (`IgnoredNotice`), and `>50k` CSV guard (now disabled in both `ExportDialog` and `ShareMenu`); however, `OrdersTable` header popovers (`ColumnFilterPopover`) look local to the table while silently mutating the global recorte. |
| 6 | Recognition Rather Than Recall | 2 | Active chips, shape+color severity, inline `MultiSelect` labels, and `EvidenceTag` work well, but global `Status` filtering is buried at the bottom inside `OrdersTable`, `<Term>` (`GMV`, `Subsídio`) uses the exact same `decoration-dotted` underline as non-interactive `Thin` small-sample values (`BreakdownTable.tsx:95`), and `StoreScatter` brush relies on a small icon without a text cue. |
| 7 | Flexibility and Efficiency | 3 | `Ctrl K`/`⌘K`, type-to-launch on `AgentAskButton`, roving tabindex across rail/presets/calendar, searchable `MultiSelect`, and `ChartAccess` on `StagesChart`/`StoreScatter`; however, `HeatmapChart` and `TrendChart` lack `<ChartAccess>` keyboard summaries, and `StoreScatter` brush is pointer-only. |
| 8 | Aesthetic and Minimalist Design | 3 | Crisp no-shadow surfaces (`0` box-shadows), disciplined wine/neutral hierarchy, and clear layout; crowded inside `AgentDock` (`403px`) where `AgentChatComanda` dumps a ~750px perforated card listing all 6 rail alerts, and in `OrdersTable` (`12` columns, `1325px` wide, `5` header popovers). |
| 9 | Error Recovery | 3 | Clear waking vs error states with collapsible details and `outsideBaseNote` filter recovery hints; misses an inline retry banner in `OrdersTable` if `fetchNextPage` fails mid-scroll and a retry action when LLM enhancement fails in `AgentChat`. |
| 10 | Help and Documentation | 3 | Strong methodology footer (`index.astro:123-146`), inline SLA note (`KpiStrip.tsx`), panel `hint`s, and `<Term>` tooltips; misses an inline legend for `OrdersTable` `↑` SLA flags and desktop hover/focus parity on `<Term>`. |
| **Total** | | **28/40** | **Good** (authored ops identity and responsive solidity held back by `AgentDock`/toolbar spatial jump, global-vs-local filter leakage, and accessibility/spec parity gaps) |

---

### Design Specificity Verdict

**LLM assessment:** Authored for this product, not category-interchangeable. The **"A comanda na fila"** concept gives an Operate console real operational voice: alerts hang on a horizontal rail (`AlertsPanel.tsx`), expand one at a time as thermal-receipt comandas with a CSS-masked perforated top edge (`.ticket`), dashed rule, tri-modal severity encoding (shape + color + word), an inverted `Ação` block, and one critical red CTA (`#D92B20`). Meanwhile, the `#3D0B1F` wine shell band and `#7A1E3D` wine data ramp keep the interface unmistakably non-branded and hold red strictly for critical severity/action. Remaining tensions: `.impeccable/surfaces/frontend-src-pages-index-astro.md` still specifies the retired 2-column first viewport (`Archivo`, `#EFEFEF`, `framboesa/oliva-lima`), `.ticket` leaks into the healthy/empty state and chat log, and `AgentOpenBand` uses `btn-primary` red despite its own file comment forbidding red on agent tickets.

**Deterministic scan:** `impeccable detect --json frontend/src` returned **6 findings** (`5 warning`, `1 advisory`, `0 error`):
- **4 × `border-accent-on-rounded` (false positives):** [`PeriodPresets.tsx#L34`](file:///C:/Projects/dashboard-insight/frontend/src/components/filters/PeriodPresets.tsx#L34), [`PeriodPresets.tsx#L166`](file:///C:/Projects/dashboard-insight/frontend/src/components/filters/PeriodPresets.tsx#L166), [`Panel.tsx#L275`](file:///C:/Projects/dashboard-insight/frontend/src/components/ui/Panel.tsx#L275), [`Panel.tsx#L288`](file:///C:/Projects/dashboard-insight/frontend/src/components/ui/Panel.tsx#L288) (`border-b-2` with flat bottom / `rounded-t-[4px]` on segmented tab indicators).
- **1 × `gradient-text` (false positive):** [`motion-content.css#L110`](file:///C:/Projects/dashboard-insight/frontend/src/styles/motion-content.css#L110) (`@utility shimmer-text` animated loading band for `"Consultando o recorte…"` / `"Carregando agente…"` with `prefers-reduced-motion` guard).
- **1 × `bounce-easing` (true positive advisory, intentional):** [`global.css#L61`](file:///C:/Projects/dashboard-insight/frontend/src/styles/global.css#L61) (`--ease-bounce: cubic-bezier(0.34, 1.36, 0.64, 1)` used exclusively on `.agent-dot` entry pop in [`motion-agent.css#L136`](file:///C:/Projects/dashboard-insight/frontend/src/styles/motion-agent.css#L136)).

**Visual overlays:** Preflight DOM/script injection succeeded on `http://localhost:4321/`, but `impeccable live-server --background` failed to keep `localhost:8400` listening on Windows (`TypeError: Failed to fetch` / `No running live server found.`), so no user-visible overlay was rendered. Fallback live checks across `1440×900`, `1024×768`, `768×1024`, `375×812`, and `320×640` (light & dark themes) confirmed **0 horizontal overflow**, **0 non-`sr-only` text truncations**, **0 WCAG contrast failures**, **all 9 charts/sparklines rendering cleanly**, and **0 runtime console or HTTP ≥ 400 network errors**.

---

### Overall Impression
The core recorte-to-evidence loop, mobile stabilization, and dark/light theme discipline are solid (`28/40` — Good). The biggest friction now sits at the seams between subsystems: opening `AgentDock` at `1440px` teleports and shrinks `AgentAskButton` while failing to show `"Conversa aberta"`; `OrdersTable` silently mutates global dashboard filters from inside an `overflow-auto` data table; `AgentChat` and `AgentComanda` bend the system's own One Red Rule, `.ticket` exclusivity, and desktop button sizing; and keyboard/AT parity still lags on `HeatmapChart`, `TrendChart`, and dense touch `.hit-target` overlays.

---

### What's Working
1. **Tight "Recorte + Evidence" synchronization**: Every island shares the URL-synced Nanostores state, and clicking any rail comanda highlights its KPI (`2px` inset ink outline) or chart evidence (`EvidenceTag` + dimmed backdrop) without altering active filters until the user commits via the CTA.
2. **Custom accessible inputs & responsive touch discipline**: Searchable APG `MultiSelect`, pt-BR `DatePicker` (floating on desktop, inline flow in mobile `FilterSheet`), and native `<dialog>` sheets hold zero overflow and `≥ 44px` mobile controls all the way down to `320×640`.
3. **Calm color & flat elevation craft**: Zero box-shadows anywhere, verified AA contrast in both themes (`data-theme="light"` / `"dark"`), and clean `prefers-reduced-motion` parity across CSS and ECharts.

---

### Priority Issues

1. **[P1] What**: `AgentAskButton` teleports from Row 1 to Row 2 and hides `"Conversa aberta"` when `AgentDock` opens at `1440×900`
   - **Evidence**: [`FilterBar.tsx#L53-L81`](file:///C:/Projects/dashboard-insight/frontend/src/components/FilterBar.tsx#L53-L81), [`AgentLauncher.tsx#L78-L81`](file:///C:/Projects/dashboard-insight/frontend/src/components/agent/AgentLauncher.tsx#L78-L81), [`DESIGN.md#L285`](file:///C:/Projects/dashboard-insight/DESIGN.md#L285). Opening `AgentDock` (`403px`) narrows `#page` to `1022px` (`< 70rem`), causing the `335×40` Row-1 launcher to vanish and the `176×32` Row-2 launcher to take over, where `@min-[18rem]/ask:inline` (`288px`) never matches so `"Conversa aberta"` never displays.
   - **Why it matters**: Clicking the launcher rearranges the toolbar right under the cursor and removes the explicit open-state text specified in `DESIGN.md`.
   - **Fix**: Keep one `AgentAskButton` anchored in Row 1 at `lg+` by adjusting `PlaceFields` basis (`flex-[1_1_28rem]` instead of `42rem`) and tightening the Row-1 compact minimum width (`min-w-[8.5rem]`), and show `"Conversa aberta"` (or `"Aberta"` at compact widths) whenever `open` is `true`.
   - **Suggested command**: `/impeccable layout`

2. **[P1] What**: Global `Status` filter is hidden inside `OrdersTable`, whose column popovers look local but mutate the entire dashboard
   - **Evidence**: [`OrdersTable.tsx#L228-L231`](file:///C:/Projects/dashboard-insight/frontend/src/components/OrdersTable.tsx#L228-L231), [`OrdersTable.tsx#L376-L420`](file:///C:/Projects/dashboard-insight/frontend/src/components/OrdersTable.tsx#L376-L420), [`FilterFields.tsx#L140-L155`](file:///C:/Projects/dashboard-insight/frontend/src/components/filters/FilterFields.tsx#L140-L155). `Status` (`Concluído`/`Cancelado`) is absent from `Mais filtros` and mobile `FilterSheet`; its only control is a `24px` icon in `OrdersTable` at `y ≈ 2764px`, and those popovers use `position: absolute` inside the `overflow-auto` scroller.
   - **Why it matters**: Filtering `Status = Cancelado` at the bottom silently breaks top SLA KPIs/alerts globally, while users scanning `FilterBar` have no idea `Status` exists.
   - **Fix**: Add `Status` to `ExtraFields` in `FilterFields.tsx` so every global filter lives in `FilterBar`/`FilterSheet`, and either remove global-mutating popovers from `OrdersTable` headers or scope table column filters strictly to the orders table.
   - **Suggested command**: `/impeccable distill`

3. **[P1] What**: `AgentChatComanda` verbosity, One Red Rule contradiction in `AgentOpenBand`, `.ticket` empty-state bleed, and undersized `AgentChat` desktop buttons
   - **Evidence**: [`AgentComanda.tsx#L24`](file:///C:/Projects/dashboard-insight/frontend/src/components/agent/AgentComanda.tsx#L24), [`AgentComanda.tsx#L48-L91`](file:///C:/Projects/dashboard-insight/frontend/src/components/agent/AgentComanda.tsx#L48-L91), [`AgentComanda.tsx#L229`](file:///C:/Projects/dashboard-insight/frontend/src/components/agent/AgentComanda.tsx#L229), [`AlertsPanel.tsx#L677`](file:///C:/Projects/dashboard-insight/frontend/src/components/AlertsPanel.tsx#L677), [`AgentChat.tsx#L346`](file:///C:/Projects/dashboard-insight/frontend/src/components/AgentChat.tsx#L346), [`AgentChat.tsx#L452`](file:///C:/Projects/dashboard-insight/frontend/src/components/AgentChat.tsx#L452), [`AgentChat.tsx#L496`](file:///C:/Projects/dashboard-insight/frontend/src/components/AgentChat.tsx#L496). Inside the `403px` dock, summary answers render a ~750px perforated card duplicating all 6 rail alerts (pushing LLM upgrade status off-screen); `AgentOpenBand` renders `btn-primary` (red) despite forbidding red on agent tickets; `AlertsPanel` puts `.ticket` perforations on the zero-alert state; and desktop `AgentChat` buttons measure `25–28px` high (`Enviar` `28px` beside a `40px` `textarea`).
   - **Why it matters**: Dilutes the single critical red CTA on the page, crowds the dock, blurs the physical comanda metaphor onto non-alert containers, and shrinks desktop click targets.
   - **Fix**: Switch `AgentOpenBand` primary drilldown to `btn-ink`; change `AlertsPanel.tsx:677` and `AgentChatComanda` from `.ticket` to bordered `.tile`/chat-card framing with concise alert summaries (collapsible detail); size `Enviar` to `h-10` matching the textarea and secondary chat actions to `min-h-8` + `.hit-target`.
   - **Suggested command**: `/impeccable polish`

4. **[P2] What**: Keyboard/AT chart parity gaps, `<Term>`/`Thin` underline collision, and `.hit-target::after` overlap in table headers
   - **Evidence**: [`HeatmapChart.tsx`](file:///C:/Projects/dashboard-insight/frontend/src/components/HeatmapChart.tsx) & [`TrendChart.tsx`](file:///C:/Projects/dashboard-insight/frontend/src/components/TrendChart.tsx) (missing `<ChartAccess>`), [`StoreScatter.tsx#L80-L94`](file:///C:/Projects/dashboard-insight/frontend/src/components/StoreScatter.tsx#L80-L94) (mouse-only brush), [`BreakdownTable.tsx#L93-L100`](file:///C:/Projects/dashboard-insight/frontend/src/components/BreakdownTable.tsx#L93-L100) & [`BreakdownTable.tsx#L298`](file:///C:/Projects/dashboard-insight/frontend/src/components/BreakdownTable.tsx#L298) (`Thin` shares `decoration-dotted` with clickable `<Term>`; `24px` row filter lacks `.hit-target`), [`OrdersTable.tsx#L66-L71`](file:///C:/Projects/dashboard-insight/frontend/src/components/OrdersTable.tsx#L66-L71) (no visible legend for `↑`), and [`global.css#L452-L466`](file:///C:/Projects/dashboard-insight/frontend/src/styles/global.css#L452-L466) (fixed `2.75rem × 2.75rem` centered `::after` overlaps adjacent table header buttons by ~16–20px and leaves ends of `95–290px` inline links uncovered).
   - **Why it matters**: Keyboard/screen-reader users cannot read trend/heatmap series breakdowns; sighted users mistake small-sample table cells for glossary tooltips; adjacent mobile header buttons steal taps.
   - **Fix**: Add `<ChartAccess>` summaries to `HeatmapChart` and `TrendChart`, use a distinct non-link treatment for `Thin` (e.g., muted text + subtle marker/footnote), add `.hit-target` to `BreakdownTable`'s row filter, document `↑ fora do SLA` in `OrdersTable`'s hint, and switch `.hit-target::after` to `min-width`/`min-height` or `inset` padding with tighter button separation in `<th>`.
   - **Suggested command**: `/impeccable audit`

5. **[P2] What**: Spec drift in `.impeccable/surfaces/frontend-src-pages-index-astro.md` and off-scale `text-lg` in `ExportDialog`
   - **Evidence**: [`.impeccable/surfaces/frontend-src-pages-index-astro.md#L17-L21`](file:///C:/Projects/dashboard-insight/.impeccable/surfaces/frontend-src-pages-index-astro.md#L17-L21) still describes the retired 2-column first viewport, `Archivo`, `#EFEFEF`, and `framboesa/oliva-lima`; [`ExportDialog.tsx#L100`](file:///C:/Projects/dashboard-insight/frontend/src/components/ExportDialog.tsx#L100) uses `text-lg` instead of the 6-step `@theme` scale ([`DESIGN.md#L204`](file:///C:/Projects/dashboard-insight/DESIGN.md#L204)).
   - **Why it matters**: Stale surface briefs and off-scale utility classes reintroduce layout/token regressions in future passes.
   - **Fix**: Update `.impeccable/surfaces/frontend-src-pages-index-astro.md` to reflect the shipped layout and tokens, and change `ExportDialog.tsx:100` to `section-title` (`text-base font-semibold`) or `text-lead`.
   - **Suggested command**: `/impeccable document`

---

### Cognitive Load Assessment
**Checklist: 3 / 8 failures (Moderate cognitive load — address soon)**
- Fails **Chunking (`≤ 4` items/group)**: **6** comandas on rail (**7** with agent comanda), **12** columns in `OrdersTable`, **10** columns + **7** dimensions in `BreakdownTable`, **6** control groups in Row 1 of `FilterBar`.
- Fails **One thing at a time**: `OrdersTable` filters mutate the global slice mid-table inspection; `AgentDock` adds a second `Nº A01` comanda system alongside `Nº 01–06`.
- Fails **Minimal choices (`≤ 4` visible options)**: `AlertsPanel` rail (`6–7`), `BreakdownTable` `Quebrar por` (`7`), `FilterBar` Row 1 (`6`), and `OrdersTable` header (`12` columns / `11` sorts / `5` column filters).
- Passes Single focus, Grouping, Visual hierarchy, Working memory, and Progressive disclosure.

---

### Emotional Journey
- **Opening (Peak)**: At `1440×900`, the wine band, sticky filter bar, full comanda rail, open `Nº 01` ticket with its red CTA, and the entire `KpiStrip` fit cleanly above the `900px` fold (`812px` bottom).
- **Investigation (Friction Valley)**: Clicking the agent launcher causes the toolbar to rearrange and loses `"Conversa aberta"`; querying rail alerts opens a tall duplicated card inside the `403px` dock; drilling into `Status` sits buried at `y ≈ 2764px`.
- **High-Stakes Guardrails (Reassurance)**: Cold-start messaging, `outsideBaseNote` zero-order recovery hints, and `amostra pequena` warnings build high operational trust.

---

### Persona Red Flags
- **Alex (Power User)**: `AgentAskButton` moves between Row 1 and Row 2 when docked; `StoreScatter` brush and `TrendChart` zoom are pointer-only; `BreakdownTable` dimensions sit inside a 7-item dropdown; `Status` filter requires scrolling to the bottom table.
- **Sam (Accessibility-Dependent)**: `HeatmapChart` and `TrendChart` lack `<ChartAccess>` DOM/keyboard summaries; `StoreScatter` brush is mouse-only; `<Term>` and `Thin` collide on `decoration-dotted`; adjacent `<th>` `.hit-target::after` boxes overlap by `~16–20px`.
- **Casey (Distracted Mobile User — `375×812` & `320×640`)**: The top stack (`header` + `sm:hidden` subtitle + `FilterBar` + rail + `OpenBand` diagnosis) pushes the primary CTA (`Ver só Color Shopping`) below `y=812px` (`y=835px`) and `KpiStrip` to `y=1019px`.
- **Jordan (First-Timer / Recruiter)**: Comanda Nº 01 says `"expedição"` at network scope and switches to `"trânsito"` after drilling into `Color Shopping` without explaining the shift; `↑` out-of-SLA cells in `OrdersTable` have no visible legend.

---

### Minor Observations
- [`StagesChart.tsx`](file:///C:/Projects/dashboard-insight/frontend/src/components/StagesChart.tsx): its `<ul class="flex flex-col gap-1">` `.chart-key` list occupies a `mt-2` wrapper below the canvas even while unfocused (`sr-only`).
- [`OrdersTable.tsx#L171`](file:///C:/Projects/dashboard-insight/frontend/src/components/OrdersTable.tsx#L171): `ColumnFilterPopover` uses `position: absolute` inside the `h-[460px] overflow-auto` scroller, which clips on short filtered tables; infinite-scroll `fetchNextPage` errors also lack an inline retry button.
- [`index.astro#L58`](file:///C:/Projects/dashboard-insight/frontend/src/pages/index.astro#L58) & [`index.astro#L167-L188`](file:///C:/Projects/dashboard-insight/frontend/src/pages/index.astro#L167-L188): `"368.990 pedidos"` is hardcoded in static HTML; the `document.body` `MutationObserver` re-scans all `section.panel-frame` elements on every virtualized scroll/popover mutation.

---

### Questions to Consider
1. What if `AgentAskButton` stayed permanently anchored on Row 1 (`lg+`) and updated cleanly to `"Conversa aberta"`, so opening the dock never jumps the toolbar under the user's cursor?
2. Should `FilterBar` own all 8 recorte filters (moving `Status` into `Mais filtros` / `FilterSheet`) while `OrdersTable` stops silently mutating the global KPIs from a column header?
3. On mobile (`375px`), would folding the `49px` `sm:hidden` header subtitle and tightening `OpenBand` above the CTA pull both the primary drilldown button and the top SLA hero KPI back into the first viewport?
4. Should summary agent replies like `"Quais os alertas e o que fazer hoje?"` avoid creating a duplicate `Nº A01` ticket on the rail when the alerts already hang right beside it?
