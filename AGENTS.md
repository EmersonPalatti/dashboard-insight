# AGENTS.md — Central de Operações (delivery analytics)

Painel interno de operação de delivery com **alertas acionáveis** e **agente de insights**, tudo sobre o recorte filtrado. Peça de portfólio para o estágio iFood (trilha AI Builder): ferramenta interna deployada, dashboard funcional e agente que resolve problema de negócio.

Leia também `PRODUCT.md` (público, princípios, o que não inventar) e `DESIGN.md` (tokens visuais).

## Arquitetura

```
frontend/  Astro (casca estática) + ilhas React ──HTTP──▶ backend/  FastAPI + DuckDB
           ECharts, Nanostores, TanStack Query/Table/Virtual         sobre backend/data/orders.parquet
           deploy: Vercel                                             deploy: Render (render.yaml)
```

- **Dados:** Delivery Center (Kaggle), 368.990 pedidos reais, jan–abr/2021. `backend/scripts/build_parquet.py` lê os 7 CSVs de `backend/data/raw/` (gitignored) e gera `backend/data/orders.parquet` (versionado). Não existe banco: o DuckDB carrega o parquet em memória na subida da API.
- **Recorte:** `backend/app/filters.py` (`Filters`, Pydantic) é o contrato único. As mesmas chaves são query params da API e da URL do frontend (`?city=Curitiba&hub=8&hub=13`). `Filters.where()` gera SQL só com parâmetros `?`.
- **Consultas:** `backend/app/repository.py`. Colunas, dimensões e ordenações vêm de listas fixas (`DIMENSIONS`, `SORTS`, `ORDER_SORTS`); nunca interpole texto do usuário em SQL.
- **Alertas:** `backend/app/alerts.py`. Cada alerta = problema + número + **ação operacional** + drill-down opcional.
- **Agente:** `backend/app/agent/`. `service.py` tenta LLM com tools → LLM com contexto → regras locais (`local.py`, que lê a pergunta em `local_intent.py` e responde em `local_answers.py`). As tools (`llm.py`: `get_kpis`, `get_alerts`, `get_timeseries`, `query_metrics`, `explain_change`, `drill_cause`) recebem o recorte do servidor; o modelo escolhe o que consultar, nunca sobre quais dados. Prompt em `prompts.md` + glossário gerado da camada semântica. Modelo gratuito do OpenRouter por padrão: orçamento de 20 s com prazo de relógio (`_call_with_deadline`), disjuntor de cota após 429 (`quota_breaker`), `fallback_reason` na resposta e aviso no chat.
- **Camada semântica:** `backend/app/semantic.toml` (lido por `semantic.py`) é a fonte única de métricas, dimensões, sinônimos, conceitos (janelas como jantar e fim de semana) e mapa causal. Métrica ou dimensão nova entra lá e no `repository`; `test_semantic.py` cruza os dois e os limiares citados no texto.
- **Análise:** `Repository.query_metrics` (até 2 dimensões, subfiltro, comparação com período anterior ou resto do recorte) e `backend/app/analytics.py` (`explain_change`: decomposição exata efeito taxa + mix; `drill_cause`: etapa que explica o atraso). A conta é sempre do backend, nunca do modelo.
- **Avaliação:** `backend/evals/` (casos derivados dos dados, sem nomes fixos). `python -m evals.run --engine local|auto` gera o placar; `test_evals.py` trava o piso do agente local. Mudou o agente? Rode o placar.
- **Frontend:** `frontend/src/pages/index.astro` é a casca sem JS. Cada componente em `src/components/` é uma ilha exportada via `island(Componente, fallback)` de `src/lib/query.tsx`, que monta o `QueryClient` compartilhado e evita hydration mismatch. `fallback` é o skeleton do SSR (altura em px ou um nó com classes por breakpoint) e deve ter a altura do estado carregando, para não haver salto de layout.
- **Painéis:** moldura, título e dica fixa ficam na casca (`src/components/ui/Panel.astro`); a ilha devolve só `PanelContent` (ações, dica dinâmica, nota, corpo) e usa `panelFallback(altura)`. Como `<astro-island>` é `display: contents`, as peças da ilha entram no mesmo flex da moldura. `Panel` com `collapsible` vira linha recolhível (o corpo fica `hidden`, então a ilha `client:visible` só hidrata ao abrir).
- **Metade de baixo (investigação da comanda):** abaixo dos KPIs, `#investigacao` mostra só o gráfico que prova a comanda aberta (ou a Tendência), `#ranking` fica sempre aberto, `#explorar` guarda o resto recolhido e `#fechamento` (`OperationalClose`) fecha a página. Regras e estado em `src/lib/investigation.ts`; quem move os gráficos entre as zonas (nós do DOM, nunca CSS `order`) é `src/lib/investigationLayout.ts`, iniciado por um `<script>` do `index.astro`.
- **Estado global:** `src/lib/filters.ts` (`$filters`, átomo Nanostores ligado à URL). Ilhas leem com `useStore($filters)` e buscam com `useRecorteQuery(path, extra)`.
- **Tipos:** `src/lib/api/schema.d.ts` é **gerado** do OpenAPI. Mudou schema Pydantic? Rode o fluxo da seção Comandos; não edite o `.d.ts` à mão.

