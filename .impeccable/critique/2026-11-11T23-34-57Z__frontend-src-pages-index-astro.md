---
target: critique (index)
total_score: 28
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
target_fingerprint: "sha256:35b1e61cd7a05bc71ee55bd7871f1e8ce735fcc67b3f8ef643e3499c0537d5fe"
target_path: "C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
timestamp: 2026-11-11T23-34-57Z
slug: frontend-src-pages-index-astro
---
Method: dual-agent (A: a3aaaad28e1f9207e · B: aad559861146230da)

# Crítica de design: Central de Operações (`frontend/src/pages/index.astro`)

## Design Health Score

| # | Heurística | Nota | Problema principal |
|---|---|---|---|
| 1 | Visibilidade do estado do sistema | 3 | A espera do agente mediu 13,9 s e 28,7 s com só um contador e a frase do servidor dormindo, que está errada quando o lento é o LLM |
| 2 | Correspondência com o mundo real | 3 | Jargão vaza: `get_kpis, get_breakdown(hour)`, "stuck rate", p90, GMV, "Subsídio de frete -R$ 0,11/entrega" sem explicação |
| 3 | Controle e liberdade | 3 | Não dá para cancelar a pergunta ao agente; "Nova conversa" apaga o histórico sem desfazer |
| 4 | Consistência e padrões | 3 | Presets de período são quatro paradas de Tab com `aria-pressed`; os segmentados dos painéis são radiogroup com foco itinerante |
| 5 | Prevenção de erros | 3 | Valor inválido na URL é descartado em silêncio e continua na URL; CSV de 369 mil linhas sem aviso de tamanho |
| 6 | Reconhecer em vez de lembrar | 3 | O KPI não mostra a meta no card; não há legenda de severidade |
| 7 | Flexibilidade e eficiência | 2 | Só Ctrl K; sem teclas entre comandas; gráficos só com mouse; 15 paradas de Tab até a primeira comanda |
| 8 | Estética e minimalismo | 3 | Sete botões "Perguntar" mais o campo do agente; linha de delta vazia nos KPIs do recorte padrão |
| 9 | Recuperação de erros | 3 | `ErrorState` tem "tentar de novo", mas imprime a mensagem crua |
| 10 | Ajuda e documentação | 2 | Nada diz ao visitante frio que KPIs, comandas e agente respondem sobre o mesmo recorte |
| **Total** | | **28/40** | **Bom (base sólida, pontos fracos localizados)** |

## Veredito de especificidade

**Avaliação do revisor.** A primeira dobra é autoral e entrega a tese: fila numerada de comandas picotadas, uma aberta com bloco **Ação** em tinta invertida, um único botão vermelho, severidade por forma, faixa vinho, zero sombras.

A página cai no padrão da categoria em três lugares:
- **Abaixo dos KPIs:** quatro painéis de gráfico e duas tabelas formam uma grade de analytics comum.
- **KPIs heróis:** número mais sparkline, sem meta, sem nada que diga "fora".
- **Agente:** dock de chat à direita cuja resposta é prosa, não comanda.

**Varredura determinística.** O CLI achou 4 avisos, todos `border-accent-on-rounded`, em `filters/PeriodPresets.tsx:29,104` e `ui/Panel.tsx:192,205`. Falsos positivos: é o indicador deslizante do segmentado, fixado no DESIGN.md.

No navegador, 3 achados de folha de estilo:
- **`gradient-text` e `marquee`:** o mesmo `shimmer-text` da espera do agente, fixado no DESIGN.md. Falsos positivos.
- **`bounce-easing`:** o token `--ease-bounce` (`global.css:57`), usado uma vez no ponto de status do agente. Fixado no DESIGN.md, mas bate de fato com a regra.

**Overlays.** Injeção funcionou; só um banner, sem contornos por elemento.

## Impressão geral

A página abre com quem faz o quê e quando, antes de qualquer gráfico. Falta o passo dois do trabalho: os KPIs não dizem se algo está fora, e o agente demora e termina em texto. A maior oportunidade é fazer a resposta do agente e o KPI falarem a língua da comanda.

## O que funciona

1. **Composição com a ação primeiro.** Fila, comanda aberta e bloco Ação ficam acima dos KPIs.
2. **Honestidade do recorte.** Filtros na URL, chips repetidos no cabeçalho do agente, "amostra pequena" no lugar do delta.
3. **Sistema visual disciplinado.** Vermelho só em crítico, delta piorando e no botão de drill-down; dados em vinho; anéis de foco em tinta.

## Problemas prioritários

**[P1] Os KPIs não dizem se algo está fora**
- **O quê:** no recorte padrão os três heróis mostram 86,2% / 41,2 min / 4,6% com a linha de delta vazia, sem meta e sem palavra de status (`KpiStrip.tsx:71`).
- **Por que importa:** ler se SLA, preparo ou cancelamento está fora é o segundo passo do trabalho, e na primeira tela só as comandas respondem isso.
- **Correção:** referência em cada herói (meta ou valor do dataset inteiro como régua na sparkline, mais "x p.p. abaixo"). Sem período anterior, comparar com o dataset inteiro.
- **Comando sugerido:** `/impeccable shape`

