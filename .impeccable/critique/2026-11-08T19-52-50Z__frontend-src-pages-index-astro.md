---
target: critique (index.astro)
total_score: 28
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
target_fingerprint: "sha256:6b062d27b29a2e71d6eb7a84a9c894b59f04d405072b93477543be0ab9d1a909"
target_path: "C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
timestamp: 2026-11-08T19-52-50Z
slug: frontend-src-pages-index-astro
---
Method: dual-agent (A: a6016ee65b0e3a1a6 · B: a7ed8da423ff8da39), Haiku.

| # | Heurística | Nota | Problema principal |
|---|---|---|---|
| 1 | Status do sistema | 3 | Status da API só por cor no celular |
| 2 | Linguagem | 3 | "Concentrado em good", "por day" |
| 3 | Controle | 3 | ok |
| 4 | Consistência | 3 | Ação com dois estilos (comanda x agente) |
| 5 | Prevenção de erro | 2 | KPI de loja sobre ~1% da base sem aviso |
| 6 | Reconhecimento | 3 | Resumo da comanda corta antes da ação |
| 7 | Flexibilidade | 3 | Sem atalhos |
| 8 | Estética | 3 | 1ª tela densa |
| 9 | Recuperação | 2 | Erro/cold start não verificados |
| 10 | Ajuda | 3 | Metodologia só no rodapé |
| Total | | 28/40 | Bom |

Especificidade: comanda autoral; moldura genérica. Detector: 5 falsos positivos conhecidos (border-accent-on-rounded x4, gradient-text x1); overlay injetado mas aba [Human] fechada pelo A (corrida paralela); marquee do shimmer respeita reduced motion.

Prioridades:
- [P1] Ação genérica em alerts.py:104 ("hub com pior SLA (alerta abaixo)") — clarify
- [P1] KPI de loja com 98,9% presos sem aviso de amostra (observado por A) — harden
- [P2] KpiStrip.tsx:180 truncate corta "fora do cálculo" — polish
- [P2] TrendChart.tsx:199 "por day"; alerts.py:135 "good"; alerts.py:176 "no {hub}"; sem aria-controls; tema 40px (TopBarStatus.tsx:68) — clarify/harden
- [P3] 5 chips + 6 comandas; resumo corta a ação — distill

Menores: faixa vinho ~1:1 no escuro; datas mm/dd/yyyy; Ver só 30px; barra 105px; exportação não nomeia recorte.
Personas: Alex sem atalhos; Sam rótulos/ECharts/foco; recrutador vê ação genérica na 1ª comanda.
