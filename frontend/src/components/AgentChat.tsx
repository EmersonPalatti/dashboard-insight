import { useStore } from "@nanostores/react";
import { Bot, ChevronDown, RotateCcw, SendHorizontal, X } from "lucide-react";
import { Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  $agentActivity,
  $agentDraft,
  $agentMessages,
  scopeKey,
  type AgentMessage,
  type AgentReadingStatus,
  type AgentTicket,
} from "@/lib/agentBridge";
import { askAgent, ApiError, type ChatResponse, type ChatTurn } from "@/lib/api/client";
import { $activeCount, $filters, toBody, type Recorte } from "@/lib/filters";
import { prefersReducedMotion } from "@/lib/media";
import { useApiHealth, useMeta } from "@/lib/query";
import { ActiveChips } from "./ui/ActiveChips";
import { useFilterModel } from "./filters/useFilterModel";
import { AgentChatComanda } from "./agent/AgentComanda";
import { Markdown, clip, plainText } from "./agent/markdown";

const SUGGESTIONS = [
  "Quais os alertas e o que fazer hoje?",
  "Onde está o gargalo do ciclo?",
  "Quais lojas mais cancelam?",
  "Como está o pico do jantar?",
  "Quanto estamos subsidiando de frete?",
];
/** Quantas sugestões aparecem de início; o resto fica atrás de "Mais perguntas". */
const SUGGESTIONS_SHOWN = 3;

let nextId = 1;
let nextSeries = 1;
for (const message of $agentMessages.get()) {
  nextId = Math.max(nextId, message.id + 1);
  if (message.comanda) nextSeries = Math.max(nextSeries, message.comanda.series + 1);
}

function historyOf(list: AgentMessage[]): ChatTurn[] {
  return list
    .filter((message) => !message.error)
    .slice(-8)
    .map((message) => ({ role: message.role, content: message.content.slice(0, 2000) }));
}

function failureDetail(err: unknown): string {
  if (err instanceof ApiError || err instanceof Error) return err.message;
  return "erro";
}

function toTicket(
  res: ChatResponse,
  messageId: number,
  series: number,
  scope: string,
  status: AgentReadingStatus,
): AgentTicket {
  return {
    id: `agent-${messageId}`,
    series,
    title: res.title,
    detail: res.diagnosis,
    action: res.action,
    drilldowns: res.drilldowns ?? [],
    n: res.base.n,
    measured: res.base.measured,
    lowSample: res.base.low_sample,
    source: res.source,
    status,
    toolLabels: res.tool_labels ?? [],
    scope,
    onRail: false,
  };
}

function replaceMessage(messageId: number, next: (message: AgentMessage) => AgentMessage) {
  $agentMessages.set($agentMessages.get().map((message) => (message.id === messageId ? next(message) : message)));
}

interface ConversationProps {
  /** Painel visível: foca o campo ao abrir e decide se resposta nova conta como não lida. */
  visible: boolean;
  onClose: () => void;
}

type Phase = "idle" | "local" | "model";

