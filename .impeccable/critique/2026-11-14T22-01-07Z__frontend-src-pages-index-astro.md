---
target: frontend/src/pages/index.astro
total_score: 27
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
target_fingerprint: "sha256:114770629f59ff494bc2e3fb68f665d190ce1a10f18bf8c59b5a086042ae7bfc"
target_path: "C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
timestamp: 2026-11-14T22-01-07Z
slug: frontend-src-pages-index-astro
closed: true
---
Method: dual-agent (A: 232907eb-6597-49bb-b922-7d7d732b0948 · B: 39e67844-4e37-4d98-82b8-71aac8e8c293)

# Crítica de Design — Central de Operações (`frontend/src/pages/index.astro`)

**Modo de superfície:** `Operate` (todas as 10 heurísticas de Nielsen aplicáveis, pontuação máxima `40`). Auditado após as correções da Rodada 2 com [index.astro](file:///c:/Projects/dashboard-insight/frontend/src/pages/index.astro), `PRODUCT.md`, `DESIGN.md` e inspeção ao vivo em `http://127.0.0.1:4321` (`1440×900`, `1024×768` e `390×844`).

---

## Veredito de Especificidade de Design

**Veredito: Genuinamente autoral e ancorado na operação brasileira de delivery — mas a especificidade perde coesão fora do miolo superior e contradiz a própria tese em duas transições reais de estado.**

O produto foge claramente de templates genéricos de dashboard SaaS: a fila de **Comandas** (`Nº 01 · SLA`, picote radial em `.ticket`, separador pontilhado, severidade dupla forma + cor `●` / `○` / `—` e bloco invertido `.action-block` em [AlertsPanel.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/AlertsPanel.tsx) e [global.css](file:///c:/Projects/dashboard-insight/frontend/src/styles/global.css)) traduz despacho operacional em vez de cards decorativos. A paleta contém cinza neutro `#ECECEC`, vinho institucional e escalas monocromáticas em vinho, reservando `--crit` apenas para alertas críticos e o CTA primário `Ver só ...`.

No entanto, a inspeção mais profunda desta rodada expôs quebras onde o sistema deveria ser mais forte:
1. **Contradição na tese central ("ação, não ranking") dentro do agente:** [AgentComanda.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/agent/AgentComanda.tsx#L67-L74) aplica `line-clamp-3` inclusive ao parágrafo de **Ação**, cortando instruções operacionais ao meio da palavra (`"...para revisa..."` no dock desktop e `"...para revisar fila de..."` no mobile).
2. **Quebra do contrato da barra de filtros no desktop (`DESIGN.md`):** Ao abrir o `AgentDock` em `1440×900`, `AgentAskButton` pula da Linha 1 para a Linha 2 ([FilterBar.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/FilterBar.tsx#L52-L78)); mesmo fechado em `1440px`, o rótulo encolhe para `"Agente"` em vez de exibir `"Pergunte sobre este recorte…"` ([AgentLauncher.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/agent/AgentLauncher.tsx#L85-L88)).
3. **Queda de acabamento no modo escuro, nas tabelas e no mobile (`390px`):** No tema escuro, `--action: #ececec` transforma a caixa de ação em um bloco quase branco ofuscante sobre `#1b1b1b` ([global.css](file:///c:/Projects/dashboard-insight/frontend/src/styles/global.css#L96-L98)); `OrdersTable` corta minutos outliers (`↑ 65,7 mir`, `↑ 68,5 mir`); gráficos colidem no eixo X em `390px`; e recortes com `0` pedidos preservam quatro molduras de gráfico vazias em altura cheia.

### Achados do Detector Determinístico (`impeccable detect --json frontend/src`)

O comando terminou com código `1` e **6 achados** (todos `category: "slop"`), **todos avaliados como falsos positivos ou exceções intencionais da `DESIGN.md`:**
- **4× `border-accent-on-rounded` (`warning`):** [PeriodPresets.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/filters/PeriodPresets.tsx#L34), [PeriodPresets.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/filters/PeriodPresets.tsx#L165), [Panel.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/ui/Panel.tsx#L275) e [Panel.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/ui/Panel.tsx#L288). Todos pertencem ao indicador deslizante inferior de abas (`rounded-t-[4px] border-b-2` — cantos superiores de `4px` e base reta), não a bordas laterais decorativas em cards.
- **1× `bounce-easing` (`advisory`):** `--ease-bounce: cubic-bezier(0.34, 1.36, 0.64, 1)` em [global.css](file:///c:/Projects/dashboard-insight/frontend/src/styles/global.css#L61), consumido exclusivamente na entrada do `.agent-dot` ([motion-agent.css](file:///c:/Projects/dashboard-insight/frontend/src/styles/motion-agent.css)), conforme especificado em `DESIGN.md` e desabilitado com `prefers-reduced-motion: reduce`.
- **1× `gradient-text` (`warning`):** `@utility shimmer-text` em [motion-content.css](file:///c:/Projects/dashboard-insight/frontend/src/styles/motion-content.css#L98-L120), aplicado apenas no pseudoelemento `::after` de varredura transitória dos estados de espera do agente, com fallback para cor sólida em `prefers-reduced-motion: reduce`.
- **Estado do overlay `/detect.js` no navegador:** A injeção em tela falhou por duas razões combinadas — o `impeccable live-server --background` encerrou após fechar o shell no Windows (porta `8400` inativa durante o preflight e encerrada ao final com `live-server stop`) e o sandbox do subagente de navegador restringe `page.evaluate`/`$eval`/`javascript:`. Portanto, **nenhum marcador `[Human]` foi renderizado no DOM**.

---

## Avaliação Heurística de Nielsen (`27/40` — Aceitável, no limite de Bom)

> A nota reflete a auditoria mais rigorosa desta rodada em estados reais de transição (dock aberto em `1440px`, tema escuro, modo `float` em `1024px`, `OrdersTable` e gráficos em `390px`), que revelou quebras não capturadas antes.

| # | Heurística | Nota | Evidências principais e lacunas concretas |
|---|-----------|------|---------------------------------------------|
| 1 | **Visibilidade do status do sistema** | **3/4** | Indicador `API no ar`, contagem `COMANDAS ABERTAS · 6`, chips ativos, rótulo `"Consultando: Alertas do recorte"` no agente e badge `COMANDA Nº 01` nos gráficos. **Lacuna:** A abertura automática de `Nº 01` já ativa `$evidence` no carregamento inicial ([AlertsPanel.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/AlertsPanel.tsx#L431-L446)), esmaecendo 13 de 14 hubs em `StagesChart` antes de o usuário pedir foco no gráfico. |
| 2 | **Correspondência sistema / mundo real** | **3/4** | Vocabulário autêntico de operação (`Praça`/hub, `Preparo`, `Coleta`, `Expedição`, `Trânsito`, `Subsídio de frete`, horário de Brasília, pt-BR). **Lacunas:** O card do agente vaza jargão em inglês (`"Três alertas high:"`) e `OrdersTable` trunca unidades para `↑ 65,7 mir` / `↑ 68,5 mir` ([OrdersTable.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/OrdersTable.tsx#L81-L83)). |
| 3 | **Controle e liberdade do usuário** | **3/4** | `Limpar recorte`, remoção por chip, filtros sincronizados na URL, `Nova conversa` com desfazer, `Recolher` na comanda, `Esc` nos modais/dock e `"Perguntar"` que pré-preenche sem enviar sozinho. **Lacunas:** Em recorte vazio por filtros conflitantes não há saída pontual do conflito, e as linhas de `OrdersTable` não abrem detalhe nem filtram hub/loja ([OrdersTable.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/OrdersTable.tsx#L211-L235)). |
| 4 | **Consistência e padrões** | **2/4** | **Quatro quebras claras:** (1) `AgentAskButton` pula da Linha 1 para a Linha 2 quando `AgentDock` abre em `1440px` ([FilterBar.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/FilterBar.tsx#L52-L78)); (2) `AgentOpenBand` usa breakpoint de viewport `lg:` enquanto `OpenBand` usa container `@min-[48rem]:` ([AgentComanda.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/agent/AgentComanda.tsx#L230)); (3) Tema escuro muda `.action-block` para `#ececec` gritante ([global.css](file:///c:/Projects/dashboard-insight/frontend/src/styles/global.css#L96-L98)); (4) `Dia × hora` quebra `Ciclo` para uma 2ª linha dentro do `Segmented` em `390px` ([Panel.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/ui/Panel.tsx#L270)). |
| 5 | **Prevenção de erros** | **3/4** | `DatePicker` delimita intervalo válido, `"Perguntar"` nunca dispara chamada de IA sem revisão, e `min_orders` / asterisco `*` de amostra pequena previnem leitura precipitada. **Lacuna:** Combinações geograficamente impossíveis (`Cidade: Curitiba` + `Hub: Golden Shopping`) são aceitas sem aviso nem explicação específica do conflito. |
| 6 | **Reconhecimento em vez de memorização** | **2/4** | Labels inline (`Cidade Todos`), `<Term>` e regras no rodapé ajudam. **Lacunas:** (1) `AgentAskButton` oculta `"Pergunte sobre este recorte…"` atrás de `"Agente"` em `1440px` ([AgentLauncher.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/agent/AgentLauncher.tsx#L85-L88)); (2) `AgentChatComanda` corta `Ação` com `line-clamp-3` atrás de `"Ver detalhe completo"` ([AgentComanda.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/agent/AgentComanda.tsx#L73)); (3) Ao clicar em `Ver no gráfico`, a comanda e seus números somem acima da dobra; (4) `OrdersTable` omite `payment_method`, `delivery_fee`, `subsidy` e `city` sem drawer de inspeção. |
| 7 | **Flexibilidade e eficiência** | **3/4** | Atalho `Ctrl+K`/`⌘K`, digitação direta no botão do agente, navegação por setas na trilha, brush retangular em `StoreScatter` e zoom no `TrendChart`. **Lacunas:** Seleção por área em `StoreScatter` não tem equivalente de teclado em grupo, e [StoreScatter.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/StoreScatter.tsx#L19-L94) emite aviso de `ToolboxComponent` não importado no console (observado na Auditoria A). |
| 8 | **Estética e design minimalista** | **2/4** | Superfícies nítidas e sem sombras no modo claro. **Lacunas:** (1) Bloco `#ECECEC` ofusca `--crit` (`#FF5D50`) no modo escuro; (2) Recorte vazio mantém 4 molduras inteiras de gráfico em branco abaixo do banner; (3) Eixos horizontais colidem no mobile `390px` (`10 m20 m30 m40 min` e `02h04h06h...`) e `.agent-fab` (`x: 311..359`) sobrepõe a caixa `.comanda-actions` (`x: 36..339`) em `28px` ao rolar no celular. |
| 9 | **Recuperação de erros** | **3/4** | Banner claro de recorte vazio (`"Sem pedidos neste recorte..."` + `Limpar recorte`), estado de cold start da API com retry e `"Tentar de novo"` em erros de página da tabela. **Lacuna:** Sem identificação do filtro causador do vazio, obriga tentativa e erro nos chips ou reset total. |
| 10 | **Ajuda e documentação** | **3/4** | Popovers `<Term>`, dicas operacionais por painel, rodapé metodológico claro e link `API (Swagger)` no desktop. **Lacunas:** Link `API (Swagger)` some no cabeçalho mobile, legenda `visualMap` em [HeatmapChart.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/HeatmapChart.tsx#L99-L114) mostra apenas `baixo`/`alto` sem valores de referência, e `StagesChart` inicia esmaecido sem explicação fora do selo compacto. |
| **Total** | | **27/40** | **Aceitável** — arquitetura e linguagem visual muito fortes no claro, penalizadas por regressões de layout/estado no agente, modo escuro, tabela bruta e mobile. |

---

## Avaliação de Carga Cognitiva

### Checklist de 8 Itens (`5/8` falhas → **Carga cognitiva alta**)
- [x] **Foco único** *(com ressalva)* — Topo claro no tema claro; ressalva no tema escuro, onde `.action-block` branco disputa fixação visual com o CTA vermelho.
- [ ] **Agrupamento / Chunking (≤4 itens)** — **Falha:** trilha exibe **6 stubs** lado a lado no desktop; `BreakdownTable` exibe **10 colunas** + ação; `OrdersTable` expõe **12 colunas** horizontais.
- [x] **Agrupamento estrutural** — **Passa:** `PeriodFields`, `PlaceFields`, `KpiStrip` (`3` blocos de taxa/tempo + `1` bloco de volume/valor) e `Panel` separam bem os papéis.
- [ ] **Hierarquia visual** — **Falha:** No tema escuro, `#ECECEC` vence `#FF5D50`; no card do agente, o corte de `Ação` em 3 linhas rebaixa a ação principal ao nível dos botões secundários (`Ver detalhe completo` + `3` filtros + `Fixar na fila`).
- [ ] **Uma coisa por vez** — **Falha:** O carregamento inicial abre a Comanda `Nº 01` **e** já aplica esmaecimento `$evidence` em `StagesChart` antes da interação do usuário.
- [ ] **Escolhas mínimas (≤4 opções visíveis)** — **Falha** (ver pontos de decisão abaixo).
- [ ] **Memória de trabalho** — **Falha:** Clicar em `Ver no gráfico` rola para longe de `Comanda Nº 01`, escondendo o delta (`+1,3 min`) e a janela (`12h–14h e 19h–21h`) enquanto se lê o gráfico.
- [x] **Revelação progressiva** — **Passa:** `Mais filtros`, `Compartilhar`, `<Term>` e folha mobile escalam bem a complexidade secundária.

### Pontos de Decisão com >4 Opções Visíveis
1. **Desktop `FilterBar`:** **6 blocos** na Linha 1 (`Período` 4 opções + `Cidade` + `Hub` + `Loja` + `Mais filtros` + `Agente`) somando 9–10 alvos interativos com `Compartilhar`.
2. **Trilha de Comandas:** **6 comandas** simultâneas (`Nº 01` a `Nº 06`) na faixa horizontal visível em `1440px`.
3. **Card de resposta do Agente (`Nº A01`):** **6 botões de ação** abaixo do diagnóstico truncado (`Ver detalhe completo`, 3× `Ver <Entidade>`, `Fixar na fila`, `Nova conversa`).
4. **Seletor `Quebrar por` (`BreakdownTable.tsx`):** **7 dimensões** (`Hubs`, `Lojas`, `Cidades`, `Canais`, `Modal`, `Pagamento`, `Dia da semana`) sobre tabela de **10 métricas**.

---

## Jornada Emocional

- **Primeiros 5 segundos:** Autoridade operacional imediata. Em vez de gráficos crus no topo, a fila `COMANDAS ABERTAS · 6` entrega prioridade, diagnóstico e ação no primeiro olhar.
- **Pico:** Coesão do recorte e fluidez do agente consultando os dados filtrados ao vivo (`"Consultou: Alertas do recorte"`), criando drill-downs clicáveis e permitindo `"Fixar na fila"`.
- **Vales emocionais:**
  1. **Salto visual e frase cortada ao abrir o agente (`1440px`):** O botão `Agente` cai da Linha 1 para a Linha 2 assim que o dock abre, e a caixa `Ação` da resposta `Nº A01` termina cortada em `"...para revisa..."`.
  2. **Clarão no tema escuro:** A caixa `.action-block` branca `#ECECEC` estoura o contraste em ambiente escuro.
  3. **Eixos colididos e vazio esticado (`390px` e `orders === 0`):** Labels sobrepostos (`10 m20 m30 m40 min`, `02h04h06h...`), aba `Ciclo` órfã na 2ª linha, sobreposição do FAB sobre a caixa de ações ao rolar e tela longa de gráficos vazios.
  4. **Tabela sem profundidade (`Pedidos do recorte`):** Ver um outlier `↑ 65,7 mir` truncado sem poder clicar na linha para ver frete, subsídio, pagamento ou filtrar a loja frustra o fim da investigação.
- **Fechamento:** O menu `Compartilhar` (link do recorte, CSV, briefing Markdown e PDF) fecha bem o fluxo no desktop.

---

## O que está funcionando

1. **Identidade autoral de "Comanda" e parcimônia de vermelho (`AlertsPanel.tsx`, `global.css`):** O recorte em picote `.ticket`, numeração `Nº 01 · SLA`, codificação dupla forma+cor e reserva estrita do vermelho para `Crítico` e um único CTA primário geram clareza instantânea.
2. **Contrato único de recorte e transparência estatística (`filters.ts`, `BreakdownTable.tsx`, `KpiStrip.tsx`):** Toda a página e o agente respeitam o recorte da URL; `*` para amostra pequena ordena no fim nos dois sentidos e as regras de SLA/presos/outliers permanecem visíveis.
3. **Arquitetura resiliente de nó único do `AgentDock` e clearances em `1024px` (`motion-agent.css`):** Em desktop (`1440px`, dock `374,39px` + `main` `1050,61px`) há zero sobreposição de conteúdo, e em tablet (`1024×768`, modo `float`) o painel flutuante mantém `+12px` abaixo da `FilterBar` e `+28px` à direita de `.comanda-actions` (`hasHorizontalOverflow: false` nos três viewports, `20/21` alvos táteis mobile nativamente `≥ 44px` e botão `"mais N"` compensado para `44px` via `.hit-target` em [global.css](file:///c:/Projects/dashboard-insight/frontend/src/styles/global.css#L444-L463)).

---

## Problemas Prioritários (`P1–P2`, por impacto)

1. **[P1] `AgentChatComanda` corta `Ação` no meio da palavra com `line-clamp-3` ([AgentComanda.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/agent/AgentComanda.tsx#L67-L74), [:230](file:///c:/Projects/dashboard-insight/frontend/src/components/agent/AgentComanda.tsx#L230))**
   - **O que acontece:** Quando `isLongComanda` é verdadeiro, `AgentChatComanda` aplica `line-clamp-3` tanto no texto de diagnóstico quanto no `<p>` dentro de `.action-block`. Ao vivo, a resposta `Nº A01` corta a instrução operacional em `"...para revisa..."` (`1440px`) e `"...para revisar fila de..."` (`390px`) atrás do botão `"Ver detalhe completo"`. Além disso, `AgentOpenBand` usa breakpoint de viewport `lg:` (`line 230`) em vez do container `@min-[48rem]:` usado em `OpenBand`.
   - **Por que importa:** Contradiz diretamente a tese do produto (*"ação, não ranking"*) dentro da entrega de IA, escondendo quem faz o quê exatamente onde o usuário espera resposta pronta.
   - **Como corrigir:** Remover `${clamped ? "line-clamp-3" : ""}` do parágrafo da caixa `.action-block` ([AgentComanda.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/agent/AgentComanda.tsx#L73)) para que `Ação` seja sempre 100% visível; manter `line-clamp-3` + `"Ver detalhe completo"` somente no texto de apoio (`detail`). Trocar `lg:grid-cols-...` em `AgentOpenBand` ([AgentComanda.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/agent/AgentComanda.tsx#L230)) por `@min-[48rem]:`.
   - **Comando sugerido:** `/impeccable clarify`

2. **[P1] `AgentAskButton` pula da Linha 1 para a Linha 2 ao abrir o dock em `1440px` e esconde o convite de pergunta ([FilterBar.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/FilterBar.tsx#L52-L78), [AgentLauncher.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/agent/AgentLauncher.tsx#L85-L88))**
   - **O que acontece:** `DesktopBar` exibe o botão da Linha 1 só em `@min-[68rem]:flex` (`1088px`) e cai para um segundo slot na Linha 2 (`w-56 @min-[68rem]:hidden`) ao lado de `Compartilhar`. Em `1440×900`, abrir o `AgentDock` (`374,39px`) reduz o container da barra para `1050,61px` (`< 1088px`), fazendo `Conversa aberta [Ctrl K]` saltar para a Linha 2. Mesmo fechado em `1440px`, `flex-[0_4_19rem]` encolhe o botão abaixo de `18rem`, exibindo `"Agente"` em vez de `"Pergunte sobre este recorte…"`. Em `1024px` (`float`), o header do painel ainda quebra `"Agente do recorte"` / `"Nova conversa"` em 2 linhas e o `<textarea>` corta o placeholder.
   - **Por que importa:** Viola `DESIGN.md` (*"Permanece ancorado na linha 1 mesmo com o painel lateral aberto, sem pular de linha"*), desloca o gatilho sob o ponteiro durante o clique e esconde a affordance principal da IA.
   - **Como corrigir:** Manter um único `AgentAskButton` fixo à direita da Linha 1 em todo desktop (`lg+` / `1024px+`), removendo o botão duplicado da Linha 2 ([FilterBar.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/FilterBar.tsx#L76-L78)). Rebalancear larguras mínimas na Linha 1 (ex.: `min-w-[14rem]` no grupo de praça e `flex-[0_2_17rem]` com `min-w-[9.5rem]` no slot do agente), reduzir o threshold de `"Pergunte sobre este recorte…"` de `@min-[18rem]/ask` para `@min-[14.5rem]/ask`, e impedir quebra no botão `"Nova conversa"` (`whitespace-nowrap`) no modo `float`.
   - **Comando sugerido:** `/impeccable adapt`

3. **[P1] Colisões responsivas em `390×844` (eixos, `Segmented`, `.agent-fab`) e corte `↑ 65,7 mir` em `OrdersTable` ([OrdersTable.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/OrdersTable.tsx#L81-L83), [StagesChart.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/StagesChart.tsx#L88), [HeatmapChart.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/HeatmapChart.tsx#L85-L96), [Panel.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/ui/Panel.tsx#L270))**
   - **O que acontece:** Quatro quebras medidas e observadas em tela:
     1. `OrdersTable` fixa `size: 86` na coluna `Ciclo` ([OrdersTable.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/OrdersTable.tsx#L81-L83)) com `ArrowUp` + `truncate`, cortando `↑ 65,7 min` para **`↑ 65,7 mir`** e `↑ 68,5 min` para **`↑ 68,5 mir`**.
     2. Em `390×844`, `StagesChart` sobrepõe ticks do eixo X (`10 m20 m30 m40 min`) e `HeatmapChart` cola rótulos (`02h04h06h08h10h12h14h16h18h20h22h`).
     3. Em `Dia × hora`, `Segmented` usa `flex-wrap` ([Panel.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/ui/Panel.tsx#L270)), jogando `Ciclo` sozinho para uma 2ª linha dentro da caixa com borda.
     4. A Auditoria B mediu sobreposição horizontal de **`28px`** no container `.comanda-actions` (`{ x: 36, width: 303 }` → direita em `339px`) com o botão flutuante `.agent-fab` (`{ x: 311, y: 780, width: 48, height: 48 }`) durante a rolagem mobile sobre `Comanda Nº 01`.
   - **Por que importa:** Unidades corrompidas (`mir`) prejudicam confiança em métricas de SLA, gráficos ilegíveis inviabilizam leitura no celular e o FAB sobrepondo ações reduz área livre de toque.
   - **Como corrigir:** Aumentar `size` de `cycle_min` para `104` (e revisar folga em `production_min` / `transit_min`); configurar `axisLabel.hideOverlap: true`, intervalo menor/abreviado (`10m`) em `StagesChart` e `interval: 3` em `HeatmapChart` no mobile; substituir `flex-wrap` do `Segmented` por rolagem horizontal limpa ou largura compacta em `< 640px`; reservar `pr-14` em `.comanda-actions` abaixo de `1024px` (ou ajustar fluxo dos botões) para isolar a faixa do `.agent-fab`.
   - **Comando sugerido:** `/impeccable layout`

4. **[P2] Tema escuro transforma `.action-block` em bloco claro ofuscante `#ECECEC` ([global.css](file:///c:/Projects/dashboard-insight/frontend/src/styles/global.css#L96-L98))**
   - **O que acontece:** `:root[data-theme="dark"]` define `--action: #ececec; --on-action: #111111;` sobre `--surface: #1b1b1b`. Ao vivo, a caixa de `Ação` se torna de longe a superfície mais luminosa de toda a interface escura.
   - **Por que importa:** Inverte a hierarquia visual — ofusca o título da comanda, o botão crítico `#FF5D50` (`Ver só ...`) e os gráficos — e provoca fadiga visual no uso noturno.
   - **Como corrigir:** Substituir o bloco quase branco por uma superfície elevada escura ou em vinho profundo com borda nítida (por exemplo, `--action: #27131a` com `--on-action: #f2f2f2` e borda `border-wine-raised` ou `--action: #262626` com borda sutil), mantendo contraste de leitura AAA/AA sem competir com `--crit: #ff5d50`.
   - **Comando sugerido:** `/impeccable colorize`

5. **[P2] Recorte vazio preserva longas molduras de gráficos em branco e `OrdersTable` não permite inspeção de pedido ([OrdersTable.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/OrdersTable.tsx#L211-L235), [Panel.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/ui/Panel.tsx))**
   - **O que acontece:** Quando `orders === 0` (ex.: `Cidade: Curitiba` + `Hub: Golden Shopping`), `AlertsPanel` exibe o aviso consolidado e `KpiStrip` oculta seus cards, mas os 4 painéis gráficos continuam renderizando caixas altas em branco apenas com `"Sem dados no recorte."` sem apontar o conflito de filtros. Além disso, cada linha de `Pedidos do recorte` é estática: não abre os campos omitidos (`payment_method`, `delivery_fee`, `subsidy`, `city`) nem filtra loja/hub.
   - **Por que importa:** A página vazia parece inacabada abaixo da dobra, e o operador que investiga um outlier na tabela não consegue inspecionar o pedido sem sair dela.
   - **Como corrigir:** Reduzir a altura mínima dos gráficos no estado `0` pedidos e detectar conflitos simples de hierarquia (cidade vs hub/loja) no banner do recorte vazio. Adicionar expansão de linha ou gaveta lateral em `OrdersTable` com os campos econômicos completos e atalhos para filtrar a loja/hub do pedido.
   - **Comando sugerido:** `/impeccable harden`

---

## Sinais de Alerta por Persona

- **Alex (Operador avançado impaciente):** Perde memória muscular quando `Agente` (`Ctrl+K`) cai da Linha 1 para a Linha 2 ao abrir o dock em `1440px`; precisa de um clique extra em `"Ver detalhe completo"` porque `line-clamp-3` cortou a `Ação`; e trava em `Pedidos do recorte` sem clique por linha nem equivalente em teclado para seleção de múltiplas lojas no `StoreScatter`.
- **Sam (Usuário dependente de acessibilidade):** Vê unidades cortadas (`↑ 65,7 mir`) e o selo mobile `Nº 04 · CANCELAME...` truncado; recebe `StagesChart` com 13 de 14 barras esmaecidas já na carga inicial por causa da abertura automática de `Nº 01`; e em recorte vazio recebe `"Sem pedidos neste recorte"` sem indicação de qual filtro anulou o outro.
- **Marina (Operadora de hub/praça em turno real):** Sofre com o clarão `#ECECEC` de `.action-block` no modo escuro; não consegue ler minutos ou horas em `StagesChart`/`HeatmapChart` no celular (`390px`); e ao clicar em `Ver no gráfico`, rola para fora da `Comanda Nº 01` tendo que guardar de cabeça a janela de horário (`12h–14h e 19h–21h`).
- **Lucas (Recrutador iFood AI Builder avaliando o portfólio):** Em laptop `1440px`, vê apenas `"Agente"` encolhido, observa o botão pular de linha ao abrir o dock, lê `"Três alertas high:"` misturado ao português e vê a caixa `Ação` cortada em `"...para revisa..."` logo nos primeiros 60 segundos de teste.

---

## Observações Menores

- **Aviso de console no `StoreScatter` ([StoreScatter.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/StoreScatter.tsx#L19-L94)):** Registrar `BrushComponent` com `brush: { toolbox: [] }` sem `ToolboxComponent` gera `[ECharts] Component toolbox is used but not imported` na carga (observado na Auditoria A).
- **Vazamento de token em inglês na resposta do agente ([prompts.md](file:///c:/Projects/dashboard-insight/backend/app/agent/prompts.md)):** O prompt pede briefing em pt-BR, mas o modelo emitiu `"Três alertas high:"` no teste ao vivo; vale proibir explicitamente rótulos de severidade em inglês (`high`, `medium`, `low`).
- **Legenda do `HeatmapChart` sem âncoras numéricas ([HeatmapChart.tsx](file:///c:/Projects/dashboard-insight/frontend/src/components/HeatmapChart.tsx#L99-L114)):** O gradiente mostra só `"baixo"` e `"alto"`, sem informar o mínimo e o máximo do recorte atual.
- **Cabeçalho do modo `float` em `1024×768`:** `"Agente do recorte"` e `"Nova conversa"` quebram em duas linhas no dock de `320px`, e o `<textarea>` exibe barras de rolagem curtas cortando o placeholder.
- **Cabeçalho mobile truncado (`390×844`):** `Nº 04 · CANCELAME...` corta o sufixo quando o card aberto tem rótulo longo ao lado de `ATENÇÃO ^ Recolher`, e o cabeçalho mobile omite acesso ao `API (Swagger)`.

---

## Perguntas a Considerar

1. **Se "Ver no gráfico" abrisse ou fixasse um resumo enxuto da Comanda ativa (alvo + janela de ação) logo abaixo da barra sticky**, o operador pararia de depender da memória ao inspecionar `StagesChart` esmaecido?
2. **Qual critério deve proteger a integridade de `.action-block`:** a caixa de `Ação` dentro do agente deve ser sempre imune a `line-clamp`, limitando o truncamento apenas ao parágrafo de evidência/detalhe?
3. **Quando o recorte dá `0` pedidos e o banner do topo já explicou a ausência de dados**, faz sentido recolher os quatro painéis gráficos para cards compactos e apontar explicitamente o conflito `Cidade` × `Hub`?
