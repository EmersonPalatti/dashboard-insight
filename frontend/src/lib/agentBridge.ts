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
/** Por que a leitura do modelo não chegou (vem do backend em `fallback_reason`). */
export type AgentFallback = "quota" | "busy" | "timeout" | "error";

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
  fallback?: AgentFallback;
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
const STORAGE_VERSION = 1;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isReadingSource(value: unknown): value is AgentTicket["source"] {
  return value === "local" || value === "llm";
}

function isReadingStatus(value: unknown): value is AgentReadingStatus {
  return value === "rules" || value === "upgraded" || value === "cancelled" || value === "failed";
}

function isFallback(value: unknown): value is AgentFallback {
  return value === "quota" || value === "busy" || value === "timeout" || value === "error";
}

function sanitizeDrill(raw: unknown): AgentDrill | null {
  if (!isRecord(raw) || typeof raw.label !== "string" || !raw.label.trim() || !isRecord(raw.filters)) {
    return null;
  }
  const filters: Record<string, (string | number)[]> = {};
  for (const [key, value] of Object.entries(raw.filters)) {
    if (!Array.isArray(value)) return null;
    filters[key] = value.filter(
      (item): item is string | number => typeof item === "string" || (typeof item === "number" && Number.isFinite(item)),
    );
  }
  return { label: raw.label, filters };
}

function sanitizeTicket(raw: unknown): AgentTicket | null {
  if (!isRecord(raw)) return null;
  if (
    typeof raw.id !== "string" ||
    !raw.id ||
    typeof raw.series !== "number" ||
    !Number.isInteger(raw.series) ||
    raw.series <= 0 ||
    typeof raw.title !== "string" ||
    typeof raw.detail !== "string" ||
    typeof raw.action !== "string" ||
    typeof raw.scope !== "string" ||
    typeof raw.n !== "number" ||
    !Number.isFinite(raw.n) ||
    raw.n < 0 ||
    typeof raw.measured !== "number" ||
    !Number.isFinite(raw.measured) ||
    raw.measured < 0 ||
    typeof raw.lowSample !== "boolean" ||
    typeof raw.onRail !== "boolean" ||
    !isReadingSource(raw.source) ||
    !isReadingStatus(raw.status)
  ) {
    return null;
  }
  if (raw.fallback !== undefined && typeof raw.fallback !== "string") return null;
  if (raw.drilldowns !== undefined && !Array.isArray(raw.drilldowns)) return null;
  if (raw.toolLabels !== undefined && !Array.isArray(raw.toolLabels)) return null;
  const drilldowns = (raw.drilldowns ?? [])
    .map(sanitizeDrill)
    .filter((drill): drill is AgentDrill => drill !== null);
  const toolLabels = (raw.toolLabels ?? []).filter((label): label is string => typeof label === "string");
  const fallback = isFallback(raw.fallback) ? raw.fallback : undefined;
  return {
    id: raw.id,
    series: raw.series,
    title: raw.title,
    detail: raw.detail,
    action: raw.action,
    drilldowns,
    n: raw.n,
    measured: raw.measured,
    lowSample: raw.lowSample,
    source: raw.source,
    status: raw.status,
    ...(fallback ? { fallback } : {}),
    toolLabels,
    scope: raw.scope,
    onRail: raw.onRail,
  };
}

function sanitizeMessage(raw: unknown): AgentMessage | null {
  if (!isRecord(raw)) return null;
  if (
    typeof raw.id !== "number" ||
    !Number.isInteger(raw.id) ||
    raw.id <= 0 ||
    (raw.role !== "user" && raw.role !== "assistant") ||
    typeof raw.content !== "string" ||
    typeof raw.scope !== "string" ||
    (raw.error !== undefined && typeof raw.error !== "boolean")
  ) {
    return null;
  }
  let comanda: AgentTicket | undefined;
  if (raw.comanda !== undefined) {
    const valid = sanitizeTicket(raw.comanda);
    if (!valid) return null;
    comanda = valid;
  }
  return {
    id: raw.id,
    role: raw.role,
    content: raw.content,
    scope: raw.scope,
    ...(comanda ? { comanda } : {}),
    ...(raw.error !== undefined ? { error: raw.error } : {}),
  };
}

/** Valida mensagens restauradas de storage externo/versões antigas antes de hidratar o chat. */
export function sanitizeMessages(raw: unknown): AgentMessage[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<number>();
  const valid: AgentMessage[] = [];
  for (const item of raw) {
    const message = sanitizeMessage(item);
    if (!message || seen.has(message.id)) continue;
    seen.add(message.id);
    valid.push(message);
  }
  return valid.slice(-40);
}

function restoreMessages(): AgentMessage[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!isRecord(parsed) || parsed.version !== STORAGE_VERSION || !Array.isArray(parsed.messages)) {
      window.sessionStorage.removeItem(STORAGE_KEY);
      return [];
    }
    const valid = sanitizeMessages(parsed.messages);
    if (parsed.messages.length > 0 && valid.length === 0) {
      window.sessionStorage.removeItem(STORAGE_KEY);
    }
    return valid;
  } catch {
    try {
      window.sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* storage bloqueado */
    }
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
    if (list.length) {
      window.sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ version: STORAGE_VERSION, messages: list.slice(-40) }),
      );
    } else {
      window.sessionStorage.removeItem(STORAGE_KEY);
    }
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

/** Comandas do agente fixadas na fila. As de outro recorte aparecem marcadas como desatualizadas. */
export const $railAgentComandas = $agentComandas;

/** Alertas da API mais comandas do agente fixadas na fila. */
export function openComandaCount(alertCount: number, agentOnRail: number): number {
  return alertCount + agentOnRail;
}

function setAgentComandaOnRail(id: string, onRail: boolean) {
  $agentMessages.set(
    $agentMessages.get().map((message) =>
      message.comanda?.id === id ? { ...message, comanda: { ...message.comanda, onRail } } : message,
    ),
  );
}

/** Tira a comanda da fila. A mensagem continua na conversa. */
export function dismissAgentComanda(id: string) {
  setAgentComandaOnRail(id, false);
}

/** Fixa a comanda na fila de alertas desta sessão. */
export function pinAgentComanda(id: string) {
  setAgentComandaOnRail(id, true);
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
  void prefetchAgentChat().catch(() => {});
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
  void prefetchAgentChat().catch(() => {});
  $agentDraft.set(question);
  openAgent();
}
