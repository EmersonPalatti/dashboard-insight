---
target: frontend/src/pages/index.astro
total_score: 30
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
target_fingerprint: "sha256:840f74b5be4d29a216bfb52f3c4bb00dfc44a37c7c679760cb8f387fa91ce713"
target_path: "C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
timestamp: 2026-11-14T18-54-20Z
slug: frontend-src-pages-index-astro
closed: true
---
Method: dual-agent (A: 2244f337-b8a3-44a2-b53e-970a2f92aa62 · B: e9ca480a-de9d-441a-889b-9bb074921c5f)

### Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Cold start (~40 s), loading states e troca `rules → model` bem comunicados; porém os ícones de `toolbox` do `StoreScatter` dessincronizam `aria-pressed` do botão `"Selecionar área"` e a `FilterBar` sem filtros esconde qualquer linha de resumo. |
| 2 | Match System / Real World | 4 | Vocabulário nativo de operação logística em pt-BR, comandas térmicas numeradas, fuso de Brasília e glossário contextual (`<Term>`) em `GMV`, `Subsídio` e `p90`. |
| 3 | User Control and Freedom | 3 | `$filters` na URL, `Esc`, `Limpar recorte`, `Limpar zoom` e `Cancelar`/`Desfazer` no chat; porém o `AgentDock` em modo `float` (`1024–1279px`) cobre `.action-block` e KPIs da comanda aberta, e `FilterSheet` aplica alterações ao vivo sem caminho de cancelamento. |
| 4 | Consistency and Standards | 2 | Regressão responsiva na `FilterBar`: `ShareMenu` na linha 1 esmaga `Cidade`/`Hub`/`Loja` (`"Cida"` cortado e `"Todos"` suprimido em `1280px`; `"Cidade To..."` em `1440px`), `Compartilhar` perde o rótulo abaixo de `70rem`, `barSkeleton` (`40px/44px`) diverge da barra real (`65px/105px/113px`); além de dois controles de pincel no `StoreScatter` e padrões mistos de ordenação no `BreakdownTable`. |
| 5 | Error Prevention | 3 | Datas limitadas ao `/api/meta`, bloqueio proativo de CSV > 50 mil linhas, trava de `50` lojas no brush e aviso `*` de amostra pequena; contudo, omitir `"Todos"` em `Hub`/`Loja` a `1280px` faz campos sem filtro parecerem vazios, e `"Ver resultado"` no mobile sugere envio adiado quando o recorte já mudou ao vivo. |
| 6 | Recognition Rather Than Recall | 3 | Comandas com evidência marcada nos gráficos (`EVIDENCE_DIM = 0,25`), chips ativos no chat e sugestões iniciais ajudam a memória; porém `Compartilhar` vira ícone sem rótulo a `1024px`/`1280px` aberto, `Ranking` no mobile (`390px`) corta `Pedidos` para `"P"` e o `AgentFab` não traz legenda visível. |
| 7 | Flexibility and Efficiency | 3 | Atalho `Ctrl K`/`⌘K`, digitar para abrir no `AgentAskButton`, *roving tabindex* em fila/atalhos de gráfico, brush por área e rolagem virtual no servidor; falta atalho `"Comandas · N"` fixo na barra desktop após rolagem profunda e alternativa visível (não `.sr-only`) ao brush em telas de toque. |
| 8 | Aesthetic and Minimalist Design | 3 | Sistema "Comanda" coeso nos temas claro e escuro, zero sombras e hierarquia tipográfica clara em Zilla Slab / Libre Franklin; prejudicado pelo aperto da `FilterBar` (`1280–1440px`), ícones redundantes de `toolbox` no gráfico de lojas, bordas `--rule` de baixo contraste (`1,37:1` / `1,40:1`) em `bg-surface` e repetição de 7 gatilhos `"Perguntar"`. |
| 9 | Error Recovery | 3 | `ErrorState` com tentativa de `/api/health`, detalhes técnicos recolhidos, retry por página na `OrdersTable` e fallback local no agente; porém o recorte com `0` pedidos empilha dois cartões quase idênticos (`AlertsPanel` + `KpiStrip`) sem botão `"Limpar recorte"` em linha. |
| 10 | Help and Documentation | 3 | Glossário `<Term>`, dicas dinâmicas por painel, legendas de `↑` / `*` e rodapé metodológico completo em 3 colunas; porém atalhos de teclado não têm guia visível e o símbolo `↑` muda de sentido entre `BreakdownTable` (taxa acima do recorte) e `OrdersTable` (ciclo fora do SLA ou `> R$ 5 mil`). |
| **Total** | | **30/40** | **Good** (base visual e aderência de domínio muito sólidas; nota contida pela regressão da `FilterBar` entre `1280–1440px` e oclusões do painel do agente em `1024px` e `390px`). |

