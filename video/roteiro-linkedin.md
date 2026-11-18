# Roteiro: motion video do LinkedIn, Central de Operações

Documento de entrada para a conversa que vai produzir o vídeo em Remotion. Todos os textos, números e nomes abaixo foram conferidos no código e no `backend/data/orders.parquet`. Não troque número nem invente métrica: se precisar de outro dado, consulte a API (`/api/kpis`, `/api/alerts`, `/api/breakdown`).

## 1. Ficha técnica

| Item | Valor |
|---|---|
| Formato | 4:5 vertical, **1080 × 1350 px**. Ocupa bem o feed no celular e aparece inteiro no desktop |
| Duração | **58 s** (1740 frames a 30 fps) |
| Áudio | Sem narração. Trilha instrumental + efeitos. O vídeo precisa ser entendido **sem som** (o LinkedIn começa mudo) |
| Ferramenta | Remotion, com a UI recriada em código a partir dos tokens abaixo (nada de print esticado) |
| Idioma | Português do Brasil, números em pt-BR (86,2%; R$ 34,7 mi; 368.990) |
| Capa | Exportar o frame de 0:19 (comanda Nº 01 aberta com o bloco Ação) como imagem de capa do post |

### Áreas seguras (vale para mobile e desktop)

```
┌──────────── 1080 ────────────┐
│ 96 px de margem no topo       │
│ ┌──────────────────────────┐ │  Zona de título: y 96–330
│ │  TEXTO DA CENA           │ │  (no máximo 2 linhas)
│ ├──────────────────────────┤ │
│ │                          │ │  Palco: y 350–1150
│ │  UI recriada / animação  │ │  (componente em close)
│ │                          │ │
│ ├──────────────────────────┤ │  Legenda de apoio: y 1160–1230
│ └──────────────────────────┘ │
│ 120 px livres na base         │  (ícones de som e legenda do LinkedIn)
└──────────────────────────────┘
  72 px de margem lateral
```

- No desktop o LinkedIn mostra o vídeo com ~550 px de largura, metade do original. Por isso: **título ≥ 64 px**, **texto de apoio ≥ 36 px** e nenhum texto abaixo de **28 px** (só rótulos de UI decorativos podem ser menores, e nunca carregam informação essencial).
- No máximo **8 palavras por frase na tela** e pelo menos **1,5 s de leitura** por frase (regra: 0,3 s por palavra + 0,5 s).
- A UI de desktop do app é larga demais para o 4:5. Mostre **um componente por vez em close** (comanda, KPIs, gráfico, resposta do agente) e use a página inteira só em miniatura, como contexto, com zoom de entrada.

## 2. Linguagem visual (mundo "Comanda")

O app trata cada alerta como **comanda de cozinha**: papel térmico, topo picotado, número no carimbo. O vídeo herda essa metáfora: tudo o que é "problema → ação" chega impresso, como uma comanda saindo da impressora.

### Cores

| Token | Claro | Escuro | Uso no vídeo |
|---|---|---|---|
| `field` | `#ECECEC` | `#111111` | Fundo das cenas |
| `surface` | `#FFFFFF` | `#1B1B1B` | Comandas, cartões, painéis |
| `sunken` | `#F5F5F5` | `#232323` | Tags, fundo de campo |
| `rule` | `#DCDCDC` | `#353535` | Linhas de 1 px, picote tracejado |
| `ink` | `#1A1A1A` | `#F2F2F2` | Texto principal; fundo do bloco **Ação** no claro |
| `muted` | `#666666` | `#A6A6A6` | Texto secundário |
| `crit` | `#D92B20` | `#FF5D50` | **Só** crítico e botão principal |
| `warn` | `#946000` | `#F0A93B` | Atenção |
| `good` | `#46700F` | `#9BC75A` | "Dentro", check |
| `wine` | `#3D0B1F` | `#26060F` | Faixa do topo, logo, tela de abertura e fechamento |
| `wine-raised` | `#5A1730` | `#45112A` | Borda do bloco Ação no escuro |
| `on-wine` | `#F1DBE3` | `#E6C3CF` | Texto sobre vinho |
| `series` | `#7A1E3D` | `#E0789A` | Séries de dados, minigráficos |
| `series-deep` / `series-soft` | `#4A0F25` / `#C07D93` | `#F4B8CB` / `#A3516C` | Rampa do gráfico de etapas |

