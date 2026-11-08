import { useStore } from "@nanostores/react";
import { useMutation } from "@tanstack/react-query";
import { Bot, ChevronDown, Cpu, RotateCcw, SendHorizontal, Wrench } from "lucide-react";
import { atom } from "nanostores";
import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { $agentDraft } from "@/lib/agentBridge";
import { askAgent, type ChatResponse } from "@/lib/api/client";
import { $activeCount, $filters, toBody, type Recorte } from "@/lib/filters";
import { island, useMeta } from "@/lib/query";

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  scope: string;
  meta?: Pick<ChatResponse, "mode" | "model" | "tools_used">;
  error?: boolean;
}

/** Histórico vive num átomo: sobrevive a re-renders e pode ser lido por outras ilhas. */
const $messages = atom<Message[]>([]);
let nextId = 1;

const SUGGESTIONS = [
  "Quais os alertas e o que fazer hoje?",
  "Onde está o gargalo do ciclo?",
  "Quais lojas mais cancelam?",
  "Como está o pico do jantar?",
  "Quanto estamos subsidiando de frete?",
];
/** Quantas sugestões aparecem de início; o resto fica atrás de "Mais perguntas". */
const SUGGESTIONS_SHOWN = 3;

/**
 * Um tokenizador para o markdown inline. Ordem importa: código, negrito, depois itálico.
 * _itálico_ só abre e fecha em fronteira de palavra, então snake_case (tools_used) fica intacto.
 */
