/**
 * Trilho de comandas: cada alerta do recorte vira uma comanda pendurada lado a
 * lado (número, categoria, severidade e título). A comanda escolhida abre numa
 * faixa larga logo abaixo do trilho, com a ação impressa. Uma aberta por vez;
 * a aberta também publica a evidência dela ($evidence) para KPIs e gráficos.
 */
import { ChevronUp, CircleSlash, Filter, LineChart, MessageSquareText, ShieldCheck } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import type { Alert } from "@/lib/api/client";
import { askAgentAbout } from "@/lib/agentBridge";
import { $evidence, EVIDENCE_ANCHOR, showEvidence } from "@/lib/evidence";
import { applyDrilldown } from "@/lib/filters";
import { island, useRecorteQuery } from "@/lib/query";
import { SEVERITY } from "./ui/EvidenceTag";
import { ErrorState } from "./ui/Panel";

const CATEGORY: Record<Alert["category"], string> = {
  sla: "SLA",
  cancelamento: "Cancelamento",
  loja: "Loja",
  frota: "Frota",
  dados: "Dados",
  volume: "Volume",
  custo: "Custo",
};

/** Movimento da faixa aberta: cada modo vira uma classe de animação em global.css. */
type Motion = "print" | "open" | "fold";
const MOTION_CLASS: Record<Motion, string> = {
  print: "ticket-print",
  open: "ticket-open",
  fold: "ticket-fold",
};

/** Reimpressão: 40ms por comanda, até o índice 5 (seis passos no máximo). Espelha o `calc(var(--i) * 40ms)`. */
const PRINT_STAGGER_CAP = 5;
/** Recolhimento: `ticket-fold` dura 160ms; este fallback fecha a faixa se animationend não disparar. */
const FOLD_FALLBACK_MS = 220;
const BAND_ID = "comanda-aberta";

const num = (i: number) => `Nº ${String(i + 1).padStart(2, "0")}`;

/** Pedido de foco: vai para o título da faixa aberta ou para a comanda no trilho. */
type FocusRequest = { id: string; on: "title" | "stub" } | null;

/** Índice de escalonamento da reimpressão, lido pelo CSS como `--i`. */
const printVars = (index: number) => ({ "--i": Math.min(index, PRINT_STAGGER_CAP) }) as CSSProperties;

/** Movimento reduzido do sistema: o recolhimento acontece na hora, sem animação. */
const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Cabeçalho da comanda. No trilho (`compact`) a severidade fica só na marca: o espaço vai para a categoria. */
function TicketHead({ alert, index, action, compact }: { alert: Alert; index: number; action?: ReactNode; compact?: boolean }) {
  const s = SEVERITY[alert.severity];
  return (
    <span className="cond flex items-center justify-between gap-3 text-[0.8rem] font-bold">
      <span className="flex min-w-0 items-center gap-2">
        <span className={`inline-block shrink-0 ${s.mark}`} aria-hidden />
        <span className="truncate">
          {num(index)} · {CATEGORY[alert.category]}
        </span>
      </span>
      {!compact && (
        <span className="flex shrink-0 items-center gap-3">
          <span className={s.tone}>{s.label}</span>
          {action}
        </span>
      )}
    </span>
  );
}

/** Comanda no trilho: só o cabeçalho e o título. A ação aparece na faixa aberta (e no papel, ao imprimir). */
function Stub({
  alert,
  index,
  selected,
  printing,
  focusOnMount,
  onToggle,
}: {
  alert: Alert;
  index: number;
  selected: boolean;
  printing: boolean;
  focusOnMount: boolean;
  onToggle: () => void;
}) {
  const buttonRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (focusOnMount) buttonRef.current?.focus();
  }, [focusOnMount]);

  return (
    <li
      data-alert={alert.id}
      className={`ticket snap-start transition-colors duration-(--duration-quick) ${selected ? "bg-surface" : "bg-surface/60 hover:bg-surface"} ${
        printing ? "ticket-print" : ""
      }`}
      style={printVars(index)}
    >
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={selected}
        aria-controls={BAND_ID}
        aria-label={`${alert.title} · ${SEVERITY[alert.severity].label} · ${num(index)}, ${CATEGORY[alert.category]}`}
        onClick={onToggle}
        className="flex h-full w-full flex-col justify-start px-4 pt-4 pb-3.5 text-left"
      >
        <TicketHead alert={alert} index={index} compact />
        <span className={`mt-1.5 line-clamp-2 text-[0.95rem] leading-snug font-semibold text-pretty ${selected ? "" : "text-ink/85"}`}>
          {alert.title}
        </span>
        <span className="mt-1 hidden text-[0.85rem] text-pretty print:block">
          <span className="cond mr-1.5 text-[0.72rem] font-bold">Ação</span>
          {alert.action}
        </span>
      </button>
    </li>
  );
}