Bloco **Ação** no tema escuro: fundo `#27131A` com borda `wine-raised`.

### Tipografia

- **Libre Franklin** (400–700): todos os títulos de cena, frases e rótulos. Título de cena em 700, 64–80 px, entrelinha 1,1.
- **Zilla Slab** (600–700): **apenas** números (KPIs, contadores), o carimbo `Nº 01 · SLA` (caixa alta, 700, letter-spacing 0.03em) e o nome **Central de Operações**.
- Números sempre com `tabular-nums` para os dígitos não pularem quando animam.

### Formas e regras

- Cantos: **4 px** (tags, chips) e **8 px** (cartões, botões). Comanda: `0 0 8px 8px` com **picote no topo** (meio-furos de 5 px a cada 14 px).
- **Sem sombras.** Profundidade só com fundo `field` atrás de `surface` e fio de 1 px.
- Severidade também pela forma: **● cheio = crítico** (`crit`), **○ vazado = atenção** (`warn`, aro de 2,5 px), **— traço = observar** (`muted`).
- Vermelho só aparece em crítico e no botão principal. Dado é sempre vinho (`series`).
- Sem logo, cores ou nome do iFood. Não citar a vaga. O projeto é independente.

### Movimento (reaproveitado do CSS do app)

| Token | Valor | Onde usar |
|---|---|---|
| Stagger | 40 ms entre itens | Comandas imprimindo em cascata |
| Rápido | 250 ms | Trocas de estado, chips, dígitos |
| Médio | 350–400 ms | Painel do agente entrando, cenas |
| Easing de saída | `cubic-bezier(0.22, 1, 0.36, 1)` | Padrão para tudo que entra |
| Easing da comanda | `cubic-bezier(0.16, 1, 0.3, 1)`, 280 ms | Comanda "desdobrando" de cima para baixo |
| Bounce | `cubic-bezier(0.34, 1.36, 0.64, 1)` | Só no ponto de status e no check |

Entradas: deslocamento de 6–12 px + fade + blur de 2 px. Saídas sempre mais rápidas que entradas. Nada de giro, zoom exagerado ou partícula: o app é sóbrio e o vídeo também.

### Trilha e efeitos

- Trilha instrumental eletrônica/lo-fi, 100–110 BPM, sem vocal. Cortes de cena no tempo forte.
- Efeitos: **impressora térmica** quando uma comanda sai (é a metáfora do produto), clique seco nos botões, "tick" leve nos dígitos dos KPIs, notificação curta na chegada das mensagens do Telegram.

## 3. Arco da história

> Gráfico mostra o problema, mas não diz o que fazer. A Central de Operações transforma 368.990 pedidos reais em comandas com ação, deixa o operador investigar com um clique, responde por um agente que só enxerga o recorte filtrado e entrega o briefing no Telegram às 8h.

| # | Tempo | Cena | Ideia |
|---|---|---|---|
| 1 | 0:00–0:05 | Gancho | Gráfico não diz o que fazer |
| 2 | 0:05–0:10 | Apresentação | Nome + dados reais |
| 3 | 0:10–0:16 | Comandas | Alertas viram comandas por severidade |
| 4 | 0:16–0:23 | Comanda aberta | Problema + número + ação |
| 5 | 0:23–0:28 | Investigação | O gráfico que prova a comanda |
| 6 | 0:28–0:33 | Drill-down | Um clique filtra tudo |
| 7 | 0:33–0:41 | Agente | Pergunta → resposta com ação, presa ao recorte |
| 8 | 0:41–0:45 | Cuidado com o dado | Dado quebrado não vira culpa da frota |
| 9 | 0:45–0:51 | Automação | n8n → Telegram às 8h |
| 10 | 0:51–0:55 | Stack | Como foi feito |
| 11 | 0:55–0:58 | Fechamento | Links |

## 4. Cena a cena

### Cena 1: Gancho (0:00–0:05, frames 0–150)

**Objetivo:** parar o scroll com uma tensão que todo mundo reconhece.