---

### Design Specificity Verdict

**Veredicto: Interface autoral e fiel ao domínio de Central de Operações (não intercambiável com template genérico de BI).**

- **Avaliação de design (LLM):** A metáfora **"A comanda na fila"** amarrada à paleta vinho institucional (`#3D0B1F` / `#26060F`), ao vermelho reservado exclusivamente para criticidade e ação primária (`#D92B20` / `#FF5D50`), aos algarismos tabulares em Zilla Slab e ao destaque de evidência cruzada (KPI com contorno `ink`, `StagesChart` com o hub culpado no topo e os demais em `EVIDENCE_DIM = 0,25`) diferencia claramente o painel de galerias genéricas de gráficos. Mesmo o tema escuro mantém a separação correta com `.action-block` em `#ececec` / `#111111`. Onde o padrão genérico ainda vaza é na barra superior comprimida entre `1280px` e `1440px` (onde `Compartilhar` na linha 1 espreme os seletores) e nos ícones padrão de `toolbox` do ECharts expostos dentro de `Lojas: volume × problema`.
- **Varredura determinística (`impeccable detect --json frontend/src`, exit code `2`):** O scanner acusou **6 apontamentos** (5 `warning` e 1 `advisory`), todos já inspecionados no código-fonte:
  - **4 falsos positivos de `border-accent-on-rounded`** (`PeriodPresets.tsx:34,165` e `Panel.tsx:275,288`): usam `rounded-t-[4px]` apenas no topo e borda inferior plana (`border-b-2`) como indicador de aba deslizante (ou espaçador `border-transparent`), não em cantos arredondados em volta do traço.
  - **1 falso positivo contextual de `gradient-text`** (`motion-content.css:110`): `@utility shimmer-text` aplica faixa animada de carregamento apenas em indicadores transitórios (`Consultando o recorte…` e `Carregando agente…`), desativada sob `prefers-reduced-motion`.
  - **1 advisory intencional de `bounce-easing`** (`global.css:61`): `--ease-bounce` (`cubic-bezier(0.34, 1.36, 0.64, 1)`) restrito à entrada do ponto `.agent-dot` em `motion-agent.css`.
  - **Auditoria de contraste e geometria ao vivo:** Todas as cores de texto passam em WCAG AA (`>= 4,5:1`) no claro e no escuro (`--ink` até `17,40:1`, `--muted` `>= 4,86:1`), e `100%` (28/28) dos alvos menores no mobile possuem `.hit-target` (`>= 44×44px`). Entretanto, a medição determinística de tokens revelou que bordas `--rule` (`#dcdcdc` claro / `#353535` escuro) sobre `bg-surface` têm contraste de apenas **`1,37:1` (claro)** e **`1,40:1` (escuro)** (< `3:1`), além da compressão severa da `FilterBar` em `1280×800` (`Cidade` medindo `49,75px` dentro de `35,19px` e `"Todos"` colapsando a `0px`).
- **Overlays visuais:** A injeção mutável no navegador sandboxado foi bloqueada por política de isolamento (`typeof document === "undefined"` e `page.evaluate`/`addScriptTag` indisponíveis no worker do navegador embutido). Conforme o protocolo de fallback, o `live-server` de overlay foi omitido de propósito e nenhuma marcação de overlay em aba humana existe; a verificação ao vivo ocorreu via DOM/estilos computados e capturas em `http://localhost:4321`.

---

### Overall Impression

A rodada anterior de correções resolveu pontos importantes (corte em 50 lojas no brush com aviso, fixação lateral de `Criado em` + outliers de GMV `> R$ 5 mil` na `OrdersTable`, `.action-block` claro no modo escuro, `EVIDENCE_DIM = 0,25`, bordas `border-ink` nos overlays, barra mobile em linha única e fixação opt-in de comandas do agente). Contudo, **colocar `ShareMenu` na linha 1 da `FilterBar` e omitir a linha 2 sem filtros introduziu uma regressão clara em `1280×800` e `1440×900`**, estrangulando `Cidade`, `Hub` e `Loja`. Além disso, em larguras intermediárias (`1024–1279px`) e mobile (`390×844`), o agente aberto/FAB ainda cobre ações centrais da tela.

---

### What's Working

