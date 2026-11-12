---
target: frontend/src/pages/index.astro
total_score: 31
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 0
target_identity: "file:C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
target_fingerprint: "sha256:aa50af0ff12825f78aadecd57b8be18bdd9fcb65ea20e6cf5cb6c3b15eca1eff"
target_path: "C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
timestamp: 2026-11-12T18-05-36Z
slug: frontend-src-pages-index-astro
---
Method: dual-agent (A: `de28d591`, revisão de design · B: `d715a63c`, detector e navegador; ambos Grok 4.7)

## Saúde do design

| # | Heurística | Nota | Ponto principal |
|---|---|---|---|
| 1 | Visibilidade do estado do sistema | 3 | Em 320×700 o botão flutuante do agente cobre parte do bloco Ação. |
| 2 | Correspondência com o mundo real | 4 | Comanda, hub, prazo e pt-BR corretos; "GMV" divide o cabeçalho entre termo de glossário e ícone de ordenar. |
| 3 | Controle e liberdade | 3 | "mais N" só avança o trilho; não há volta equivalente. |
| 4 | Consistência e padrões | 3 | O popover de filtro da tabela de pedidos usa `shadow-lg`, e o `DESIGN.md` proíbe sombras. |
| 5 | Prevenção de erros | 3 | `Nowhere` é recusada pelo nome; `2031-01-01` é aceita e esvazia todos os painéis. |
| 6 | Reconhecer em vez de lembrar | 3 | Os limites 85%/80% e 6%/9% ficam no rodapé, longe dos KPIs. |
| 7 | Flexibilidade e eficiência | 3 | Ordenar por GMV e Subsídio depende de um ícone de 12×12. |
| 8 | Estética e minimalismo | 3 | Os primeiros 900px ainda carregam seis KPIs e o topo de Tendência. |
| 9 | Recuperação de erros | 3 | Fechar o aviso apaga a única frase que diz que `Nowhere` saiu do recorte. |
| 10 | Ajuda e documentação | 3 | As formas de severidade (cheia, vazada, traço) não são explicadas no trilho. |
| **Total** | | **31/40** | **Bom** |

## Veredito de especificidade

**Avaliação da revisão:** a metade de cima é deste produto: faixa vinho, trilho picotado, uma comanda aberta por vez e o bloco Ação em tinta. A metade de baixo (tendência, mapa de calor, dispersão, ranking de 10 colunas, pedidos) é uma pilha analítica comum com os mesmos tokens; outro produto poderia reaproveitá-la.

**Detector:** 4 achados, todos `border-accent-on-rounded` (`PeriodPresets.tsx:34` e `:166`, `Panel.tsx:275` e `:288`). Falsos positivos: sublinhado de aba com canto só no topo.

**Sobreposição ao vivo:** a injeção funcionou com o servidor em primeiro plano (o modo `--background` saiu sozinho). O console registrou um grupo com quatro linhas: `flat-type-hierarchy` (corpo 13,6px, h2 16px, h3 18px, passo de 1,18), `gradient-text`, `bounce-easing` e `marquee`. Os três últimos parecem vir do texto e do esqueleto de carregamento e da curva `--ease-bounce` do selo; não conferido elemento a elemento. A aba ficou oculta, sem sobreposição visível para o usuário.

## Impressão geral

Os consertos da rodada anterior se confirmaram nas medições: barra em 81px de 1024 a 1440, "mais 2/3/5" no trilho, filtro do ranking sempre dentro da área visível, amostras pequenas no fim nos dois sentidos, e nenhum texto abaixo do contraste mínimo nos dois temas. O que resta está concentrado no celular: o botão do agente ainda encosta na Ação, e a tabela de pedidos ficou de fora do ajuste de toque que o ranking recebeu.

## O que funciona

- **Amostra pequena não vence o ranking.** Por cancelamento decrescente, o topo é Elixir Shopping (10.249 pedidos, 30,8%); os cinco hubs de 1 a 89 pedidos ficam no fim nos dois sentidos, pontilhados e com "(amostra pequena)".
- **URL ruim não finge.** Com `?city=Nowhere&start=2031-01-01`, a cidade sai com aviso nominal e as comandas e os KPIs dizem que a base vai de 01/01/2021 a 30/04/2021.
- **Uma comanda por vez, com a saída dentro dela.** Abrir a Nº 02 fecha a Nº 01; "Ver só Color Shopping" pôs `?hub=22` e o SLA foi a 80,0% Crítico.

## Problemas prioritários

