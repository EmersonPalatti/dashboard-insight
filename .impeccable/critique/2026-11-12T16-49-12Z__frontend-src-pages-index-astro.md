---
target: frontend/src/pages/index.astro
total_score: 30
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 1
target_identity: "file:C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
target_fingerprint: "sha256:aa50af0ff12825f78aadecd57b8be18bdd9fcb65ea20e6cf5cb6c3b15eca1eff"
target_path: "C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
timestamp: 2026-11-12T16-49-12Z
slug: frontend-src-pages-index-astro
---
Method: dual-agent (A: Crítica A, revisão de design, Grok 4.7 · B: Crítica B, detector e navegador, Grok 4.7)

## Design Health Score

| # | Heurística | Nota | Ponto principal |
|---|---|---|---|
| 1 | Visibilidade do estado do sistema | 3 | Em 1024px o trilho mostra 961px de 1373px de comandas; a contagem é a única pista das que ficaram fora |
| 2 | Correspondência com o mundo real | 3 | O agente local diz "6 alerta(s) no recorte" (`local.py:122`) |
| 3 | Controle e liberdade | 3 | Esc deixa de fechar o agente depois que uma pergunta sugerida é enviada |
| 4 | Consistência e padrões | 3 | Ícone "Filtrar por…" do ranking tem 22×22 sem área de toque ampliada; o resto da página tem 24 ou 44px |
| 5 | Prevenção de erros | 3 | Ordenar por cancelamento põe no topo hubs com 2, 13 e 89 pedidos a 100% |
| 6 | Reconhecimento em vez de memória | 3 | Cabeçalhos "Seg." e "Cancel." continuam abreviados |
| 7 | Flexibilidade e eficiência | 3 | Há presets, URL e Ctrl+K; não há ação sobre mais de uma comanda |
| 8 | Estética e minimalismo | 3 | Em 320×700 o botão flutuante do agente cobre os últimos 48px do bloco Ação |
| 9 | Recuperação de erros | 3 | Data fora da base (2031) vira "Sem pedidos" sem dizer que a base vai de jan a abr/2021 |
| 10 | Ajuda e documentação | 3 | Rodapé e glossários cobrem as regras; "Seg." e os traços do ranking não têm explicação |
| **Total** | | **30/40** | **Bom** |

## Veredito de especificidade

**Avaliação de design:** a página é deste produto. A faixa vinho, o trilho picotado, o carimbo `Nº 01 · SLA` e o bloco Ação invertido não serviriam a outro painel sem mudar de identidade. Os gráficos e as duas tabelas são um conjunto analítico genérico vestido com os mesmos tokens. O brief da superfície ainda descreve comandas numa coluna de 460px à direita; o que está no ar é o trilho acima dos KPIs, como diz o `DESIGN.md`.

**Detector:** 4 achados, todos `border-accent-on-rounded`, em `PeriodPresets.tsx:34` e `:166` e `Panel.tsx:275` e `:288`. Os quatro são falsos positivos: a borda é inferior e o raio é só no topo (indicador de aba).

**Overlay:** não há overlay visível. O `live-server` saiu logo depois de subir e a injeção do `detect.js` falhou.

## Impressão geral

A primeira tela continua operável e disciplinada, e os truncamentos da rodada anterior sumiram: nenhuma largura tem rolagem horizontal de página, e o aviso de URL inválida some ao escolher um período. O que sobrou está no caminho até a ação fora do desktop: alvos de toque do ranking, o botão flutuante sobre o bloco Ação e o teclado dentro do agente.

## O que funciona

- **O trilho reimprime com o recorte.** "7 dias" trocou a URL, a comanda aberta e a linha dos KPIs juntos; "Limpar recorte" voltou para `/`.
- **Um só controle vermelho.** Na comanda aberta, só o drill é vermelho; Recolher, Ver no gráfico e Perguntar ao agente são neutros.
- **Contraste limpo nos dois temas.** O mínimo medido foi 4,86:1 no claro e 5,37:1 no escuro, em todos os grupos checados.

## Problemas prioritários

**[P1] Botão "Filtrar por…" do ranking tem 22×22 e sai da tela em telas estreitas**
- **Por que importa:** é o drill da linha do ranking. Fica abaixo do mínimo de 24px (WCAG 2.2 AA) em todas as larguras, e em 768px a coluna começa em x=1022 num contêiner de 671px.
- **Correção:** dar `hit-target` ao botão em `BreakdownTable.tsx:246`, com 44px abaixo de `lg`, e fixar a coluna do filtro à direita ou recolher Preparo, Trânsito e Subsídio.
- **Comando sugerido:** `/impeccable adapt`

