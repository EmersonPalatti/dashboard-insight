/**
 * Evidência da comanda aberta. O trilho de comandas publica aqui a comanda que
 * está aberta; KPIs e gráficos leem e destacam o dado que a sustenta (hub,
 * loja, horas, cartão), sem mexer no recorte. Comanda recolhida: null.
 */
import { atom } from "nanostores";
import type { Alert, Evidence } from "./api/client";
import { prefersReducedMotion } from "./media";

export interface FocusedEvidence {
  alertId: string;
  /** "Nº 02", o mesmo número impresso na comanda. */
  number: string;
  title: string;
  severity: Alert["severity"];
  evidence: Evidence;
}

export const $evidence = atom<FocusedEvidence | null>(null);

/**
 * Opacidade do que não é a evidência da comanda aberta. 0,25 atenua o restante
 * dentro da faixa de 20–30% sem apagar a leitura dos eixos e rótulos.
 */
export const EVIDENCE_DIM = 0.25;

/** Painel de cada gráfico que pode provar uma comanda (id da seção, para rolar até ela). */
export const EVIDENCE_ANCHOR: Record<Exclude<Evidence["view"], "kpi">, { id: string; label: string }> = {
  stages: { id: "grafico-etapas", label: "Ver nas etapas por hub" },
  heatmap: { id: "grafico-dia-hora", label: "Ver no mapa dia × hora" },
  scatter: { id: "grafico-lojas", label: "Ver no gráfico de lojas" },
};

/** Leva a tela até o gráfico da evidência e põe o foco nele (sem segundo salto de rolagem). */
export function showEvidence(view: Evidence["view"]) {
  if (view === "kpi" || typeof document === "undefined") return;
  const el = document.getElementById(EVIDENCE_ANCHOR[view].id);
  if (!el) return;
  const reduce = prefersReducedMotion();
  el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  el.focus({ preventScroll: true });
  // Os gráficos no caminho hidratam enquanto a página rola e mudam de altura: o alvo sai do lugar.
  // No fim da rolagem, um acerto sem animação devolve o gráfico ao topo (abaixo da barra de filtros).
  const settle = () => {
    const margin = parseFloat(getComputedStyle(el).scrollMarginTop) || 0;
    if (Math.abs(el.getBoundingClientRect().top - margin) > 8) el.scrollIntoView({ behavior: "auto", block: "start" });
  };
  if ("onscrollend" in window) window.addEventListener("scrollend", settle, { once: true });
  else setTimeout(settle, 900);
}
