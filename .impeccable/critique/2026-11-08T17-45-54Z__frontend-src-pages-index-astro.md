---
target: Central de Operações (index.astro)
total_score: 25
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
target_fingerprint: "sha256:bec3b0add9f012bae614ec3157e4efa129b193441913c0f7468990e1b10e0fc3"
target_path: "C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
timestamp: 2026-11-08T17-45-54Z
slug: frontend-src-pages-index-astro
---
Method: dual-agent (A: Haiku 5.5 high design review · B: Haiku 5.5 high detector + browser)

| # | Heurística | Nota | Problema principal |
|---|---|---|---|
| 1 | Status do sistema | 3 | Dado velho só esmaece 60% |
| 2 | Mundo real | 3 | "por day" (TrendChart.tsx:192), "Markdown" (ExportDialog.tsx:87) |
| 3 | Controle e liberdade | 2 | Comanda aberta não recolhe; MultiSelect só fecha com Escape, não com Tab |
| 4 | Consistência | 2 | Listbox inválido; role=radio sem setas (Panel.tsx:62); DESIGN.md diz Enviar vermelho |
| 5 | Prevenção de erros | 2 | Recorte sem pedidos afirma "dentro do esperado" (AlertsPanel.tsx:122-129) |
| 6 | Reconhecimento | 3 | Chips nomeiam o recorte |
| 7 | Flexibilidade | 2 | Sem atalhos, ~19 Tabs até o conteúdo |
| 8 | Estética | 3 | 9 painéis, rótulos condensados pequenos |
| 9 | Recuperação de erros | 2 | Foco cai no BODY ao abrir comanda |
| 10 | Ajuda | 3 | Metodologia e SLA ao lado dos KPIs |
| Total | | 25/40 | Aceitável |

Detector: 2x border-accent-on-rounded (FilterBar.tsx:172, ui/Panel.tsx:72), falsos positivos (sublinhado de aba). Overlay: 2 stragglers. B: data final sem nome acessível (FilterBar.tsx:180-200).

## Problemas prioritários
1. [P1] Teclado perde o lugar: foco no BODY ao abrir comanda (AlertsPanel.tsx:133-138); datas com outline-none (FilterBar.tsx:189,199); data final sem nome. -> harden
2. [P1] Recorte vazio diz "dentro do esperado" (AlertsPanel.tsx:122-129). -> clarify
3. [P1] MultiSelect não é combobox: option dentro de li, sem setas, não fecha no focusout. -> harden
4. [P2] Barra de filtros sticky 113px, ~14 decisões antes do 1º KPI; Segmento/Canal/Modal em "Mais filtros". -> layout
5. [P2] Vermelho em células de BreakdownTable (63-72) e OrdersTable (28,40), limiares no frontend. -> colorize

## Personas
Alex: 19 Tabs, sem atalhos, foco some, brush/heatmap só mouse. Sam: volta ao topo, data final sem nome, fila sem headings, ol aria-live, gráficos sem tabela. Operador: hub sem pedidos parece saudável; sem "resolvida"; alvos <24px no celular (28/74).

## Menores
DESIGN.md desatualizado (Enviar); severidade alta/média/baixa vs Crítico/Atenção/Observar; numeração muda com filtro; chip #999999; ExportDialog sem nome; medianas empilhadas não somam; 2 stragglers; "sem período anterior" x6.

## Perguntas
Fila primeiro com filtros recolhidos? "Tudo certo" sem dados? Medianas empilhadas honestas?
