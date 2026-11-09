import { useEffect, useRef, useState, type FocusEvent, type KeyboardEvent, type RefObject, type TransitionEvent } from "react";
import { prefersReducedMotion } from "@/lib/media";

/**
 * Máquina de estados: closed → open → closing → closed.
 * "closing" mantém o painel montado durante a saída (--duration-quick). Ele sai
 * quando a transição de opacidade termina; o timer abaixo é o fallback, caso
 * transitionend não dispare. Movimento reduzido pula direto para closed.
 */
export type Phase = "closed" | "open" | "closing";

/** Duração de --duration-quick (150 ms) com folga; só entra se transitionend faltar. */
const CLOSE_FALLBACK_MS = 200;

export interface Disclosure {
  phase: Phase;
  isOpen: boolean;
  /** Raiz que contém botão e painel: clique e foco fora dela fecham. */
  rootRef: RefObject<HTMLDivElement | null>;
  /** Botão que abre o painel: recebe o foco ao fechar com Esc. */
  buttonRef: RefObject<HTMLButtonElement | null>;
  /** Fecha (com saída animada, se o movimento não estiver reduzido); returnFocus devolve o foco ao botão. */
  dismiss: (returnFocus: boolean) => void;
  toggle: () => void;
  /** Esc fecha e devolve o foco ao botão. Ignora Esc já tratado por um filho (defaultPrevented). */
  onKeyDown: (e: KeyboardEvent<HTMLElement>) => void;
  /** Foco que sai da raiz fecha; foco que some (clique em área sem foco) não fecha. */
  onBlur: (e: FocusEvent<HTMLElement>) => void;
  /** Atributos do painel: data-state, inert durante a saída e o fim da transição. */
  panelProps: {
    "data-state": Phase;
    inert: boolean;
    onTransitionEnd: (e: TransitionEvent<HTMLElement>) => void;
  };
}

/**
 * Estado de abrir/fechar de popovers e menus não modais: saída animada com fallback
 * por timer, clique fora, Esc, foco que sai e movimento reduzido. Usado por Popover e ShareMenu.
 */
export function useDisclosure(): Disclosure {
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

  const onKeyDown = (e: KeyboardEvent<HTMLElement>) => {
    if (e.key === "Escape" && !e.defaultPrevented && phase === "open") {
      e.preventDefault();
      dismiss(true);
    }
  };

  const onBlur = (e: FocusEvent<HTMLElement>) => {
    const next = e.relatedTarget as Node | null;
    if (next && !rootRef.current?.contains(next)) dismiss(false);
  };

  const toggle = () => (phase === "open" ? dismiss(false) : setPhase("open"));

  return {
    phase,
    isOpen: phase === "open",
    rootRef,
    buttonRef,
    dismiss,
    toggle,
    onKeyDown,
    onBlur,
    panelProps: {
      "data-state": phase,
      inert: phase === "closing",
      onTransitionEnd: (e) => {
        if (e.target === e.currentTarget && e.propertyName === "opacity") setPhase((p) => (p === "closing" ? "closed" : p));
      },
    },
  };
}