**Visual:** fundo `field`. No palco, um gráfico de barras genérico em cinza (`muted`, sem rótulo, 8 barras) se desenha de baixo para cima em 600 ms. Em 2,6 s as barras encolhem e se fundem numa tira branca que sobe como **uma comanda saindo da impressora** (topo picotado, carimbo `Nº 01 · SLA` com ● vermelho). Na passagem para a cena 2, a comanda fica na tela e a câmera aproxima.

**Texto na tela (título, 72 px, `ink`):**
- 0:00–0:02,5: **"Gráfico mostra o problema."**
- 0:02,5–0:05: **"Não diz o que fazer hoje."** (a palavra "hoje" em `crit`)

**Som:** batida entra no frame 0; impressora térmica em 0:02,6.

### Cena 2: Apresentação (0:05–0:10, frames 150–300)

**Objetivo:** dizer o que é e provar que os dados são reais.

**Visual:** um wipe vertical de baixo para cima pinta a tela de `wine` (sem fade). Ao centro, o logo "Carimbo Nº" (recibo picotado com `Nº`, `#F2E6EA` sobre quadrado `wine` de cantos 6 px) e **Central de Operações** em Zilla Slab 700, 84 px, `on-wine`. Abaixo, em Libre Franklin 36 px: "Painel de delivery com alertas e agente de IA".

Depois, quatro contadores entram em cascata (40 ms de stagger), números em Zilla Slab 96 px contando de 0 até o valor em 800 ms:

| Número | Rótulo (36 px) |
|---|---|
| **368.990** | pedidos reais |
| **32** | hubs |
| **4** | cidades |
| **jan–abr 2021** | (sem contagem; entra com fade) |

**Legenda de apoio (28 px, `on-wine` a 70%):** "Dataset público Delivery Center (Kaggle)"

### Cena 3: As comandas (0:10–0:16, frames 300–480)

**Objetivo:** mostrar o diferencial visual. Alerta não é um sino genérico, é uma fila de comandas por gravidade.

**Visual:** volta para `field`. Cabeçalho em Zilla Slab caixa alta: **COMANDAS ABERTAS · 6** e, à direita, "3 críticas · 3 em atenção" (`muted`). As seis comandas fechadas imprimem **em coluna** (o trilho do app é horizontal, mas no 4:5 empilhar funciona melhor), descendo 6 px com 40 ms de stagger e um "tick" de impressora em cada uma. Cada stub tem 936 × 120 px, fundo `surface`, picote no topo:

| Carimbo | Forma | Título | Número · referência |
|---|---|---|---|
| Nº 01 · SLA | ● crit | Hub lento: Color Shopping | **80,0% no SLA** · recorte 86,2% |
| Nº 02 · LOJA | ● crit | Loja sem entregas: Muspuo Smiru | **100% cancelado** |
| Nº 03 · LOJA | ● crit | Loja crítica: Uvurusm | **25,8% cancel.** · recorte 4,6% |
| Nº 04 · CANCELAMENTO | ○ warn | Cancelamento fora da curva: Elixir Shopping | **30,8% cancel.** · recorte 4,6% |
| Nº 05 · FROTA | ○ warn | SLA cai no horário de pico | **84,4% no pico** · fora do pico 88,1% |
| Nº 06 · DADOS | ○ warn | Pedidos presos no fluxo | **17.280 presos** · 4,9% (> 4h) |

Números em Zilla Slab, referência em `muted`. Os nomes de hub e loja já vêm anonimizados no dataset.

**Texto na tela (título, 64 px):** **"Cada alerta vira uma comanda."**
**Legenda de apoio (32 px), entra em 0:13:** "● crítico   ○ atenção   — observar", com as formas desenhadas e não como caractere de texto.

### Cena 4: A comanda aberta (0:16–0:23, frames 480–690)

**Objetivo:** a cena central. Mostrar que o alerta fecha com **quem faz o quê, onde e quando**.

**Visual:** a Nº 01 se destaca (as outras somem para cima em 150 ms) e **desdobra** de cima para baixo (280 ms, easing da comanda). Comanda em `surface`, 936 px de largura:

