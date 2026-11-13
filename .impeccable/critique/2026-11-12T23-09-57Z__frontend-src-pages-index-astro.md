---
target: frontend/src/pages/index.astro
total_score: 28
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 2
target_identity: "file:C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
target_fingerprint: "sha256:15815488a4ff7d87418519de223da17e5752c5d51896869c147799ff4a1c0924"
target_path: "C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
timestamp: 2026-11-12T23-09-57Z
slug: frontend-src-pages-index-astro
closed: true
---
Method: dual-agent (A: 95ad7e6e4559f71d65e8451c3b1bc7ed · B: b600de49d4cf1c11c213a4ef16079a65)

### Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---:|---|
| 1 | Visibility of System Status | 3 | `OpenBand` (`article#comanda-aberta`) pode nascer invisível no carregamento inicial; ao rolar o trilho, a comanda aberta sai de vista sem reancoragem. |
| 2 | Match System / Real World | 3 | Linguagem operacional pt-BR excelente (*comanda, recorte, preso no fluxo*), mas `AgentChat` expõe `"LLM com ferramentas, regras locais de reserva."` e `StagesChart` ordena por soma de medianas contra a alegação de "Hub lento" (SLA%). |
| 3 | User Control and Freedom | 3 | Chips de recorte, `Limpar`, `Nova conversa`, `Recolher` e `Esc` funcionam bem; porém enviar pergunta ao agente rola direto para `data-answer`, escondendo a própria pergunta do operador. |
| 4 | Consistency and Standards | 2 | `ShareMenu` não desabilita CSV acima de 50k como `ExportDialog`; `OrdersTable` alinha números à esquerda enquanto `BreakdownTable` alinha à direita; `AgentComanda` usa `btn-ink` branco brilhante no escuro competindo com `btn-primary`. |
| 5 | Error Prevention | 3 | Boas travas (`CSV_LARGE_ROWS = 10_000`, teto `50.000`, `IgnoredNotice`, mínimo de 30 pedidos no scatter), porém o item bloqueado no `ShareMenu` mantém aparência clicável (`hover:bg-sunken`). |
| 6 | Recognition Rather Than Recall | 2 | Com o `AgentDock` aberto a `1440px`, `Cidade` e `Loja` perdem o rótulo (`sr-only` via `yieldLabel`), virando dois botões idênticos `Todos ▾` lado a lado; sublinhado pontilhado significa ora amostra pequena, ora glossário (`<Term>`). |
| 7 | Flexibility and Efficiency | 3 | `Ctrl+K`, setas no trilho e brush-to-filter agilizam o fluxo, mas com `AgentDock` aberto a `1440px` o botão do launcher encolhe para `"Ag... Ctrl K"`. |
| 8 | Aesthetic and Minimalist Design | 3 | Paleta e taxonomia muito disciplinadas; no mobile (`320px–375px`) o cabeçalho de Comandas espreme resumo em 4–6 linhas estreitas, e `Dia × hora` ganha ~100px de vão vazio por `align-content` no grid de altura igual. |
| 9 | Error Recovery | 3 | `EmptyState`, aviso de cold start (`waking`), `IgnoredNotice` e erros `409/500` em pt-BR são claros; falta legenda explicando quando `StagesChart` ordena por ciclo total vs. SLA% da comanda. |
| 10 | Help and Documentation | 4 | Glossário inline (`<Term>`), acordeão de `Metodologia`, regra explícita de SLA e `hint` contextual em cada painel. |
| **Total** | | **28/40** | **Good** (base sólida, travada por regressões de compositor, compressão com dock aberto e ajustes de mobile/consistência) |

---

### Design Specificity Verdict

