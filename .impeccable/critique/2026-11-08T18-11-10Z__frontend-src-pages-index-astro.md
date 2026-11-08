---
target: frontend/src/pages/index.astro (critique | animate)
total_score: 28
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
target_fingerprint: "sha256:94e49f1689403e76abd6bc25f216b5359b9cda705fc937293685e3357d0657ec"
target_path: "C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
timestamp: 2026-11-08T18-11-10Z
slug: frontend-src-pages-index-astro
---
Method: dual-agent (A: Haiku 5.5 high · B: Haiku 5.5 high), foco em movimento (critique | animate)

## Design Health Score
| # | Heurística | Nota | Problema-chave |
|---|---|---|---|
| 1 | Visibilidade do estado | 3 | Trend some e reconstrói a cada recorte; tema recria os 5 gráficos |
| 2 | Sistema × mundo real | 3 | "p.p.", "presos no fluxo" sem explicação |
| 3 | Controle e liberdade | 2 | Recorte novo reabre a comanda Nº 01 e zera o lugar; trend remonta |
| 4 | Consistência | 3 | Tokens e botões coesos; movimento inconsistente (abre com desdobra, fecha seco) |
| 5 | Prevenção de erro | 3 | Datas limitadas, cascata limpa hub/loja, comanda só rascunha |
| 6 | Reconhecimento | 3 | Chips, datas reais e metas de SLA no KPI |
| 7 | Flexibilidade | 3 | Teclado APG, URL compartilhável, export; sem atalhos |
| 8 | Estética e minimalismo | 2 | ~12 controles na barra; "Mais filtros" aberto leva a faixa fixa a ~225px |
| 9 | Recuperação de erro | 3 | Retry, cold start explicado |
| 10 | Ajuda | 3 | Rodapé de metodologia; "sem período anterior" repetido 6× |
| **Total** | | **28/40** | **Good** |

## Design Specificity Verdict
LLM: específico na fila de comandas (picote, Nº/categoria, severidade por forma, Ação em tinta, vermelho único); genérico abaixo dela (KPIs + ECharts + tabela padrão). O mundo para na coluna de alertas.
Detector: 2 avisos border-accent-on-rounded (FilterBar.tsx:176, ui/Panel.tsx:72), ambos falsos positivos (sublinhado de aba com só o topo arredondado). Overlay: 1 straggler real (index.astro:94, "Parquet." sozinho), 1 straggler sem fonte rastreada, 1 text-occlusion falso (o próprio rótulo do overlay).

## Priority Issues
- [P1] Gráficos se reconstroem a cada recorte e ao trocar tema (TrendChart.tsx:187 key por filtros; EChart.tsx:92-110 dispose/init por tema). Movimento que contradiz continuidade. Fix: uma instância por painel, setOption com transição curta, setTheme do ECharts 6. → /impeccable animate
- [P1] Mobile: primeira comanda ~1.417px abaixo; primeira tela é formulário. Fix: resumo do recorte em uma linha + atalho para comandas sob lg. → /impeccable adapt
- [P2] Recorte novo descarta o lugar do operador (AlertsPanel.tsx:158-161 reabre Nº 01; zoom do trend sobrevive a um intervalo que não existe mais). → /impeccable harden
- [P2] Resposta do agente cai fora da vista (AgentChat.tsx:220 rola um log que nunca transborda). → /impeccable polish
- [P2] Lacunas de movimento/live region: KpiStrip.tsx:166 anuncia 471 caracteres por recorte; TopBarStatus.tsx:41 pulsa sem guarda; ECharts sem política de reduced motion; sem rede global. → /impeccable harden

## Motion audit
Existe: ticket-unfold 280ms (bom, guardado), skeleton pulse (guardado), dim opacity-60, spinner, pontos do agente (guardados), pulse do status (sem guarda), hover transition-colors 150ms, ECharts com animação padrão.
Proposta focal: "Reimpressão do recorte" — quando a fila é recalculada, as comandas saem da impressora em sequência (ticket-unfold, 40ms entre elas, máx. 6, <400ms). Apoio: dobra reversa 160ms ao recolher; morph de 300ms nos gráficos no recorte, nenhum no tema; sem count-up, sem digitação falsa no agente.

## Persona Red Flags
Alex: filtro novo perde comanda aberta e zoom; "Mais filtros" empurra a página; 7 abas no ranking; resposta do agente fora da tela.
Sam: KPI reanuncia 471 caracteres; gráficos role=img sem valores; pulse e gráficos sem reduced motion.
Recrutador: no celular a primeira tela é um formulário; no desktop a resposta do agente pede rolagem.

## Minor Observations
Heatmap com ~130px vazios sob a legenda; "Perguntar ao agente…" quebra centralizado no mobile; troca de ícone do copiar link seca; toggle de tema 32px.

## Questions to Consider
1. Se o recorte é a verdade, por que a fila esquece qual comanda o operador lia?
2. O operador confiaria mais vendo as barras irem do valor antigo ao novo do que vendo o gráfico sumir?
3. O recrutador vê o agente em 3 minutos se a resposta começa abaixo da dobra?