- Topo: `● Nº 01 · SLA` à esquerda, **CRÍTICO** em `crit` (Zilla Slab caixa alta) à direita. Linha tracejada de 1,5 px (`rule`) abaixo.
- Título (Libre Franklin 600, 44 px): **Hub lento: Color Shopping**
- Diagnóstico (32 px, `ink`): "SLA de 80,0% contra 86,2% do recorte em 4.592 entregas. Maior desvio na etapa de expedição (+1,3 min sobre a mediana do recorte)."
- **Bloco Ação** (fundo `ink`, texto branco, cantos 8 px, padding 28 px), entra 300 ms depois do diagnóstico. Rótulo "Ação" em 600, texto em 34 px:
  > Gargalo dentro do hub Color Shopping: revisar fila de coleta e posicionamento de entregadores nos horários 12h–14h e 19h–21h. Meta: expedição abaixo da mediana do recorte.
- Três botões embaixo: **Ver só Color Shopping** (fundo `crit`, texto branco, o único vermelho de ação), **Ver no gráfico** e **Perguntar ao agente** (fantasmas: `surface` com fio `rule`).

**Anotações (0:19,5–0:23):** três marcações em `series` sublinham trechos do bloco Ação, cada uma com um rótulo de 28 px que aparece ao lado:
- "hub Color Shopping" → **onde**
- "revisar fila de coleta e posicionamento de entregadores" → **o quê**
- "12h–14h e 19h–21h" → **quando**

**Texto na tela (título, 64 px):** **"Problema, número e ação."**

### Cena 5: Investigação (0:23–0:28, frames 690–840)

**Objetivo:** mostrar que a página se reorganiza para provar a comanda aberta.

**Visual:** o cursor clica em **Ver no gráfico**. Transição: a comanda encolhe para uma tira no topo do palco ("Investigação · Comanda Nº 01", 28 px, `muted`) e o gráfico entra.

**Gráfico "Onde o tempo vai, por hub":** barras horizontais empilhadas com a mediana de cada etapa em minutos. Quatro cores na rampa de vinho: **Preparo na loja** `series-deep`, **Coleta** `series`, **Expedição** `series-soft`, **Trânsito** `muted`. São os 14 hubs com mais pedidos, mais o hub da comanda (o app o inclui mesmo fora do top 14). Dados reais:

| Hub | Preparo | Coleta | Expedição | Trânsito |
|---|---|---|---|---|
| **Color Shopping** (destaque) | 15,8 | 1,5 | 7,7 | 16,8 |
| Golden Shopping | 15,9 | 1,1 | 6,5 | 17,4 |
| Subway Shopping | 13,6 | 2,1 | 7,9 | 17,3 |
| Pagode Shopping | 19,2 | 1,9 | 5,0 | 14,4 |
| Hip Hop Shopping | 17,1 | 1,4 | 7,2 | 16,7 |
| Green Shopping | 15,2 | 0,8 | 3,1 | 13,8 |
| Coffee Shopping | 15,0 | 2,2 | 6,8 | 18,7 |
| People Shopping | 15,6 | 2,3 | 6,9 | 15,9 |
| Rap Shopping | 12,3 | 2,3 | 7,4 | 15,7 |
| Beach Shopping | 13,5 | 1,3 | 7,8 | 17,4 |
| Purple Shopping | 14,0 | 1,5 | 7,1 | 19,2 |
| Small Shopping | 15,8 | 1,6 | 6,4 | 14,8 |
| Avenue Shopping | 13,7 | 1,9 | 7,3 | 16,5 |
| Black Shopping | 18,2 | 2,0 | 4,6 | 14,6 |
| Wolf Shopping | 16,0 | 2,7 | 7,3 | 17,9 |

No 4:5, mostre só **8 linhas** (Color Shopping + as 7 primeiras) para as barras ficarem legíveis: rótulos de hub em 28 px e barras de 44 px de altura.

**Animação:** as barras crescem da esquerda (300 ms, `cubicOut`, stagger de 40 ms). Em 0:25,5, todas as linhas exceto Color Shopping caem para **25% de opacidade**; Color Shopping sobe para o topo com um marcador ● e rótulo em negrito. O segmento **Expedição** do Color Shopping ganha um contorno `ink` de 2 px.

**Texto na tela (64 px):** **"O gráfico que prova a comanda sobe sozinho."**

