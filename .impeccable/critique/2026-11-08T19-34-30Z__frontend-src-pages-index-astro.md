---
target: dashboard (index.astro)
total_score: 28
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 1
target_identity: "file:C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
target_fingerprint: "sha256:d725756f6f1a219c6e20019b00572daf8d7a9bc7cb34beb5526f571be26b21cd"
target_path: "C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
timestamp: 2026-11-08T19-34-30Z
slug: frontend-src-pages-index-astro
---
Method: dual-agent (A: a05b63d96a705db5c · B: a2f0e3c5ecd5d5c75)

## Design Health Score
| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | KPI tile delta "—" reads as missing data |
| 2 | Match System / Real World | 3 | Export: "gerado no servidor via DuckDB" |
| 3 | User Control and Freedom | 3 | Esc/Fechar everywhere, removable chips, Limpar recorte |
| 4 | Consistency and Standards | 3 | Filters render 3 ways (bar, popover, sheet) by design |
| 5 | Error Prevention | 2 | Date pair accepts empty/partial ranges silently |
| 6 | Recognition Rather Than Recall | 3 | Segmento/Canal/Modal hidden behind popover |
| 7 | Flexibility and Efficiency | 3 | URL recorte + copy link; no shortcuts |
| 8 | Aesthetic and Minimalist Design | 3 | ~130px dead band left column at 1280 |
| 9 | Error Recovery | 2 | Agent/API failure paths not exercised |
| 10 | Help and Documentation | 3 | Cleaning rules disclosed in place |
| Total | | 28/40 | Good |

## Priority Issues
- [P1] Mobile header 186px at 390 (adapt)
- [P2] Left-column dead band at 1280 (layout)
- [P2] Small touch targets: Recolher 24px, Ver só 30px, agent chips 32px, Editar (adapt)
- [P2] Export copy leaks DuckDB (clarify)
- [P3] KPI "—" delta unlabelled; text-occlusion in comanda li (polish)