**[P2] O botão do agente ainda cobre a Ação em 320×700**
- **Por que importa:** o botão (48×48) sobrepõe 28×48 do bloco Ação e 12×48 do texto da comanda. Em 768×1024 ele cobre 40×40 do KPI "No prazo". É a terceira rodada com essa sobreposição; rolar tira o texto de baixo.
- **Correção:** reservar à direita da comanda aberta, abaixo de `lg`, uma faixa da largura do botão, ou subir o botão para fora do bloco enquanto a comanda aberta está na faixa inferior.
- **Comando sugerido:** `/impeccable adapt`

**[P2] Filtros de coluna da tabela de pedidos têm 24×24 no celular e o popover tem sombra**
- **Por que importa:** Status, Hub, Segmento, Canal e Modal medem 24×24 em 768 e 320, enquanto o ranking já tem 44px. O popover usa `shadow-lg` (`OrdersTable.tsx:171`), contra a regra de não usar sombras.
- **Correção:** `max-lg:size-11` no botão (`OrdersTable.tsx:156`) e trocar a sombra pela borda do popover de "Mais filtros".
- **Comando sugerido:** `/impeccable adapt`

**[P2] O título "Central de Operações" é cortado na vertical**
- **Por que importa:** o `h1` tem `leading-none` e `sm:truncate` (`index.astro:46`); a altura do conteúdo é 26px numa caixa de 24px (20 em 18 no celular), o que apara cedilha e til. Medido só pela avaliação A; não conferido na tela.
- **Correção:** altura de linha acima de 1 no título e tirar o `truncate`, já que a largura cabe.
- **Comando sugerido:** `/impeccable typeset`

**[P3] Ordenar por GMV e Subsídio é um ícone de 12×12**
- **Por que importa:** a área clicável chega a 24×24, mas o alvo pintado é minúsculo ao lado do termo de glossário, diferente das outras oito colunas.
- **Correção:** dar ao ícone a mesma altura de 24px dos outros cabeçalhos, com o termo de glossário ao lado.
- **Comando sugerido:** `/impeccable polish`

**[P3] A folha de filtros do celular mostra 16 controles de uma vez**
- **Por que importa:** quatro períodos, duas datas, seis seletores e três botões numa rolagem só. Os grupos Lugar e Pedido ajudam, mas o desktop já esconde Segmento, Canal e Modal atrás de "Mais filtros".
- **Correção:** recolher o grupo Pedido na folha, aberto quando há filtro ativo nele.
- **Comando sugerido:** `/impeccable distill`

## Alertas por persona

**Alex (usuário avançado):** depois do link de pular, ainda passa por API, tema, Período, três seletores, Mais filtros, agente e Compartilhar antes da primeira comanda. "mais N" não tem volta. O clique real em "mais 2" rolou o trilho na avaliação A (0 para 220); na B, com a aba oculta, não rolou.

**Sam (teclado e leitor de tela):** Esc real em 1440 no tema escuro fechou o agente e devolveu o foco ao campo de pergunta. A ordem de Tab, o Esc da folha de filtros e o de "Mais filtros" não foram testados: a aba de teste da B não entregou teclas. Zoom de 200% também não foi feito.

**Casey (celular, uma mão):** botão do agente sobre a Ação, filtros de coluna de 24px e o preset "Dia" com 40,8px de largura. O drill vermelho da comanda fica em y=894 numa tela de 700px.

## Observações menores

- A tabela de pedidos rola na horizontal de 1280px para baixo (1318 de 1166px); a coluna "Segmento" mais larga aumentou isso.
- Em 320px o título "Hub lento: Color Shopping" de uma comanda trunca (145 de 102px).
- As seis células "… min fora do SLA" continuam aparecendo como truncadas (83 de 69px); atribuído antes ao texto só para leitor de tela, ainda não conferido na tela.
- No fim da página em 320px o botão do agente cobre parte do rodapé (48×12 e 48×20).
- Os segmentos de Período medem 34px dentro de uma moldura de 40px no desktop.
- "Quebrar por" segue com sete opções.
- `prefers-reduced-motion` não pôde ser emulado; a geometria no tema escuro não foi medida, só o contraste.

## Perguntas para pensar

1. Quando o botão do agente e o bloco Ação disputam o mesmo canto em 320px, qual dos dois se move?
2. Uma data fora da base deveria ser recusada como `Nowhere`, ou o recorte vazio com o intervalo escrito ensina mais?
3. Seis comandas no notebook são a fila, ou o notebook também deveria parar em quatro e usar "mais"?