### Cena 6: Drill-down (0:28–0:33, frames 840–990)

**Objetivo:** "recorte em tudo". Um clique e todos os números passam a falar só daquele hub.

**Visual:** o cursor clica em **Ver só Color Shopping** (botão `crit`, leve compressão de 0,97 no clique). Aparece o chip `Hub Color Shopping ×` (tag `sunken`, cantos 4 px) e, ao lado, o link "Desfazer filtro". Embaixo, os três KPIs principais em cartões `surface`, empilhados ou em coluna larga, com **só os dígitos que mudam deslizando** 4 px (efeito real do app, 250 ms):

| KPI | Antes (rede) | Depois (Color Shopping) | Veredito |
|---|---|---|---|
| No prazo (SLA) | 86,2% | **80,0%** | **Crítico**, ● `crit` · "6,2 p.p. abaixo da rede" |
| Ciclo mediano | 41,2 min | **44,3 min** | "3,1 min acima da rede" (sem veredito) |
| Cancelamento | 4,6% | **3,4%** | **Dentro**, — `good` · "1,2 p.p. abaixo da rede" |

Cada cartão tem um minigráfico diário em `series` com a linha tracejada "rede" por baixo (pode ser uma linha suave estilizada, sem precisar de dado diário real).

**Texto na tela (64 px):** **"Um clique filtra tudo."**
**Legenda de apoio (32 px):** "KPIs, gráficos, alertas e agente no mesmo recorte."

### Cena 7: O agente (0:33–0:41, frames 990–1230)

**Objetivo:** mostrar o agente de IA com o limite que importa. Ele só consulta o recorte filtrado, e o servidor é quem aplica o filtro.

**Visual (0:33–0:35):** painel "Agente do recorte" entra pela direita (12 px + fade, 400 ms) ocupando o palco. Linha de contexto em `muted`: "Responde só sobre este recorte." A pergunta é digitada no campo e sobe como balão `sunken`:
> Por que o Color Shopping está lento e o que fazer hoje?

**(0:35–0:37):** texto "Consultando o recorte…" com brilho passando (shimmer de 1,6 s). Enquanto isso, cinco etiquetas de ferramenta acendem uma a uma (tags `sunken`, 28 px, borda `series` quando ativas): **KPIs do recorte · Alertas do recorte · Quebra por hub · Quebra por loja · Quebra por hora**. Um cadeado pequeno ao lado da faixa das ferramentas, com o texto "recorte: Color Shopping".

**(0:37–0:41):** a resposta **imprime como comanda** (picote, impressora):
- Carimbo: `— Nº A01 · AGENTE` (traço `muted`)
- Título (40 px, 600): **Color Shopping: SLA 80% por expedição lenta**
- Diagnóstico (30 px): "Hub opera com SLA de 80,0% (recorte 86,2%) em 4.592 entregas; expedição 1,3 min acima da mediana do recorte (7,8 min vs 6,5 min)."
- Bloco **Ação** (`ink`): "Revisar fila de coleta e posicionamento de entregadores no Color Shopping hoje, nas janelas 12h–14h e 19h–21h, para trazer expedição abaixo de 6,5 min."
- Botão fantasma: "Ver estágios do Color Shopping" · botão "Fixar na fila"

Esses textos são a resposta real do modelo capturada em `assets/agente.png`.

**Texto na tela:**
- 0:33–0:37 (64 px): **"Um agente que só vê o recorte filtrado."**
- 0:37–0:41 (36 px, legenda): "LLM com tool calling. Sem API key, responde por regras locais."

### Cena 8: Cuidado com o dado (0:41–0:45, frames 1230–1350)

**Objetivo:** mostrar critério analítico, não só interface. É a cena que separa "fez um dashboard" de "pensou no problema".

**Visual:** fundo `field`. Um cartão grande com o número **98,5%** em Zilla Slab 160 px e, abaixo, "dos pedidos do Elixir Shopping ficam 'presos' por mais de 4h". Em 0:42,5, um carimbo diagonal discreto (aro `ink` de 3 px, sem rotação exagerada, no máximo −4°) marca **DADOS**. Ao lado entra a comanda Nº 06 em miniatura com o bloco Ação:
> Conferir a rotina de finalização desses pedidos (baixa manual, agendamento ou goods com retirada posterior) antes de cobrar SLA do hub.

