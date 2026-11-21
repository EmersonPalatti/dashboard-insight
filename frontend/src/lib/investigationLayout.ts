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
import { $view, initFilters, isTrendFromUrl, setView } from "./filters";
import { prefersReducedMotion } from "./media";
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
  /** Primeira comanda aberta desde o carregamento (a abertura automática do trilho). */
  let firstFocus = true;
  /** Fade em curso por painel: cancelar o anterior evita listener acumulado e classe arrancada no meio. */
  const fades = new Map<HTMLElement, AbortController>();

  function fadeIn(slot: HTMLElement) {
    fades.get(slot)?.abort();
    fades.delete(slot);
    slot.classList.remove("investigation-fade");
    // movimento reduzido: o CSS zera a animação e animationend nunca dispara; não há o que esperar
    if (prefersReducedMotion()) return;
    void slot.offsetWidth;
    slot.classList.add("investigation-fade");
    const ctrl = new AbortController();
    fades.set(slot, ctrl);
    slot.addEventListener(
      "animationend",
      (e) => {
        if (e.target !== slot) return; // animação de um filho sobe até aqui e não encerra o fade
        slot.classList.remove("investigation-fade");
        ctrl.abort();
        if (fades.get(slot) === ctrl) fades.delete(slot);
      },
      { signal: ctrl.signal },
    );
  }

  /**
   * Mover um nó com o foco dentro tira o foco dele (vai para o body). Depois da troca,
   * devolve ao mesmo elemento se ele segue visível; se o painel recolheu, ao botão do painel.
   * Se o painel subiu para a investigação com o foco no botão (que some), o foco vai para o
   * próprio painel (`tabindex="-1"`, rotulado pelo título), nunca para o body.
   */
  function restoreFocus(active: HTMLElement | null, slot: HTMLElement | null) {
    if (!active || !slot || document.activeElement === active) return;
    if (active.isConnected && !active.closest("[hidden]")) {
      active.focus({ preventScroll: true });
      return;
    }
    const toggle = slot.querySelector<HTMLButtonElement>("[data-panel-toggle]");
    if (toggle && !toggle.closest("[hidden]")) toggle.focus({ preventScroll: true });
    else slot.focus({ preventScroll: true });
  }

  function syncEvidence(focused: FocusedEvidence | null) {
    heading!.textContent = focused ? `Investigação · Comanda ${focused.number}` : "Pulso do recorte";

    // A comanda escolhe a métrica sem empurrar histórico (Voltar não alterna a Tendência).
    // Na abertura automática, um `?trend=` explícito do link compartilhado vale mais que a comanda.
    const keepUrlTrend = firstFocus && isTrendFromUrl();
    if (focused) firstFocus = false;
    if (focused?.evidence.view === "kpi" && !keepUrlTrend) {
      const nextTrend = trendViewForKpi(focused.evidence.kpi);
      if (nextTrend && $view.get().trend !== nextTrend) {
        setView({ trend: nextTrend }, { history: "replace" });
      }
    }

    const targetView = investigationViewFor(focused?.evidence);
    const targetSlot = slots.get(targetView);
    if (!targetSlot) return;

    const changed = currentPromoted !== null && currentPromoted !== targetView;

    const active = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const activeSlot = active?.closest<HTMLElement>("[data-investigation-slot]") ?? null;

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
    restoreFocus(active, activeSlot);

    if (changed) fadeIn(targetSlot);

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
