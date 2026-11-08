/**
 * Fila de comandas: cada alerta do recorte vira uma comanda com número,
 * categoria, severidade e a ação impressa no rodapé. Uma comanda aberta por
 * vez; as outras esperam resumidas na fila.
 */
import { ChevronDown, ChevronUp, CircleSlash, Filter, MessageSquareText, ShieldCheck } from "lucide-react";
import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from "react";
import type { Alert } from "@/lib/api/client";
import { askAgentAbout } from "@/lib/agentBridge";
import { applyDrilldown } from "@/lib/filters";
import { island, useRecorteQuery } from "@/lib/query";
import { ErrorState } from "./ui/Panel";

/** Severidade também por forma (cheia, vazada, traço), nunca só por cor. */
const SEVERITY = {
  high: { label: "Crítico", mark: "size-3 rounded-full bg-crit", tone: "text-crit" },
  medium: { label: "Atenção", mark: "size-3 rounded-full border-[2.5px] border-warn", tone: "text-warn" },
  low: { label: "Observar", mark: "h-[3px] w-3 rounded-full bg-muted", tone: "text-muted" },
} as const;

const CATEGORY: Record<Alert["category"], string> = {
  sla: "SLA",
  cancelamento: "Cancelamento",
  loja: "Loja",
  frota: "Frota",
  dados: "Dados",
  volume: "Volume",
  custo: "Custo",
};

/** Movimento de uma comanda: cada modo vira uma classe de animação em global.css. */
type Motion = "print" | "open" | "fold" | "none";
const MOTION_CLASS: Record<Motion, string> = {
  print: "ticket-print",
  open: "ticket-open",
  fold: "ticket-fold",
  none: "",
};

/** Reimpressão: 40ms por comanda, até o índice 5 (seis passos no máximo). Espelha o `calc(var(--i) * 40ms)`. */
const PRINT_STAGGER_CAP = 5;
/** Recolhimento: `ticket-fold` dura 160ms; este fallback fecha a comanda se animationend não disparar. */
const FOLD_FALLBACK_MS = 220;

const num = (i: number) => `Nº ${String(i + 1).padStart(2, "0")}`;

/** Pedido de foco: vai para o título da comanda aberta ou para o botão da comanda recolhida. */
type FocusRequest = { id: string; on: "title" | "queued" } | null;

/** Id da comanda (aberta ou na fila): estável por alerta, para o botão de cada comanda apontar para ela (aria-controls). */
const bodyId = (alertId: string) => `comanda-${alertId.replace(/[^\w-]/g, "-")}`;

/** Índice de escalonamento da reimpressão, lido pelo CSS como `--i`. */
const printVars = (index: number) => ({ "--i": Math.min(index, PRINT_STAGGER_CAP) }) as CSSProperties;

/** Movimento reduzido do sistema: o recolhimento acontece na hora, sem animação. */
const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function TicketHead({ alert, index, action }: { alert: Alert; index: number; action?: ReactNode }) {
  const s = SEVERITY[alert.severity];
  return (
    <span className="cond flex items-center justify-between gap-3 text-[0.8rem] font-bold">
      <span className="flex items-center gap-2">
        <span className={`inline-block shrink-0 ${s.mark}`} aria-hidden />
        {num(index)} · {CATEGORY[alert.category]}
      </span>
      <span className="flex items-center gap-3">
        <span className={s.tone}>{s.label}</span>
        {action}
      </span>
    </span>
  );
}