**Texto na tela (60 px):**
- 0:41–0:45: **"Dado quebrado não vira culpa da frota."** (fica a cena toda)
- 0:42,5–0:45 (legenda 32 px): "Hub com mais de 30% de pedidos presos sai da comparação de SLA."

### Cena 9: Automação diária (0:45–0:51, frames 1350–1530)

**Objetivo:** a ferramenta trabalha mesmo sem ninguém abrir o painel.

**Visual (0:45–0:47):** um relógio digital em Zilla Slab marca **08:00**. Abaixo, um fluxo horizontal de quatro nós ligados por linhas que se desenham da esquerda para a direita (estilo de canvas de automação, nós como retângulos `surface` de cantos 8 px, ícones simples):
**Agenda 8h → API → Briefing + roteamento → Telegram**

**(0:47–0:51):** um celular em moldura neutra (sem marca de aparelho) ocupa o palco. Chegam três mensagens em balões com o som de notificação. Os textos são da execução real em `n8n/exemplo-briefing.md` e podem ser resumidos para caber:

1. **📋 Briefing de 22/02/2021**
   2.143 pedidos · GMV R$ 157.520,18 · ticket R$ 77,48
   SLA 86,9% · ciclo mediano 39,0 min
   Cancelamento 5,1%
2. 🟠 **Para: Time de operações da praça**
   SLA cai no horário de pico. 84,1% no prazo no pico contra 90,5% fora dele. **Ação:** antecipar a escala de entregadores em 30 min antes das 11h.
3. 🟠 **Para: Líder do hub Pagode Shopping (31)**
   Pedidos presos no fluxo: 120 entregas (5,9%) acima de 4h. **Ação:** conferir a rotina de finalização antes de cobrar SLA do hub.

**Texto na tela:**
- 0:45–0:48 (64 px): **"Todo dia às 8h, o briefing chega."**
- 0:48–0:51 (36 px, legenda): "Cada alerta vai direto para quem resolve."

Mostre o nome "Telegram" só como texto no nó do fluxo. Não recrie o logo nem a interface oficial do app: balões genéricos bastam.

### Cena 10: Como foi feito (0:51–0:55, frames 1530–1650)

**Objetivo:** dar credibilidade técnica rápida para quem é da área.

**Visual:** a cena entra com a **troca para o tema escuro** (o fundo vai de `#ECECEC` para `#111111` em 400 ms, como o botão de tema do app). É uma forma silenciosa de mostrar que existe tema escuro. Três colunas de chips (tags `surface` escuro `#1B1B1B`, fio `#353535`, texto 30 px):

| Frontend | Backend | IA e automação |
|---|---|---|
| Astro | FastAPI | OpenRouter (tool calling) |
| React | DuckDB + Parquet | Agente local por regras |
| ECharts | Pydantic | n8n |
| TanStack | Tipos TS gerados do OpenAPI | Telegram |

Abaixo, dois números em Zilla Slab 72 px (`series` escuro `#E0789A`):
- **< 100 ms** · "KPIs sobre 369 mil linhas"
- **202** · "testes automatizados"

**Texto na tela (60 px):** **"Deploy real: Vercel + Render."**

### Cena 11: Fechamento (0:55–0:58, frames 1650–1740)

**Visual:** fundo `wine` (escuro `#26060F` para continuar no tema escuro, ou `#3D0B1F`). Logo + **Central de Operações** em Zilla Slab 84 px, `on-wine`. Abaixo, em Libre Franklin 34 px, com ícones simples de link e repositório:

- **dashboard-insight-kappa.vercel.app**
- **github.com/EmersonPalatti/dashboard-insight**

Rodapé (24 px, `on-wine` a 60%): "Projeto independente · dados públicos Delivery Center (Kaggle) · nomes de loja anonimizados pelo dataset"

Os dois links ficam **pelo menos 2,5 s** na tela. A trilha termina no último frame, sem fade longo.

## 5. Componentes para recriar no Remotion

Vale montar cada um como componente isolado e reaproveitar entre as cenas.

