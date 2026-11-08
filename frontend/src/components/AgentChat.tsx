import { useStore } from "@nanostores/react";
import { useMutation } from "@tanstack/react-query";
import { Bot, Cpu, RotateCcw, SendHorizontal, Wrench } from "lucide-react";
import { atom } from "nanostores";
import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
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

/** Markdown mínimo e seguro (negrito, listas, parágrafos), sem innerHTML. */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : <Fragment key={i}>{part}</Fragment>,
  );
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
  const { data: meta } = useMeta();
  const [input, setInput] = useState("");
  const log = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, mutation.isPending]);

  const send = (question: string) => {
    const q = question.trim();
    if (!q || mutation.isPending) return;
    const history = $messages.get();
    $messages.set([...history, { id: nextId++, role: "user", content: q, scope: scopeKey(filters) }]);
    setInput("");
    mutation.mutate({ question: q, history, filters });
  };

  const scopeChanged = messages.length > 0 && messages.at(-1)!.scope !== scopeKey(filters);

  return (
    <section className="panel flex h-full min-h-[520px] flex-col" aria-label="Agente de insights">
      <header className="flex items-start justify-between gap-2 border-b border-rule p-4 pb-3">
        <div>
          <h2 className="section-title flex items-center gap-2">
            <Bot className="size-4 text-chili" aria-hidden /> Agente do recorte
          </h2>
          <p className="label mt-0.5">
            Responde só sobre os filtros ativos{active ? ` (${active})` : ""}.{" "}
            {meta ? (meta.llm_enabled ? "LLM com ferramentas, regras locais de reserva." : "Modo local: regras e estatísticas, sem API key.") : ""}
          </p>
        </div>
        {messages.length > 0 && (
          <button type="button" className="btn-ghost px-2 py-1 text-[0.8rem]" onClick={() => $messages.set([])}>
            <RotateCcw className="size-3.5" aria-hidden /> Nova conversa
          </button>
        )}
      </header>

      <div ref={log} className="flex-1 space-y-3 overflow-auto p-4" aria-live="polite">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="label">Comece por uma destas ou escreva a sua:</p>
            <div className="grid gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="btn-ghost justify-start text-left" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => {
          const prev = messages[i - 1];
          return (
            <Fragment key={m.id}>
              {prev && m.role === "user" && prev.scope !== m.scope && (
                <p className="border-t border-dashed border-rule pt-2 text-center text-[0.75rem] text-muted">
                  recorte mudou: as respostas abaixo usam os filtros novos
                </p>
              )}
              {m.role === "user" ? (
                <div className="ml-8 rounded-fold bg-kraft px-3 py-2 text-[0.95rem]">{m.content}</div>
              ) : (
                <div className={`mr-2 border-l-[3px] pl-3 text-[0.95rem] ${m.error ? "border-l-amber" : "border-l-chili"}`}>
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
          <div className="mr-2 flex items-center gap-2 border-l-[3px] border-l-rule pl-3 text-muted">
            <span className="flex gap-1" aria-hidden>
              <span className="size-1.5 animate-bounce rounded-full bg-muted [animation-delay:-0.2s]" />
              <span className="size-1.5 animate-bounce rounded-full bg-muted [animation-delay:-0.1s]" />
              <span className="size-1.5 animate-bounce rounded-full bg-muted" />
            </span>
            <span className="text-[0.85rem]">Consultando o recorte…</span>
          </div>
        )}
      </div>

      {scopeChanged && !mutation.isPending && (
        <p className="mx-4 mb-2 rounded-fold bg-kraft px-3 py-1.5 text-[0.8rem] text-muted">
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
          value={input}
          maxLength={800}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Pergunte sobre este recorte…"
          className="min-w-0 flex-1 rounded-fold border border-rule bg-paper px-3 py-2 text-[0.95rem] outline-none placeholder:text-muted focus:border-chili"
        />
        <button type="submit" className="btn-primary" disabled={!input.trim() || mutation.isPending} aria-label="Enviar">
          <SendHorizontal className="size-4" aria-hidden />
        </button>
      </form>
    </section>
  );
}

export default island(AgentChatInner, 520);