function OpenTicket({
  alert,
  index,
  motion,
  focusOnMount,
  onCollapse,
  onFolded,
}: {
  alert: Alert;
  index: number;
  motion: Motion;
  focusOnMount: boolean;
  onCollapse: () => void;
  onFolded: () => void;
}) {
  const titleRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (focusOnMount) titleRef.current?.focus();
  }, [focusOnMount]);

  return (
    <li
      id={bodyId(alert.id)}
      className={`ticket bg-surface px-5 pt-5 pb-4 ${MOTION_CLASS[motion]}`}
      style={printVars(index)}
      onAnimationEnd={(e) => {
        if (e.animationName === "ticket-fold") onFolded();
      }}
    >
      <div className="border-b-[1.5px] border-dashed border-rule pb-2.5">
        <TicketHead
          alert={alert}
          index={index}
          action={
            <button
              type="button"
              aria-expanded={true}
              aria-controls={bodyId(alert.id)}
              onClick={onCollapse}
              className="-my-1 -mr-1.5 inline-flex min-h-6 max-lg:min-h-11 items-center gap-1 rounded-tick px-1.5 font-bold text-muted hover:text-ink"
            >
              <ChevronUp className="size-3.5" aria-hidden /> Recolher
            </button>
          }
        />
      </div>
      <h3 ref={titleRef} tabIndex={-1} className="mt-3 text-[1.08rem] leading-snug font-semibold text-balance">
        {alert.title}
      </h3>
      <p className="mt-1.5 text-[0.95rem] leading-relaxed text-pretty text-ink/85">{alert.detail}</p>
      <div className="mt-3.5 rounded-card bg-ink px-3.5 py-3 text-surface">
        <p className="cond text-[0.72rem] font-bold opacity-70">Ação</p>
        <p className="mt-1 text-[0.95rem] leading-snug text-pretty">{alert.action}</p>
      </div>
      <div className="no-print mt-3 flex flex-wrap gap-2">
        {alert.drilldown && (
          <button type="button" className="btn-primary max-lg:min-h-11 lg:min-h-9" onClick={() => applyDrilldown(alert.drilldown!.filters)}>
            <Filter className="size-3.5" aria-hidden /> {alert.drilldown.label}
          </button>
        )}
        <button
          type="button"
          className="btn-ghost max-lg:min-h-11 lg:min-h-9"
          onClick={() => askAgentAbout(`Sobre a comanda "${alert.title}": o que explica isso neste recorte e o que fazer hoje?`)}
        >
          <MessageSquareText className="size-3.5" aria-hidden /> Perguntar ao agente sobre esta comanda
        </button>
      </div>
    </li>
  );
}

function QueuedTicket({
  alert,
  index,
  motion,
  focusOnMount,
  onOpen,
}: {
  alert: Alert;
  index: number;
  motion: Motion;
  focusOnMount: boolean;
  onOpen: () => void;
}) {
  const buttonRef = useRef<HTMLButtonElement>(null);
  const actionId = useId();
  useEffect(() => {
    if (focusOnMount) buttonRef.current?.focus();
  }, [focusOnMount]);

  return (
    <li id={bodyId(alert.id)} className={`ticket bg-surface/70 transition-colors hover:bg-surface ${MOTION_CLASS[motion]}`} style={printVars(index)}>
      <h3>
        <button
          ref={buttonRef}
          type="button"
          aria-expanded={false}
          aria-controls={bodyId(alert.id)}
          aria-label={`${alert.title} · ${SEVERITY[alert.severity].label} · ${num(index)}, ${CATEGORY[alert.category]}`}
          aria-describedby={actionId}
          onClick={onOpen}
          className="block w-full px-5 pt-4 pb-3.5 text-left"
        >
          <TicketHead alert={alert} index={index} />
          <span className="mt-2 flex items-start justify-between gap-3">
            <span className="min-w-0">
              <span className="block leading-snug font-semibold">{alert.title}</span>
              <span id={actionId} className="mt-0.5 line-clamp-2 text-pretty text-[0.88rem] text-muted">
                <span className="cond mr-1.5 text-[0.72rem] font-bold">Ação</span>
                {alert.action}
              </span>
            </span>
            <ChevronDown className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
          </span>
        </button>
      </h3>
    </li>
  );
}