**LLM assessment:** A metáfora **"A comanda na fila"** é autêntica e sustentada de ponta a ponta. O trilho superior com picotes (`.ticket`), numeração carimbada em Zilla Slab (`Nº 01 · SLA`), faixa de detalhe com linha tracejada, bloco invertido de `Ação`, botões de drill-down e tags de evidência (`COMANDA Nº 01`) propagadas para KPIs e gráficos formam uma linguagem coerente para operação de delivery — sem cara de dashboard SaaS genérico e sem copiar identidade de marca externa. Como deriva de contrato, [frontend-src-pages-index-astro.md](file:///C:/Projects/dashboard-insight/.impeccable/surfaces/frontend-src-pages-index-astro.md) ficou desatualizado em relação ao [DESIGN.md](file:///C:/Projects/dashboard-insight/DESIGN.md) (ainda descreve grade em 2 colunas com `Archivo` em vez de trilho largo + `AgentDock` fora da grade + `Zilla Slab`), e na inspeção ao vivo três falhas de compositor e largura comprimida quebram parte desse rigor.

**Deterministic scan:** `impeccable detect --json frontend/src` retornou código `2` com **6 ocorrências** (`5` warnings, `1` advisory):
- `border-accent-on-rounded` (4 warnings — **todos falsos positivos**): [PeriodPresets.tsx:34](file:///C:/Projects/dashboard-insight/frontend/src/components/filters/PeriodPresets.tsx#L34), [PeriodPresets.tsx:166](file:///C:/Projects/dashboard-insight/frontend/src/components/filters/PeriodPresets.tsx#L166), [Panel.tsx:275](file:///C:/Projects/dashboard-insight/frontend/src/components/ui/Panel.tsx#L275) e [Panel.tsx:288](file:///C:/Projects/dashboard-insight/frontend/src/components/ui/Panel.tsx#L288). São botões/indicadores deslizantes de aba com `rounded-t-[4px] border-b-2` (`border-transparent` nos inativos e linha inferior plana `border-ink` no indicador ativo), não cards com borda lateral colorida.
- `bounce-easing` (1 advisory — **positivo verdadeiro intencional**): [global.css:61](file:///C:/Projects/dashboard-insight/frontend/src/styles/global.css#L61) define `--ease-bounce: cubic-bezier(0.34, 1.36, 0.64, 1)`, restrito à entrada do ponto de status `.agent-dot` em [motion-agent.css:136](file:///C:/Projects/dashboard-insight/frontend/src/styles/motion-agent.css#L136) com respeito a `prefers-reduced-motion`.
- `gradient-text` (1 warning — **match sintático / falso positivo semântico**): [motion-content.css:110](file:///C:/Projects/dashboard-insight/frontend/src/styles/motion-content.css#L110) aplica `background-clip: text` no pseudoelemento `::after` de `.shimmer-text`, usado exclusivamente no estado de espera `"Consultando o recorte…"` em [AgentChat.tsx:443](file:///C:/Projects/dashboard-insight/frontend/src/components/AgentChat.tsx#L443).
- **Verificação em runtime** (`1440×900`, `768×1024`, `375×812`, `320×640`, claro e escuro): `0` erros de rede (`109` recursos, 12 chamadas `/api/*` com HTTP `200`), `0` overflow horizontal após estabilização, `0` falta de `alt`/nomes acessíveis ou contraste baixo; o scanner em runtime pegou **4 cabeçalhos `.truncate` cortados por 5–9px** (`Hub`, `Loja`, `Valor`, `Ciclo`) na tabela `Pedidos do recorte` a `320px`, além de overflow transitório de `<canvas>` do ECharts durante o redimensionamento `1440 → 768` até o `ResizeObserver` assentar.

**Visual overlays:** A Avaliação B confirmou suporte à injeção mutável no DOM em `http://localhost:4321`, iniciou `impeccable live-server` (porta `8400`) e injetou `detect.js`. O console (`[impeccable]`) e o banner `.impeccable-overlay.impeccable-banner` no navegador reportaram os 3 itens esperados em runtime (`gradient-text`, `bounce-easing` e `marquee` disparado pela animação infinita `shimmer-band` do estado de carregamento). O servidor temporário foi encerrado com `live-server stop --keep-inject` e a aba temporária foi fechada ao final da checagem.

---

### Overall Impression

O produto tem identidade rara e funcional: o loop **Recorte único → Comanda aberta → Evidência marcada no gráfico → Pergunta pré-preenchida ao agente** entrega exatamente o que promete ao recrutador e ao operador de praça. O que impede a nota excelente hoje não é o conceito visual, e sim três quebras concretas na execução ao vivo: uma falha de renderização no Chromium que deixa a comanda aberta invisível no primeiro carregamento, a compressão da barra de filtros a `1440px` quando o dock do agente abre, e a inversão/espremimento da comanda no celular.

---

### What's Working

1. **Circuito fechado de evidência (`Comanda → Gráfico → Recorte`):** Clicar em `Ver no gráfico` ancora no painel exato com o carimbo `COMANDA Nº 01` ([EvidenceTag.tsx](file:///C:/Projects/dashboard-insight/frontend/src/components/ui/EvidenceTag.tsx)) e atenuamento das barras não relacionadas, enquanto `Ver só Color Shopping` sincroniza KPIs, gráficos, tabelas e agente no mesmo recorte.
2. **Disciplina tipográfica e cromática do mundo "Comanda":** Campo neutro frio, superfícies sem sombra (`The No Shadow Rule`), faixa vinho exclusiva da casca, Zilla Slab reservada a carimbos e números-chave, e vermelho (`#d92b20`) guardado apenas para crítico e CTA principal.
3. **Resiliência de dados e arquitetura mobile de filtros:** Decisões de limpeza visíveis (`presos no fluxo`, `amostra pequena`), glossário inline (`<Term>`) e recolhimento dos filtros para folha inferior (`Recorte · Editar`) evitam overflow horizontal até `320px`.

---

### Priority Issues

#### [P0] Corrigir sumiço visual de `OpenBand` no carregamento inicial e de `h1.header-reveal-title` após transições
- **What:** Na carga inicial estabilizada a `1440×900`, `article#comanda-aberta` (`Nº 01 · SLA`) renderizou completamente em branco (~215px de vão cinza abaixo do trilho) até que outra comanda fosse clicada. Em trocas de tema e redimensionamento para `320px`, `h1.header-reveal-title` (`"Central de Operações"`) também sumiu visualmente mantendo caixa no DOM.
- **Why it matters:** A comanda aberta é a peça central acima da dobra; um bloco vazio no primeiro acesso passa sensação de aplicação quebrada logo nos primeiros segundos do recrutador.
- **Fix:**
  1. Em [global.css](file:///C:/Projects/dashboard-insight/frontend/src/styles/global.css#L246-L278), desacoplar `mask` (`.ticket`), `animation` (`ticket-print` com `clip-path` + `animation-fill-mode: both`) e `filter: blur(0)` no ancestral `.band-collapse > div` — aplicar `blur` apenas durante `[data-state="closing"]` e animar entrada com `opacity`/`translateY` em vez de `clip-path` persistente sobre elemento mascarado.
  2. Em [motion-content.css](file:///C:/Projects/dashboard-insight/frontend/src/styles/motion-content.css#L126-L144), remover `filter: blur(0)` e `both` no estado final de `header-reveal-title` (`filter: none` limpo ao concluir).
- **Suggested command:** `/impeccable animate`

#### [P1] Evitar perda de rótulos (`Todos ▾` / `Todos ▾`) e truncamento `"Ag..."` com o `AgentDock` aberto a `1440px`
- **What:** Abrir o [AgentDock](file:///C:/Projects/dashboard-insight/frontend/src/components/agent/AgentDock.tsx) (`403px`) reduz `#page` para `1022px`. Em [FilterBar.tsx](file:///C:/Projects/dashboard-insight/frontend/src/components/FilterBar.tsx), `PlaceFields` comprime para `397px` (3 colunas de `127px`), disparando `yieldLabel` em [MultiSelect.tsx](file:///C:/Projects/dashboard-insight/frontend/src/components/ui/MultiSelect.tsx#L241-L279), o que esconde `Cidade` e `Loja` em `sr-only` e deixa **dois botões `Todos ▾` idênticos**. Ao mesmo tempo, [AgentLauncher.tsx](file:///C:/Projects/dashboard-insight/frontend/src/components/agent/AgentLauncher.tsx#L70-L86) corta `"Agente"` para `"Ag... Ctrl K"`.
- **Why it matters:** Exatamente quando o operador cruza recomendações do agente com os filtros geográficos, `Cidade` e `Loja` ficam indistinguíveis visualmente e o botão principal do agente parece quebrado.
- **Fix:** Nunca colapsar para `"Todos"` puro quando `yieldLabel` dispara — exibir `"Cidade: Todas"` / `"Loja: Todas"` ou adaptar `PlaceFields` e a barra com `@container` sobre `#page` (passando para o layout compacto quando a largura útil ficar abaixo de `1120px`); dar `shrink-0` ao rótulo `"Agente"` e esconder a dica `Ctrl K` antes de truncar o nome.
- **Suggested command:** `/impeccable layout`

#### [P1] Corrigir espremimento do cabeçalho do trilho e ordem invertida da `Ação` no mobile (`320px–375px`)
- **What:**
  1. Em [AlertsPanel.tsx](file:///C:/Projects/dashboard-insight/frontend/src/components/AlertsPanel.tsx#L588-L631), o `<header>` do trilho coloca título, resumo multi-nível (`3 críticas · 3 em atenção · 1 do agente`) e `voltar` / `mais 5` na mesma linha, esmagando o resumo em **4 a 6 linhas verticais** a `320px–375px`.
  2. Em `OpenBand` ([AlertsPanel.tsx:239](file:///C:/Projects/dashboard-insight/frontend/src/components/AlertsPanel.tsx#L239)), `max-lg:order-first` joga o bloco escuro `Ação` **antes** do título e da leitura do problema, enquanto `max-lg:pr-9` reduz a largura útil de todo o texto.
- **Why it matters:** No celular, o operador lê uma prescrição fora de contexto antes de saber qual hub ou métrica falhou, abaixo de um cabeçalho comprimido.
- **Fix:** Quebrar o cabeçalho do trilho em 2 linhas abaixo de `sm:` (`flex-wrap`: linha 1 `Comandas abertas · 7` + controles de paginação; linha 2 resumo em largura total); remover `max-lg:order-first` e `max-lg:pr-9` de `OpenBand` para manter diagnóstico → `Ação` → botões (deixando o respiro do FAB apenas no rodapé da faixa).
- **Suggested command:** `/impeccable adapt`

#### [P2] Harmonizar comanda do agente (`AgentComanda`), hierarquia no tema escuro e contexto da rolagem
- **What:** Em [AgentComanda.tsx](file:///C:/Projects/dashboard-insight/frontend/src/components/agent/AgentComanda.tsx) e [AgentChat.tsx](file:///C:/Projects/dashboard-insight/frontend/src/components/AgentChat.tsx): (1) `.ticket` (`bg-surface`) dentro do painel `bg-surface` apaga visualmente o picote superior da comanda do agente; (2) os botões de drill-down usam `btn-ink` (branco sólido `#f2f2f2` no escuro), roubando foco do `btn-primary` da página; (3) ao enviar pergunta, a rolagem pula direto para `data-answer` escondendo a pergunta do usuário; (4) o cabeçalho expõe `"LLM com ferramentas, regras locais de reserva."` ao operador.
- **Why it matters:** Quebra a metáfora física da comanda dentro do chat, inverte a prioridade visual do tema escuro e desorienta o usuário na conversa.
- **Fix:** Dar fundo sutil `bg-field` / `bg-sunken/50` à área de mensagens para destacar o picote da comanda; usar `btn-ghost` (ou contorno em tinta) nos drills secundários dentro do chat; rolar para o bloco do turno (`pergunta + resposta`); e trocar o subtítulo técnico por copy operacional (ex.: `"Respostas calculadas direto sobre os dados do recorte."`).
- **Suggested command:** `/impeccable polish`

#### [P2] Alinhar desabilitação do `ShareMenu`, vão vazio em `Dia × hora` e sincronia do stub ativo no trilho
- **What:** (1) [ShareMenu.tsx:124-136](file:///C:/Projects/dashboard-insight/frontend/src/components/filters/ShareMenu.tsx#L124-L136) não passa `disabled={csv.busy || csv.blocked}` nem `disabled:opacity-50` quando passa de 50.000 linhas (diferente de [ExportDialog.tsx:108](file:///C:/Projects/dashboard-insight/frontend/src/components/ExportDialog.tsx#L108)); (2) `.panel-frame` em [global.css:199-214](file:///C:/Projects/dashboard-insight/frontend/src/styles/global.css#L199-L214) não tem `content-start`, esticando ~100px de espaço morto entre o subtítulo e o heatmap de `Dia × hora` ao lado de `Onde o tempo vai, por hub`; (3) rolar o trilho ou abrir o dock deixa o stub aberto (`Nº 01`) fora da tela à esquerda.
- **Why it matters:** Elimina falsas ações clicáveis, remove espaço morto não intencional na grade de evidência e mantém clara a ligação entre o stub selecionado e a comanda expandida.
- **Fix:** Aplicar `disabled={csv.busy || csv.blocked}` e `disabled:opacity-50` em `ShareMenu`; adicionar `content-start` em `.panel-frame`; chamar `scrollIntoView({ block: "nearest", inline: "nearest" })` no stub ativo quando a seleção ou largura do trilho mudar.
- **Suggested command:** `/impeccable harden`

---

### Persona Red Flags

- **Sam (usuário de teclado e leitor de tela):**
  - No `ShareMenu` com 368.990 pedidos, o item `"CSV acima do limite"` continua focável e sem `disabled`/`aria-disabled` real, aparentando estado interativo (`hover:bg-sunken`).
  - Com o `AgentDock` aberto a `1440px`, leitores de tela ainda leem `"Cidade Todos"` e `"Loja Todos"` via `aria-labelledby`, enquanto usuários videntes de teclado veem apenas dois `Todos ▾` idênticos.
  - Em [OrdersTable.tsx:438](file:///C:/Projects/dashboard-insight/frontend/src/components/OrdersTable.tsx#L438), colunas numéricas ficam alinhadas à esquerda (oposto de `BreakdownTable`), e o sublinhado pontilhado significa ora amostra pequena, ora definição no glossário.
- **Casey (operador no celular a `320px–375px`):**
  - Encontra o cabeçalho de Comandas espremido em 4–6 linhas e lê o bloco `Ação` antes de saber qual hub ou problema originou o alerta.
  - A `320px`, 4 cabeçalhos ordenáveis de `Pedidos do recorte` (`Hub`, `Loja`, `Valor`, `Ciclo`) truncam entre 5px e 9px.
  - Ao rolar o trilho, `Nº 01` some para a esquerda enquanto a faixa expandida continua aberta abaixo dos stubs `Nº 02`/`Nº 03`, facilitando atribuir a ação à comanda errada.
- **Alex (power user / recrutador avaliando o fluxo completo):**
  - Ao abrir o `AgentDock` em tela de `1440px`, perde os nomes `Cidade`/`Loja` e vê `"Ag... Ctrl K"` no topo.
  - Ao clicar `Ver no gráfico` na comanda `Nº 01` (`Hub lento: Color Shopping`), vê `Color Shopping` (~41,9 min somados) acima de `Wolf Shopping` (~44,8 min) sem indicação visual do `80,0% SLA` que motivou o alerta.

---

### Minor Observations

- **[OrdersTable.tsx:438](file:///C:/Projects/dashboard-insight/frontend/src/components/OrdersTable.tsx#L438):** Alinhar colunas numéricas (`Valor`, `Ciclo`, `Preparo`, `Trânsito`, `Distância`) à direita com `tabular-nums` para casar com `BreakdownTable`; deixar claro no rótulo do filtro de `Canal` que o filtro atua em tipo (`Marketplace`/`Próprio`) enquanto a célula mostra o nome do canal.
- **Cabeçalhos da `OrdersTable` a `320px`:** Dar folga mínima (`min-w`) às colunas `Hub`, `Loja`, `Valor` e `Ciclo` dentro do container com scroll horizontal para não cortar 5–9px dos rótulos ordenáveis.
- **[StoreScatter.tsx:80-86](file:///C:/Projects/dashboard-insight/frontend/src/components/StoreScatter.tsx#L80-L86):** Os ícones `10×10` do toolbox do ECharts para seleção retangular passam despercebidos; um botão explícito ou dica mais visível aumenta descoberta.
- **Separação de popovers sem sombra:** Em superfícies `bg-surface/60`, reforçar sutilmente a borda dos popovers (`Mais filtros`, `Compartilhar`) para `border-ink/20` melhora o recorte sem violar `The No Shadow Rule`.
- **Sheet mobile do agente (`375×812`):** O segundo chip rápido abaixo da comanda do agente encosta/corta atrás da barra fixa de envio, e a barra de rolagem nativa consome margem direita.
- **Brief desatualizado:** Atualizar [frontend-src-pages-index-astro.md](file:///C:/Projects/dashboard-insight/.impeccable/surfaces/frontend-src-pages-index-astro.md) para refletir o layout atual (`DESIGN.md`).

---

### Questions to Consider

1. O bloco `Ação` deve continuar sendo apenas texto impresso ou deveria suportar estado leve de turno (`Marcar em andamento` / `Copiar despacho`) para o operador não encarar 3 comandas `CRÍTICO` indistintas após já ter agido?
2. Como o `AgentDock` reduz `#page` para ~`1022px` dentro de uma janela de `1440px`, não faz sentido promover `#page` a `@container` para que filtros, launcher e grades respondam à largura útil real em vez do viewport?
3. Quando `StagesChart` recebe evidência da comanda `Nº 01` (`Hub lento` por SLA%), vale exibir o `SLA %` ao lado da barra ou reordenar pela métrica da comanda enquanto a tag estiver ativa, evitando a contradição visual com a soma de medianas?
