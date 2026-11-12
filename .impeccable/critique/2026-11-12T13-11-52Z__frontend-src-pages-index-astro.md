---
target: frontend/src/pages/index.astro
total_score: 30
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 0
target_identity: "file:C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
target_fingerprint: "sha256:7c4e4e0d2c572b5b519bd167c45fab3d962677999b8420d05fbc94a962739d4c"
target_path: "C:\\Projects\\dashboard-insight\\frontend\\src\\pages\\index.astro"
timestamp: 2026-11-12T13-11-52Z
slug: frontend-src-pages-index-astro
---
Method: dual-agent (A: Crítica A, revisão de design, Grok 4.7 · B: Crítica B, detector e navegador, Grok 4.7)

## Design Health Score

| # | Heurística | Nota | Ponto principal |
|---|---|---|---|
| 1 | Visibilidade do estado do sistema | 3 | A referência "abaixo da rede" some nos cartões de KPI em 1024 e 320px |
| 2 | Correspondência com o mundo real | 3 | Voz de comanda fluente; cabeçalhos abreviados "Cancel." e "Seg." |
| 3 | Controle e liberdade | 3 | Aviso de URL inválida continua depois que o operador monta outro recorte |
| 4 | Consistência e padrões | 3 | Barra fixa mede 97px contra os 80px do DESIGN.md; ciclo sem veredito (decisão do dono) |
| 5 | Prevenção de erros | 3 | URL inválida é recusada com clareza; o aviso fica sobre um recorte válido |
| 6 | Reconhecimento em vez de memória | 3 | Faixa do ciclo ainda depende do rodapé para ser lida |
| 7 | Flexibilidade e eficiência | 3 | Ctrl K, Esc, ordenação; ranking esconde 3 colunas atrás de rolagem a 1440 |
| 8 | Estética e minimalismo | 3 | Abaixo da comanda, seis painéis com o mesmo peso de título |
| 9 | Recuperação de erros | 3 | Mensagem nomeia valor e aceito; sobrevive à recuperação |
| 10 | Ajuda e documentação | 3 | Glossário e dicas na página; cartão do ciclo sem frase própria |
| **Total** | | **30/40** | **Bom** |

## Design Specificity Verdict

Autoral. A fila picotada de comandas, a faixa aberta com a ação impressa, um único botão vermelho, severidade por forma e números em Zilla Slab 40px não cabem em outro produto. Os painéis de baixo são painéis de gráfico comuns, mantidos no mesmo mundo pela série em vinho e pela etiqueta "COMANDA Nº 01".

Detector (CLI): index.astro 0 achados; components 4 achados, todos `border-accent-on-rounded` e todos falsos positivos (PeriodPresets.tsx:34,166; ui/Panel.tsx:275,288: sublinhado de aba com raio só no topo).

Detector na página: 4 regras, todas já avaliadas: `flat-type-hierarchy` (corpo 13,6 / h2 16 / h3 18px, peso separa), `gradient-text` e `marquee` (brilho do texto de status em motion-content.css, respeita movimento reduzido), `bounce-easing` (especificado no DESIGN.md).

Overlay: injeção funcionou em aba própria, que foi fechada; não há aba [Human] com overlay visível.

## Medições (Avaliação B)

- Sem rolagem horizontal da página em 1440, 1280, 1024, 768, 390 e 320, nos dois temas, recorte padrão e hub 22 / março.
- Contraste: 0 falhas nos dois temas. Menor razão clara 4,86:1; escura 5,37:1.
- 0 controles sem nome acessível; sem níveis de título pulados.
- Texto cortado: h1 "Central de Operações" em 320 (226 de 167px); referência do KPI "· 10,6 p.p. abaixo da rede" em 1280 (153 de 119), 1024 (153 de 54) e 320 (153 de 89); "Nº 04 · CANCELAMENTO" em 1280, 1024 e 768 (143 de 114-118).
- Alvos abaixo do piso: links do rodapé "Código" (45×16,5) e "Delivery Center…" (16,5 a 36,9 de altura).
- Tabelas e gráficos não hidrataram na pré-visualização da B (aria-sort não lido ao vivo); na A hidrataram e a ordenação por Ciclo funcionou.

## Overall Impression

O topo cumpre a promessa do produto: abre no problema e na ação. O que resta é acabamento em bordas: aviso que não sai, referência cortada em telas estreitas, botão principal espremido em 320.

## What's Working

- A fila de comandas é um objeto físico e é a primeira coisa da página.
- O recorte é uma coisa só: escolher hub e mês reescreve URL, chips, período e a fila; o painel do agente encosta no conteúdo sem cobrir.
- URL inválida falha limpo, com valor recusado e valor aceito nomeados.

## Priority Issues

**[P2] Aviso de URL inválida sobrevive ao recorte seguinte.** Depois de limpar a URL e escolher Color Shopping em março, o bloco de KPIs ainda abre com "Hub 99999 (não existe nesta base)", logo acima de "SLA 74,2%, Crítico". Só sai em "Fechar aviso". Causa: ui/IgnoredNotice.tsx:16, `$ignored` só muda na leitura da URL. Correção: limpar `$ignored` quando o operador edita o recorte. Comando: /impeccable harden.

**[P2] Referência do KPI cortada em 1024 e 320px.** "· 10,6 p.p. abaixo da rede" cabe em 54px de 153 a 1024 e 89 de 153 a 320: o operador vê o veredito e a variação, mas não em relação a quê. Correção: deixar a referência quebrar para a linha de baixo quando não cabe. Causa: KpiStrip.tsx (linha de status). Comando: /impeccable adapt.

**[P2] Ação principal da comanda espremida em 320px.** "Ver só Color Shopping" mede 121×69 e quebra em duas linhas, com espaço vazio ao lado; a coluna perde 7rem sempre, mesmo quando o botão do agente não está ao lado. Causa: styles/motion-filters.css:53. Correção: botões na largura toda; a folga do botão flutuante fica só no scroll-padding. Comando: /impeccable adapt.

**[P2] Ranking esconde colunas a 1440px.** A tabela mede 1059px num quadro de 628: Preparo, Trânsito e Subsídio ficam atrás de rolagem horizontal. Correção: dar ao ranking a largura toda ou priorizar colunas. Comando: /impeccable layout.

**[P3] Faixa do topo.** O h1 corta em 320px (226 de 167px) e a 1280/1440 a linha do título começa em y=0. Causa: pages/index.astro:46. Comando: /impeccable polish.

## Persona Red Flags

**Alex:** ranking com 3 colunas atrás de rolagem a 1440; lista de hubs com 32 linhas (há busca); sem ação em lote nos pedidos.

**Sam:** anel de foco de 2px em todos os controles testados, Esc devolve o foco. Links do rodapé com 16,5px de altura; cabeçalhos lidos como "Cancel." e "Seg.".

**Casey:** sem rolagem horizontal em 320. Botão vermelho de 121px; nome do produto cortado; a 768 o botão do agente fica sobre a sparkline do SLA.

## Minor Observations

- Barra fixa com 97px (py-2 em index.astro:75 em volta de uma barra de 80px).
- "Nº 04 · CANCELAMENTO" corta na fila em 1280, 1024 e 768.
- Seis painéis abaixo da comanda com o mesmo peso de título.
- `impeccable live-server --background` não manteve a porta aberta nesta máquina.

## Questions to Consider

- O cartão do ciclo deveria dizer "sem régua", para a ausência de veredito ser uma decisão visível?
- Uma comanda que cita um KPI deveria marcar esse KPI também no recorte da rede toda?
- Em 320px, o botão vermelho não seria mais claro na largura toda?
