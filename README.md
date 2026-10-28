# Central de Operações — Food Delivery Insights

Dashboard interno para um operador de marketplace de delivery: ver rápido o que está acontecendo **no recorte filtrado** (cidade, culinária, período, restaurante) e sair com **alerta + ação**, não só com um ranking.

Feito para o portfólio de estágio iFood (ferramenta interna deployada: dashboard + agente).

## Problema

Quem opera praça não precisa de mais um gráfico bonito. Precisa saber, no filtro de agora:

- o SLA de entrega estourou?
- a nota caiu em um parceiro com volume, não na média?
- o cancelamento é nacional ou de uma cidade?
- o que fazer hoje — reforçar frota no jantar, ligar para o restaurante, revisar raio.

Este app gera pedidos mock realistas (90 dias, cidades brasileiras) e coloca KPIs, Plotly e um agente em cima **do mesmo DataFrame filtrado**.

## Como rodar

Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Em Linux/macOS: `source .venv/bin/activate`.

O app funciona **sem API key**. O agente local responde com regras e estatísticas do recorte.

Para deixar o texto mais livre, copie `.env.example` para `.env` e preencha `OPENROUTER_API_KEY` (modelo padrão: `nvidia/nemotron-3-ultra-550b-a55b:free`). No Streamlit Cloud, use o painel de Secrets com as mesmas chaves.

## O que está no MVP

- 12 mil pedidos mock (lognormal no ticket, gamma no tempo, pico de almoço/jantar, qualidade por restaurante).
- Filtros na sidebar: período, cidade, culinária, restaurante, tipo de cliente, status.
- KPIs: pedidos, GMV, ticket, tempo, nota, cancelamento.
- Alertas proativos no topo (SLA, nota, cancelamento, praça/restaurante fora da curva) com ação sugerida.
- Abas Plotly: tendência, ranking, operação.
- Chat do agente no rodapé, histórico em `st.session_state.messages`, modo dual (local / LLM).

## Estrutura

```
app.py                  # orquestra Streamlit
data/generator.py       # mock
dashboard/filters.py    # recorte
dashboard/metrics.py    # KPIs
dashboard/charts.py     # Plotly
agent/insights.py       # alertas + respostas
agent/prompts.md        # system prompt do LLM
tests/                  # gerador, filtros, agente
```

## Deploy (Streamlit Cloud)

1. Suba este repositório no GitHub.
2. Em [share.streamlit.io](https://share.streamlit.io), aponte para `app.py`.
3. (Opcional) Secrets: `OPENROUTER_API_KEY` (e, se quiser, `OPENROUTER_MODEL`).

**App deployado:** _ainda não publicado — cole o link aqui depois do primeiro deploy._

## Screenshots

Coloque 2–4 prints em `assets/` depois do primeiro run e referencie aqui:

- `assets/kpis.png` — faixa de KPIs + alertas
- `assets/tendencia.png` — pedidos/GMV e heatmap de hora
- `assets/ranking.png` — restaurantes e culinária
- `assets/agente.png` — chat com alerta e ação

## Métricas de uso

Preencher com o próprio uso / Streamlit analytics após o deploy:

| Métrica | Valor |
|---|---|
| Acessos (7 dias) | — |
| Perguntas ao agente | — |
| Feedback útil / não útil | — |

## Stack

Streamlit · Plotly · pandas · numpy · agente local + OpenRouter (Nemotron) opcional.
