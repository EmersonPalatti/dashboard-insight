// Textos e números do vídeo do agente (video/roteiro-agente-linkedin.md). Cada valor foi conferido
// no código, no histórico do git ou no parquet; a origem está no roteiro, seção 2.
// Não altere número sem conferir de novo.

/** Cena 1: gancho. */
export const HOOK = {
  first: "Plugou LLM em tools? Fácil.",
  second: { accent: "Confiar", rest: " na resposta é outra história." },
  header: "Agente · v1",
  question: "Por que o SLA caiu?",
  // Commits be301d6 (conta de cabeça), ed7858a (rodada passava de 46 s; 429 sem motivo na tela).
  failures: ["conta de cabeça", "46 s sem resposta", "cota estourada sem aviso"],
};

/** Cena 2: como era antes (agente do 1º vídeo, commit b3116d0). */
export const BEFORE = {
  stamp: "V1 · ANTES",
  question: "Por que o SLA caiu?",
  model: "LLM",
  tools: ["get_kpis", "get_breakdown", "get_alerts", "get_timeseries"],
  /** Ordem em que o modelo "passeia" pelas ferramentas na animação (índices de `tools`). */
  walk: [0, 1, 3, 1, 2, 1],
  pains: ["uma dimensão por vez", "sem mapa causal", "teste no olhômetro"],
};

/** Cena 3: camada semântica (backend/app/semantic.toml). */
export const SEMANTIC = {
  query: "atraso no jantar de sexta",
  file: "semantic.toml",
  note: "inspirado no Genie do Databricks",
  maps: [
    { term: "atraso", key: "sla_rate", detail: "food ≤ 60 · goods ≤ 120 min" },
    { term: "jantar", key: "window: jantar", detail: "18h–22h" },
    { term: "sexta", key: "weekday: 4", detail: "segunda = 0" },
  ],
  counts: [
    { n: 22, label: "métricas" },
    { n: 11, label: "dimensões" },
    { n: 18, label: "conceitos" },
    { n: 10, label: "mapas causais" },
  ],
  seal: "Testes cruzam a camada com o SQL",
};

/** Cena 4: grafo de investigação (backend/app/agent/investigate.py). */
export const GRAPH = {
  nodes: [
    { id: "frame", tag: "get_kpis", text: "enquadra a métrica e as quebras" },
    { id: "decompose", tag: "explain_change", text: "efeito taxa + mix por hub e loja" },
    { id: "drill", tag: "drill_cause", text: "acha a etapa que explica" },
    { id: "synthesize", tag: "sem tools", text: "redige a comanda com as provas" },
  ],
  server: { figure: "< 0,5 s", line: ["no servidor,", "sem LLM"] },
  llm: { figure: "1 chamada", line: "ao LLM" },
  // README (INVESTIGATION_ENABLED) e commit ed7858a: ERNIE, 4 perguntas roteadas, 8 execuções.
  compare: [
    { label: "Chamadas ao LLM", before: "3,4", after: "1,4" },
    { label: "Tempo mediano", before: "11,5 s", after: "8,6 s" },
  ],
  compareHead: { before: "loop de tools", after: "grafo" },
  compareNote: "Placar com ERNIE · 4 perguntas × 8 execuções",
};

/**
 * Cena 5: março/2021 contra o período anterior, no parquet real.
 * explain_change(sla_rate, hub) e drill_cause(hub Sampa Shopping); ação = resposta do agente local.
 */
export const MARCH = {
  period: "01/03 a 31/03/2021 · vs. 29/01 a 28/02",
  sla: { label: "SLA da rede", before: "86,1%", after: "84,9%", delta: "−1,3 p.p." },
  driver: {
    label: "Quem mais puxou",
    name: "Sampa Shopping",
    before: "89,2%",
    after: "80,4%",
    evidence: "21% da queda · efeito taxa",
  },
  stagesTitle: "Etapas no Sampa Shopping · vs. período anterior",
  stages: [
    { label: "Preparo na loja", delta: -4.9, text: "−4,9 min" },
    { label: "Coleta", delta: 1.5, text: "+1,5 min" },
    { label: "Expedição", delta: 4.0, text: "+4,0 min", focus: true },
    { label: "Trânsito", delta: 2.9, text: "+2,9 min" },
  ],
  ticket: {
    stamp: "Nº A01 · AGENTE",
    title: "SLA caiu 1,3 p.p.",
    detail: "Sampa Shopping: 89,2% → 80,4% (−0,3 p.p.; 21% da variação, efeito taxa)",
    action:
      "Líder do hub Sampa Shopping deve revisar hoje a fila de expedição e o posicionamento de entregadores, antes das 12h (SLA 89,2% → 80,4%). Expedição +4,0 min contra o período anterior.",
  },
  captions: { stages: "Preparo caiu. Expedição subiu 4,0 min.", ticket: "Ação com dono, lugar e hora." },
};

/** Cena 6: leitura progressiva e limites de produção (frontend AgentComanda + README "Agente com limites"). */
export const PROGRESSIVE = {
  header: "Agente do recorte",
  question: "Por que o SLA caiu?",
  rulesNote: "Leitura pelas regras. Aprofundando com o modelo…",
  llmNote: "Leitura do modelo. Consultou: Por que mudou, Etapa que explica o atraso.",
  guards: [
    { icon: "clock", title: "Prazo de relógio", text: "20 s por pergunta · 35 s no grafo" },
    { icon: "breaker", title: "Disjuntor de cota", text: "cota acabou: regras assumem e avisam" },
    { icon: "gate", title: "Semáforo", text: "até 8 perguntas ao LLM ao mesmo tempo" },
    { icon: "shield", title: "Comanda validada", text: "hub fora do recorte não vira botão" },
  ],
  caption: "Sem chave de API, as regras respondem.",
} as const;

/** Cena 7: placar (backend/evals, commit 22875f5 para o confronto). */
export const EVALS = {
  cases: { n: 45, label: "perguntas de operador" },
  categories: { n: 13, label: "categorias" },
  chips: ["SLA", "cancelamento", "comparação", "por quê", "fora de escopo", "injeção de prompt"],
  duel: {
    title: "Confronto de 5 modelos gratuitos",
    winner: "ERNIE 5.5 Flash",
    tag: "modelo padrão",
    stats: "6 de 7 respostas pelo LLM · p50 9 s",
    others: "Os outros 4: prazo estourado ou provedor congestionado.",
  },
  seal: "Regras locais: 100% travado no CI",
  caption: "Gabarito calculado dos dados na hora.",
};

/** Cena 8: resumo (tema escuro). 875 = 830 testes do backend + 45 do frontend. */
export const SUMMARY = {
  title: "De protótipo a agente auditado.",
  cards: [
    { value: "3,4 → 1,4", label: "chamadas ao LLM no “por que mudou?”" },
    { value: "11,5 → 8,6 s", label: "tempo mediano da investigação" },
    { value: "45", label: "perguntas no placar do CI" },
    { value: "202 → 875", label: "testes automatizados" },
  ],
};

/** Cena 9: fechamento (links do 1º vídeo, rodapé novo). */
export const CLOSE_FOOTER =
  "Projeto independente · dados públicos Delivery Center (Kaggle) · OpenRouter + LangGraph + DuckDB";
