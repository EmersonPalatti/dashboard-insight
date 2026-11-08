import { useStore } from "@nanostores/react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, ClipboardCopy, FileSpreadsheet, Link2, Printer, Share2 } from "lucide-react";
import { useEffect, useId, useRef, useState, type FocusEvent, type KeyboardEvent } from "react";
import { copyBriefing, csvHref } from "@/lib/exportActions";
import { $filters, shareUrl } from "@/lib/filters";
import { prefersReducedMotion } from "./media";
import { iconSwap } from "../ui/swap";

/**
 * Máquina de estados: closed → open → closing → closed (mesma de FiltersPopover).
 * "closing" mantém o painel montado durante a saída; o timer é o fallback do transitionend.
 */
type Phase = "closed" | "open" | "closing";
type Briefing = "idle" | "busy" | "done" | "error";

/** Duração de --duration-quick (150 ms) com folga; só entra se transitionend faltar. */
const CLOSE_FALLBACK_MS = 200;
/** O estado "copiado" dura 1,8 s (igual ao CopyLinkButton). */
const FEEDBACK_MS = 1800;
/** A impressão espera o menu fechar (--duration-quick, 150 ms) com folga, para ele não sair no PDF. */
const PRINT_DELAY_MS = 250;

const itemClass =
  "flex w-full items-start gap-2.5 rounded-tick px-2.5 py-2 text-left transition-colors duration-(--duration-quick) hover:bg-sunken focus-visible:bg-sunken";

/** Itens navegáveis do menu, na ordem do DOM (botões habilitados e links). */
function menuItems(panel: HTMLElement | null): HTMLElement[] {
  if (!panel) return [];
  return Array.from(panel.querySelectorAll<HTMLElement>('[role="menuitem"]:not(:disabled)'));
}

function ItemText({ title, detail }: { title: string; detail: string }) {
  return (
    <span className="grid min-w-0 gap-0.5">
      <span className="text-[0.92rem] font-medium text-ink">{title}</span>
      <span className="text-[0.82rem] text-muted">{detail}</span>
    </span>
  );
}

/**
 * "Compartilhar" no desktop: menu não modal ancorado no botão, com link, CSV,
 * briefing e PDF. Esc fecha e devolve o foco ao botão; clique fora ou Tab para fora também fecham.
 */