const INLINE =
  /`([^`\n]+)`|\*\*([^*\n]+?)\*\*|(?<![\p{L}\p{N}])_([^_\s](?:[^_\n]*[^_\s])?)_(?![\p{L}\p{N}])|\*([^*\s](?:[^*\n]*[^*\s])?)\*/gu;

/** Markdown inline como ReactNode, sem innerHTML. Asterisco solto ("5 * 3") continua literal. */
function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(INLINE)) {
    const at = m.index ?? 0;
    if (at > last) out.push(text.slice(last, at));
    const key = out.length;
    const [, code, bold, underscore, star] = m;
    if (code !== undefined) {
      out.push(
        <code key={key} className="rounded-[4px] bg-sunken px-1 text-[0.9em]">
          {code}
        </code>,
      );
    } else if (bold !== undefined) {
      out.push(<strong key={key}>{inline(bold)}</strong>);
    } else {
      out.push(<em key={key}>{inline(underscore ?? star)}</em>);
    }
    last = at + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Remove os marcadores inline, mantendo o conteúdo. */
function stripMarks(text: string): string {
  return text.replace(INLINE, (_m, code, bold, underscore, star) => code ?? stripMarks(bold ?? underscore ?? star));
}

/** Texto puro para leitor de tela: sem marcadores, títulos, marcas de lista ou tabela. */
function plainText(md: string): string {
  const flat = md
    .replace(/^\s*(?:#{1,4}\s+|[-*•]\s+|\d+\.\s+)/gm, "")
    .replace(/^\s*\|[\s:|-]+\|\s*$/gm, "")
    .replace(/\|/g, " ");
  return stripMarks(flat).replace(/\s+/g, " ").trim();
}

function clip(text: string, max = 200): string {
  return text.length > max ? `${text.slice(0, max).trimEnd()}…` : text;
}

function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) {
      blocks.push(
        <ul key={`ul-${blocks.length}`} className="ml-4 list-disc space-y-0.5">
          {list.map((li, i) => (
            <li key={i}>{inline(li)}</li>
          ))}
        </ul>,
      );
      list = [];
    }
  };
  let table: string[][] = [];
  const flushTable = () => {
    if (!table.length) return;
    const [head, ...body] = table;
    blocks.push(
      <div key={`t-${blocks.length}`} className="overflow-x-auto">
        <table className="w-full text-[0.85rem] tabular-nums">
          <thead>
            <tr>
              {head.map((c, i) => (
                <th key={i} className="border-b border-rule px-1.5 py-1 text-left font-semibold">
                  {inline(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {body.map((r, i) => (
              <tr key={i}>
                {r.map((c, j) => (
                  <td key={j} className="border-b border-rule/60 px-1.5 py-1">
                    {inline(c)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    );
    table = [];
  };
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    if (/^\s*\|.*\|\s*$/.test(line)) {
      flush();
      if (!/^\s*\|[\s:|-]+\|\s*$/.test(line)) table.push(line.trim().slice(1, -1).split("|").map((c) => c.trim()));
      continue;
    }
    flushTable();
    if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) continue;
    const item = line.match(/^\s*(?:[-*•]|\d+\.)\s+(.*)$/);
    if (item) {
      list.push(item[1]);
      continue;
    }
    flush();
    if (!line.trim()) continue;
    const heading = line.match(/^#{1,4}\s+(.*)$/);
    blocks.push(
      <p key={`p-${blocks.length}`} className={heading ? "font-semibold" : ""}>
        {inline(heading ? heading[1] : line)}
      </p>,
    );
  }
  flush();
  flushTable();
  return <div className="space-y-1.5">{blocks}</div>;
}

function ModeTag({ meta }: { meta: NonNullable<Message["meta"]> }) {
  if (meta.mode === "local") {
    return (
      <span className="inline-flex items-center gap-1 text-[0.75rem] text-muted">
        <Cpu className="size-3" aria-hidden /> regras locais
      </span>
    );
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-1 text-[0.75rem] text-muted" title={meta.model ?? ""}>
      <Wrench className="size-3" aria-hidden />
      {meta.mode === "llm-tools" ? `LLM consultou: ${meta.tools_used.join(", ") || "nenhuma ferramenta"}` : "LLM com contexto do recorte"}
    </span>
  );
}

function scopeKey(f: Recorte) {
  return JSON.stringify(f);
}

function AgentChatInner() {
  const messages = useStore($messages);
  const filters = useStore($filters);
  const active = useStore($activeCount);
  const draft = useStore($agentDraft);
  const { data: meta } = useMeta();
  const [input, setInput] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [moreSuggestions, setMoreSuggestions] = useState(false);
  const panelRef = useRef<HTMLElement>(null);
  const lastMsgRef = useRef<HTMLDivElement>(null);
  const pendingRef = useRef<HTMLDivElement>(null);
  const mountedRef = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);
  /** Rascunho cujo caret vai ao fim assim que o React gravar esse valor no campo. */
  const caretAfter = useRef<string | null>(null);

  const mutation = useMutation({
    mutationFn: (vars: { question: string; history: Message[]; filters: Recorte }) =>
      askAgent({
        question: vars.question,
        filters: toBody(vars.filters),
        history: vars.history
          .filter((m) => !m.error)
          .slice(-8)
          .map((m) => ({ role: m.role, content: m.content.slice(0, 6000) })),
      }),
    onSuccess: (res, vars) =>
      $messages.set([
        ...$messages.get(),
        { id: nextId++, role: "assistant", content: res.answer, scope: scopeKey(vars.filters), meta: res },
      ]),
    onError: (err, vars) =>
      $messages.set([
        ...$messages.get(),
        {
          id: nextId++,
          role: "assistant",
          content: `Não consegui responder agora (${err instanceof Error ? err.message : "erro"}). Se o servidor estava dormindo, tente de novo em alguns segundos.`,
          scope: scopeKey(vars.filters),
          error: true,
        },
      ]),
  });

  // Rola a página até a mensagem nova. Pergunta enviada sempre rola; resposta que chega só rola
  // se o painel ainda estiver na tela, para não puxar a página de quem já foi embora. Carga com histórico não rola.
  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;
      return;
    }
    const target = mutation.isPending ? pendingRef.current : lastMsgRef.current;
    const panel = panelRef.current;
    if (!target || !panel) return;
    // "Na tela" = pelo menos 120px do painel visíveis; uma faixa de poucos pixels não conta.
    const box = panel.getBoundingClientRect();
    const visiblePx = Math.min(box.bottom, window.innerHeight) - Math.max(box.top, 0);
    if (!mutation.isPending && visiblePx < 120) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // O alvo é sempre o último filho do log: se o log tiver overflow, scrollIntoView também leva o rolamento interno ao fim.
    target.scrollIntoView({ block: "nearest", behavior: reduced ? "auto" : "smooth" });
  }, [messages.length, mutation.isPending]);

  // Tempo decorrido na espera. O cliente não sabe as etapas reais da ferramenta, então só mostra segundos.
  useEffect(() => {
    if (!mutation.isPending) return;
    const started = Date.now();
    const id = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => {
      window.clearInterval(id);
      setElapsed(0);
    };
  }, [mutation.isPending]);

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

  const send = (question: string) => {
    const q = question.trim();
    if (!q || mutation.isPending) return;
    const history = $messages.get();
    $messages.set([...history, { id: nextId++, role: "user", content: q, scope: scopeKey(filters) }]);
    setInput("");
    mutation.mutate({ question: q, history, filters });
  };

  const scopeChanged = messages.length > 0 && messages.at(-1)!.scope !== scopeKey(filters);

  // Só a última resposta do agente vai para o leitor de tela, e só quando ela muda.
  const announcement = useMemo(() => {
    const latest = messages.filter((m) => m.role === "assistant").at(-1);
    if (!latest) return "";
    const text = clip(plainText(latest.content));
    return latest.error ? text : `Resposta do agente: ${text}`;
  }, [messages]);

  return (
    <section ref={panelRef} className="panel flex h-full min-h-[440px] flex-col" aria-label="Agente de insights">
      <header className="flex items-start justify-between gap-2 border-b border-rule p-4 pb-3">
        <div>
          <h2 className="section-title flex items-center gap-2">
            <Bot className="size-4 text-series" aria-hidden /> Agente do recorte
          </h2>
          <p className="label mt-0.5">
            Responde só sobre os filtros ativos{active ? ` (${active})` : ""}.{" "}
            {meta ? (meta.llm_enabled ? "LLM com ferramentas, regras locais de reserva." : "Modo local: regras e estatísticas, sem API key.") : ""}
          </p>
        </div>
        {messages.length > 0 && (
          <button type="button" className="btn-ghost px-2 py-1 text-[0.8rem] max-lg:min-h-11" onClick={() => $messages.set([])}>
            <RotateCcw className="size-3.5" aria-hidden /> Nova conversa
          </button>
        )}
      </header>

      <div className="flex-1 space-y-3 overflow-auto p-4" role="log" aria-live="off" aria-label="Conversa com o agente">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="label">Comece por uma destas ou escreva a sua:</p>
            <div className="grid gap-1.5">
              {(moreSuggestions ? SUGGESTIONS : SUGGESTIONS.slice(0, SUGGESTIONS_SHOWN)).map((s) => (
                <button key={s} type="button" className="btn-ghost justify-start text-left max-lg:min-h-11" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
            {SUGGESTIONS.length > SUGGESTIONS_SHOWN && (
              <button
                type="button"
                className="btn-ghost px-2 py-1 text-[0.8rem] max-lg:min-h-11"
                aria-expanded={moreSuggestions}
                onClick={() => setMoreSuggestions((v) => !v)}
              >
                <ChevronDown className={`size-3.5 transition-transform duration-(--duration-fast) motion-reduce:transition-none ${moreSuggestions ? "rotate-180" : ""}`} aria-hidden />
                Mais perguntas
              </button>
            )}
          </div>
        )}
        {messages.map((m, i) => {
          const prev = messages[i - 1];
          const isLast = i === messages.length - 1;
          return (
            <Fragment key={m.id}>
              {prev && m.role === "user" && prev.scope !== m.scope && (
                <p className="border-t border-dashed border-rule pt-2 text-center text-[0.75rem] text-muted">
                  recorte mudou: as respostas abaixo usam os filtros novos
                </p>
              )}
              {m.role === "user" ? (
                <div ref={isLast ? lastMsgRef : undefined} className="ml-8 rounded-card bg-sunken px-3 py-2 text-[0.95rem]">
                  {m.content}
                </div>
              ) : (
                // Chegada discreta: a resposta entra com fade, 4px de subida e um desfoque leve. Reduzido, aparece direto.
                <div
                  ref={isLast ? lastMsgRef : undefined}
                  className={`mr-2 rounded-card border bg-surface px-3 py-2.5 text-[0.95rem] transition-[opacity,translate,filter] duration-(--duration-fast) ease-(--ease-smooth-out) starting:translate-y-(--distance-micro) starting:opacity-0 starting:blur-(--blur-small) motion-reduce:transition-none ${m.error ? "border-warn" : "border-rule"}`}
                >
                  <Markdown text={m.content} />
                  {m.meta && (
                    <div className="mt-1.5">
                      <ModeTag meta={m.meta} />
                    </div>
                  )}
                </div>
              )}
            </Fragment>
          );
        })}
        {mutation.isPending && (
          <div ref={pendingRef} role="status" className="mr-2 px-3 text-muted">
            <div className="text-[0.85rem]">
              <p className="tabular-nums">
                {/* Brilho sem JS; o texto real fica no DOM uma vez (o pseudo-elemento não é lido). */}
                <span className="shimmer-text" data-text="Consultando o recorte…">
                  Consultando o recorte…
                </span>
                {elapsed >= 5 && <span aria-hidden> {elapsed} s</span>}
              </p>
              {elapsed >= 5 && <p className="text-[0.75rem]">Se o servidor estava dormindo, a primeira resposta leva até ~40 s.</p>}
            </div>
          </div>
        )}
      </div>

      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {announcement}
      </p>

      {scopeChanged && !mutation.isPending && (
        <p className="mx-4 mb-2 rounded-card bg-sunken px-3 py-1.5 text-[0.8rem] text-muted">
          Os filtros mudaram desde a última resposta. A próxima pergunta já usa o recorte novo.
        </p>
      )}

      <form
        className="flex gap-2 border-t border-rule p-3"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <label className="sr-only" htmlFor="agent-input">
          Pergunta para o agente
        </label>
        <input
          id="agent-input"
          ref={inputRef}
          value={input}
          maxLength={800}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Pergunte sobre este recorte…"
          className="min-w-0 flex-1 rounded-card border border-rule bg-surface px-3 py-2 text-[0.95rem] outline-none placeholder:text-muted focus:border-ink max-lg:min-h-11"
        />
        <button type="submit" className="btn-ink max-lg:min-h-11 max-lg:min-w-11 max-lg:justify-center" disabled={!input.trim() || mutation.isPending} aria-label="Enviar">
          <SendHorizontal className="size-4" aria-hidden />
        </button>
      </form>
    </section>
  );
}

export default island(AgentChatInner, 520);
