/**
 * Ponte entre ilhas e o painel do agente. As ilhas não compartilham árvore
 * React, então o estado do painel vive em átomos:
 *  - $agentOpen: painel aberto ou fechado (botão da barra, botão flutuante, Ctrl+K)
 *  - $agentDraft: pergunta pronta vinda de uma comanda ou gráfico. Preenche o
 *    campo sem enviar; o operador revisa e aperta Enviar.
 *  - $agentActivity: o que o botão de abrir mostra com o painel fechado.
 */
import { atom } from "nanostores";

/** Pergunta pendente para o campo do agente; `null` quando já foi consumida. */
export const $agentDraft = atom<string | null>(null);

export const $agentOpen = atom(false);

/** `pending`: consultando o recorte. `unread`: chegou resposta com o painel fechado. */
export type AgentActivity = "idle" | "pending" | "unread";
export const $agentActivity = atom<AgentActivity>("idle");

/** Comanda do agente. Série própria (`Nº A01`), só nesta aba, fora da fila de alertas do servidor. */
export interface AgentDrill {
  label: string;
  filters: Record<string, (string | number)[]>;
}

export type AgentReadingStatus = "rules" | "upgraded" | "cancelled" | "failed";

export interface AgentTicket {
  id: string;
  series: number;
  title: string;
  detail: string;
  action: string;
  drilldowns: AgentDrill[];
  n: number;
  measured: number;
  lowSample: boolean;
  source: "local" | "llm";
  status: AgentReadingStatus;
  toolLabels: string[];
  /** `JSON.stringify` do recorte no momento da pergunta. */
  scope: string;
  onRail: boolean;
}

export interface AgentMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  scope: string;
  comanda?: AgentTicket;
  error?: boolean;
}

const STORAGE_KEY = "central-ops:agent-messages";

function restoreMessages(): AgentMessage[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? (parsed as AgentMessage[]).slice(-40) : [];
  } catch {
    return [];
  }
}

/** Conversa da aba. A fila de comandas do agente sai daqui: some com a sessão, não com o servidor. */
export const $agentMessages = atom<AgentMessage[]>(restoreMessages());

export const $agentComandas = atom<AgentTicket[]>([]);

function projectComandas(list: readonly AgentMessage[]): AgentTicket[] {
  return list.flatMap((message) => (message.comanda?.onRail ? [message.comanda] : []));
}

$agentMessages.listen((list) => {
  try {
    if (list.length) window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(list.slice(-40)));
    else window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // storage cheio ou bloqueado: a conversa continua em memória
  }
  const tickets = projectComandas(list);
  // Fora do render de quem gravou a mensagem: a fila é outra ilha.
  queueMicrotask(() => $agentComandas.set(tickets));
});

$agentComandas.set(projectComandas($agentMessages.get()));

export function scopeKey(filters: object): string {
  return JSON.stringify(filters);
}

/** Tira a comanda da fila. A mensagem continua na conversa. */
export function dismissAgentComanda(id: string) {
  $agentMessages.set(
    $agentMessages.get().map((message) =>
      message.comanda?.id === id ? { ...message, comanda: { ...message.comanda, onRail: false } } : message,
    ),
  );
}

export function agentStamp(series: number) {
  return `Nº A${String(series).padStart(2, "0")}`;
}

type ChatModule = typeof import("@/components/AgentChat");
let chatModule: Promise<ChatModule> | null = null;

/**
 * Baixa o chunk da conversa (idempotente). O painel usa a mesma Promise no React.lazy,
 * então prefetch por intenção (hover, foco, idle) deixa a primeira abertura instantânea.
 * Se a rede falhar, a próxima chamada tenta de novo em vez de guardar a rejeição.
 */
export function prefetchAgentChat(): Promise<ChatModule> {
  chatModule ??= import("@/components/AgentChat").catch((err: unknown) => {
    chatModule = null;
    throw err;
  });
  return chatModule;
}

/** Quem abriu o painel recebe o foco de volta quando ele fecha. */
let opener: HTMLElement | null = null;

export function openAgent() {
  prefetchAgentChat();
  if ($agentOpen.get()) return;
  if (typeof document !== "undefined") {
    const el = document.activeElement;
    opener = el instanceof HTMLElement && el !== document.body ? el : null;
  }
  $agentOpen.set(true);
}

export function closeAgent() {
  if (!$agentOpen.get()) return;
  $agentOpen.set(false);
  const from = opener;
  opener = null;
  // o botão flutuante só reaparece depois que o React tira o painel: resolve o alvo dois quadros depois
  requestAnimationFrame(() =>
    requestAnimationFrame(() => {
      const shown = (el: HTMLElement | null) => !!el && el.isConnected && el.getClientRects().length > 0;
      // sem quem abriu (Ctrl+K com foco no corpo), vale o botão de abrir que estiver visível
      const target = shown(from)
        ? from
        : [...document.querySelectorAll<HTMLElement>("[data-agent-launcher]")].find((el) => shown(el));
      target?.focus({ preventScroll: true });
    }),
  );
}

export function toggleAgent() {
  if ($agentOpen.get()) closeAgent();
  else openAgent();
}

/** Abre o painel com a pergunta preenchida. A página fica onde está. */
export function askAgentAbout(question: string) {
  prefetchAgentChat();
  $agentDraft.set(question);
  openAgent();
}
