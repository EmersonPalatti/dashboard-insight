# Central de Operações: painel de delivery com alertas e agente

Painel interno para quem opera hubs de delivery: filtre um recorte (período, cidade, hub, loja, segmento, canal, modal) e veja **o que está fora da curva e o que fazer hoje**: qual hub estourou o SLA e em qual etapa, qual loja ligar, quando reforçar a frota.

Roda sobre **368.990 pedidos reais** do dataset [Delivery Center](https://www.kaggle.com/datasets/nosbielcs/brazilian-delivery-center) (jan–abr/2021, 32 hubs em São Paulo, Rio, Curitiba e Porto Alegre).

**App:** _deploy pendente: link da Vercel aqui_ · **API:** _link do Render aqui_ `/docs`

![Painel com KPIs, alertas e agente](assets/painel.png)

## O problema

Um dashboard com gráficos não diz para o operador o que fazer. Ele precisa de respostas no recorte que está olhando:

- O SLA estourou? Em qual hub? É a loja demorando para preparar ou é trânsito?
- O cancelamento é geral ou de duas lojas com cadastro quebrado?
- O pico do jantar está pior que o resto do dia?

Por isso tudo aqui (KPIs, gráficos, tabelas, exportação, alertas e agente) usa **o mesmo recorte**, e cada alerta termina com uma **ação** e um botão que filtra o painel no hub ou loja em questão.

## O que dá para fazer

| | |
|---|---|
| **Alertas com ação** | Hub lento com a etapa que explica o atraso; lojas que cancelam fora da curva; loja sem entregas (tirar do ar); SLA no pico; pedidos presos no fluxo; queda de volume; subsídio de frete. Cada alerta traz um drill-down de um clique. |
| **Agente do recorte** | Sem API key: regras e estatísticas locais. Com `OPENROUTER_API_KEY`: LLM com **tool calling**: escolhe entre KPIs, quebras, alertas e série temporal, mas o recorte é aplicado pelo servidor, então o modelo não consegue sair dele. A UI mostra quais ferramentas foram consultadas. |
| **Gráficos (ECharts)** | Tendência com zoom que vira período do filtro, etapas do ciclo por hub (clique filtra), mapa de calor dia × hora, dispersão de lojas com seleção retangular para filtrar um grupo. |
| **Tabelas (TanStack)** | Ranking por hub/loja/cidade/canal/modal/pagamento; pedidos brutos com paginação e ordenação no servidor e rolagem virtualizada. |
| **Compartilhar e exportar** | O recorte fica na URL (`?city=Curitiba&hub=8`). Exporta CSV dos pedidos, briefing em Markdown e PDF da tela. |

![Tendência](assets/tendencia.png)
![Etapas por hub e mapa de calor](assets/operacao.png)
![Lojas e ranking](assets/lojas.png)

## Arquitetura

```
frontend/ (Vercel)                         backend/ (Render)
Astro: casca estática, zero JS     HTTP    FastAPI + Pydantic
 └─ ilhas React (client:load/visible) ───▶  ├─ repository.py  DuckDB em memória ← data/orders.parquet
    Nanostores: recorte ↔ URL               ├─ alerts.py      regras → alerta + ação + drill-down
    TanStack Query: cache, cancelamento     └─ agent/         LLM com tools → contexto → regras locais
    ECharts · TanStack Table/Virtual
    Tipos TS gerados do OpenAPI
```

Decisões que vale conhecer:

- **DuckDB sobre Parquet, sem banco.** O dataset tem 9,4 MB em Parquet; o DuckDB carrega tudo em memória e agrega 369 mil linhas em ~50 ms. O SQL recebe valores só por parâmetros, e colunas e ordenações vêm de listas fixas.
- **Um contrato de filtro.** `Filters` (Pydantic) é a query string da API e da URL do navegador. Os tipos TypeScript são gerados do OpenAPI: se um schema muda, o `astro check` quebra no build.
- **Ilhas que se falam sem Provider global.** O filtro grava num átomo Nanostores; KPIs, gráficos, tabelas e agente são ilhas separadas que escutam o mesmo átomo e compartilham um `QueryClient`.

## Limpeza dos dados

O ETL (`backend/scripts/build_parquet.py`) junta os 7 CSVs num parquet desnormalizado. Estas decisões mudam números, e o rodapé do app também as mostra:

- **Fuso:** os horários do dataset estão em UTC (picos às 15h e 22h). Convertidos para Brasília, os picos ficam no almoço e no jantar.
- **SLA por segmento:** food ≤ 60 min, goods ≤ 120 min. Goods tem um ciclo bem mais longo e não dá para medir pela mesma régua.
- **Pedidos presos:** ciclo > 4h (4,9% das entregas, concentradas em goods) fica fora das medianas e do SLA e gera um alerta de dados próprio.
- **Outliers:** pedidos acima de R$ 5 mil (63, como um de R$ 100.000,11) ficam fora do GMV. Distâncias acima de 50 km e métricas negativas viram nulo.
- **Várias entregas/pagamentos por pedido:** vale a última entrega concluída e o meio de pagamento de maior valor.

## Rodar localmente

```bash
# backend: Python 3.11+
cd backend
python -m venv .venv && .venv\Scripts\activate      # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload                       # http://localhost:8000/docs
pytest                                              # 20 testes, com parquet sintético

# frontend: Node 20+
cd frontend
npm install
npm run dev                                         # http://localhost:4321
```

O parquet processado já vem no repositório. Para refazer o ETL, coloque os CSVs do Kaggle em `backend/data/raw/` e rode `python scripts/build_parquet.py`.

Agente com LLM (opcional): copie `backend/.env.example` para `backend/.env` e preencha `OPENROUTER_API_KEY`. O backend também lê o `.env` da raiz.

## Deploy

1. **Backend (Render):** *New → Blueprint* apontando para este repo (usa `render.yaml`). Preencha `CORS_ORIGINS` com a URL da Vercel e, se quiser, `OPENROUTER_API_KEY`. O plano grátis dorme depois de 15 min sem acesso; o app mostra "acordando o servidor" enquanto isso.
2. **Frontend (Vercel):** importe o repo com *Root Directory* = `frontend` e defina `PUBLIC_API_URL` com a URL do Render.

## Métricas de uso

_Preencher após o deploy (Vercel Analytics + logs do Render)._

| Métrica | Valor |
|---|---|
| Visitantes (30 dias) | — |
| Perguntas ao agente | — |
| Alertas com drill-down clicado | — |

## Stack

Astro 7 · React 19 · TypeScript · Tailwind CSS 4 · Lucide · Apache ECharts 6 · Nanostores · TanStack Query / Table / Virtual · Python · FastAPI · Pydantic · DuckDB · Parquet · OpenRouter (API compatível com OpenAI).

Dados: Delivery Center, Kaggle. Os nomes de lojas vêm anonimizados no próprio dataset. Projeto independente, sem relação com o iFood.