**[P2] Esc para de fechar o agente depois de uma pergunta sugerida, e o foco não volta ao gatilho**
- **Por que importa:** a pergunta sugerida some ao ser clicada e o foco cai no `body`; como o Esc só é ouvido dentro do painel (`AgentDock.tsx:158`), a saída documentada falha. Quando o Esc funciona, o foco fica no "Fechar agente" já oculto. Ctrl+K ainda fecha.
- **Correção:** mover o foco para o campo de pergunta quando as sugestões saem, ouvir Esc na janela enquanto o painel está aberto e devolver o foco ao gatilho.
- **Comando sugerido:** `/impeccable harden`

**[P2] Em 320×700 o botão flutuante do agente cobre o fim do bloco Ação**
- **Por que importa:** o bloco Ação vai de y=498 a 697 e o botão ocupa y=636 a 684; o drill "Ver só…" fica em y=877, abaixo da dobra. É o mesmo tipo de sobreposição que ficou de fora em 768px na rodada anterior. Rolando, o texto sai de baixo.
- **Correção:** esconder o botão flutuante enquanto o bloco Ação da comanda aberta está na faixa inferior, ou encolhê-lo para só o ícone.
- **Comando sugerido:** `/impeccable adapt`

**[P2] Em 1024px a barra fixa mede 129px e três comandas ficam fora do trilho**
- **Por que importa:** o `DESIGN.md` pede 80px (81px em 1280 e 1440). Em 1024 as comandas 05 e 06 e a do agente ficam cortadas, só com a contagem e uma barra de rolagem fina como pista.
- **Correção:** deixar o campo do agente encolher antes de a linha quebrar em `lg`, e pôr um "mais N" no fim do trilho quando houver comandas fora.
- **Comando sugerido:** `/impeccable layout`

**[P2] Ordenar por cancelamento e data fora da base parecem respostas**
- **Por que importa:** quem pergunta "qual hub cancela mais" recebe um hub de 2 pedidos a 100%. Quem cola uma data de 2031 lê "Sem pedidos", que é verdade e incompleto.
- **Correção:** aplicar no ranking o mesmo piso de amostra dos KPIs (lógica no backend) e avisar na dica; no estado vazio, dizer o intervalo da base quando o período cai fora dele.
- **Comando sugerido:** `/impeccable harden`

## Alertas por persona

**Alex (usuário avançado):** depois de enviar uma pergunta sugerida, o foco cai no `body` e Esc não fecha o agente. Não há ação em lote no trilho.

**Sam (teclado e leitor de tela):** 32 botões de 22×22 no ranking sem área ampliada. Na folha de filtros do celular, o Esc não fechou o diálogo no teste automatizado; isso não foi confirmado com tecla real.

**Casey (celular, uma mão):** botão flutuante sobre o bloco Ação em 320×700, drill abaixo da dobra, e controles segmentados dos painéis com 30px de altura. A folha de filtros em si está bem: todos os botões têm 44px ou mais.

## Observações menores

- A comanda do agente (`Nº A01`) repete o título da `Nº 01`, "Hub lento: Color Shopping".
- Em 320px o título da comanda do agente trunca (102 de 145px).
- A tabela de pedidos rola na horizontal já em 1280px (1285 de 1166px).
- Título do trilho em Zilla Slab 15,2px peso 600; o `DESIGN.md` pede condensada 0,75rem peso 700 (`AlertsPanel.tsx:344`).
- "Quebrar por" tem sete opções visíveis; a folha de filtros empilha seis seletores sem agrupamento.
- No fim da página em 320px, o botão flutuante encosta 11px no texto do rodapé.
- As seis células "… min fora do SLA" apontadas como truncadas são, pelo código, o texto só para leitor de tela contado na largura (`OrdersTable.tsx:70`); não conferido na tela.

## Perguntas para pensar

1. A Ação diz "Tirar a loja do ar hoje" e o único botão filtra o recorte. O botão principal deveria levar o verbo operacional?
2. Uma barra de rolagem fina basta para as comandas fora do trilho em 1024px?
3. O ranking deveria recusar ordenar uma taxa enquanto a linha não passa do piso de amostra?
