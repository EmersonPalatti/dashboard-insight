# Roteiro: motion video do agente, Central de Operações

Segundo vídeo do LinkedIn: como era o agente de insights no primeiro vídeo e como ele está agora. Mesma linguagem visual, mesmas áreas seguras e mesmo projeto Remotion do [primeiro roteiro](roteiro-linkedin.md); a composição é `Agente` em [`remotion/src/agente/`](remotion/src/agente/).

Todo número abaixo tem origem na seção 2. Não troque número sem conferir de novo: o vídeo é público.

## 1. Ficha técnica

| Item | Valor |
|---|---|
| Formato | 4:5 vertical, **1080 × 1350 px**, 30 fps |
| Duração | **60 s** (1800 frames), 9 cenas |
| Áudio | Sem narração. Precisa ser entendido **sem som**. Marcas de efeito em `src/agente/sfx.ts` (impressora, clique, tick, notificação) |
| Visual | Tokens do `DESIGN.md` (seção 2 do primeiro roteiro). Sem sombras, cantos 4/8 px, Libre Franklin no texto, Zilla Slab só em números, carimbos e etiquetas de evidência |
| Capa | Frame **0:26** (780): grafo completo com a faixa "3,4 → 1,4 chamadas" |
| Comandos | `npm run dev` (Studio, composição `Agente`), `npm run render:agente` (`../out/agente.mp4`), `npm run capa:agente` (`../out/capa-agente.png`) |

## 2. Números e de onde vêm

| Número | Origem |
|---|---|
| v1 com 4 ferramentas (`get_kpis`, `get_breakdown`, `get_alerts`, `get_timeseries`), `get_breakdown` com uma dimensão | `backend/app/agent/llm.py` no commit `b3116d0` (o do primeiro vídeo) |
| "conta de cabeça", "46 s sem resposta", "cota estourada sem aviso" | Commits `be301d6` (o LLM fazia média de taxas) e `ed7858a` (keep-alive do OpenRouter fazia uma rodada passar de 46 s; 429 caía nas regras sem dizer o motivo) |
| 22 métricas, 11 dimensões, 18 conceitos, 10 mapas causais | `backend/app/semantic.toml` |
| "atraso" → `sla_rate`, "jantar" → 18h–22h, "sexta" → `weekday: 4` | `semantic.toml` (sinônimos de `metrics.sla_rate`, `concepts.jantar`, valores de `weekday`) |
| `frame` → `decompose` → `drill` → `synthesize`, < 0,5 s no servidor | `backend/app/agent/investigate.py` e README ("em menos de meio segundo") |
| 3,4 → 1,4 chamadas ao LLM; p50 11,5 s → 8,6 s | README (`INVESTIGATION_ENABLED`) e commit `ed7858a`: ERNIE, 4 perguntas roteadas ao grafo, 8 execuções por configuração |
| Março/2021: SLA 86,1% → 84,9% (−1,3 p.p.); Sampa Shopping 89,2% → 80,4%, 21% da queda, efeito taxa | `analytics.explain_change(sla_rate, hub)` no parquet real, 01/03–31/03/2021 contra 29/01–28/02/2021 |
| Etapas do Sampa Shopping: preparo −4,9, coleta +1,5, expedição +4,0, trânsito +2,9 min | `analytics.drill_cause(sla_rate, hub=27)`, mesmo recorte |
| Texto da comanda de março (título, linha do Sampa Shopping e ação) | Resposta real do agente local para "Por que o SLA caiu?" no mesmo recorte |
| "Leitura pelas regras. Aprofundando com o modelo…" e "Leitura do modelo. Consultou: …" | `frontend/src/components/agent/AgentComanda.tsx` e `markdown.tsx`; rótulos das ferramentas em `reading.py` |
| 20 s por pergunta, 35 s no grafo, até 8 perguntas simultâneas, disjuntor de cota | README ("Agente com limites") e `backend/app/config.py` |
| 45 perguntas, 13 categorias | `backend/evals/cases.py` |
| Confronto de 5 modelos gratuitos; ERNIE 5.5 Flash 6 de 7 pelo LLM, p50 9 s | Commit `22875f5` |
| Regras locais em 100% no CI | `tests/test_evals.py` e `.github/workflows/ci.yml` (`--min-pass-rate 1.0`) |
| 202 → 875 testes | 202 no primeiro roteiro; hoje 830 no `pytest --collect-only` + 45 no Vitest |

## 3. Arco

> Plugar um LLM em ferramentas é fácil. O difícil é confiar na resposta. O agente saiu de um loop livre, em que o modelo escolhia a rota e fazia a conta, para uma camada semântica única, um grafo que investiga no servidor, resposta progressiva com limites de produção e um placar que decide cada mudança.

