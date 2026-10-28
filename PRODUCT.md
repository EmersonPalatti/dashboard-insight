# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary visitor is an **iFood internship recruiter** evaluating a deployed (or locally run) internal tool as a portfolio piece. They are not operating a real praça; they need to understand, in a few minutes, that this is a working dashboard + insights agent — not a chart gallery.

The in-product persona is a **praça operator** on a Brazilian food-delivery marketplace: they have already applied a recorte (period, city, cuisine, restaurant, customer type, status) and need to know whether delivery SLA, partner rating, or cancellation is off in *this* slice, then leave with an action for today (fleet at dinner, call the restaurant, review radius).

Design the UI as that operator’s tool. Success is the recruiter being able to perform that job and see the differentiator.

## Product Purpose

**Central de Operações** is an internal food-delivery operations console. It shows KPIs, Plotly views, proactive alerts, and a chat agent on the **same filtered DataFrame** (the recorte), so the visitor exits with **alert + action**, not only a ranking.

It exists to cover the internship portfolio requirement for a deployed internal tool (dashboard or agent), with a food-delivery theme aligned to iFood’s domain — without being an iFood product.

Success: a recruiter can filter a slice, read whether SLA / note / cancelamento is off, and get a concrete operational action from alerts or the agent.

## Positioning

Neighboring Streamlit dashboards have charts. Neighboring agents chat over a whole CSV. This product’s claim is that **KPIs, charts, alerts, and the agent all run on the current recorte** and **close with a concrete operational action** (who talks to whom, in which time band, toward which threshold) — not “top restaurants” or generic engagement advice.

## Operating Context

- Single Streamlit page (`streamlit run app.py`). Intended deploy is Streamlit Cloud; the live URL is not published yet.
- Sidebar **Recorte** drives everything below: KPIs, alert strip, Tendência / Ranking / Operação tabs, and the footer agent. Empty recorte shows a warning and stops the rest of the page.
- Mock orders: 12 000 rows, last 90 days, ten Brazilian cities, ten cuisines, restaurant quality variation, lunch/dinner peaks. Not live marketplace data.
- Agent: local rules + statistics without an API key; optional OpenRouter LLM (`OPENROUTER_API_KEY`) for freer prose on the same numbers. Chat history in `st.session_state.messages`.
- Recruiter / operator language of the product is **Brazilian Portuguese**. Currency and number formats are pt-BR (R$, comma decimals).
- Portfolio artifact: README should eventually hold deploy link, screenshots, and usage metrics — those are absent today.

## Capabilities and Constraints

**In the product today**

- Filters: period, city, cuisine, restaurant (scoped by city/cuisine), customer type (Novo, Recorrente, VIP), status (Entregue, Cancelado). Empty multi-select = all.
- KPIs on the recorte: pedidos, GMV (delivered only), ticket médio, tempo de entrega, nota média, cancelamento; promo rate as supporting caption.
- Proactive alerts (SLA, rating, cancellation, city/restaurant outliers) with suggested action; high vs warning severity.
- Charts: orders/GMV over time, weekday×hour heatmap, restaurant ranking, cuisine mix, delivery by city, rating distribution, cancel by customer type.
- Insights agent on the recorte summary (not the raw full dataset); suggested prompts; “Nova conversa”.
- Dual mode: must remain useful with **no API key**.

**Must preserve**

- Recorte is the unit of truth. Never answer or chart the unfiltered dataset when filters are on.
- Mock-only: no CSV upload or live API in current product truth.
- Independent of iFood trademarks, logos, and official identity. Domain (pedidos, praças, restaurantes, cidades BR) is in-theme; the brand is not iFood.
- Do not hardcode restaurant or city names into chart titles; they come from the data.
- Business logic stays in `data/`, `dashboard/`, `agent/` — not piled into `app.py`.
- Thresholds used by the local agent: delivery warn/high ~42/48 min, rating warn/low ~4.20/4.00, cancel warn/high ~7%/10%, with minimum volume before calling out a restaurant or city.

**Undecided / out of scope for now**

- Heatmap map, PDF export, real-data ingest, multi-page navigation (listed as later ideas in AGENTS.md, not product commitments).
- Accessibility standard beyond ordinary web UI (none specified).

## Brand Commitments

- **Name:** Central de Operações (page: “Central de Operações · Delivery”; README: “Central de Operações — Food Delivery Insights”).
- **Voice:** Direct Brazilian Portuguese, like an internal ops briefing. No marketing fluff. No emojis. Prefer 1–3 short paragraphs or a short list. Cite concrete numbers and the recorte; finish with an action when something is off.
- **Independence:** No iFood wordmark, logo, or official visual identity. Do not imply this is an iFood product or that the recruiter is using production iFood data.
- Repo folder `dashboard-insight` is not a customer-facing name.

## Evidence on Hand

- Synthetic orders from `data/generator.py` (seeded mock). Cities, restaurants, tickets, times, and ratings are generated — not production.
- No screenshots in `assets/` yet. README placeholders must not be treated as real captures.
- No Streamlit Cloud URL. Do not invent a deploy link.
- No usage metrics (visits, agent questions, feedback). Do not invent them.
- No testimonials, customers, benchmarks, pricing, or press. Do not fabricate recruiter or operator quotes.

## Product Principles

1. **Recorte first.** Every number, chart, alert, and agent reply is about the slice on screen.
2. **Action, not ranking.** A useful output names the problem in this slice and what to do today.
3. **Honest without a key.** The console works on rules and statistics; an LLM may only rephrase the same recorte facts.
4. **Mock is labeled by absence of claims.** Never present generated orders, missing screenshots, or unpublished deploys as real marketplace evidence.
5. **Recruiter can do the operator’s job in minutes.** Filters, KPIs, alerts, and agent have to be scannable without a walkthrough.
