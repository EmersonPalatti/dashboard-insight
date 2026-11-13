---
version: 1
slug: "frontend-src-pages-index-astro"
primary_target: "frontend/src/pages/index.astro"
related_targets: []
---

# Surface: Central de Operações (index)

Mode: Operate. Visitor: recrutador fazendo o trabalho do operador de hub/praça sobre um recorte. Tarefa: filtrar, ler se SLA/preparo/cancelamento está fora, abrir o alerta e sair com uma ação.
Constraints: PRODUCT.md (sem identidade oficial do iFood, funciona sem chave, recorte em tudo), tema claro e escuro.

## Direction contract

THESIS: Cada alerta é uma comanda aberta (número, hub, prazo, ação impressa no rodapé). Recusa o grid de cards SaaS com borda colorida à esquerda e o painel kraft/papel quente.

OWN-WORLD: Base cinza fria (campo #ECECEC, superfícies brancas, bordas #DCDCDC, cantos 8px / 4px internos), faixa vinho #3D0B1F no topo, Libre Franklin (400–700) no texto, rótulos, controles e gráficos, e Zilla Slab (500–700) só em números de destaque (`figure`), identidade `cond` das comandas e nome do produto (`font-slab`), com algarismos tabulares. Vermelho próprio #D92B20 só em crítico e na única ação principal da comanda aberta; série de dados em vinho #7A1E3D; botões secundários e filtros ativos em tinta. Comandas na fila com picote no topo e linha tracejada; ação em bloco `action-block`.

STORY: O operador vê o recorte nos chips, percebe a fila de comandas no topo, abre uma comanda e sai com a ação ou drill-down, checa o contexto nos KPIs e gráficos e pergunta ao agente sobre o recorte.

FIRST VIEWPORT: Faixa vinho de 64px (`56px` abaixo de `sm`, com nome, links, status da API e tema). Barra de filtros branca fixa (104px no desktop, duas linhas: controles de recorte + `Mais filtros` + `AgentAskButton` fixo na linha 1; chips e `Compartilhar` na linha 2). Corpo em largura total: trilho de comandas + comanda aberta em faixa larga, seguido pelos KPIs em duas faixas (`3fr` operação + `1fr` volume empilhado), tendência, etapas | dia×hora, dispersão de lojas, ranking e pedidos. O painel do agente (`AgentDock`) fica fora do grid (`dock` ≥1280px, `float` 1024–1279px, `sheet` <1024px).

FORM: Comanda (candidata 3 da lista ordenada). seed:0702dd4e001757de. Signature: fila de comandas, uma aberta por vez. Raises: uma comanda aberta (feed); tabelas em um só corpo (timetable); severidade por forma (exposure); números em grade (crouwel); camada sem sombra (acetate).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