| # | Tempo | Frames | Cena | Ideia |
|---|---|---|---|---|
| 1 | 0:00–0:05 | 0–150 | Gancho | Confiar na resposta é a parte difícil |
| 2 | 0:05–0:11 | 150–330 | Antes | Loop livre com 4 ferramentas |
| 3 | 0:11–0:18 | 330–540 | Camada semântica | A fala do operador vira chave validada |
| 4 | 0:18–0:28 | 540–840 | Grafo | O servidor investiga, o LLM redige |
| 5 | 0:28–0:35 | 840–1050 | Março real | Decomposição, etapa e ação |
| 6 | 0:35–0:43 | 1050–1290 | Resposta e limites | Regras na hora, modelo depois, quatro limites |
| 7 | 0:43–0:51 | 1290–1530 | Placar | 45 perguntas e o confronto de modelos |
| 8 | 0:51–0:56 | 1530–1680 | Antes e agora | Quatro números, tema escuro |
| 9 | 0:56–1:00 | 1680–1800 | Fechamento | Links |

## 4. Cena a cena

Frames locais de cada cena ficam no topo do arquivo dela (`A01` … `A08`). Textos e números ficam em `src/agente/data.ts`.

### Cena 1: Gancho (0:00–0:05)

- Título (68 px): **"Plugou LLM em tools? Fácil."** até 2,5 s; depois **"Confiar na resposta é outra história."**, com "Confiar" em `crit`.
- Palco: cartão "Agente · v1" com a pergunta "Por que o SLA caiu?" e quatro linhas de texto genérico. Três etiquetas com ○ de atenção entram em cascata: **conta de cabeça · 46 s sem resposta · cota estourada sem aviso**.
- Saída: uma linha vinho de 12 px varre de baixo para cima e leva tudo.

### Cena 2: Antes (0:05–0:11)

- Título: **"Antes: um loop livre de ferramentas."**
- Palco: cartão com carimbo `— V1 · ANTES`, a pergunta, um bloco vinho "LLM / decide a rota" ligado por fios tracejados a `get_kpis`, `get_breakdown`, `get_alerts` e `get_timeseries`. O fio ativo pula de ferramenta em ferramenta.
- Abaixo, com traço `muted`: **uma dimensão por vez · sem mapa causal · teste no olhômetro**.
- Legenda: "O modelo escolhia a rota e a conta."

### Cena 3: Camada semântica (0:11–0:18)

- Título: **"Agora: camada semântica única."**
- Palco: campo de busca digita "atraso no jantar de sexta"; cada termo ganha sublinhado vinho quando a linha dele entra no cartão `semantic.toml` ("inspirado no Genie do Databricks"):
  - atraso → `sla_rate` · food ≤ 60 · goods ≤ 120 min
  - jantar → `window: jantar` · 18h–22h
  - sexta → `weekday: 4` · segunda = 0
- Contadores: **22** métricas · **11** dimensões · **18** conceitos · **10** mapas causais.
- Selo `good`: "Testes cruzam a camada com o SQL". Legenda: "Sem SQL livre. Sem média de cabeça."

### Cena 4: Grafo (0:18–0:28)

- Título: **"Por que mudou? / O servidor investiga."** até 5 s; depois **"O LLM só redige, com a prova."**
- Palco: quatro nós empilhados, com um ponto vinho percorrendo o caminho:
  1. `frame` · `get_kpis` · enquadra a métrica e as quebras
  2. `decompose` · `explain_change` · efeito taxa + mix por hub e loja
  3. `drill` · `drill_cause` · acha a etapa que explica
  4. `synthesize` (vinho) · sem tools · redige a comanda com as provas
- Chave nos três primeiros: **< 0,5 s** "no servidor, sem LLM". Ao lado do quarto: **1 chamada** "ao LLM".
- Faixa comparativa (loop de tools × grafo): chamadas ao LLM **3,4 → 1,4**; tempo mediano **11,5 s → 8,6 s**. Nota: "Placar com ERNIE · 4 perguntas × 8 execuções".

### Cena 5: Março real (0:28–0:35)

- Título: **"Causa exata, não palpite."** Recorte: "01/03 a 31/03/2021 · vs. 29/01 a 28/02".
- Passo 1: SLA da rede **86,1% → 84,9%** (−1,3 p.p., `warn`). Quem mais puxou: **Sampa Shopping 89,2% → 80,4%**, etiqueta "21% da queda · efeito taxa".
- Passo 2: barras divergentes das etapas no Sampa Shopping contra o período anterior; expedição em destaque. Legenda: "Preparo caiu. Expedição subiu 4,0 min."
- Passo 3 (4,3 s): os passos sobem e a comanda imprime. Carimbo `— Nº A01 · AGENTE`, título "SLA caiu 1,3 p.p.", linha "Sampa Shopping: 89,2% → 80,4% (−0,3 p.p.; 21% da variação, efeito taxa)" e a ação:
  > Líder do hub Sampa Shopping deve revisar hoje a fila de expedição e o posicionamento de entregadores, antes das 12h (SLA 89,2% → 80,4%). Expedição +4,0 min contra o período anterior.
- Legenda: "Ação com dono, lugar e hora."

### Cena 6: Resposta e limites (0:35–0:43)

