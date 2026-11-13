import { ChevronUp, Filter, X } from "lucide-react";
import { useEffect, useRef, type CSSProperties } from "react";
import { agentStamp, dismissAgentComanda, type AgentTicket } from "@/lib/agentBridge";
import { applyDrilldown } from "@/lib/filters";
import { fmt } from "@/lib/format";
import { SEVERITY } from "../ui/EvidenceTag";
import { Markdown, readingNote } from "./markdown";

/** A fila do agente não usa o vermelho de crítico: a marca é o traço, o carimbo diz AGENTE. */
const MARK = SEVERITY.low.mark;

export function baseLine(ticket: AgentTicket): string {
  if (ticket.lowSample) return `Base: ${fmt.int(ticket.measured)} entregas medidas · amostra pequena`;
  return `Base: ${fmt.int(ticket.n)} pedidos`;
}

function DrillButtons({ ticket, primary }: { ticket: AgentTicket; primary: boolean }) {
  return (
    <>
      {ticket.drilldowns.map((drill, index) => (
        <button
          key={`${drill.label}-${index}`}
          type="button"
          className={`${primary && index === 0 ? "btn-primary" : "btn-ghost"} max-lg:min-h-11 lg:min-h-9`}
          onClick={() => applyDrilldown(drill.filters)}
        >
          <Filter className="size-3.5" aria-hidden /> {drill.label}
        </button>
      ))}
    </>
  );
}

/** Comanda dentro da conversa. O vermelho fica na faixa aberta da fila, não aqui. */
export function AgentChatComanda({
  ticket,
  stale,
  waiting,
  onCancel,
}: {
  ticket: AgentTicket;
  stale: boolean;
  waiting: boolean;
  onCancel: () => void;
}) {
  const note = waiting ? "Leitura pelas regras. Aprofundando com o modelo…" : readingNote(ticket.status, ticket.toolLabels);
  return (
    <article className="ticket mr-2 bg-surface px-3 pt-4 pb-3" aria-label={`${agentStamp(ticket.series)} · ${ticket.title}`}>
      <div className="border-b-[1.5px] border-dashed border-rule pb-2">
        <span className="cond flex items-center gap-2 text-meta font-bold">
          <span className={`inline-block shrink-0 ${MARK}`} aria-hidden />
          <span className="truncate">
            {agentStamp(ticket.series)} · Agente
          </span>
        </span>
      </div>
      {stale && <p className="mt-2 text-meta text-muted">Recorte mudou</p>}
      <h3 className="mt-2 text-lead leading-snug font-semibold text-balance">{ticket.title}</h3>
      <div className="mt-1.5 text-body leading-relaxed text-pretty text-ink/85">
        <Markdown text={ticket.detail} />
      </div>
      <div className="mt-3 action-block rounded-card px-4 py-3.5">
        <p className="text-aux font-semibold opacity-70">Ação</p>
        <p className="mt-1 text-body leading-snug text-pretty">{ticket.action}</p>
      </div>
      {ticket.drilldowns.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          <DrillButtons ticket={ticket} primary={false} />
        </div>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-meta text-muted">
        <p className="min-w-0 text-pretty">{note}</p>
        {waiting && (
          <button type="button" className="btn-ghost px-2 py-1 text-meta max-lg:min-h-11" onClick={onCancel}>
            Cancelar
          </button>
        )}
        <p className="tabular-nums">{baseLine(ticket)}</p>
        {ticket.onRail && (
          <button
            type="button"
            className="btn-ghost px-2 py-1 text-meta max-lg:min-h-11"
            onClick={() => dismissAgentComanda(ticket.id)}
          >
            Tirar da fila
          </button>
        )}
      </div>
    </article>
  );
}

/** Comanda do agente no trilho: mesmo papel das outras, numerada na série A. */
export function AgentStub({
  ticket,
  stale,
  index,
  total,
  tabIndex,
  selected,
  bandMounted,
  printing,
  focusOnMount,
  onToggle,
}: {
  ticket: AgentTicket;
  stale: boolean;
  index: number;
  total: number;
  tabIndex: number;
  selected: boolean;
  bandMounted: boolean;
  printing: boolean;
  focusOnMount: boolean;
  onToggle: () => void;
}) {
  const buttonRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (focusOnMount) buttonRef.current?.focus();
  }, [focusOnMount]);
  const hoverClasses = !selected ? "hover:after:opacity-100 has-[:focus-visible]:after:opacity-100" : "";
  return (
    <li
      data-alert={ticket.id}
      className={`relative snap-start after:pointer-events-none after:absolute after:inset-x-0 after:-bottom-2 after:h-[3px] after:rounded-full after:bg-rule after:opacity-0 after:transition-opacity after:duration-(--duration-quick) after:ease-(--ease-smooth-out) print:after:hidden ${hoverClasses} ${
        printing ? "ticket-print" : ""
      }`}
      style={{ "--i": Math.min(index, 5) } as CSSProperties}
    >
      <button
        ref={buttonRef}
        type="button"
        tabIndex={tabIndex}
        aria-expanded={selected}
        aria-controls={bandMounted ? "comanda-aberta" : undefined}
        aria-label={`${ticket.title}, comanda ${index + 1} de ${total}, agente${stale ? ", recorte mudou" : ""}`}
        onClick={onToggle}
        className={`group ticket flex h-full w-full flex-col justify-start px-4 pt-4 pb-3.5 text-left transition-colors duration-(--duration-quick) ease-(--ease-smooth-out) ${
          selected ? "bg-surface" : "bg-surface/60 hover:bg-surface"
        }`}
      >
        <span className="cond flex items-center gap-2 text-meta font-bold">
          <span className={`inline-block shrink-0 ${MARK}`} aria-hidden />
          <span className="whitespace-nowrap">
            {agentStamp(ticket.series)} · Agente
          </span>
        </span>
        {/* w-0 + min-w-full: o título não entra na largura mínima da coluna do trilho. */}
        <span
          className={`mt-1.5 line-clamp-2 w-0 min-w-full text-body leading-snug font-semibold text-pretty transition-colors duration-(--duration-quick) ease-(--ease-smooth-out) ${
            selected ? "" : "text-ink/85 group-hover:text-ink"
          }`}
        >
          {ticket.title}
        </span>
        {stale && <span className="mt-1 text-meta text-muted">Recorte mudou</span>}
        <span className="mt-1 hidden text-aux text-pretty print:block">
          <span className="mr-1.5 text-aux font-semibold">Ação</span>
          {ticket.action}
        </span>
      </button>
    </li>
  );
}

