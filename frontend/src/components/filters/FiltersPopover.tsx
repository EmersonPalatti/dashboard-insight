import { SlidersHorizontal } from "lucide-react";
import { useEffect, useRef, useState, type FocusEvent, type KeyboardEvent, type ReactNode } from "react";
import { prefersReducedMotion } from "./media";

/**
 * Máquina de estados: closed → open → closing → closed.
 * "closing" mantém o painel montado durante a saída (--duration-quick). Ele sai
 * quando a transição de opacidade termina; o timer abaixo é o fallback, caso
 * transitionend não dispare. Movimento reduzido pula direto para closed.
 */
type Phase = "closed" | "open" | "closing";

/** Duração de --duration-quick (150 ms) com folga; só entra se transitionend faltar. */
const CLOSE_FALLBACK_MS = 200;

/**
 * "Mais filtros" no desktop: popover não modal ancorado no botão. Esc fecha e
 * devolve o foco ao botão; clique fora ou Tab para fora também fecham.
 * Sem overflow hidden, então os listboxes do MultiSelect não são cortados.
 */
export function FiltersPopover({ count, children }: { count: number; children: ReactNode }) {
  const [phase, setPhase] = useState<Phase>("closed");
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

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
    // Esc dentro de um seletor já foi tratado por ele (defaultPrevented): só o Esc livre fecha o popover
    if (e.key === "Escape" && !e.defaultPrevented && phase === "open") {
      e.preventDefault();
      dismiss(true);
    }
  };

  // Tab para fora do popover fecha; foco que some (clique em área sem foco) não fecha
  const onBlur = (e: FocusEvent<HTMLDivElement>) => {
    const next = e.relatedTarget as Node | null;
    if (next && !rootRef.current?.contains(next)) dismiss(false);
  };

  const toggle = () => (phase === "open" ? dismiss(false) : setPhase("open"));

  return (
    <div ref={rootRef} className="relative flex min-w-0" onKeyDown={onKeyDown} onBlur={onBlur}>
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={phase === "open"}
        aria-controls="filtros-extra"
        onClick={toggle}
        className="btn-ghost w-full justify-center self-stretch"
      >
        <SlidersHorizontal className="size-3.5" aria-hidden />
        Mais filtros{count > 0 ? ` · ${count}` : ""}
      </button>
      <div
        id="filtros-extra"
        data-state={phase}
        inert={phase === "closing"}
        className={`recorte-popover absolute top-full right-0 z-30 mt-1.5 w-72 max-w-[calc(100vw-2rem)] rounded-card border border-rule bg-surface p-3 ${
          phase === "closed" ? "hidden" : ""
        }`}
        onTransitionEnd={(e) => {
          if (e.target === e.currentTarget && e.propertyName === "opacity") setPhase((p) => (p === "closing" ? "closed" : p));
        }}
      >
        <div className="grid gap-2">{children}</div>
      </div>
    </div>
  );
}
