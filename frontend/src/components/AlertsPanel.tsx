/**
 * Trilho de comandas: cada alerta do recorte vira uma comanda pendurada lado a
 * lado (número, categoria, severidade e título). A comanda escolhida abre numa
 * faixa larga logo abaixo do trilho, com a ação impressa. Uma aberta por vez;
 * a aberta também publica a evidência dela ($evidence) para KPIs e gráficos.
 */
import { useStore } from "@nanostores/react";
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, CircleSlash, Filter, LineChart, MessageSquareText, ShieldCheck } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type ReactNode } from "react";
import type { Alert } from "@/lib/api/client";
import { $railAgentComandas, askAgentAbout, openComandaCount, scopeKey } from "@/lib/agentBridge";
import { AgentOpenBand, AgentStub } from "./agent/AgentComanda";
import { $evidence, EVIDENCE_ANCHOR, showEvidence } from "@/lib/evidence";
import { $filters, applyDrilldown } from "@/lib/filters";
import { prefersReducedMotion } from "@/lib/media";
import { island, useMeta, useRecorteQuery } from "@/lib/query";
import { outsideBaseNote } from "@/lib/format";
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
type Motion = "print" | "open" | "none";
const MOTION_CLASS: Record<Motion, string> = {
  print: "ticket-print",
  open: "ticket-open",
  none: "",
};

/** Reimpressão: 40ms por comanda, até o índice 5 (seis passos no máximo). Espelha o `calc(var(--i) * 40ms)`. */
const PRINT_STAGGER_CAP = 5;
/** Recolhimento: 250ms (--duration-fast) + 80ms de margem; este fallback fecha a faixa se transitionend não disparar. */
const FOLD_FALLBACK_MS = 330;
const BAND_ID = "comanda-aberta";

const num = (i: number) => `Nº ${String(i + 1).padStart(2, "0")}`;

/** Pedido de foco: vai para o título da faixa aberta ou para a comanda no trilho. */
type FocusRequest = { id: string; on: "title" | "stub" } | null;

/** Índice de escalonamento da reimpressão, lido pelo CSS como `--i`. */
const printVars = (index: number) => ({ "--i": Math.min(index, PRINT_STAGGER_CAP) }) as CSSProperties;