## Comandos

```bash
# backend (Python 3.11+)
cd backend
pip install -r requirements-dev.txt
python scripts/build_parquet.py          # só se mudar o ETL; precisa dos CSVs em data/raw/
uvicorn app.main:app --reload            # http://localhost:8000/docs
pytest                                   # usa parquet sintético, não precisa do Kaggle

# tipos do frontend a partir do backend
python scripts/export_openapi.py && (cd ../frontend && npm run gen:api)

# frontend (Node 22+)
cd frontend
npm install
npm run dev                              # http://localhost:4321 (PUBLIC_API_URL, padrão localhost:8000)
npm run build                            # astro check + build estático
```

## Regras

1. **Recorte em tudo.** KPIs, gráficos, tabelas, exportação, alertas e agente usam o mesmo `Filters`. Nada responde sobre o dataset inteiro quando há filtro.
2. **Funciona sem API key.** O agente local é obrigatório; LLM é melhoria.
3. **Ação, não ranking.** Alerta e resposta do agente fecham com quem faz o quê, onde e quando.
4. **Sem nomes fixos.** Hubs, lojas e cidades vêm dos dados, nunca do código.
5. **Lógica de negócio no backend** (`repository`, `alerts`, `agent`). Componentes só exibem e filtram.
6. **Ilhas só onde há interação ou dado do recorte.** Texto que não depende de estado (títulos, dicas fixas, rodapé) fica no `.astro`. `client:load` acima da dobra e para gatilhos globais (agente), `client:visible` no resto. O que só abre por clique (diálogos, folhas, conversa do agente) entra com `React.lazy`.
7. **Decisões de limpeza visíveis.** Fuso UTC→Brasília, SLA por segmento (food 60 / goods 120 min), pedido "preso" (ciclo > 4h) fora de medianas e SLA, valor > R$ 5 mil fora do GMV. Se mudar, atualize rodapé, README e testes.
8. **Design (mundo "Comanda", ver `DESIGN.md`):** só tokens semânticos (`bg-field`, `bg-surface`, `bg-wine`, `text-crit`, `text-series`…) de `src/styles/global.css`. Vermelho (`crit`) só para crítico e ação principal; série de dados em vinho (`series`); severidade também por forma (cheia, vazada, traço). Picote (`ticket`) só em comandas de alerta. Sem sombras; cantos 4px/8px; Libre Franklin no texto; Zilla Slab só em números, Nº da comanda e nome do produto; tema claro e escuro.
9. **Testes:** toda regra de alerta nova ganha um cenário plantado em `backend/tests/conftest.py`.

## Português

Interface, alertas e agente em português do Brasil, formato pt-BR (R$ 1.234,56; 4,6%). Código e nomes de variáveis em inglês.