function AlertsPanelInner() {
  const { data, error, isPending, refetch, isPlaceholderData } = useRecorteQuery("/api/alerts");
  const alerts = data?.alerts ?? [];
  // undefined = o operador ainda não escolheu (abre a primeira); null = recolheu todas
  const [openId, setOpenId] = useState<string | null | undefined>(undefined);
  const [folding, setFolding] = useState<string | null>(null);
  const [focusRequest, setFocusRequest] = useState<FocusRequest>(null);
  const [printKey, setPrintKey] = useState(0);
  const [printing, setPrinting] = useState(false);
  const [seenData, setSeenData] = useState(data);
  const sectionRef = useRef<HTMLElement>(null);
  const high = alerts.filter((a) => a.severity === "high").length;

  // dado novo do recorte: reimprime a fila e mantém a comanda aberta se ela ainda existe.
  // O ajuste é feito durante o render (não num effect), então a fila nova já nasce certa, sem frame com a antiga.
  if (data !== seenData) {
    setSeenData(data);
    setPrintKey((k) => k + 1);
    setPrinting(true);
    setFolding(null);
    const kept = typeof openId === "string" && alerts.some((a) => a.id === openId) ? openId : undefined;
    setOpenId(kept);
    // A reimpressão remonta a fila. Se o foco estava nela (ex.: drill-down da comanda), ele vai para o
    // título da comanda aberta no recorte novo, em vez de cair no body. Fora disso, não rouba o foco.
    const hadFocus = typeof document !== "undefined" && !!sectionRef.current?.contains(document.activeElement);
    const target = kept ?? alerts[0]?.id;
    setFocusRequest(hadFocus && target ? { id: target, on: "title" } : null);
  }
  const effectiveOpen = openId === undefined ? (alerts[0]?.id ?? null) : openId;

  const finishCollapse = (id: string) => {
    setFolding(null);
    setOpenId(null);
    setFocusRequest({ id, on: "queued" });
  };

  // fallback do recolhimento: se animationend não disparar, a comanda fecha no mesmo tempo
  useEffect(() => {
    if (folding === null) return;
    const id = folding;
    const timer = window.setTimeout(() => finishCollapse(id), FOLD_FALLBACK_MS);
    return () => window.clearTimeout(timer);
  }, [folding]); // eslint-disable-line react-hooks/exhaustive-deps

  const openTicket = (id: string) => {
    setPrinting(false);
    setFolding(null);
    setOpenId(id);
    setFocusRequest({ id, on: "title" });
  };
  const collapseTicket = (id: string) => {
    setPrinting(false);
    if (prefersReducedMotion()) {
      finishCollapse(id);
      return;
    }
    setFolding(id);
  };
  const isRequested = (id: string, on: "title" | "queued") => focusRequest?.id === id && focusRequest.on === on;

  // texto anunciado por leitor de tela quando a fila muda (sem anunciar a lista inteira)
  const noOrders = data?.orders === 0;
  const countText = alerts.length === 1 ? "1 comanda aberta" : `${alerts.length} comandas abertas`;
  const highText = high === 0 ? "nenhuma crítica" : high === 1 ? "1 crítica" : `${high} críticas`;
  const status = !data
    ? ""
    : alerts.length > 0
      ? `${countText}, ${highText}`
      : noOrders
        ? "Sem pedidos neste recorte."
        : "Nenhuma comanda aberta neste recorte.";

  return (
    <section ref={sectionRef} aria-labelledby="comandas-title" className={`transition-opacity ${isPlaceholderData ? "opacity-60" : ""}`}>
      <header className="mb-2.5 flex items-baseline justify-between gap-2 bg-field px-0.5 pb-0.5 lg:sticky lg:top-0 lg:z-[2]">
        <h2 id="comandas-title" className="cond text-[0.9rem] font-bold text-ink">
          Comandas abertas{data ? ` · ${alerts.length}` : ""}
        </h2>
        {data && alerts.length > 0 && <p className="text-[0.82rem] text-muted">{highText}</p>}
      </header>
      <p className="sr-only" aria-live="polite">
        {status}
      </p>
      {isPending ? (
        <div className="grid gap-2.5">
          <div className="skeleton h-[300px]" />
          <div className="skeleton h-[84px]" />
          <div className="skeleton h-[84px]" />
        </div>
      ) : error ? (
        <div className="tile p-4">
          <ErrorState error={error} onRetry={() => refetch()} />
        </div>
      ) : alerts.length === 0 ? (
        noOrders ? (
          <div className="ticket bg-surface flex items-start gap-3 px-5 pt-6 pb-5">
            <CircleSlash className="mt-0.5 size-5 shrink-0 text-muted" aria-hidden />
            <div>
              <p className="font-semibold">Sem pedidos neste recorte.</p>
              <p className="label mt-0.5 text-pretty">Não dá para afirmar SLA nem cancelamento sem pedidos. Amplie o período ou tire um filtro.</p>
            </div>
          </div>
        ) : (
          <div className="ticket bg-surface flex items-start gap-3 px-5 pt-6 pb-5">
            <ShieldCheck className="mt-0.5 size-5 shrink-0 text-good" aria-hidden />
            <div>
              <p className="font-semibold">Nenhuma comanda aberta neste recorte.</p>
              <p className="label mt-0.5 text-pretty">SLA, cancelamento e lojas dentro do esperado. Mude o recorte para checar outro hub.</p>
            </div>
          </div>
        )
      ) : (
        // keyed em printKey: cada recorte novo remonta a fila e a reimprime inteira
        <ol key={printKey} className="grid grid-cols-[minmax(0,1fr)] gap-2.5">
          {alerts.map((a, i) => {
            if (a.id === effectiveOpen) {
              // na reimpressão a comanda aberta usa só o movimento de impressão, sem o desdobrar de abrir
              const motion: Motion = folding === a.id ? "fold" : printing ? "print" : "open";
              return (
                <OpenTicket
                  key={a.id}
                  alert={a}
                  index={i}
                  motion={motion}
                  focusOnMount={isRequested(a.id, "title")}
                  onCollapse={() => collapseTicket(a.id)}
                  onFolded={() => finishCollapse(a.id)}
                />
              );
            }
            return (
              <QueuedTicket
                key={a.id}
                alert={a}
                index={i}
                motion={printing ? "print" : "none"}
                focusOnMount={isRequested(a.id, "queued")}
                onOpen={() => openTicket(a.id)}
              />
            );
          })}
        </ol>
      )}
    </section>
  );
}

export default island(AlertsPanelInner, 420);
