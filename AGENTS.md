# AGENTS.md — Dashboard + Agente de Insights (Food Delivery Analytics)

Este arquivo define as regras, stack, estrutura e convenções para o projeto **dashboard-insights-ia** (ou nome temático como `food-delivery-insights`).

O objetivo é construir um **dashboard interativo deployado** com gráficos Plotly/Streamlit e um **agente de insights integrado** que responde perguntas sobre os dados filtrados, gera alertas e sugere ações. O projeto cobre o requisito de “ferramentas internas deployadas, dashboards ou agentes” do portfólio do estágio iFood.

Tema preferencial: **food delivery analytics** (mock de pedidos, restaurantes, cidades brasileiras) para ficar alinhado ao iFood.

## Contexto e Diferencial

Projetos similares existentes (referência de pesquisa):

| Projeto / Tipo | Stack principal | O que faz bem | O que falta (oportunidade) |
|----------------|------------------|---------------|----------------------------|
| Vários e-commerce Streamlit (RFM, cohorts) | Streamlit + Plotly + pandas | Dashboards limpos e KPIs | Pouco ou nenhum agente de insights integrado |
| munas-git/AI-powered-sales-dashboard | Streamlit + LangChain + OpenAI | Chat agent sobre dados de vendas | Tema genérico, menos foco em alertas/ações |
| syedsaadali11/Ai-Data-Analyst-Agent | Streamlit + LangGraph | Upload CSV → perguntas + visualizações | Não é um dashboard temático fixo com filtros ricos |
| Food delivery analysis projects (Swiggy/Zomato style) | Streamlit + Plotly | Tema delivery, KPIs operacionais | Quase nenhum tem agente de chat + alertas |
| Dashboards Olist / marketplace BR | Streamlit + DuckDB | Dados reais brasileiros | Geralmente sem agente conversacional |

**Nosso diferencial para o portfólio:**
- Tema food delivery (pedidos, restaurantes, tempo de entrega, nota, promo, cidades BR).
- Dashboard com filtros ricos + agente que **analisa o estado filtrado** (não o dataset inteiro).
- Agente gera **alertas** e **sugestões de ação** concretas (não só responde “qual é o top”).
- Deploy real no Streamlit Cloud + README com prints, link e métricas de uso.
- Código limpo e modular para que agentes de coding possam iterar facilmente.

## Stack Recomendada

| Camada | Tecnologia | Motivo |
|--------|------------|--------|
| Linguagem | Python 3.11+ | Padrão |
| Interface | **Streamlit** | Deploy gratuito e rápido no Streamlit Cloud |
| Visualização | **Plotly** (plotly.express) | Interativo, bonito, nativo no Streamlit |
| Dados | **pandas** (ou Polars se quiser performance) | Suficiente para mock + filtros |
| Dados mock | Gerador próprio (numpy + pandas) | Controle total, sem depender de datasets externos |
| Agente | Tool calling simples ou LangGraph leve | Respostas sobre o DataFrame filtrado |
| LLM | LiteLLM ou OpenAI / Groq / Gemini | Flexibilidade; modo local como fallback |
| Structured | Pydantic (opcional) | Se quiser structured insights/alertas |
| Config | python-dotenv + Streamlit Secrets | API keys no Cloud |
| Testes | pytest (opcional) | Validar gerador de dados e funções de insight |

**Recomendação prática:**
- Começar com agente **local** (regras + estatísticas) + fallback LLM.
- Usar `st.session_state` para o histórico do chat.
- Cachear o dataset com `@st.cache_data`.

## Estrutura de Pastas Sugerida

```
dashboard-insights-ia/
├── AGENTS.md                  # Este arquivo
├── README.md                  # Overview + link do deploy + prints + métricas de uso
├── requirements.txt
├── .env.example
├── .gitignore
├── .streamlit/
│   └── config.toml            # (opcional) tema, layout
├── app.py                     # Entrada principal do Streamlit
├── data/
│   └── generator.py           # Geração de dados mock food delivery
├── dashboard/
│   ├── __init__.py
│   ├── filters.py             # Lógica de filtros
│   ├── metrics.py             # Cálculo de KPIs
│   └── charts.py              # Funções que retornam figuras Plotly
├── agent/
│   ├── __init__.py
│   ├── insights.py            # Agente local + integração LLM
│   └── prompts.md             # System prompt do agente (versionado)
├── assets/                    # (opcional) logos, screenshots para o README
└── tests/
    └── test_generator.py
```

## Convenções e Regras para Agentes

### O que os agentes devem fazer
1. **Dados mock realistas**: Gerar pedidos com cidades brasileiras, culinárias, tempo de entrega, nota, promo, tipo de cliente, status. Usar distribuições realistas (lognormal para valor, gamma para tempo).
2. **Filtros afetam tudo**: KPIs, gráficos e agente devem operar sobre o DataFrame filtrado.
3. **Agente consciente do contexto**: O agente recebe um resumo estatístico do estado filtrado atual (não o dataset bruto inteiro).
4. **Alertas e ações**: Além de responder perguntas, o agente deve identificar problemas (tempo alto, nota baixa, cancelamento alto) e sugerir ações.
5. **Modo dual**: Funcionar sem API key (regras locais) e melhorar com LLM quando houver chave.
6. **Session state**: Manter histórico do chat com `st.session_state.messages`.
7. **Deploy-ready**: Código deve rodar limpo no Streamlit Cloud (sem arquivos locais obrigatórios, secrets via painel).
8. **README completo**: Incluir link do app deployado, prints, e métricas de uso (mesmo que sejam do próprio uso).

### O que os agentes NÃO devem fazer
- Hardcodar nomes de restaurantes ou cidades nos gráficos (usar os dados dinâmicos).
- Fazer o agente responder sobre dados não filtrados quando o usuário aplicou filtros.
- Depender de API key para o app funcionar (modo local obrigatório).
- Gerar gráficos que não respeitem o filtro atual.
- Colocar lógica de negócio pesada dentro do `app.py` (separar em módulos).

## Métricas e Documentação para o Portfólio

No README incluir:

- Link do app no Streamlit Cloud
- 2–4 screenshots (KPIs + gráficos + chat do agente)
- Seção “Métricas de uso” (acessos, perguntas feitas ao agente, feedback)
- Descrição clara do problema que o dashboard resolve (“operador de food delivery precisa de visão rápida + insights acionáveis”)

## Fluxo Mínimo Viável (MVP)

1. Gerar dados mock de pedidos (últimos 90 dias).
2. Sidebar com filtros (período, cidade, culinária, restaurante, tipo de cliente).
3. KPIs principais no topo.
4. Abas ou seções com gráficos Plotly (tendência, ranking, operação).
5. Chat do agente no final da página que responde sobre o estado filtrado.
6. Deploy no Streamlit Cloud.
7. README com prints e link.

## Melhorias Futuras (opcional)

- Mapa de calor por cidade (plotly mapbox ou folium).
- Alertas proativos no topo do dashboard (não só no chat).
- Export de relatório PDF do estado atual.
- Integração com dados reais (CSV upload ou API mock).
- Modo multi-página (st.navigation ou multipage).

---

**Última atualização:** 2026-10-27. Foco em diferencial de portfólio: dashboard temático food delivery deployado + agente que gera alertas e ações sobre dados filtrados.
