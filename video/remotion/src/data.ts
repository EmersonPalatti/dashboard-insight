// Textos e números do roteiro (video/roteiro-linkedin.md), conferidos no parquet.
// Não altere valores: se precisar de outro dado, consulte a API do projeto.
import type { Severity } from "./components/SeverityMark";

export type Comanda = {
  number: string;
  category: string;
  severity: Severity;
  title: string;
  figure: string;
  figureRef?: string;
};

/** Cena 3: as seis comandas fechadas, na ordem do trilho. */
export const COMANDAS: Comanda[] = [
  { number: "01", category: "SLA", severity: "high", title: "Hub lento: Color Shopping", figure: "80,0% no SLA", figureRef: "recorte 86,2%" },
  { number: "02", category: "LOJA", severity: "high", title: "Loja sem entregas: Muspuo Smiru", figure: "100% cancelado" },
  { number: "03", category: "LOJA", severity: "high", title: "Loja crítica: Uvurusm", figure: "25,8% cancel.", figureRef: "recorte 4,6%" },
  { number: "04", category: "CANCELAMENTO", severity: "medium", title: "Cancelamento fora da curva: Elixir Shopping", figure: "30,8% cancel.", figureRef: "recorte 4,6%" },
  { number: "05", category: "FROTA", severity: "medium", title: "SLA cai no horário de pico", figure: "84,4% no pico", figureRef: "fora do pico 88,1%" },
  { number: "06", category: "DADOS", severity: "medium", title: "Pedidos presos no fluxo", figure: "17.280 presos", figureRef: "4,9% (> 4h)" },
];

/**
 * Layout da pilha de comandas (cena 3), reaproveitado na cena 4 para a Nº 01
 * sair exatamente de onde estava. Coordenadas absolutas no quadro 1080 × 1350.
 */
export const STACK = {
  headerTop: 350,
  firstTop: 404,
  stubHeight: 116,
  gap: 8,
};
export const stubTop = (i: number) => STACK.firstTop + i * (STACK.stubHeight + STACK.gap);

/** Cena 4: comanda Nº 01 aberta. */
export const COMANDA_01 = {
  title: "Hub lento: Color Shopping",
  detail:
    "SLA de 80,0% contra 86,2% do recorte em 4.592 entregas. Maior desvio na etapa de expedição (+1,3 min sobre a mediana do recorte).",
  // O bloco Ação vem em partes para as anotações (onde / o quê / quando).
  action: {
    a: "Gargalo dentro do ",
    where: "hub Color Shopping",
    b: ": ",
    what: "revisar fila de coleta e posicionamento de entregadores",
    c: " nos horários ",
    when: "12h–14h e 19h–21h",
    d: ". Meta: expedição abaixo da mediana do recorte.",
  },
  buttons: {
    primary: "Ver só Color Shopping",
    chart: "Ver no gráfico",
    agent: "Perguntar ao agente",
  },
};

/** Cena 5: "Onde o tempo vai, por hub" (medianas em minutos). Primeira linha = hub da comanda. */
export const STAGES_LEGEND = ["Preparo na loja", "Coleta", "Expedição", "Trânsito"] as const;
export const STAGES: { hub: string; prep: number; pickup: number; dispatch: number; transit: number }[] = [
  { hub: "Color Shopping", prep: 15.8, pickup: 1.5, dispatch: 7.7, transit: 16.8 },
  { hub: "Golden Shopping", prep: 15.9, pickup: 1.1, dispatch: 6.5, transit: 17.4 },
  { hub: "Subway Shopping", prep: 13.6, pickup: 2.1, dispatch: 7.9, transit: 17.3 },
  { hub: "Pagode Shopping", prep: 19.2, pickup: 1.9, dispatch: 5.0, transit: 14.4 },
  { hub: "Hip Hop Shopping", prep: 17.1, pickup: 1.4, dispatch: 7.2, transit: 16.7 },
  { hub: "Green Shopping", prep: 15.2, pickup: 0.8, dispatch: 3.1, transit: 13.8 },
  { hub: "Coffee Shopping", prep: 15.0, pickup: 2.2, dispatch: 6.8, transit: 18.7 },
  { hub: "People Shopping", prep: 15.6, pickup: 2.3, dispatch: 6.9, transit: 15.9 },
  { hub: "Rap Shopping", prep: 12.3, pickup: 2.3, dispatch: 7.4, transit: 15.7 },
  { hub: "Beach Shopping", prep: 13.5, pickup: 1.3, dispatch: 7.8, transit: 17.4 },
  { hub: "Purple Shopping", prep: 14.0, pickup: 1.5, dispatch: 7.1, transit: 19.2 },
  { hub: "Small Shopping", prep: 15.8, pickup: 1.6, dispatch: 6.4, transit: 14.8 },
  { hub: "Avenue Shopping", prep: 13.7, pickup: 1.9, dispatch: 7.3, transit: 16.5 },
  { hub: "Black Shopping", prep: 18.2, pickup: 2.0, dispatch: 4.6, transit: 14.6 },
  { hub: "Wolf Shopping", prep: 16.0, pickup: 2.7, dispatch: 7.3, transit: 17.9 },
];