1. **Circuito fechado "Comanda + Evidência + Ação":** Abrir uma comanda destaca instantaneamente o KPI ou o hub responsável (`StagesChart.tsx:62-112` fixa o hub no topo e atenua pares em `EVIDENCE_DIM = 0,25`) e oferece ação operacional datada no bloco invertido `.action-block`, preservando a regra de vermelho único nos dois temas.
2. **Arquitetura resiliente sem chave de API (`AgentChat` + `TopBarStatus`):** O cold start (~40 s) é comunicado em sincronia na faixa superior, nos skeletons de KPI e no chat; o agente entrega leitura imediata por regras locais antes de aprofundar via LLM e permite fixar na fila apenas o que o operador escolher.
3. **Alvos táteis e zero estouro horizontal de página:** Mesmo em `390×844`, o documento inteiro mantém `scrollWidth <= innerWidth` (`0` transbordos não intencionais), rolagem dedicada na fila de comandas e tabelas com `hit-target` expandido para `44×44px` abaixo de `1024px`.

---

### Priority Issues

1. **[P1] `FilterBar` desktop estrangula `Cidade`/`Hub`/`Loja` (`1280–1440px`), quebra agrupamento com `Compartilhar` e oscila altura**
   - **What:** Em `FilterBar.tsx:36-58`, `PeriodFields`, `PlaceFields`, `Mais filtros`, `ShareMenu` e `AgentAskButton` disputam a mesma linha horizontal com `@min-[75rem]:flex-nowrap`. Como `AgentAskButton` mantém `flex-[0_6_22rem]` e `ShareMenu` ocupa `~160px` no centro, o grid de lugares cai para **`85,19px` por seletor em `1280×800`** (`35,19px` úteis internos): `"Cidade"` (`49,75px`) é cortado ao meio e o rótulo `"Todos"` colapsa para **`0px`** em `Cidade`, `Hub` e `Loja` (já que `MultiSelect.tsx:242-246` desativa `yieldLabel` quando `value.length === 0`). Até em `1440×900`, `"Cidade Todos"` trunca para `"Cidade To..."`. Sem chips, a linha 2 some (`65px` → `105px+` ao filtrar, `113px` quando `AgentAskButton` quebra linha), descasando também de `barSkeleton` (`h-11 lg:h-10` em `FilterBar.tsx:224`) e da especificação em `DESIGN.md:251-258`.
   - **Why it matters:** Na resolução mais comum de notebook corporativo (`1280px`) e em desktops `1440px`, os três filtros geográficos principais parecem quebrados/vazios logo acima da dobra e deslocam a altura da barra fixa ao primeiro filtro ou ao abrir o agente.
   - **Fix:** Devolver `ShareMenu`, `Limpar recorte` e uma linha curta de estado (`"Recorte completo: todos os pedidos."` quando `chips.length === 0`) para a **Linha 2** da `FilterBar`, mantendo a altura estável (~104px no desktop) e alinhada ao `barSkeleton` (`lg:h-[80px]`). Na Linha 1, dar piso mínimo ao grid `PlaceFields` (`min-w-[21rem]`) e usar `flex-[1_4_13rem]` no slot do `AgentAskButton` para que `Cidade Todos`, `Hub Todos` e `Loja Todos` caibam inteiros em `1280px` e `1440px`.
   - **Suggested command:** `/impeccable layout`

2. **[P1] `AgentDock` em modo `float` (`1024–1279px`) e `AgentFab` (`390×844`) cobrem a ação primária da comanda**
   - **What:** Entre `1024px` e `1279px` (`AgentDock.tsx:12,19-20`), abrir o agente posiciona o painel flutuante (`360 × 563px` a `x: 633, y: 189` em `1024×768`) exatamente por cima do bloco `.action-block` da comanda aberta e da coluna direita de KPIs, sem recuo do conteúdo. No mobile (`390×844`, `AgentLauncher.tsx:119`), o `AgentFab` (`48×48px` fixo em `right-4 bottom-4`) pousa sobre a extremidade direita do único botão vermelho primário da dobra (`"Ver só Color Shopping"`) e sobre barras de rolagem horizontais das tabelas durante a navegação.
   - **Why it matters:** Em tablets e notebooks menores, consultar o agente oculta a instrução operacional que o operador precisa validar; no celular, o botão flutuante induz toque acidental ao tentar acionar o drill-down crítico.
   - **Fix:** Abaixo de `1024px`, incorporar o gatilho do agente diretamente na barra fixa móvel (`MobileRecorte`) ao lado de `Recorte` e `Comandas` (removendo o botão flutuante sobre o conteúdo) ou reservar margem direita no botão primário em `<640px`; entre `1024px` e `1279px`, dockear em coluna estreita (`320px`) ajustada com container queries na `FilterBar`, evitando sobrepor `.action-block`.
   - **Suggested command:** `/impeccable adapt`