/** Faixa da comanda aberta: o problema à esquerda, a ação impressa e os atalhos à direita. */
function OpenBand({
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
  const view = alert.evidence?.view;
  const anchor = view && view !== "kpi" ? EVIDENCE_ANCHOR[view] : null;

  return (
    <article
      id={BAND_ID}
      aria-labelledby={`${BAND_ID}-title`}
      className={`ticket mt-2 bg-surface px-5 pt-5 pb-4 ${MOTION_CLASS[motion]}`}
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
              aria-controls={BAND_ID}
              onClick={onCollapse}
              className="no-print -my-1 -mr-1.5 inline-flex min-h-6 items-center gap-1 rounded-tick px-1.5 font-bold text-muted transition-colors duration-(--duration-quick) hover:text-ink max-lg:min-h-11"
            >
              <ChevronUp className="size-3.5" aria-hidden /> Recolher
            </button>
          }
        />
      </div>
      <div className="mt-3 grid gap-x-8 gap-y-3.5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div className="min-w-0">
          <h3 id={`${BAND_ID}-title`} ref={titleRef} tabIndex={-1} className="text-[1.08rem] leading-snug font-semibold text-balance">
            {alert.title}
          </h3>
          <p className="mt-1.5 max-w-[68ch] text-[0.95rem] leading-relaxed text-pretty text-ink/85">{alert.detail}</p>
          <div className="no-print mt-3 flex flex-wrap gap-2">
            {alert.drilldown && (
              <button type="button" className="btn-primary max-lg:min-h-11 lg:min-h-9" onClick={() => applyDrilldown(alert.drilldown!.filters)}>
                <Filter className="size-3.5" aria-hidden /> {alert.drilldown.label}
              </button>
            )}
            {anchor && (
              <button type="button" className="btn-ghost max-lg:min-h-11 lg:min-h-9" aria-label={anchor.label} onClick={() => showEvidence(view!)}>
                <LineChart className="size-3.5" aria-hidden /> Ver no gráfico
              </button>
            )}
            <button
              type="button"
              className="btn-ghost max-lg:min-h-11 lg:min-h-9"
              aria-label="Perguntar ao agente sobre esta comanda"
              onClick={() => askAgentAbout(`Sobre a comanda "${alert.title}": o que explica isso neste recorte e o que fazer hoje?`)}
            >
              <MessageSquareText className="size-3.5" aria-hidden /> Perguntar ao agente
            </button>
          </div>
        </div>
        <div className="self-start rounded-card bg-ink px-4 py-3.5 text-surface max-lg:order-first lg:mt-0.5">
          <p className="cond text-[0.72rem] font-bold opacity-70">Ação</p>
          <p className="mt-1 text-[0.98rem] leading-snug text-pretty">{alert.action}</p>
        </div>
      </div>
    </article>
  );
}

/**
 * Marca da comanda aberta no trilho: um traço sob ela que desliza de uma para outra
 * (--duration-fast, simétrico como abas). Mede o item escolhido dentro do próprio trilho,
 * então acompanha a rolagem horizontal sem recalcular.
 */