/** Faixa aberta da comanda do agente. Um botão vermelho: o primeiro atalho. */
export function AgentOpenBand({
  ticket,
  stale,
  motion,
  focusOnMount,
  onCollapse,
}: {
  ticket: AgentTicket;
  stale: boolean;
  motion: string;
  focusOnMount: boolean;
  onCollapse: () => void;
}) {
  const titleRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (focusOnMount) titleRef.current?.focus();
  }, [focusOnMount]);
  return (
    <article
      id="comanda-aberta"
      aria-labelledby="comanda-aberta-title"
      className={`ticket mt-2 bg-surface px-5 pt-5 pb-4 ${motion}`}
      style={{ "--i": 0 } as CSSProperties}
    >
      <div className="border-b-[1.5px] border-dashed border-rule pb-2.5">
        <span className="cond flex items-center justify-between gap-3 text-meta font-bold">
          <span className="flex min-w-0 items-center gap-2">
            <span className={`inline-block shrink-0 ${MARK}`} aria-hidden />
            <span className="truncate">
              {agentStamp(ticket.series)} · Agente
            </span>
          </span>
          <span className="flex shrink-0 items-center gap-3">
            <span className="text-series">Agente</span>
            <button
              type="button"
              aria-expanded={true}
              aria-controls="comanda-aberta"
              onClick={onCollapse}
              className="no-print -my-1 -mr-1.5 inline-flex min-h-6 items-center gap-1 rounded-tick px-1.5 font-medium text-muted transition-colors duration-(--duration-quick) hover:text-ink max-lg:min-h-11"
            >
              <ChevronUp className="size-3.5" aria-hidden /> Recolher
            </button>
          </span>
        </span>
      </div>
      <div className="mt-3 grid gap-x-8 gap-y-3.5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:grid-rows-[auto_1fr]">
        <div className="min-w-0 lg:col-start-1 lg:row-start-1">
          {stale && <p className="mb-1.5 text-meta text-muted">Recorte mudou</p>}
          <h3 id="comanda-aberta-title" ref={titleRef} tabIndex={-1} className="text-lead leading-snug font-semibold text-balance">
            {ticket.title}
          </h3>
          <div className="mt-1.5 max-w-[68ch] text-body leading-relaxed text-pretty text-ink/85">
            <Markdown text={ticket.detail} />
          </div>
        </div>
        <div className="self-start action-block rounded-card px-4 py-3.5 lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:mt-0.5">
          <p className="text-aux font-semibold opacity-70">Ação</p>
          <p className="mt-1 text-body leading-snug text-pretty">{ticket.action}</p>
        </div>
        <div className="min-w-0 self-start lg:col-start-1 lg:row-start-2">
          <div className="comanda-actions no-print flex flex-wrap gap-2">
            <DrillButtons ticket={ticket} primary />
            <button type="button" className="btn-ghost max-lg:min-h-11 lg:min-h-9" onClick={() => dismissAgentComanda(ticket.id)}>
              <X className="size-3.5" aria-hidden /> Tirar da fila
            </button>
          </div>
          <p className="mt-3 text-meta text-pretty text-muted">{readingNote(ticket.status, ticket.toolLabels)}</p>
          <p className="mt-1 text-meta tabular-nums text-muted">{baseLine(ticket)}</p>
        </div>
      </div>
    </article>
  );
}
