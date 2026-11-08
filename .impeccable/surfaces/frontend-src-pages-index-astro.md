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

OWN-WORLD: Base cinza fria (campo #EFEFEF, superfícies brancas, bordas #DCDCDC, cantos 8px), faixa vinho #3D0B1F no topo, Archivo com eixo de largura (condensada em caixa-alta só para rótulos e cabeçalho de comanda), algarismos tabulares. Vermelho próprio #D92B20 só em crítico e na ação principal; botões neutros em tinta. Food = framboesa, goods = oliva-lima. Comandas com picote no topo e linha tracejada; ação em bloco de tinta.

STORY: O operador vê o recorte nos chips, lê três KPIs com tendência e onset, percebe a fila de comandas, abre a primeira, executa a ação ou aplica o drill-down, pergunta ao agente.

FIRST VIEWPORT: Faixa vinho de 64px (nome, links, status da API, tema). Barra de filtros branca fixa. Grade: à esquerda KPIs (3 heróis + linha de volume) e agente; à direita (~460px) fila de comandas, a primeira aberta com bloco Ação e botões.

FORM: Comanda (candidata 3 da lista ordenada). seed:0702dd4e001757de. Signature: fila de comandas, uma aberta por vez. Raises: uma comanda aberta (feed); tabelas em um só corpo (timetable); severidade por forma (exposure); números em grade (crouwel); camada sem sombra (acetate).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
