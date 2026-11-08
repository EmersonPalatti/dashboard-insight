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
- **Agente:** `backend/app/agent/`. `service.py` tenta LLM com tools → LLM com contexto → regras locais (`local.py`). As tools (`llm.py`) recebem o recorte do servidor; o modelo escolhe o que consultar, nunca sobre quais dados. Prompt em `prompts.md`.
- **Frontend:** `frontend/src/pages/index.astro` é a casca sem JS. Cada componente em `src/components/` é uma ilha exportada via `island(Componente, alturaDoSkeleton)` de `src/lib/query.tsx`, que monta o `QueryClient` compartilhado e evita hydration mismatch.
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

# frontend (Node 20+)
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
6. **Ilhas só onde há interação.** Conteúdo estático fica no `.astro`. `client:load` acima da dobra, `client:visible` no resto.
7. **Decisões de limpeza visíveis.** Fuso UTC→Brasília, SLA por segmento (food 60 / goods 120 min), pedido "preso" (ciclo > 4h) fora de medianas e SLA, valor > R$ 5 mil fora do GMV. Se mudar, atualize rodapé, README e testes.
8. **Design (mundo "Comanda", ver `DESIGN.md`):** só tokens semânticos (`bg-field`, `bg-surface`, `bg-wine`, `text-crit`, `text-series`…) de `src/styles/global.css`. Vermelho (`crit`) só para crítico e ação principal; série de dados em vinho (`series`); severidade também por forma (cheia, vazada, traço). Picote (`ticket`) só em comandas de alerta. Sem sombras; cantos 4px/8px; Archivo, condensada só em rótulos; tema claro e escuro.
9. **Testes:** toda regra de alerta nova ganha um cenário plantado em `backend/tests/conftest.py`.

## Português

Interface, alertas e agente em português do Brasil, formato pt-BR (R$ 1.234,56; 4,6%). Código e nomes de variáveis em inglês.