3. **[P1] `StoreScatter` expõe dois controles de pincel concorrentes e dessincroniza `aria-pressed`**
   - **What:** `StoreScatter.tsx:93-101` renderiza os ícones nativos de `toolbox.feature.brush` (`rect` e `clear`) no canto superior direito do canvas ECharts logo abaixo do botão React `"Selecionar área"` no cabeçalho do painel (`StoreScatter.tsx:165-173`). Acionar o pincel ou limpar pelos ícones do canvas não altera `brushing` no React (`aria-pressed` continua `"false"`), quebra a unidade visual com ícones finos de biblioteca e permanece visível mesmo no mobile `390px`, onde arrastar pincel compete com a rolagem vertical.
   - **Why it matters:** Estado de acessibilidade mentiroso para leitores de tela, redundância de affordance e ruído visual de UI padrão de biblioteca.
   - **Fix:** Remover a chave `toolbox` de `StoreScatter.tsx:93-99`, mantendo apenas o `brush` programático via `takeGlobalCursor` controlado pelo botão React `"Selecionar área"` (mais um botão claro `"Limpar seleção"` no cabeçalho quando ativo) e oferecendo atalho visível para `"Filtrar no ranking"` abaixo de `lg` em vez de depender só de `ChartAccess` `.sr-only`.
   - **Suggested command:** `/impeccable distill`

4. **[P2] `Ranking do recorte` (`BreakdownTable`) corta `Pedidos` no mobile e divide padrões de clique de ordenação**
   - **What:** Em `BreakdownTable.tsx:281,294`, a coluna fixa `right-0` (`max-lg:size-11`) não possui borda divisória (`border-l border-rule`) e divide espaço com a primeira coluna longa (`Hub + Cidade`), deixando em `390×844` apenas `Hub`, um recorte da primeira letra de `Pedidos` e o botão de filtro visíveis acima da dobra. Além disso, em `BreakdownTable.tsx:255-277`, clicar em `"GMV"` ou `"Subsídio"` abre o popover `<Term>` enquanto a ordenação exige clicar no ícone `24×24px` `ArrowUpDown`, divergindo das outras 8 colunas da mesma tabela e da `OrdersTable.tsx` (que só exibe seta na coluna ordenada ativa).
   - **Why it matters:** Quem abre o ranking no celular precisa rolar de lado antes de ler sequer a primeira métrica; no desktop, clicar no cabeçalho `"GMV"` esperando ordenar os hubs por receita abre uma definição de glossário.
   - **Fix:** Adicionar `border-l border-rule` na célula/cabeçalho sticky direito, limitar largura da coluna de entidade no `<640px` (`max-sm:max-w-36`) quebrando cidade abaixo do nome para liberar `Pedidos` e `No prazo`, tornar `"GMV"`/`"Subsídio"` botões inteiros de ordenação acompanhados de um pequeno gatilho de ajuda ao lado, e unificar a exibição de setas inativas com a `OrdersTable`.
   - **Suggested command:** `/impeccable polish`

5. **[P2] Estado vazio (`0 pedidos`) exibe cartões duplicados sem botão de recuperação rápida**
   - **What:** Quando o cruzamento de filtros zera o recorte, `AlertsPanel.tsx:677-691` renderiza `"Sem pedidos neste recorte."` e `KpiStrip.tsx:465-476` repete logo abaixo `"Nenhum pedido neste recorte. Afrouxe período, hub ou loja. Os painéis abaixo ficam vazios até lá."` acima de 6 blocos vazios empilhados — nenhum dos dois cartões oferece um botão `"Limpar recorte"` em linha.
   - **Why it matters:** No exato momento em que o operador cai em beco sem saída de filtros, a interface repete a mesma explicação duas vezes sem atalho de saída contextual.
   - **Fix:** Consolidar a mensagem de recorte vazio em um bloco único com `outsideBaseNote`, chips removíveis dos filtros ativos e botão direto `"Limpar recorte"`, ocultando ou recolhendo os corpos vazios dos painéis analíticos inferiores enquanto `current.orders === 0`.
   - **Suggested command:** `/impeccable harden`

---

### Persona Red Flags