function useRailMarker(railRef: React.RefObject<HTMLOListElement | null>, selectedId: string | null, deps: unknown) {
  const [marker, setMarker] = useState<{ x: number; w: number; animate: boolean } | null>(null);
  const placed = useRef(false);

  useLayoutEffect(() => {
    const rail = railRef.current;
    if (!rail) return;
    const place = (animate: boolean) => {
      const item = selectedId ? rail.querySelector<HTMLElement>(`[data-alert="${CSS.escape(selectedId)}"]`) : null;
      if (!item) {
        setMarker((m) => (m ? { ...m, w: 0, animate: false } : null));
        placed.current = false;
        return;
      }
      setMarker({ x: item.offsetLeft, w: item.offsetWidth, animate: animate && placed.current });
      placed.current = true;
    };
    place(true);
    const observer = new ResizeObserver(() => place(false));
    // o trilho e cada comanda: a largura delas muda sem o trilho mudar (ex.: fonte que carrega depois)
    observer.observe(rail);
    rail.querySelectorAll("[data-alert]").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [railRef, selectedId, deps]);

  return marker;
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
  const railRef = useRef<HTMLOListElement>(null);
  const high = alerts.filter((a) => a.severity === "high").length;
  const medium = alerts.filter((a) => a.severity === "medium").length;

  // dado novo do recorte: reimprime o trilho e mantém a comanda aberta se ela ainda existe.
  // O ajuste é feito durante o render (não num effect), então o trilho novo já nasce certo, sem frame com o antigo.
  if (data !== seenData) {
    setSeenData(data);
    setPrintKey((k) => k + 1);
    setPrinting(true);
    setFolding(null);
    const kept = typeof openId === "string" && alerts.some((a) => a.id === openId) ? openId : undefined;
    setOpenId(kept);
    // A reimpressão remonta o trilho. Se o foco estava nele (ex.: drill-down da comanda), ele vai para o
    // título da comanda aberta no recorte novo, em vez de cair no body. Fora disso, não rouba o foco.
    const hadFocus = typeof document !== "undefined" && !!sectionRef.current?.contains(document.activeElement);
    const target = kept ?? alerts[0]?.id;
    setFocusRequest(hadFocus && target ? { id: target, on: "title" } : null);
  }
  const effectiveOpen = openId === undefined ? (alerts[0]?.id ?? null) : openId;
  const openIndex = alerts.findIndex((a) => a.id === effectiveOpen);
  const open = openIndex >= 0 ? alerts[openIndex] : null;

  // a comanda aberta publica a evidência; recolhida (ou sem evidência), os gráficos voltam ao normal
  useEffect(() => {
    $evidence.set(
      open?.evidence && folding !== open.id
        ? { alertId: open.id, number: num(openIndex), title: open.title, severity: open.severity, evidence: open.evidence }
        : null,
    );
  }, [open, openIndex, folding]);

  const marker = useRailMarker(railRef, folding ? null : effectiveOpen, `${printKey}:${alerts.length}`);

  const finishCollapse = (id: string) => {
    setFolding(null);
    setOpenId(null);
    setFocusRequest({ id, on: "stub" });
  };

  // fallback do recolhimento: se animationend não disparar, a faixa fecha no mesmo tempo
  useEffect(() => {
    if (folding === null) return;
    const id = folding;
    const timer = window.setTimeout(() => finishCollapse(id), FOLD_FALLBACK_MS);
    return () => window.clearTimeout(timer);
  }, [folding]); // eslint-disable-line react-hooks/exhaustive-deps

  const collapse = (id: string) => {
    setPrinting(false);
    if (prefersReducedMotion()) {
      finishCollapse(id);
      return;
    }
    setFolding(id);
  };
  const toggle = (id: string) => {
    if (id === effectiveOpen && folding !== id) {
      collapse(id);
      return;
    }
    setPrinting(false);
    setFolding(null);
    setOpenId(id);
    // clique no trilho: o foco fica no trilho (o leitor de tela ouve a faixa pelo aria-expanded)
    setFocusRequest(null);
  };
  const isRequested = (id: string, on: "title" | "stub") => focusRequest?.id === id && focusRequest.on === on;

  // texto anunciado por leitor de tela quando o trilho muda (sem anunciar a lista inteira)
  const noOrders = data?.orders === 0;
  const countText = alerts.length === 1 ? "1 comanda aberta" : `${alerts.length} comandas abertas`;
  const highText = high === 0 ? "nenhuma crítica" : high === 1 ? "1 crítica" : `${high} críticas`;
  const mediumText = medium === 0 ? "" : ` · ${medium} em atenção`;
  const status = !data
    ? ""
    : alerts.length > 0
      ? `${countText}, ${highText}`
      : noOrders
        ? "Sem pedidos neste recorte."
        : "Nenhuma comanda aberta neste recorte.";

  return (
    <section ref={sectionRef} aria-labelledby="comandas-title" className={`transition-opacity ${isPlaceholderData ? "opacity-60" : ""}`}>
      <header className="mb-2 flex items-baseline justify-between gap-2 px-0.5">
        <h2 id="comandas-title" className="cond text-[0.9rem] font-bold text-ink">
          Comandas abertas{data ? ` · ${alerts.length}` : ""}
        </h2>
        {data && alerts.length > 0 && (
          <p className="text-[0.82rem] text-muted">
            {highText}
            {mediumText}
          </p>
        )}
      </header>
      <p className="sr-only" aria-live="polite">
        {status}
      </p>
      {isPending ? (
        <div className="grid gap-2">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className={`skeleton h-[88px] ${i > 1 ? "max-sm:hidden" : ""}`} />
            ))}
          </div>
          <div className="skeleton h-[180px]" />
        </div>
      ) : error ? (
        <div className="tile p-4">
          <ErrorState error={error} onRetry={() => refetch()} />
        </div>
      ) : alerts.length === 0 ? (
        <div className="ticket flex items-center gap-3 bg-surface px-5 pt-5 pb-4">
          {noOrders ? (
            <CircleSlash className="size-5 shrink-0 text-muted" aria-hidden />
          ) : (
            <ShieldCheck className="size-5 shrink-0 text-good" aria-hidden />
          )}
          <p className="text-pretty">
            <span className="font-semibold">{noOrders ? "Sem pedidos neste recorte." : "Nenhuma comanda aberta neste recorte."}</span>{" "}
            <span className="text-muted">
              {noOrders
                ? "Não dá para afirmar SLA nem cancelamento sem pedidos. Amplie o período ou tire um filtro."
                : "SLA, cancelamento e lojas dentro do esperado. Mude o recorte para checar outro hub."}
            </span>
          </p>
        </div>
      ) : (
        // keyed em printKey: cada recorte novo remonta o trilho e o reimprime inteiro
        <div key={printKey}>
          <ol
            ref={railRef}
            aria-label="Trilho de comandas"
            className="comanda-rail relative grid snap-x auto-cols-[minmax(12rem,1fr)] grid-flow-col gap-2 overflow-x-auto overscroll-x-contain pb-2 max-sm:auto-cols-[15rem] print:grid-flow-row print:grid-cols-2 print:overflow-visible"
          >
            {alerts.map((a, i) => (
              <Stub
                key={a.id}
                alert={a}
                index={i}
                selected={a.id === effectiveOpen && folding !== a.id}
                printing={printing}
                focusOnMount={isRequested(a.id, "stub")}
                onToggle={() => toggle(a.id)}
              />
            ))}
            <li
              aria-hidden
              className={`pointer-events-none absolute bottom-0 left-0 h-[3px] rounded-full bg-ink print:hidden ${
                marker?.animate
                  ? "transition-[translate,width,opacity] duration-(--duration-fast) ease-(--ease-smooth-out) motion-reduce:transition-none"
                  : ""
              } ${marker && marker.w > 0 ? "opacity-100" : "opacity-0"}`}
              style={{ translate: `${marker?.x ?? 0}px 0`, width: marker?.w ?? 0 }}
            />
          </ol>
          {open && (
            // keyed na comanda: trocar de comanda imprime a faixa de novo (desdobra de cima para baixo)
            <OpenBand
              key={open.id}
              alert={open}
              index={openIndex}
              motion={folding === open.id ? "fold" : printing ? "print" : "open"}
              focusOnMount={isRequested(open.id, "title")}
              onCollapse={() => collapse(open.id)}
              onFolded={() => finishCollapse(open.id)}
            />
          )}
        </div>
      )}
    </section>
  );
}

export default island(AlertsPanelInner, 300);