/** Cabeçalho da comanda. No trilho (`compact`) a severidade fica na marca e um chevron indica expansão. */
function TicketHead({
  alert,
  index,
  action,
  compact,
  selected,
}: {
  alert: Alert;
  index: number;
  action?: ReactNode;
  compact?: boolean;
  selected?: boolean;
}) {
  const s = SEVERITY[alert.severity];
  return (
    <span className="cond flex items-center justify-between gap-3 text-meta font-bold">
      <span className={`flex items-center gap-2 ${compact ? "shrink-0" : "min-w-0"}`}>
        <span className={`inline-block shrink-0 ${s.mark}`} aria-hidden />
        <span className={compact ? "whitespace-nowrap" : "truncate"}>
          {num(index)} · {CATEGORY[alert.category]}
        </span>
      </span>
      {compact ? (
        <span
          data-selected={selected ? "true" : undefined}
          className={`stub-chevron-wrap shrink-0 items-center justify-center ${
            selected ? "text-ink" : "text-muted group-hover:text-ink"
          }`}
        >
          <ChevronDown className="stub-chevron size-3.5 shrink-0" aria-hidden />
        </span>
      ) : (
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
  total,
  tabIndex,
  selected,
  bandMounted,
  printing,
  focusOnMount,
  onToggle,
}: {
  alert: Alert;
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
      data-alert={alert.id}
      className={`relative snap-start after:pointer-events-none after:absolute after:inset-x-0 after:-bottom-2 after:h-[3px] after:rounded-full after:bg-rule after:opacity-0 after:transition-opacity after:duration-(--duration-quick) after:ease-(--ease-smooth-out) print:after:hidden ${hoverClasses} ${
        printing ? "ticket-print" : ""
      }`}
      style={printVars(index)}
    >
      <button
        ref={buttonRef}
        type="button"
        tabIndex={tabIndex}
        aria-expanded={selected}
        aria-controls={bandMounted ? BAND_ID : undefined}
        aria-label={`${alert.title}, comanda ${index + 1} de ${total}, ${SEVERITY[alert.severity].label}, ${num(index)} ${CATEGORY[alert.category]}`}
        onClick={onToggle}
        className={`group ticket flex h-full w-full flex-col justify-start px-4 pt-4 pb-3.5 text-left transition-colors duration-(--duration-quick) ease-(--ease-smooth-out) ${
          selected ? "bg-surface" : "bg-surface/60 hover:bg-surface"
        }`}
      >
        <TicketHead alert={alert} index={index} compact selected={selected} />
        {/* w-0 + min-w-full: o título quebra em duas linhas e não alarga a coluna. A largura mínima fica com o carimbo. */}
        <span
          className={`mt-1.5 line-clamp-2 w-0 min-w-full text-body leading-snug font-semibold text-pretty transition-colors duration-(--duration-quick) ease-(--ease-smooth-out) ${
            selected ? "" : "text-ink/85 group-hover:text-ink"
          }`}
        >
          {alert.title}
        </span>
        <span className="mt-1 hidden text-aux text-pretty print:block">
          <span className="mr-1.5 text-aux font-semibold">Ação</span>
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
}: {
  alert: Alert;
  index: number;
  motion: Motion;
  focusOnMount: boolean;
  onCollapse: () => void;
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
              className="no-print -my-1 -mr-1.5 inline-flex min-h-6 items-center gap-1 rounded-tick px-1.5 font-medium text-muted transition-colors duration-(--duration-quick) hover:text-ink max-lg:min-h-11"
            >
              <ChevronUp className="size-3.5" aria-hidden /> Recolher
            </button>
          }
        />
      </div>
      <div className="mt-3 grid gap-x-8 gap-y-3.5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:grid-rows-[auto_1fr]">
        <div className="min-w-0 lg:col-start-1 lg:row-start-1">
          <h3 id={`${BAND_ID}-title`} ref={titleRef} tabIndex={-1} className="text-lead leading-snug font-semibold text-balance">
            {alert.title}
          </h3>
          <p className="mt-1.5 max-w-[68ch] text-body leading-relaxed text-pretty text-ink/85">{alert.detail}</p>
        </div>
        <div className="self-start action-block rounded-card px-4 py-3.5 lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:mt-0.5">
          <p className="text-aux font-semibold opacity-70">Ação</p>
          <p className="mt-1 text-body leading-snug text-pretty">{alert.action}</p>
        </div>
        <div className="comanda-actions no-print flex flex-wrap gap-2 self-start lg:col-start-1 lg:row-start-2">
          {alert.drilldown && (
            <button type="button" className="btn-primary max-lg:min-h-11 lg:min-h-9" onClick={() => applyDrilldown(alert.drilldown!.filters)}>
              <Filter className="size-3.5" aria-hidden /> {alert.drilldown.label}
            </button>
          )}
          {anchor && (
            <button
              type="button"
              className="btn-ghost max-lg:min-h-11 lg:min-h-9"
              aria-label={`Ver no gráfico · ${anchor.label}`}
              onClick={() => showEvidence(view!)}
            >
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
    </article>
  );
}

/**
 * Marca da comanda aberta no trilho: um traço sob ela que desliza de uma para outra
 * (--duration-fast, simétrico como abas). Mede o item escolhido dentro do próprio trilho,
 * então acompanha a rolagem horizontal sem recalcular.
 */
function useRailMarker(railRef: React.RefObject<HTMLOListElement | null>, selectedId: string | null, deps: unknown) {
  const [marker, setMarker] = useState<{ x: number; w: number; visible: boolean; slide: boolean } | null>(null);
  const placed = useRef(false);

  useLayoutEffect(() => {
    const rail = railRef.current;
    if (!rail) return;
    const place = (animate: boolean) => {
      const item = selectedId ? rail.querySelector<HTMLElement>(`[data-alert="${CSS.escape(selectedId)}"]`) : null;
      if (!item) {
        setMarker((m) => (m ? { ...m, visible: false, slide: false } : null));
        return;
      }
      setMarker((prev) => ({
        x: item.offsetLeft,
        w: item.offsetWidth,
        visible: true,
        slide: animate && placed.current && prev?.visible === true,
      }));
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

/** Quantas comandas do trilho estão cortadas à direita (fora da vista ou pela metade) e se já há trilho rolado para trás. */
function useRailOverflow(railRef: { current: HTMLOListElement | null }, deps: string) {
  const [count, setCount] = useState(0);
  const [behind, setBehind] = useState(false);
  useEffect(() => {
    const rail = railRef.current;
    if (!rail) {
      setCount(0);
      setBehind(false);
      return;
    }
    // Leitura direta (meia dúzia de retângulos): sem rAF, que não roda com a aba em segundo plano.
    const measure = () => {
      const edge = rail.getBoundingClientRect().right + 1;
      const hidden = [...rail.querySelectorAll<HTMLElement>(":scope > [data-alert]")].filter(
        (el) => el.getBoundingClientRect().right > edge,
      ).length;
      setCount(hidden);
      setBehind(rail.scrollLeft > 1);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(rail);
    rail.addEventListener("scroll", measure, { passive: true });
    return () => {
      observer.disconnect();
      rail.removeEventListener("scroll", measure);
    };
  }, [railRef, deps]);
  return { ahead: count, behind };
}

function AlertsSkeletonBody() {
  return (
    <div className="grid gap-2" aria-hidden="true">
      {/* Trilho de comandas (stubs): 2 visíveis em mobile, 4 em sm+ */}
      <div className="grid grid-cols-2 gap-2 pb-2 sm:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className={`ticket flex h-[96px] flex-col justify-start bg-surface px-4 pt-4 pb-3.5 ${
              i === 0 ? "border-b-2 border-ink" : "bg-surface/60"
            } ${i > 1 ? "max-sm:hidden" : ""}`}
          >
            <div className="flex items-center justify-between">
              <div className="skeleton h-3 w-20" />
              <div className="skeleton size-3.5 rounded" />
            </div>
            <div className="skeleton mt-2 h-4 w-full" />
            <div className="skeleton mt-1 h-4 w-3/4" />
          </div>
        ))}
      </div>
      {/* Faixa aberta: a primeira comanda abre por padrão; no mobile diagnóstico → Ação → botões, no desktop lado a lado */}
      <div className="ticket mt-2 bg-surface px-5 pt-5 pb-4">
        <div className="flex items-center justify-between border-b-[1.5px] border-dashed border-rule pb-2.5">
          <div className="flex items-center gap-2">
            <div className="skeleton size-2.5 rounded-full" />
            <div className="skeleton h-3.5 w-28" />
          </div>
          <div className="skeleton h-4 w-16" />
        </div>
        <div className="mt-3 grid gap-x-8 gap-y-3.5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:grid-rows-[auto_1fr]">
          <div className="min-w-0 lg:col-start-1 lg:row-start-1">
            <div className="skeleton h-5 w-3/4 max-w-sm" />
            <div className="mt-2 space-y-1.5">
              <div className="skeleton h-4 w-full" />
              <div className="skeleton h-4 w-5/6" />
            </div>
          </div>
          <div className="self-start rounded-card bg-sunken-strong/40 p-4 lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:mt-0.5">
            <div className="skeleton h-3 w-12" />
            <div className="mt-2 space-y-1.5">
              <div className="skeleton h-4 w-full" />
              <div className="skeleton h-4 w-4/5" />
            </div>
          </div>
          <div className="comanda-actions flex flex-wrap gap-2 self-start lg:col-start-1 lg:row-start-2">
            <div className="skeleton h-9 w-28 rounded-card max-lg:h-11 max-lg:w-full max-lg:basis-full" />
            <div className="skeleton h-9 w-32 rounded-card max-lg:h-11 max-lg:w-36" />
            <div className="skeleton h-9 w-36 rounded-card max-lg:h-11 max-lg:w-40" />
          </div>
        </div>
      </div>
    </div>
  );
}

function AlertsSkeleton() {
  return (
    <section aria-labelledby="comandas-title" aria-hidden="true">
      <header className="mb-2 flex items-baseline justify-between gap-2 px-0.5">
        <h2 id="comandas-title" className="cond text-body text-ink">
          Comandas abertas
        </h2>
        <div className="skeleton h-3.5 w-28 max-sm:hidden" />
      </header>
      <AlertsSkeletonBody />
    </section>
  );
}

function AlertsPanelInner() {
  const { data, error, isPending, refetch, isPlaceholderData } = useRecorteQuery("/api/alerts");
  const alerts = data?.alerts ?? [];
  const railAgents = useStore($railAgentComandas);
  const filters = useStore($filters);
  const { data: meta } = useMeta();
  const scope = scopeKey(filters);
  // undefined = o operador ainda não escolheu (abre a primeira); null = recolheu todas
  const [openId, setOpenId] = useState<string | null | undefined>(undefined);
  const [folding, setFolding] = useState<string | null>(null);
  const [expanding, setExpanding] = useState(false);
  const [openedFromCollapsed, setOpenedFromCollapsed] = useState(false);
  const [focusRequest, setFocusRequest] = useState<FocusRequest>(null);
  // Última comanda focada no trilho: só ela entra na ordem do Tab.
  const [railCursor, setRailCursor] = useState<string | null>(null);
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
    setExpanding(false);
    setOpenedFromCollapsed(false);
    const kept =
      typeof openId === "string" &&
      (alerts.some((a) => a.id === openId) || railAgents.some((ticket) => ticket.id === openId))
        ? openId
        : undefined;
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
  const agentOpen = open ? null : (railAgents.find((ticket) => ticket.id === effectiveOpen) ?? null);

  // a comanda de alerta publica a evidência; a do agente não mexe nos gráficos
  useEffect(() => {
    if (agentOpen && folding !== agentOpen.id) {
      $evidence.set(null);
      return;
    }
    $evidence.set(
      open?.evidence && folding !== open.id
        ? { alertId: open.id, number: num(openIndex), title: open.title, severity: open.severity, evidence: open.evidence }
        : null,
    );
  }, [agentOpen, open, openIndex, folding]);

  // Tirou da fila, ou a comanda sumiu: fecha a faixa sem reabrir a primeira.
  useEffect(() => {
    if (typeof openId !== "string") return;
    const alive = alerts.some((alert) => alert.id === openId) || railAgents.some((ticket) => ticket.id === openId);
    if (!alive) setOpenId(null);
  }, [openId, alerts, railAgents]);

  const { ahead: hiddenAhead, behind: railBehind } = useRailOverflow(railRef, `${printKey}:${alerts.length}:${railAgents.length}`);
  const scrollRail = (direction: 1 | -1) => {
    const rail = railRef.current;
    if (!rail) return;
    rail.scrollBy({ left: direction * rail.clientWidth * 0.8, behavior: prefersReducedMotion() ? "auto" : "smooth" });
  };

  const marker = useRailMarker(
    railRef,
    folding ? null : effectiveOpen,
    `${printKey}:${alerts.length}:${railAgents.length}`,
  );

  // Mantém a comanda aberta visível na horizontal do trilho ao trocar de seleção ou largura (ex.: painel do agente),
  // sem mexer na rolagem vertical da página nem desfazer a navegação por "voltar" / "mais N".
  useEffect(() => {
    const rail = railRef.current;
    if (!rail || !effectiveOpen) return;
    const ensureVisible = (smooth: boolean) => {
      const item = rail.querySelector<HTMLElement>(`[data-alert="${CSS.escape(effectiveOpen)}"]`);
      if (!item) return;
      const left = item.offsetLeft;
      const right = left + item.offsetWidth;
      const viewLeft = rail.scrollLeft;
      const viewRight = viewLeft + rail.clientWidth;
      let nextLeft: number | null = null;
      if (left < viewLeft) nextLeft = left;
      else if (right > viewRight) nextLeft = right - rail.clientWidth;
      if (nextLeft !== null && Math.abs(nextLeft - viewLeft) > 1) {
        rail.scrollTo({ left: nextLeft, behavior: smooth && !prefersReducedMotion() ? "smooth" : "auto" });
      }
    };
    ensureVisible(true);
    let prevWidth = rail.clientWidth;
    const ro = new ResizeObserver(() => {
      if (rail.clientWidth !== prevWidth) {
        prevWidth = rail.clientWidth;
        ensureVisible(false);
      }
    });
    ro.observe(rail);
    return () => ro.disconnect();
  }, [effectiveOpen, printKey, alerts.length, railAgents.length]);

  // Se abriu a partir de um estado totalmente recolhido, faz o flip 0fr → 1fr no frame seguinte
  useLayoutEffect(() => {
    if (!expanding) return;
    let raf1: number;
    let raf2: number;
    raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => {
        setExpanding(false);
      });
    });
    return () => {
      cancelAnimationFrame(raf1);
      cancelAnimationFrame(raf2);
    };
  }, [expanding]);

  const finishCollapse = (id: string) => {
    setFolding(null);
    setOpenId(null);
    setOpenedFromCollapsed(false);
    setExpanding(false);
    setFocusRequest({ id, on: "stub" });
  };

  // fallback do recolhimento: se transitionend não disparar, a faixa fecha no mesmo tempo
  useEffect(() => {
    if (folding === null) return;
    const id = folding;
    const timer = window.setTimeout(() => finishCollapse(id), FOLD_FALLBACK_MS);
    return () => window.clearTimeout(timer);
  }, [folding]); // eslint-disable-line react-hooks/exhaustive-deps

  const collapse = (id: string) => {
    setPrinting(false);
    setExpanding(false);
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
    const wasClosed = effectiveOpen === null || folding !== null;
    setPrinting(false);
    setFolding(null);
    setOpenId(id);
    setOpenedFromCollapsed(wasClosed);
    if (wasClosed && !prefersReducedMotion()) {
      setExpanding(true);
    }
    // clique no trilho: o foco fica no trilho (o leitor de tela ouve a faixa pelo aria-expanded)
    setFocusRequest(null);
  };
  const isRequested = (id: string, on: "title" | "stub") => focusRequest?.id === id && focusRequest.on === on;

  const railIds = [...alerts.map((a) => a.id), ...railAgents.map((ticket) => ticket.id)];
  const tabRailId =
    (railCursor && railIds.includes(railCursor) ? railCursor : null) ??
    (effectiveOpen && railIds.includes(effectiveOpen) ? effectiveOpen : null) ??
    railIds[0];

  const onRailKeyDown = (e: KeyboardEvent<HTMLOListElement>) => {
    const buttons = [...(railRef.current?.querySelectorAll<HTMLButtonElement>(":scope > li > button") ?? [])];
    const i = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (i < 0) return;
    const last = buttons.length - 1;
    let next = i;
    switch (e.key) {
      case "ArrowRight":
      case "ArrowDown":
      case "ArrowLeft":
      case "ArrowUp": {
        const forward = e.key === "ArrowRight" || e.key === "ArrowDown";
        next = forward ? (i === last ? i : i + 1) : i === 0 ? i : i - 1;
        break;
      }
      case "Home":
        next = 0;
        break;
      case "End":
        next = last;
        break;
      default:
        return;
    }
    if (next === i) return;
    e.preventDefault();
    const btn = buttons[next];
    const id = btn.closest<HTMLElement>("[data-alert]")?.dataset.alert ?? null;
    if (id) setRailCursor(id);
    btn.focus();
    btn.scrollIntoView({ block: "nearest", inline: "nearest" });
  };

  // texto anunciado por leitor de tela quando o trilho muda (sem anunciar a lista inteira)
  const noOrders = data?.orders === 0;
  const total = openComandaCount(alerts.length, railAgents.length);
  const countText = total === 1 ? "1 comanda aberta" : `${total} comandas abertas`;
  const highText = high === 0 ? "nenhuma crítica" : high === 1 ? "1 crítica" : `${high} críticas`;
  const mediumText = medium === 0 ? "" : ` · ${medium} em atenção`;
  const agentSide = railAgents.length === 0 ? "" : railAgents.length === 1 ? "1 do agente" : `${railAgents.length} do agente`;
  const agentStatus = agentSide ? `, ${agentSide}` : "";
  const status = !data
    ? ""
    : total > 0
      ? alerts.length > 0
        ? `${countText}, ${highText}${mediumText}${agentStatus}`
        : `${countText}, ${agentSide}`
      : noOrders
        ? "Sem pedidos neste recorte."
        : "Nenhuma comanda aberta neste recorte.";

  return (
    <section ref={sectionRef} aria-labelledby="comandas-title" className={`min-w-0 transition-opacity ${isPlaceholderData ? "opacity-60" : ""}`}>
      <header className="mb-2 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 px-0.5">
        <h2 id="comandas-title" className="cond text-body text-ink">
          Comandas abertas{data ? ` · ${total}` : ""}
        </h2>
        {data && total > 0 ? (
          <>
            <p className="text-aux text-muted max-sm:order-last max-sm:basis-full sm:ml-auto">
              {alerts.length > 0 ? (
                <>
                  {highText}
                  {mediumText}
                  {agentSide ? ` · ${agentSide}` : ""}
                </>
              ) : (
                agentSide
              )}
            </p>
            {(railBehind || hiddenAhead > 0) && (
              <div className="flex shrink-0 items-baseline gap-3">
                {railBehind && (
                  <button
                    type="button"
                    onClick={() => scrollRail(-1)}
                    className="hit-target inline-flex shrink-0 items-center gap-0.5 rounded-tick text-aux font-medium whitespace-nowrap text-ink underline decoration-rule underline-offset-2 hover:decoration-ink print:hidden"
                    aria-label="Mostrar as comandas anteriores"
                  >
                    <ChevronLeft className="size-3.5" aria-hidden />
                    voltar
                  </button>
                )}
                {hiddenAhead > 0 && (
                  <button
                    type="button"
                    onClick={() => scrollRail(1)}
                    className="hit-target inline-flex shrink-0 items-center gap-0.5 rounded-tick text-aux font-medium whitespace-nowrap text-ink underline decoration-rule underline-offset-2 hover:decoration-ink print:hidden"
                    aria-label={`Mostrar as próximas comandas: ${hiddenAhead} fora da vista`}
                  >
                    mais {hiddenAhead}
                    <ChevronRight className="size-3.5" aria-hidden />
                  </button>
                )}
              </div>
            )}
          </>
        ) : (
          !data && <div className="skeleton h-3.5 w-28 max-sm:hidden" aria-hidden />
        )}
      </header>
      <p className="sr-only" aria-live="polite">
        {status}
      </p>
      {isPending ? (
        <AlertsSkeletonBody />
      ) : error ? (
        <div className="tile p-4">
          <ErrorState error={error} onRetry={() => refetch()} />
        </div>
      ) : alerts.length === 0 && railAgents.length === 0 ? (
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
                ? `Não dá para afirmar SLA nem cancelamento sem pedidos. ${outsideBaseNote(filters, meta) ?? "Amplie o período ou tire um filtro."}`
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
            onKeyDown={onRailKeyDown}
            onFocus={(e) => {
              const id = (e.target as HTMLElement).closest<HTMLElement>("[data-alert]")?.dataset.alert;
              if (id) setRailCursor(id);
            }}
            className="comanda-rail relative grid snap-x auto-cols-[minmax(max-content,1fr)] grid-flow-col *:min-w-46 gap-2 overflow-x-auto overflow-y-hidden overscroll-x-contain pb-2 max-sm:auto-cols-[15rem] print:grid-flow-row print:grid-cols-2 print:overflow-visible"
          >
            {alerts.map((a, i) => (
              <Stub
                key={a.id}
                alert={a}
                index={i}
                total={total}
                tabIndex={a.id === tabRailId ? 0 : -1}
                selected={a.id === effectiveOpen && folding !== a.id}
                bandMounted={Boolean(open || agentOpen)}
                printing={printing}
                focusOnMount={isRequested(a.id, "stub")}
                onToggle={() => toggle(a.id)}
              />
            ))}
            {railAgents.map((ticket, index) => (
              <AgentStub
                key={ticket.id}
                ticket={ticket}
                stale={ticket.scope !== scope}
                index={alerts.length + index}
                total={total}
                tabIndex={ticket.id === tabRailId ? 0 : -1}
                selected={ticket.id === effectiveOpen && folding !== ticket.id}
                bandMounted={Boolean(open || agentOpen)}
                printing={printing}
                focusOnMount={isRequested(ticket.id, "stub")}
                onToggle={() => toggle(ticket.id)}
              />
            ))}
            <li
              aria-hidden
              className={`pointer-events-none absolute bottom-0 left-0 h-[3px] rounded-full bg-ink duration-(--duration-fast) ease-(--ease-smooth-out) motion-reduce:transition-none print:hidden ${
                marker?.slide ? "transition-[translate,width,opacity]" : "transition-opacity"
              } ${marker?.visible ? "opacity-100" : "opacity-0"}`}
              style={{ translate: `${marker?.x ?? 0}px 0`, width: marker?.w ?? 0 }}
            />
          </ol>
          {(open || agentOpen) && (
            // keyed na comanda: trocar de comanda imprime a faixa de novo (desdobra de cima para baixo)
            <div
              className="band-collapse"
              data-state={folding || expanding ? "closing" : "open"}
              onTransitionEnd={(e) => {
                if (e.propertyName === "grid-template-rows" && e.target === e.currentTarget) {
                  if (folding) finishCollapse(folding);
                }
              }}
            >
              <div>
                {agentOpen ? (
                  <AgentOpenBand
                    key={agentOpen.id}
                    ticket={agentOpen}
                    stale={agentOpen.scope !== scope}
                    motion={MOTION_CLASS[printing ? "print" : openedFromCollapsed ? "none" : "open"]}
                    focusOnMount={isRequested(agentOpen.id, "title")}
                    onCollapse={() => collapse(agentOpen.id)}
                  />
                ) : open ? (
                  <OpenBand
                    key={open.id}
                    alert={open}
                    index={openIndex}
                    motion={printing ? "print" : openedFromCollapsed ? "none" : "open"}
                    focusOnMount={isRequested(open.id, "title")}
                    onCollapse={() => collapse(open.id)}
                  />
                ) : null}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

export default island(AlertsPanelInner, <AlertsSkeleton />);