- **Alex (Power User):**
  - Em `1280×800` e `1440×900`, `"Cida"`/`"Hub"`/`"Loja"` sem `"Todos"` visível e `"Cidade To..."` atrasam a conferência instantânea do recorte.
  - Clicar em `"GMV"` ou `"Subsídio"` no `BreakdownTable` abre definição em vez de ordenar; precisa acertar o ícone adjacente `24px`.
  - Após rolar até `OrdersTable`, a barra fixa desktop não oferece atalho rápido para voltar às `Comandas` como a versão mobile já faz.
- **Sam (Accessibility-Dependent User):**
  - `section.panel-frame` (`index.astro:166-187`) recebe `tabIndex="0"` antes da hidratação `client:visible` e o perde assim que monta, alterando a ordem de Tab durante o carregamento.
  - Bordas `--rule` de seletores/botões sobre `bg-surface` medem **`1,37:1` (claro) / `1,40:1` (escuro)**, abaixo do mínimo `3:1` (WCAG 1.4.11) para delimitação de controles.
  - Ícones `toolbox` do ECharts (`StoreScatter.tsx:93-99`) não recebem foco por teclado e deixam `aria-pressed` dessincronizado; linhas virtualizadas posicionadas absolutamente (`OrdersTable.tsx`) podem causar saltos de leitura entre janela montada e `aria-rowcount`.
- **Riley (Deliberate Stress Tester):**
  - Alternar o `AgentDock` em `1280px` ou aplicar o 1º filtro faz a `FilterBar` saltar entre `65px`, `105px` e `113px`, enquanto o `barSkeleton` reserva `40px`/`44px`.
  - No mobile (`FilterSheet`), cada toque altera URL e dispara requisições imediatamente, mas o rodapé apresenta botão `"Ver resultado"` sem opção `"Cancelar"` / desfazer edição do sheet.
  - Símbolo `↑` muda de significado entre `BreakdownTable` (acima do recorte) e `OrdersTable` (fora do SLA / GMV > R$ 5 mil).
- **Casey (Distracted Mobile User — `390×844`):**
  - `AgentFab` cobre a borda direita do CTA primário `"Ver só Color Shopping"` na dobra inicial, elevando risco de toque acidental.
  - `Ranking do recorte` exibe só `Hub` e um pedaço de `Pedidos` (`"P"`) com coluna direita sticky sem divisória, exigindo rolagem lateral incômoda acima do `AgentFab`.
- **Coordenador de Turno / Analista de Operações (do `PRODUCT.md`):**
  - No notebook `1280px`, `Cidade`/`Hub`/`Loja` sem `"Todos"` dificulta confirmar se há filtro ativo no plantão; com o agente aberto em `1024–1279px` (`float`), a resposta do agente cobre a ação `.action-block` da comanda que ele precisa repassar, e `Compartilhar` perde o texto visível.

---

### Minor Observations & Questions to Consider

#### Minor Observations
- **Contraste de bordas de controles (`--rule` em `global.css`):** `#dcdcdc` sobre `#ffffff` (`1,37:1`) e `#353535` sobre `#1b1b1b` (`1,40:1`) enfraquecem os limites visuais dos campos de filtro e botões `ghost` em relação ao fundo da barra.
- **Comentário desatualizado em `FilterBar.tsx:75,221`:** A documentação interna cita `104px` e `80px` no desktop, mas o componente atual alterna `65px` (sem chips) / `105px+` (com chips) / `113px` (wrap) e usa `barSkeleton` `h-11 lg:h-10`.
- **`Ciclo mediano` em hub único no período completo (`KpiStrip.tsx`):** Exibe `"sem referência"` quando não há período anterior, mesmo tendo `network_value` disponível para o trilho.
- **Densidade de `"Perguntar"`:** Sete botões `"Perguntar"` / `"Perguntar ao agente"` repetidos nos painéis competem com o launcher fixo da barra superior.

#### Questions to Consider
1. Se **"Recorte first"** é a tese central do console, vale mesmo ceder `352px` da Linha 1 para um campo de agente ainda vazio enquanto `Cidade`, `Hub` e `Loja` colapsam para `"Cida"` e `"Todos"` desaparece em `1280px`?
2. Por que manter `toolbox.feature.brush` nativo do ECharts no canvas de lojas se o botão autoral `"Selecionar área"` já vive no cabeçalho e dá acesso por teclado?
3. Em `1024–1279px`, não seria mais produtivo dockear o agente em `320px` (ou empurrar o layout) do que fazê-lo flutuar em cima do bloco `.action-block` que ele próprio comenta?
4. No mobile (`390×844`), mover o atalho do agente para a barra fixa `Recorte / Comandas` elimina de uma vez a oclusão do botão `"Ver só Color Shopping"` e das tabelas — ou há motivo forte para manter o `AgentFab` flutuante?