**[P1] O agente é lento, opaco e termina em prosa**
- **O quê:** respostas de 14 a 29 s com contador simples; sem cancelar (`client.ts:80` aceita `signal`, `AgentChat.tsx:232` não passa); pergunta pré-preenchida num input de uma linha; resposta sem botões; a entrada parece busca.
- **Por que importa:** um recrutador com três minutos gasta um sexto deles num shimmer, e a prova de "travado no recorte" é uma linha cinza com nomes de tool.
- **Correção:** resposta das regras locais na hora, LLM substitui depois; `AbortSignal` e "Cancelar"; textarea que cresce; botões de drill-down para as entidades citadas; nomes de tool em português.
- **Comando sugerido:** `/impeccable shape`

**[P2] O caminho por teclado é longo e pula os gráficos**
- **O quê:** sem skip link, barra de filtros sem landmark, 15 paradas até a primeira comanda; clique em barra e brush do scatter só com mouse; fila sem setas.
- **Correção:** skip link para `#comandas`, foco itinerante nos presets e na fila, `role="search"` na barra, tabela de ranking como rota de teclado.
- **Comando sugerido:** `/impeccable audit`

**[P2] A marcação de evidência parece um gráfico desabilitado**
- **O quê:** `StagesChart.tsx:78` apaga barras sem evidência para 28% e o hub marcado fica na última linha. Com o dock aberto a etiqueta do KPI corta em "COMANDA Nº 0".
- **Correção:** fixar o hub marcado na primeira linha, esmaecer para 45–50%, etiqueta compacta nos heróis abaixo de uma largura de contêiner.
- **Comando sugerido:** `/impeccable polish`

**[P2] Cabeçalho mobile quebra em duas linhas**
- **O quê:** em 375px mede 100px, com status e tema órfãos na segunda linha (`index.astro:40,44`: `flex-wrap` com título `shrink-0`). Na folha de filtros, presets 38px, remover chip 24px, "Limpar recorte" 33px, contra o piso de 44px.
- **Correção:** `flex-nowrap` com título truncando abaixo de `sm`; subir os três controles para 44px.
- **Comando sugerido:** `/impeccable adapt`

## Carga cognitiva

Três de oito itens falham (moderada): escolhas mínimas, revelação progressiva e memória de trabalho. Mais de quatro opções visíveis em: barra de filtros (nove controles), fila (seis comandas), cabeçalho de Tendência (sete), ranking (dez colunas, filtro por linha, sete quebras), pedidos (doze colunas). Abaixo da dobra tudo sempre expandido: 3.070px no desktop, 5.157px no mobile.

## Jornada emocional

- **Pico:** a primeira dobra, que abre numa ação impressa.
- **Vale 1:** o drill-down. A fila encolhe de 6 para 2, a nova Nº 01 não tem botão principal, a comanda original some.
- **Vale 2:** a espera do agente.
- **Fim:** a resposta é boa, mas é um bloco de texto no fundo do dock.

## Alertas por persona

**Alex:** só Ctrl K; sem teclas para comandas e drill-down; sem recortes salvos; envio bloqueado durante a espera; "Quebrar por" não vai para a URL.

**Sam:** 15 paradas sem skip link; gráficos em canvas só com `aria-label`; estado esmaecido e `series-soft` muito fracos. Bom: `aria-live` em KPIs, comandas e agente; contraste de texto passa.

**Recrutador(a):** a frase que resume o produto é um subtítulo de 13px, escondido no mobile; o agente parece busca; nomes anonimizados parecem bug; sem próximo passo depois do drill-down.

## Observações menores

- Listas numeradas do agente viram marcadores (`AgentChat.tsx:170`).
- O log do agente rola para o fim da resposta.
- Aviso do React ao enviar pergunta: "Cannot update a component while rendering a different component (AgentConversation)".
- Recorte de um dia mostra "+79,3% (melhorou)" sobre 52 pedidos.
- Botão flutuante do agente no mobile cobre o canto da comanda aberta.
- No tema escuro o bloco Ação é mais forte que o vermelho.
- Cabeçalho desktop com 94px contra 64px na especificação.
- Brief de superfície desatualizado em relação ao DESIGN.md.
- Não confirmado: painéis desistem após 2 tentativas (~4,5 s, `query.tsx:17`) enquanto o cabeçalho diz "Acordando o servidor (até ~40 s)".

## Perguntas para pensar

1. Se cada alerta é uma comanda, por que a resposta do agente não é uma também?
2. A página ficaria mais forte se tudo abaixo de Tendência nascesse fechado e abrisse só como evidência da comanda em mãos?
3. Qual é o verbo aqui para "tratada"?