export function ShareMenu() {
  const [phase, setPhase] = useState<Phase>("closed");
  const [linkCopied, setLinkCopied] = useState(false);
  const [briefing, setBriefing] = useState<Briefing>("idle");
  const filters = useStore($filters);
  const qc = useQueryClient();
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const linkTimer = useRef<number | undefined>(undefined);
  const briefingTimer = useRef<number | undefined>(undefined);
  const uid = useId();
  const panelId = `${uid}-menu`;

  useEffect(
    () => () => {
      window.clearTimeout(linkTimer.current);
      window.clearTimeout(briefingTimer.current);
    },
    [],
  );

  const dismiss = (returnFocus: boolean) => {
    setPhase((p) => (p === "open" ? (prefersReducedMotion() ? "closed" : "closing") : p));
    if (returnFocus) buttonRef.current?.focus();
  };

  // fallback da saída: se transitionend não chegar, fecha no mesmo tempo
  useEffect(() => {
    if (phase !== "closing") return;
    const timer = window.setTimeout(() => setPhase("closed"), CLOSE_FALLBACK_MS);
    return () => window.clearTimeout(timer);
  }, [phase]);

  // ao abrir, o foco vai para o primeiro item
  useEffect(() => {
    if (phase === "open") menuItems(panelRef.current)[0]?.focus();
  }, [phase]);

  // clique fora fecha enquanto aberto
  useEffect(() => {
    if (phase !== "open") return;
    const onPointerDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) dismiss(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [phase]);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (phase !== "open") return;
    if (e.key === "Escape") {
      e.preventDefault();
      dismiss(true);
      return;
    }
    const list = menuItems(panelRef.current);
    const i = list.indexOf(document.activeElement as HTMLElement);
    const last = list.length - 1;
    const go = (n: number) => {
      e.preventDefault();
      list[n]?.focus();
    };
    switch (e.key) {
      case "ArrowDown":
        go(i < 0 || i === last ? 0 : i + 1);
        break;
      case "ArrowUp":
        go(i <= 0 ? last : i - 1);
        break;
      case "Home":
        go(0);
        break;
      case "End":
        go(last);
        break;
    }
  };

  // Tab para fora do menu fecha; foco que some (clique em área sem foco) não fecha
  const onBlur = (e: FocusEvent<HTMLDivElement>) => {
    const next = e.relatedTarget as Node | null;
    if (next && !rootRef.current?.contains(next)) dismiss(false);
  };

  const toggle = () => (phase === "open" ? dismiss(false) : setPhase("open"));

  const onCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl());
      setLinkCopied(true);
      window.clearTimeout(linkTimer.current);
      linkTimer.current = window.setTimeout(() => setLinkCopied(false), FEEDBACK_MS);
    } catch {
      /* clipboard negado: o link continua na barra de endereço */
    }
  };

  const onCopyBriefing = async () => {
    window.clearTimeout(briefingTimer.current);
    setBriefing("busy");
    try {
      await copyBriefing(qc, filters);
      setBriefing("done");
    } catch {
      setBriefing("error");
    }
    briefingTimer.current = window.setTimeout(() => setBriefing("idle"), FEEDBACK_MS);
  };

  const briefingTitle =
    briefing === "busy"
      ? "Copiando briefing…"
      : briefing === "done"
        ? "Briefing copiado"
        : briefing === "error"
          ? "Não deu para copiar"
          : "Copiar briefing (Markdown)";

  // o aviso para leitores de tela segue o feedback visível
  const announce = briefing === "done" ? "Briefing copiado" : linkCopied ? "Link copiado" : "";

  return (
    <div ref={rootRef} className="relative flex min-w-0" onKeyDown={onKeyDown} onBlur={onBlur}>
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={phase === "open"}
        aria-controls={panelId}
        onClick={toggle}
        className="btn-ghost h-8 whitespace-nowrap"
      >
        <Share2 className="size-3.5" aria-hidden />
        Compartilhar
        <ChevronDown
          className={`size-3.5 text-muted transition-[rotate] duration-(--duration-fast) ease-(--ease-smooth-out) motion-reduce:transition-none ${
            phase === "open" ? "rotate-180" : ""
          }`}
          aria-hidden
        />
      </button>
      <span className="sr-only" aria-live="polite">
        {announce}
      </span>
      <div
        ref={panelRef}
        id={panelId}
        role="menu"
        aria-label="Compartilhar recorte"
        data-state={phase}
        inert={phase === "closing"}
        onTransitionEnd={(e) => {
          if (e.target === e.currentTarget && e.propertyName === "opacity") setPhase((p) => (p === "closing" ? "closed" : p));
        }}
        className={`recorte-popover absolute top-full right-0 z-30 mt-1.5 w-80 max-w-[calc(100vw-2rem)] rounded-card border border-rule bg-surface p-1.5 ${
          phase === "closed" ? "hidden" : ""
        }`}
      >
        <div role="none" className="grid gap-0.5">
          <button type="button" role="menuitem" className={itemClass} onClick={onCopyLink}>
            <span className="mt-0.5 grid size-4 shrink-0 place-items-center" aria-hidden>
              <Link2 className={`text-series ${iconSwap(!linkCopied, "size-4")}`} />
              <Check className={`text-good ${iconSwap(linkCopied, "size-4")}`} />
            </span>
            <ItemText title={linkCopied ? "Link copiado" : "Copiar link"} detail="Quem abrir vê o mesmo recorte." />
          </button>

          <a role="menuitem" className={itemClass} href={csvHref(filters)} download onClick={() => dismiss(true)}>
            <FileSpreadsheet className="mt-0.5 size-4 shrink-0 text-series" aria-hidden />
            <ItemText title="Pedidos em CSV" detail="Uma linha por pedido, com o recorte atual." />
          </a>

          <button type="button" role="menuitem" className={itemClass} onClick={onCopyBriefing} disabled={briefing === "busy"}>
            <span className="mt-0.5 grid size-4 shrink-0 place-items-center" aria-hidden>
              <ClipboardCopy className={`text-series ${iconSwap(briefing !== "done", "size-4")}`} />
              <Check className={`text-good ${iconSwap(briefing === "done", "size-4")}`} />
            </span>
            <ItemText title={briefingTitle} detail="KPIs, alertas e ações, pronto para colar no Slack ou num doc." />
          </button>

          <button
            type="button"
            role="menuitem"
            className={itemClass}
            onClick={() => {
              dismiss(true);
              window.setTimeout(() => window.print(), PRINT_DELAY_MS);
            }}
          >
            <Printer className="mt-0.5 size-4 shrink-0 text-series" aria-hidden />
            <ItemText title="PDF da tela" detail={'Abre a impressão; escolha "Salvar como PDF".'} />
          </button>
        </div>
      </div>
    </div>
  );
}
