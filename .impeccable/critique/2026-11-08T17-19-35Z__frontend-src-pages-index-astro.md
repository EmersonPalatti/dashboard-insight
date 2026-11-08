---
target: index (Central de Operações)
total_score: 25
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
target_fingerprint: "sha256:3316d936cf04302ed6fbf979165ea43ee8bf345b76afe8d5103c8a210ad66d6f"
target_path: "C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
timestamp: 2026-11-08T17-19-35Z
slug: frontend-src-pages-index-astro
---
Method: dual-agent (A: a11ee96164d4e0aa0 · B: a6c6069185bd43700), Haiku 5.5 subagents, Opus 5.5 synthesis

## Design Health Score

| # | Heurística | Nota | Problema principal |
|---|---|---|---|
| 1 | Visibilidade do status | 3 | Agente fica 20+ s só com "Consultando o recorte…", sem etapa (AgentChat.tsx:240-249) |
| 2 | Mundo real | 3 | "Modal", "presos", "p90", "p.p." sem explicação |
| 3 | Controle e liberdade | 2 | Comanda aberta não recolhe; Escape no MultiSelect não devolve foco |
| 4 | Consistência | 2 | Seleção por shadow inset (FilterBar.tsx:77, Panel.tsx:73) contra a No Shadow Rule; 3 btn-primary |
| 5 | Prevenção de erros | 3 | Envio vazio bloqueado, aviso de recorte mudado |
| 6 | Reconhecimento | 2 | "1 filtro(s) ativo(s)" não nomeia o filtro (FilterBar.tsx:135) |
| 7 | Flexibilidade | 2 | Sem atalhos; URL compartilhável ajuda |
| 8 | Estética/minimalismo | 3 | Topo contido; página longa termina numa tabela |
| 9 | Recuperação de erros | 3 | ErrorState com "Tentar de novo", dica de servidor dormindo |
| 10 | Ajuda | 2 | Metodologia no rodapé; sem ajuda contextual de termos |
| **Total** | | **25/40** | **Aceitável** |

## Design Specificity Verdict
Comanda (picote, Nº 01 · CATEGORIA, bloco Ação em tinta, uma aberta por vez), faixa vinho e série em vinho são autorais. Abaixo da dobra cai para gráficos/tabelas genéricos de categoria.
Detector CLI: 0 findings (exit 0). Overlay no navegador: 2 `straggler` (viúvas tipográficas) no detalhe da comanda e no rodapé. Overflow horizontal de 17 px a 1280 px (causa não identificada); 390 px sem overflow.

## Priority Issues
1. [P1] Recorte não se nomeia e o agente fica abaixo da dobra (FilterBar.tsx:135; agente y≈617 em 1280×800). Fix: chips nomeados com x; ponte "Perguntar ao agente" na fila. /impeccable clarify + /impeccable layout
2. [P1] Foco invisível na faixa vinho no tema claro: outline var(--ink) #1A1A1A sobre #3D0B1F ≈ 1,05:1 (global.css:97-100). Fix: outline on-wine dentro de .bg-wine. /impeccable audit
3. [P2] Três btn-primary vermelhos simultâneos (AlertsPanel.tsx:59, AgentChat.tsx:276, StoreScatter.tsx:127, TrendChart.tsx:149). Fix: Enviar e ações de gráfico em btn-ink. /impeccable polish
4. [P2] Sombra inset como indicador de seleção (FilterBar.tsx:77, Panel.tsx:73). Fix: border-b-2 border-ink. /impeccable polish
5. [P2] Agente: *itálico* literal (parser só ** em AgentChat.tsx:31-36), espera sem progresso, aria-live no log inteiro (AgentChat.tsx:203). /impeccable harden

## Persona Red Flags
- Alex: sem atalhos; comanda aberta reseta para Nº 01 ao mudar recorte; Limpar longe dos filtros.
- Sam: foco invisível na faixa; gráficos role=img sem dados; aria-live re-anuncia conversa; listbox sem setas; title como tooltip.
- Recrutador: não lê "alertas e agente sobre o recorte" acima da dobra; "1 filtro(s)" não confirma o que fez.

## Minor Observations
- "sem período anterior" seis vezes no recorte "Tudo".
- Mobile: ~418 px de cabeçalho+filtros antes dos KPIs.
- skeleton animate-pulse sem prefers-reduced-motion.
- "Loja crítica: X … no Elixir Shopping" ambíguo loja/hub.
- Viúvas tipográficas (text-wrap: pretty resolve).

## Questions to Consider
- O agente deveria estar acima da dobra, ao lado da fila?
- A fila precisa mostrar 5–6 comandas ou "1 aberta + N em espera"?
- O vermelho marca o crítico ou a ação? Hoje marca os dois.