/** Conversa com o agente. O contêiner (lateral, flutuante ou folha) é do AgentDock. */
export function AgentConversation({ visible, onClose }: ConversationProps) {
  const messages = useStore($agentMessages);
  const filters = useStore($filters);
  const active = useStore($activeCount);
  const draft = useStore($agentDraft);
  const { data: meta } = useMeta();
  const health = useApiHealth();
  const [input, setInput] = useState(() => $agentDraft.get() ?? "");
  const [elapsed, setElapsed] = useState(0);
  const [slow, setSlow] = useState(false);
  const [moreSuggestions, setMoreSuggestions] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [upgradingId, setUpgradingId] = useState<number | null>(null);
  const [turn, setTurn] = useState(0);
  const [undo, setUndo] = useState<AgentMessage[] | null>(null);
  const { chips } = useFilterModel();
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const phaseRef = useRef<Phase>("idle");
  const generationRef = useRef(0);
  const scrolled = useRef<string | null>(null);
  /** Rascunho cujo caret vai ao fim assim que o React gravar esse valor no campo. */
  const caretAfter = useRef<string | null>(null);
  const llmEnabledRef = useRef(meta?.llm_enabled);
  const asleepRef = useRef(false);
  llmEnabledRef.current = meta?.llm_enabled;
  asleepRef.current = health.isError || slow;

  const setBusy = (next: Phase) => {
    phaseRef.current = next;
    setPhase(next);
  };

  const scopeNow = scopeKey(filters);
  const latestAnswer = [...messages].reverse().find((message) => message.role === "assistant");
  const scrollKey = phase === "local" ? `pending-${turn}` : latestAnswer ? String(latestAnswer.id) : "";

  // O log rola até a pergunta do turno (quando existe) para manter pergunta e resposta juntas à vista.
  useEffect(() => {
    if (!scrollKey || scrolled.current === scrollKey) return;
    const log = logRef.current;
    const answer = log?.querySelector<HTMLElement>(`[data-answer="${CSS.escape(scrollKey)}"]`);
    if (!log || !answer) return;
    const target = answer.previousElementSibling?.hasAttribute("data-question") ? answer.previousElementSibling : answer;
    const top = target.getBoundingClientRect().top - log.getBoundingClientRect().top + log.scrollTop - 8;
    log.scrollTo({ top: Math.max(0, top), behavior: visible && !prefersReducedMotion() ? "smooth" : "auto" });
    scrolled.current = scrollKey;
  }, [scrollKey, visible, messages.length]);

  // Foco no campo ao abrir o painel. A pergunta pronta de uma comanda tem o próprio efeito abaixo.
  useEffect(() => {
    if (visible && !$agentDraft.get()) inputRef.current?.focus({ preventScroll: true });
  }, [visible]);

  // O botão de abrir mostra a espera e a resposta que chegou com o painel fechado.
  const answers = messages.filter((message) => message.role === "assistant").length;
  const seenAnswers = useRef(answers);
  useEffect(() => {
    const current = $agentActivity.get();
    let next = current;
    if (phase !== "idle") next = "pending";
    else if (!visible && answers > seenAnswers.current) next = "unread";
    else if (visible || current === "pending") next = "idle";
    if (next !== current) $agentActivity.set(next);
    if (visible) seenAnswers.current = answers;
  }, [phase, answers, visible]);

  // Segundos só na espera da leitura local. A linha do servidor dormindo depende do /api/health.
  useEffect(() => {
    if (health.isSuccess) return setSlow(false);
    const timer = window.setTimeout(() => setSlow(true), 2500);
    return () => window.clearTimeout(timer);
  }, [health.isSuccess]);

  useEffect(() => {
    if (phase !== "local") return;
    const started = Date.now();
    const id = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => {
      window.clearInterval(id);
      setElapsed(0);
    };
  }, [phase]);

  // Ponte com a comanda: preenche o campo e foca, mas não envia. O operador revisa e aperta Enviar.
  useEffect(() => {
    if (draft === null) return;
    const el = inputRef.current;
    el?.focus({ preventScroll: true });
    if (el && el.value === draft) el.setSelectionRange(draft.length, draft.length);
    else caretAfter.current = draft;
    setInput(draft);
    $agentDraft.set(null);
  }, [draft]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el || caretAfter.current !== input) return;
    caretAfter.current = null;
    el.setSelectionRange(input.length, input.length);
  }, [input]);

  // O campo cresce com o texto, até 10rem, para a pergunta pronta caber inteira.
  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [input]);

  const cancel = () => abortRef.current?.abort();

  const run = async (question: string, history: ChatTurn[], recorte: Recorte, scope: string, gen: number) => {
    const localCtrl = new AbortController();
    abortRef.current = localCtrl;
    setBusy("local");
    let local: ChatResponse;
    try {
      local = await askAgent(
        { question, filters: toBody(recorte), history, engine: "local" },
        localCtrl.signal,
      );
    } catch (err) {
      if (gen !== generationRef.current) return;
      setBusy("idle");
      if (localCtrl.signal.aborted) return;
      const detail = failureDetail(err);
      const content = asleepRef.current
        ? `Não consegui responder agora (${detail}). O servidor está acordando. Tente de novo em alguns segundos.`
        : `Não consegui responder agora (${detail}). Tente de novo.`;
      $agentMessages.set([
        ...$agentMessages.get(),
        { id: nextId++, role: "assistant", content, scope, error: true },
      ]);
      return;
    }
    if (gen !== generationRef.current || localCtrl.signal.aborted) {
      if (gen === generationRef.current) setBusy("idle");
      return;
    }
    const assistantId = nextId++;
    const series = nextSeries++;
    $agentMessages.set([
      ...$agentMessages.get(),
      {
        id: assistantId,
        role: "assistant",
        content: local.answer,
        scope,
        comanda: toTicket(local, assistantId, series, scope, "rules"),
      },
    ]);
    if (llmEnabledRef.current === false) {
      setBusy("idle");
      return;
    }
    const llmCtrl = new AbortController();
    abortRef.current = llmCtrl;
    setUpgradingId(assistantId);
    setBusy("model");
    try {
      const llm = await askAgent(
        { question, filters: toBody(recorte), history, engine: "auto" },
        llmCtrl.signal,
      );
      if (gen !== generationRef.current) return;
      if (llmCtrl.signal.aborted) {
        replaceMessage(assistantId, (message) =>
          message.comanda ? { ...message, comanda: { ...message.comanda, status: "cancelled" } } : message,
        );
        return;
      }
      if (llm.source === "llm") {
        replaceMessage(assistantId, (message) =>
          message.comanda
            ? {
                ...message,
                content: llm.answer,
                comanda: {
                  ...toTicket(llm, assistantId, message.comanda.series, message.comanda.scope, "upgraded"),
                  onRail: message.comanda.onRail,
                },
              }
            : message,
        );
      }
    } catch {
      if (gen !== generationRef.current) return;
      const status: AgentReadingStatus = llmCtrl.signal.aborted ? "cancelled" : "failed";
      replaceMessage(assistantId, (message) =>
        message.comanda ? { ...message, comanda: { ...message.comanda, status } } : message,
      );
    } finally {
      if (gen === generationRef.current) {
        setUpgradingId(null);
        setBusy("idle");
      }
    }
  };

  const send = (question: string) => {
    const q = question.trim();
    if (!q || phaseRef.current !== "idle") return;
    setUndo(null);
    const history = historyOf($agentMessages.get());
    const scope = scopeKey(filters);
    phaseRef.current = "local";
    const gen = generationRef.current + 1;
    generationRef.current = gen;
    const nextTurn = turn + 1;
    setTurn(nextTurn);
    $agentMessages.set([...$agentMessages.get(), { id: nextId++, role: "user", content: q, scope }]);
    setInput("");
    // A pergunta sugerida some ao ser enviada: o foco vai para o campo, não para o body (Esc segue no painel).
    inputRef.current?.focus({ preventScroll: true });
    void run(q, history, filters, scope, gen);
  };

  const wipe = () => {
    const current = $agentMessages.get();
    if (!current.length) return;
    generationRef.current += 1;
    abortRef.current?.abort();
    setBusy("idle");
    setUpgradingId(null);
    setUndo(current);
    $agentMessages.set([]);
  };

  const restore = () => {
    if (!undo) return;
    $agentMessages.set(undo);
    setUndo(null);
  };

  const scopeChanged = messages.length > 0 && messages.at(-1)!.scope !== scopeNow;
  const serverAsleep = health.isError || slow;

  // Só a última resposta vai para o leitor de tela, e só quando o texto muda.
  const announcement = useMemo(() => {
    const latest = [...messages].reverse().find((message) => message.role === "assistant");
    if (!latest) return "";
    if (latest.comanda) return `Comanda do agente: ${latest.comanda.title}. Ação: ${latest.comanda.action}`;
    const text = clip(plainText(latest.content));
    return latest.error ? text : `Resposta do agente: ${text}`;
  }, [messages]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="grid gap-2 border-b border-rule px-4 pt-3 pb-3">
        <div className="flex items-center justify-between gap-2">
          <h2 id="agent-title" className="section-title flex items-center gap-2">
            <Bot className="size-4 text-series" aria-hidden /> Agente do recorte
          </h2>
          <div className="flex items-center gap-1">
            {messages.length > 0 && (
              <button type="button" className="btn-ghost hit-target min-h-8 px-2.5 py-1 text-meta max-lg:min-h-11" onClick={wipe}>
                <RotateCcw className="size-3.5" aria-hidden /> Nova conversa
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Fechar agente"
              title="Fechar (Esc)"
              className="hit-target inline-flex size-8 items-center justify-center rounded-card text-muted hover:bg-sunken hover:text-ink max-lg:size-11"
            >
              <X className="size-4" aria-hidden />
            </button>
          </div>
        </div>
        {/* O recorte da conversa fica à vista: mexer nos filtros com o painel aberto muda a próxima resposta. */}
        <div className="grid gap-1.5">
          {chips.length === 0 ? (
            <p className="label text-pretty">Recorte completo: todos os pedidos do período.</p>
          ) : (
            <ActiveChips chips={chips} />
          )}
          <p className="text-meta text-pretty text-muted">
            Responde só sobre {active ? (active === 1 ? "este filtro" : `estes ${active} filtros`) : "este recorte"}.{" "}
            {meta ? (meta.llm_enabled ? "Respostas calculadas direto sobre os dados do recorte." : "Leitura local por regras e estatísticas do recorte.") : ""}
          </p>
        </div>
      </header>

      <div ref={logRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain bg-field p-4" role="log" aria-live="off" aria-label="Conversa com o agente">
        {messages.length === 0 && (
          <div className="space-y-2">
            {undo && (
              <div className="flex items-center justify-between gap-2 rounded-card border border-rule bg-surface px-3 py-2">
                <p className="text-body">Conversa apagada.</p>
                <button type="button" className="btn-ghost hit-target min-h-8 px-2.5 py-1 text-meta max-lg:min-h-11" onClick={restore}>
                  Desfazer
                </button>
              </div>
            )}
            <p className="label">Comece por uma destas ou escreva a sua:</p>
            <div className="grid gap-1.5">
              {(moreSuggestions ? SUGGESTIONS : SUGGESTIONS.slice(0, SUGGESTIONS_SHOWN)).map((suggestion) => (
                <button key={suggestion} type="button" className="btn-ghost justify-start text-left max-lg:min-h-11" onClick={() => send(suggestion)}>
                  {suggestion}
                </button>
              ))}
            </div>
            {SUGGESTIONS.length > SUGGESTIONS_SHOWN && (
              <button
                type="button"
                className="btn-ghost hit-target min-h-8 px-2.5 py-1 text-meta max-lg:min-h-11"
                aria-expanded={moreSuggestions}
                onClick={() => setMoreSuggestions((value) => !value)}
              >
                <ChevronDown className={`size-3.5 transition-transform duration-(--duration-fast) ease-(--ease-smooth-out) motion-reduce:transition-none ${moreSuggestions ? "rotate-180" : ""}`} aria-hidden />
                Mais perguntas
              </button>
            )}
          </div>
        )}
        {messages.map((message, index) => {
          const prev = messages[index - 1];
          return (
            <Fragment key={message.id}>
              {prev && message.role === "user" && prev.scope !== message.scope && (
                <p className="border-t border-dashed border-rule pt-2 text-center text-meta text-muted">
                  recorte mudou: as respostas abaixo usam os filtros novos
                </p>
              )}
              {message.role === "user" ? (
                <div data-question={message.id} className="ml-8 rounded-card border border-rule bg-sunken px-3 py-2 text-body">
                  {message.content}
                </div>
              ) : message.comanda ? (
                <div
                  data-answer={message.id}
                  className="transition-[opacity,translate,filter] duration-(--duration-fast) ease-(--ease-smooth-out) starting:translate-y-(--distance-micro) starting:opacity-0 starting:blur-(--blur-small) motion-reduce:transition-none"
                >
                  <AgentChatComanda
                    ticket={message.comanda}
                    stale={message.comanda.scope !== scopeNow}
                    waiting={phase === "model" && upgradingId === message.id}
                    onCancel={cancel}
                  />
                </div>
              ) : (
                <div
                  data-answer={message.id}
                  className={`mr-2 rounded-card border bg-surface px-3 py-2.5 text-body transition-[opacity,translate,filter] duration-(--duration-fast) ease-(--ease-smooth-out) starting:translate-y-(--distance-micro) starting:opacity-0 starting:blur-(--blur-small) motion-reduce:transition-none ${message.error ? "border-warn" : "border-rule"}`}
                >
                  <Markdown text={message.content} />
                </div>
              )}
            </Fragment>
          );
        })}
        {phase === "local" && (
          <div data-answer={`pending-${turn}`} role="status" className="mr-2 px-3 text-muted">
            <p className="text-aux tabular-nums">
              <span className="shimmer-text" data-text="Consultando o recorte…">
                Consultando o recorte…
              </span>
              {elapsed >= 5 && <span aria-hidden> {elapsed} s</span>}
            </p>
            {serverAsleep && <p className="text-meta">O servidor está acordando. A primeira leitura leva até ~40 s.</p>}
            <button type="button" className="btn-ghost hit-target mt-1 min-h-8 px-2.5 py-1 text-meta max-lg:min-h-11" onClick={cancel}>
              Cancelar
            </button>
          </div>
        )}
      </div>

      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {announcement}
      </p>

      {scopeChanged && phase === "idle" && (
        <p className="mx-4 my-2 rounded-card border border-rule bg-sunken px-3 py-1.5 text-meta text-muted">
          Os filtros mudaram desde a última resposta. A próxima pergunta já usa o recorte novo.
        </p>
      )}

      <form
        className="flex items-end gap-2 border-t border-rule p-3"
        onSubmit={(event) => {
          event.preventDefault();
          send(input);
        }}
      >
        <label className="sr-only" htmlFor="agent-input">
          Pergunta para o agente
        </label>
        <textarea
          id="agent-input"
          ref={inputRef}
          rows={1}
          value={input}
          maxLength={800}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== "Enter" || event.shiftKey) return;
            const native = event.nativeEvent as { isComposing?: boolean; keyCode?: number };
            if (native.isComposing || native.keyCode === 229) return;
            event.preventDefault();
            send(input);
          }}
          placeholder="Pergunte sobre este recorte…"
          className="max-h-40 min-h-11 w-full min-w-0 flex-1 resize-none overflow-y-auto rounded-card border border-rule bg-surface px-3 py-2 text-body outline-none placeholder:text-muted focus:border-ink lg:min-h-10"
        />
        <button type="submit" className="btn-ink justify-center max-lg:min-h-11 max-lg:min-w-11 lg:h-10 lg:px-3.5" disabled={!input.trim() || phase !== "idle"} aria-label="Enviar">
          <SendHorizontal className="size-4" aria-hidden />
        </button>
      </form>
    </div>
  );
}