- Título A: **"Resposta na hora. / O modelo aprofunda depois."**
- Palco A: painel "Agente do recorte"; a pergunta sobe e a comanda das regras imprime logo em seguida, com a nota real da tela "Leitura pelas regras. Aprofundando com o modelo…" com brilho. Em 2,7 s passa um brilho pela comanda e a nota vira "Leitura do modelo. Consultou: Por que mudou, Etapa que explica o atraso." com check `good`.
- Título B (4 s): **"Se o modelo falhar, / a operação não para."**
- Palco B: quatro cartões com ícone: **Prazo de relógio** (20 s por pergunta · 35 s no grafo), **Disjuntor de cota** (cota acabou: regras assumem e avisam), **Semáforo** (até 8 perguntas ao LLM ao mesmo tempo), **Comanda validada** (hub fora do recorte não vira botão).
- Legenda: "Sem chave de API, as regras respondem."

### Cena 7: Placar (0:43–0:51)

- Título: **"Mudou o agente? Roda o placar."** Legenda: "Gabarito calculado dos dados na hora."
- Palco: **45** perguntas de operador e **13** categorias, com etiquetas SLA, cancelamento, comparação, por quê, fora de escopo, injeção de prompt.
- Cartão "Confronto de 5 modelos gratuitos": cinco quadrados, o primeiro preenche; check + **ERNIE 5.5 Flash** + "modelo padrão"; "6 de 7 respostas pelo LLM · p50 9 s"; "Os outros 4: prazo estourado ou provedor congestionado."
- Selo `good`: "Regras locais: 100% travado no CI".

### Cena 8: Antes e agora (0:51–0:56)

- O fundo passa para o tema escuro em 400 ms. Título: **"De protótipo a agente auditado."**
- Grade 2 × 2: **3,4 → 1,4** chamadas ao LLM no "por que mudou?" · **11,5 → 8,6 s** tempo mediano da investigação · **45** perguntas no placar do CI · **202 → 875** testes automatizados (o segundo número conta a partir de 202).

### Cena 9: Fechamento (0:56–1:00)

Reaproveita a cena 11 do primeiro vídeo (`S11Close`) com outro rodapé: "Projeto independente · dados públicos Delivery Center (Kaggle) · OpenRouter + LangGraph + DuckDB". Links na tela por 3,5 s.

## 5. Mudanças em relação ao rascunho aprovado

- **Cena 2 sem "prompt de 23 linhas" nem "3,4 chamadas · p50 11,5 s".** O prompt do v1 tinha 36 linhas, e as medidas 3,4 e 11,5 são do loop de tools já com a camada semântica, não do v1. Elas ficaram na comparação da cena 4, que é o que mediram.
- **Cena 5 com as quatro etapas**, não só expedição e preparo: o trânsito também subiu (+2,9 min), e esconder isso seria escolher o dado. A ação é a resposta real do agente, não um texto escrito para o vídeo.
- **Cena 6 sem "0,1 s".** A leitura pelas regras não foi cronometrada para o vídeo; a cena diz "na hora". Depois da chegada do modelo a comanda mantém o texto das regras e só a nota muda, para não inventar uma resposta do LLM.
- **Cena 7 sem "88,9%".** Esse placar completo foi medido antes do corretor ficar mais rígido (`8027302`); o vídeo usa o resultado do confronto (6 de 7, p50 9 s), que é o que escolheu o modelo.
- **Variação pior em `warn`, não em `crit`** (regra 8 do AGENTS.md): o vermelho fica só no "Confiar" do gancho.

## 6. O que não dizer

- Não citar iFood, vaga ou processo seletivo.
- Não dizer "IA prevê", "tempo real" ou "100% de acerto do LLM". O 100% travado no CI é das regras locais.
- Não inventar usuários, economia em reais ou ganho operacional.

## 7. Texto sugerido para o post

> Plugar um LLM em ferramentas é a parte fácil. Fazer o agente acertar a conta, responder rápido e continuar útil quando o modelo falha é onde dá trabalho.
>
> Depois do primeiro vídeo da Central de Operações (368.990 pedidos reais de delivery), reescrevi o agente de insights. O que mudou:
>
> 1. Camada semântica única no lugar de SQL livre: 22 métricas, 11 dimensões, 18 conceitos e 10 mapas causais num arquivo só, conferidos contra o SQL nos testes. "Atraso no jantar de sexta" vira SLA, 18h–22h e sexta antes de chegar ao modelo.
> 2. Grafo de investigação em LangGraph para "por que mudou?": o servidor decompõe a variação em efeito taxa e efeito mix e acha a etapa que explica, em menos de meio segundo. O LLM só redige. No placar, de 3,4 para 1,4 chamadas por pergunta e de 11,5 s para 8,6 s de mediana.
> 3. Resposta progressiva com limites de produção: a leitura pelas regras aparece na hora e o modelo atualiza depois; prazo de relógio, semáforo, disjuntor de cota e atalhos conferidos contra o recorte.
> 4. Placar com 45 perguntas de operador e gabarito tirado dos dados: foi com ele que o modelo padrão saiu de um confronto entre 5 modelos gratuitos. As regras locais ficam travadas em 100% no CI, e a suíte foi de 202 para 875 testes.
>
> App: dashboard-insight-kappa.vercel.app
> Código: github.com/EmersonPalatti/dashboard-insight
