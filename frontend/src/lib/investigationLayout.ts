/**
 * Controlador da metade inferior da página:
 * - Zona 1 ("investigacao"): mostra exatamente um gráfico — o que prova a comanda
 *   aberta ($evidence), ou Tendência quando sem comanda / comanda do agente / KPI.
 * - Zona 2 ("explorar"): mantém os demais gráficos + Pedidos do recorte recolhidos
 *   em ordem estável (usando nós de comentário como marcadores). Painéis abertos
 *   manualmente permanecem abertos quando comandas mudam.
 * - Recorte vazio ($recorteEmpty): marca `data-recorte-empty` em `<main>` para
 *   recolher Zona 1, Ranking, Zona 2 e Fechamento.
 */
import { $evidence, type FocusedEvidence } from "./evidence";
import { $view, initFilters, setView } from "./filters";
import { $recorteEmpty, investigationViewFor, trendViewForKpi, type InvestigationView } from "./investigation";

const SLOT_ORDER: readonly InvestigationView[] = ["trend", "stages", "heatmap", "scatter"];

let initialized = false;

export function initInvestigationLayout() {
  if (initialized || typeof document === "undefined") return;

  const main = document.querySelector<HTMLElement>("main");
  const stage = document.querySelector<HTMLElement>("[data-investigation-stage]");
  const heading = document.querySelector<HTMLElement>("[data-investigation-heading]");
  const explorarList = document.querySelector<HTMLElement>("[data-explorar-list]");
  if (!main || !stage || !heading || !explorarList) return;

  initialized = true;
  initFilters();

  const slots = new Map<InvestigationView, HTMLElement>();
  const markers = new Map<InvestigationView, Comment>();
  const userOpened = new Set<string>();

  for (const view of SLOT_ORDER) {
    const slot = document.querySelector<HTMLElement>(`[data-investigation-slot="${view}"]`);
    if (!slot) continue;
    slots.set(view, slot);

    const anchorEl = explorarList.querySelector(`[data-slot-anchor="${view}"]`);
    const marker = document.createComment(`slot:${view}`);
    if (anchorEl) {
      anchorEl.replaceWith(marker);
    } else if (slot.parentElement === explorarList) {
      explorarList.insertBefore(marker, slot);
    } else {
      explorarList.appendChild(marker);
    }
    markers.set(view, marker);
  }

  function applyPanelState(container: ParentNode, { promoted, open }: { promoted: boolean; open: boolean }) {
    const section = container.querySelector<HTMLElement>("section.panel-frame");
    const staticHead = container.querySelector<HTMLElement>(".panel-head-static");
    const toggleHead = container.querySelector<HTMLElement>(".panel-head-toggle");
    const staticH2 = staticHead?.querySelector<HTMLElement>("h2");
    const toggleH2 = toggleHead?.querySelector<HTMLElement>("h2");
    const toggleBtn = toggleHead?.querySelector<HTMLButtonElement>("[data-panel-toggle]");
    const body = container.querySelector<HTMLElement>("[data-panel-body]");
    const headingId =
      section?.getAttribute("aria-labelledby") ??
      staticH2?.dataset.panelHeadingId ??
      toggleH2?.dataset.panelHeadingId;

    if (container instanceof HTMLElement && container.hasAttribute("data-investigation-slot")) {
      container.toggleAttribute("data-promoted", promoted);
    }

    const effectiveOpen = promoted || open;
    if (promoted) {
      staticHead?.removeAttribute("hidden");
      toggleHead?.setAttribute("hidden", "");
      if (headingId) {
        toggleH2?.removeAttribute("id");
        staticH2?.setAttribute("id", headingId);
      }
    } else {
      staticHead?.setAttribute("hidden", "");
      toggleHead?.removeAttribute("hidden");
      if (headingId) {
        staticH2?.removeAttribute("id");
        toggleH2?.setAttribute("id", headingId);
      }
    }

    toggleBtn?.setAttribute("aria-expanded", effectiveOpen ? "true" : "false");
    if (effectiveOpen) {
      body?.removeAttribute("hidden");
      section?.setAttribute("data-panel-open", "true");
    } else {
      body?.setAttribute("hidden", "");
      section?.removeAttribute("data-panel-open");
    }
  }

  let currentPromoted: InvestigationView | null = null;

  function syncEvidence(focused: FocusedEvidence | null) {
    heading!.textContent = focused ? `Investigação · Comanda ${focused.number}` : "Pulso do recorte";

    if (focused?.evidence.view === "kpi") {
      const nextTrend = trendViewForKpi(focused.evidence.kpi);
      if (nextTrend && $view.get().trend !== nextTrend) {
        setView({ trend: nextTrend });
      }
    }

    const targetView = investigationViewFor(focused?.evidence);
    const targetSlot = slots.get(targetView);
    if (!targetSlot) return;

    const changed = currentPromoted !== null && currentPromoted !== targetView;

    for (const view of SLOT_ORDER) {
      if (view === targetView) continue;
      const slot = slots.get(view);
      const marker = markers.get(view);
      if (!slot || !marker) continue;
      if (slot.parentElement !== explorarList || slot.previousSibling !== marker) {
        marker.parentNode?.insertBefore(slot, marker.nextSibling);
      }
      applyPanelState(slot, { promoted: false, open: userOpened.has(view) });
    }

    if (targetSlot.parentElement !== stage) {
      stage!.appendChild(targetSlot);
    }
    applyPanelState(targetSlot, { promoted: true, open: true });

    if (changed) {
      targetSlot.classList.remove("investigation-fade");
      void targetSlot.offsetWidth;
      targetSlot.classList.add("investigation-fade");
      targetSlot.addEventListener("animationend", () => targetSlot.classList.remove("investigation-fade"), { once: true });
    }

    currentPromoted = targetView;
  }

  explorarList.addEventListener("click", (e) => {
    const btn = (e.target as HTMLElement | null)?.closest<HTMLButtonElement>("[data-panel-toggle]");
    if (!btn || !explorarList.contains(btn)) return;
    if (btn.closest("[hidden]")) return;

    const slot = btn.closest<HTMLElement>("[data-investigation-slot]");
    const panelKey =
      slot?.dataset.investigationSlot ?? btn.closest<HTMLElement>("[data-explorar-panel]")?.dataset.explorarPanel;
    const container =
      slot ?? btn.closest<HTMLElement>("[data-explorar-panel]") ?? btn.closest<HTMLElement>("section.panel-frame");
    if (!container) return;

    const nextOpen = btn.getAttribute("aria-expanded") !== "true";
    if (panelKey) {
      if (nextOpen) userOpened.add(panelKey);
      else userOpened.delete(panelKey);
    }
    applyPanelState(container, { promoted: false, open: nextOpen });
  });

  $recorteEmpty.subscribe((empty) => {
    main.toggleAttribute("data-recorte-empty", empty);
  });

  $evidence.subscribe(syncEvidence);
}