1. **`<Ticket>`**: comanda com picote no topo (máscara `radial-gradient` de meio-furos de 5 px a cada 14 px), cantos `0 0 8px 8px`, fundo `surface`. Props: `variant="stub" | "open"`, `severity="high" | "medium" | "low"`, `number`, `category`, `title`, `figure`, `figureRef`, `detail`, `action`. Animação de entrada "printing": `translateY(-6px)` → 0, clip de cima para baixo, 280 ms.
2. **`<SeverityMark>`**: ● cheio `crit` 12 px · ○ aro `warn` 2,5 px · — traço `muted` 3 × 12 px. Escalar 2,5× no vídeo.
3. **`<ActionBlock>`**: fundo `ink`, texto branco, rótulo "Ação", cantos 8 px. No escuro: `#27131A` + borda `wine-raised`.
4. **`<KpiCard>`**: rótulo 28 px, valor Zilla Slab 96 px com `<RollingDigits>` (só o dígito que muda desliza 4 px na direção da variação, 250 ms), veredito com forma + palavra, referência em `muted`, minigráfico em `series`.
5. **`<StagesChart>`**: barras horizontais empilhadas com 4 segmentos, estado `dimmed` (25% de opacidade) e `focus` (contorno `ink`).
6. **`<AgentPanel>`**: cabeçalho "Agente do recorte", balão de pergunta, `<Shimmer>` "Consultando o recorte…", `<ToolTag>` com estado aceso e a resposta como `<Ticket variant="open" severity="low">` com carimbo `Nº A01 · AGENTE`.
7. **`<FilterChip>`**: tag `sunken`, cantos 4 px, "Hub Color Shopping ×".
8. **`<Cursor>`**: seta simples `ink` com borda branca, clique com anel que expande e some em 250 ms.
9. **`<FlowNode>`** e **`<ChatBubble>`** para a cena da automação.

Fontes via `@remotion/google-fonts` (`LibreFranklin`, `ZillaSlab`). Composição: `width 1080`, `height 1350`, `fps 30`, `durationInFrames 1740`. Cada cena vira uma `<Sequence>` com os frames da seção 4; transições de 8–12 frames.

## 6. O que não dizer

- Não chamar de produto do iFood, não usar a marca nem mencionar a vaga.
- Não inventar usuários, empresas clientes, economia em reais ou ganho percentual de operação. Não existem métricas de uso.
- Não dizer "IA prevê", "machine learning" ou "tempo real": os alertas são regras estatísticas sobre dados de 2021, e o LLM só lê o recorte por ferramentas.
- Não dizer que o agente "sempre usa LLM": sem chave, ele responde por regras locais, e isso é uma qualidade a mostrar.
- Os nomes de lojas (Muspuo Smiru, Uvurusm) são anonimizados pelo próprio dataset. A legenda final já avisa.

## 7. Texto sugerido para o post (opcional)

> Gráfico mostra o problema. Quem opera delivery precisa saber o que fazer hoje.
>
> Construí a Central de Operações sobre 368.990 pedidos reais (Delivery Center, Kaggle): cada alerta vira uma comanda com o número e a ação, por exemplo qual hub revisar, em qual etapa e em qual faixa de horário. KPIs, gráficos, alertas e um agente de IA respondem sobre o mesmo recorte filtrado; o agente consulta os dados por tool calling e o servidor é quem aplica o filtro. Todo dia às 8h, um fluxo no n8n manda o briefing no Telegram com cada alerta encaminhado para o responsável.
>
> Astro + React no front, FastAPI + DuckDB no back, 202 testes, deploy na Vercel e no Render.
>
> App: dashboard-insight-kappa.vercel.app
> Código: github.com/EmersonPalatti/dashboard-insight

## 8. Prompt para abrir a conversa de produção

> Vou produzir um motion video de 58 s em Remotion, 4:5 (1080 × 1350, 30 fps), para o LinkedIn. O roteiro completo, com textos, números, cores, fontes, tempos por frame e lista de componentes, está em `video/roteiro-linkedin.md`. Siga-o à risca: não altere números nem textos de UI, use só os tokens listados e respeite as áreas seguras. Comece pelos componentes da seção 5 e pela cena 4 (a comanda aberta), que também é a capa. Depois monte as demais cenas em ordem. Use a skill `remotion-best-practices`.
