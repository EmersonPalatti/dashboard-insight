# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary visitor is an **iFood internship recruiter** (AI Builder track) evaluating a deployed internal tool as a portfolio piece. They are not operating a real praça; they need to understand, in a few minutes, that this is a working dashboard + insights agent on real data — not a chart gallery.

The in-product persona is a **hub/praça operator** on a Brazilian delivery platform: they have already applied a recorte (period, city, hub, store, segment, channel, courier modal) and need to know whether delivery SLA, store prep time, or cancellation is off in *this* slice, then leave with an action for today (call the store, reinforce fleet before dinner, take a broken store offline, review radius).

Design the UI as that operator’s tool. Success is the recruiter being able to perform that job and see the differentiator.

## Product Purpose

**Central de Operações** is an internal delivery operations console. KPIs, ECharts views, proactive alerts with drill-down, raw order tables and a chat agent all run on the **same recorte**, so the visitor exits with **alert + action**, not only a ranking.

It covers the portfolio requirement for a deployed internal tool (dashboard and agent), with a delivery theme aligned to iFood’s domain — without being an iFood product.

Success: a recruiter filters a slice, reads whether SLA / prep / cancelamento is off and where, clicks an alert to drill into the hub or store, and gets a concrete operational action from alerts or the agent.

## Positioning

Neighboring dashboards have charts. Neighboring agents chat over a whole CSV. This product’s claim is that **KPIs, charts, alerts, and the agent all run on the current recorte** — the agent’s tools are locked to it on the server — and **close with a concrete operational action** (who talks to whom, in which hub, in which time band, toward which threshold).

## Operating Context

- Static Astro shell + React islands (frontend, Vercel) talking to a FastAPI + DuckDB API (backend, Render free tier — cold start ~40 s, surfaced in the UI).
- Recorte lives in a Nanostores atom synced to the URL query string; the same keys are the API’s query params, so links are shareable.
- Data: **Delivery Center (Kaggle)** — 368,990 real orders, 01/01–30/04/2021, 32 hubs in São Paulo, Rio de Janeiro, Curitiba and Porto Alegre, ~950 stores (names anonymized by the dataset), segments food/goods. Built into `backend/data/orders.parquet` by `backend/scripts/build_parquet.py`.
- Cleaning decisions that change numbers (keep them visible in the footer/README): timestamps converted UTC→Brasília; SLA by segment (food ≤ 60 min, goods ≤ 120 min); cycle > 4h = "preso" and excluded from medians and SLA; amount > R$ 5,000 excluded from GMV/ticket.
- Agent: local rules + statistics without an API key; with `OPENROUTER_API_KEY`, an LLM with tool calling (KPIs, breakdowns, alerts, time series) — falls back to a single context prompt, then to local rules.
- Product language is **Brazilian Portuguese**; pt-BR currency and number formats.

## Capabilities and Constraints

**In the product today**

- Filters: period (presets + dates + zoom-to-period from the trend chart), city, hub (scoped by city), store (searchable, scoped by hub), segment, channel type, courier modal. Empty multi-select = all.
- KPIs with delta vs. previous period of equal length: SLA, median cycle, cancelamento (hero row); pedidos, GMV, ticket (volume row).
- Alerts: recorte SLA, slowest hub with the stage that explains it, cancel outliers by hub and store, broken stores (~100% canceled), SLA drop at peak, stuck orders (data), weekly volume drop, freight subsidy. Each has an action and, when scoped, a drill-down filter.
- Charts: trend (volume / SLA+cycle / cancel; hour/day/week), cycle stages per hub, weekday × hour heatmap, store scatter with brush-to-filter.
- Tables: ranking by dimension (client sort) and raw orders (server paging/sort, virtualized).
- Export: orders CSV, Markdown briefing to clipboard, print-to-PDF.

**Must preserve**

- Recorte is the unit of truth. Never answer or chart the unfiltered dataset when filters are on.
- App works with **no API key**.
- Independent of iFood trademarks, logos, and official identity.
- No hardcoded hub, store or city names in UI or alert logic; they come from the data.
- Business logic in `backend/app/` (repository, alerts, agent), not in components or endpoints.

**Undecided / out of scope for now**

- Hub map (lat/long exists in the raw dataset), CSV upload, auth, multi-page navigation.

## Brand Commitments

- **Name:** Central de Operações.
- **Voice:** Direct Brazilian Portuguese, like an internal ops briefing. No marketing fluff. No emojis. Cite concrete numbers and the recorte; finish with an action when something is off.
- **Independence:** No iFood wordmark, logo, or official visual identity. Do not imply this is an iFood product or iFood data.

## Evidence on Hand

- Real public dataset (Delivery Center, Kaggle), 2021. Not iFood data. Store names are anonymized strings.
- No screenshots in `assets/` yet, no deploy URL yet, no usage metrics yet. Do not invent them.
- No testimonials, customers, benchmarks or press.

## Product Principles

1. **Recorte first.** Every number, chart, alert, and agent reply is about the slice on screen.
2. **Action, not ranking.** A useful output names the problem in this slice and what to do today.
3. **Honest without a key.** The console works on rules and statistics; the LLM only queries the same recorte through tools.
4. **Say what was cleaned.** Timezone, SLA targets, stuck orders and outliers are disclosed where the numbers appear.
5. **Recruiter can do the operator’s job in minutes.** Filters, KPIs, alerts, and agent have to be scannable without a walkthrough.