/** Cena 6: KPIs antes (rede) e depois (Color Shopping). */
export const KPIS = [
  { label: "No prazo (SLA)", before: "86,2%", after: "80,0%", verdict: "Crítico", severity: "high" as Severity | "good" | null, ref: "6,2 p.p. abaixo da rede" },
  { label: "Ciclo mediano", before: "41,2 min", after: "44,3 min", verdict: null, severity: null, ref: "3,1 min acima da rede" },
  { label: "Cancelamento", before: "4,6%", after: "3,4%", verdict: "Dentro", severity: "good" as Severity | "good" | null, ref: "1,2 p.p. abaixo da rede" },
];

/** Cena 7: agente. */
export const AGENT = {
  header: "Agente do recorte",
  context: "Responde só sobre este recorte.",
  question: "Por que o Color Shopping está lento e o que fazer hoje?",
  thinking: "Consultando o recorte…",
  tools: ["KPIs do recorte", "Alertas do recorte", "Quebra por hub", "Quebra por loja", "Quebra por hora"],
  lock: "recorte: Color Shopping",
  stamp: "Nº A01 · AGENTE",
  title: "Color Shopping: SLA 80% por expedição lenta",
  detail:
    "Hub opera com SLA de 80,0% (recorte 86,2%) em 4.592 entregas; expedição 1,3 min acima da mediana do recorte (7,8 min vs 6,5 min).",
  action:
    "Revisar fila de coleta e posicionamento de entregadores no Color Shopping hoje, nas janelas 12h–14h e 19h–21h, para trazer expedição abaixo de 6,5 min.",
  buttons: { ghost: "Ver estágios do Color Shopping", pin: "Fixar na fila" },
};

/** Cena 8: cuidado com o dado. */
export const DATA_CARE = {
  figure: "98,5%",
  line: "dos pedidos do Elixir Shopping ficam 'presos' por mais de 4h",
  stamp: "DADOS",
  action:
    "Conferir a rotina de finalização desses pedidos (baixa manual, agendamento ou goods com retirada posterior) antes de cobrar SLA do hub.",
};

/** Cena 9: automação diária (n8n/exemplo-briefing.md). */
export const BRIEFING = {
  clock: "08:00",
  flow: ["Agenda 8h", "API", "Briefing + roteamento", "Telegram"],
  messages: [
    {
      heading: "📋 Briefing de 22/02/2021",
      lines: [
        "2.143 pedidos · GMV R$ 157.520,18 · ticket R$ 77,48",
        "SLA 86,9% · ciclo mediano 39,0 min",
        "Cancelamento 5,1%",
      ],
    },
    {
      heading: "🟠 Para: Time de operações da praça",
      lines: [
        "SLA cai no horário de pico. 84,1% no prazo no pico contra 90,5% fora dele.",
        "Ação: antecipar a escala de entregadores em 30 min antes das 11h.",
      ],
    },
    {
      heading: "🟠 Para: Líder do hub Pagode Shopping (31)",
      lines: [
        "Pedidos presos no fluxo: 120 entregas (5,9%) acima de 4h.",
        "Ação: conferir a rotina de finalização antes de cobrar SLA do hub.",
      ],
    },
  ],
};

/** Cena 10: stack. */
export const STACK_CHIPS = {
  Frontend: ["Astro", "React", "ECharts", "TanStack"],
  Backend: ["FastAPI", "DuckDB + Parquet", "Pydantic", "Tipos TS gerados do OpenAPI"],
  "IA e automação": ["OpenRouter (tool calling)", "Agente local por regras", "n8n", "Telegram"],
};

/** Cena 11: links. */
export const LINKS = {
  app: "dashboard-insight-kappa.vercel.app",
  repo: "github.com/EmersonPalatti/dashboard-insight",
  footer:
    "Projeto independente · dados públicos Delivery Center (Kaggle) · nomes de loja anonimizados pelo dataset",
};
