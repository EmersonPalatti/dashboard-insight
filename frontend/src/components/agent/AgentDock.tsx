import { useStore } from "@nanostores/react";
import { useEffect, useLayoutEffect, useRef, type KeyboardEvent } from "react";
import { $agentOpen, closeAgent, toggleAgent } from "@/lib/agentBridge";
import { island } from "@/lib/query";
import { AgentConversation } from "../AgentChat";
import { useMediaQuery } from "../filters/media";
import { AgentFab } from "./AgentLauncher";

/**
 * Onde o agente mora, por largura:
 *  - dock  (≥ 1280px): coluna fixa à direita; a página encolhe e nada fica coberto.
 *  - float (1024–1279px): painel solto sob a barra de filtros, sem travar a página.
 *  - sheet (< 1024px): tela cheia, modal (resto da página inerte), aberto pelo botão flutuante.
 * O mesmo nó atravessa os três modos, então a conversa e a consulta em andamento não remontam.
 */
type Mode = "dock" | "float" | "sheet";

/** Ponto de corte do modo lateral. Abaixo disso a página não tem largura para encolher. */
const DOCK_QUERY = "(min-width: 1280px)";
const DESKTOP_QUERY = "(min-width: 1024px)";

function AgentDockInner() {
  const open = useStore($agentOpen);
  const dock = useMediaQuery(DOCK_QUERY);
  const desktop = useMediaQuery(DESKTOP_QUERY);
  const mode: Mode = dock ? "dock" : desktop ? "float" : "sheet";
  const panelRef = useRef<HTMLDivElement>(null);

  // Ctrl+K / ⌘K abre e fecha de qualquer lugar. Com um diálogo modal aberto (exportar, folha de filtros), não faz nada.
  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.altKey || e.key.toLowerCase() !== "k") return;
      if (document.querySelector("dialog[open]")) return;
      e.preventDefault();
      toggleAgent();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Modo lateral: a página abre espaço (padding no body) no mesmo quadro em que o painel começa a entrar.
  useLayoutEffect(() => {
    const root = document.documentElement;
    if (open && mode === "dock") root.dataset.agentDock = "";
    else delete root.dataset.agentDock;
    return () => {
      delete root.dataset.agentDock;
    };
  }, [open, mode]);

  // Folha (mobile): o resto da página fica inerte e sem rolagem, como num diálogo modal.
  useEffect(() => {
    const page = document.getElementById("page");
    if (!page || !(open && mode === "sheet")) return;
    page.inert = true;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    return () => {
      page.inert = false;
      document.body.style.overflow = overflow;
    };
  }, [open, mode]);

  // Modo solto: o painel começa logo abaixo da barra de filtros, que é sticky e muda de altura com os chips.
  useEffect(() => {
    if (!(open && mode === "float")) return;
    const bar = document.querySelector<HTMLElement>("[data-filter-bar]");
    const panel = panelRef.current;
    if (!bar || !panel) return;
    let frame = 0;
    const place = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        panel.style.setProperty("--agent-top", `${Math.max(0, bar.getBoundingClientRect().bottom) + 12}px`);
      });
    };
    place();
    const ro = new ResizeObserver(place);
    ro.observe(bar);
    window.addEventListener("scroll", place, { passive: true });
    window.addEventListener("resize", place);
    return () => {
      cancelAnimationFrame(frame);
      ro.disconnect();
      window.removeEventListener("scroll", place);
      window.removeEventListener("resize", place);
    };
  }, [open, mode]);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "Escape" || e.defaultPrevented) return;
    e.preventDefault();
    closeAgent();
  };

  return (
    <>
      {mode === "sheet" && !open && <AgentFab />}
      <div
        ref={panelRef}
        id="agente"
        data-mode={mode}
        data-open={open}
        inert={!open}
        role={mode === "sheet" ? "dialog" : "complementary"}
        aria-modal={mode === "sheet" ? true : undefined}
        aria-labelledby="agent-title"
        onKeyDown={onKeyDown}
        className="agent-panel no-print"
      >
        <AgentConversation visible={open} onClose={closeAgent} />
      </div>
    </>
  );
}

export default island(AgentDockInner, 0);
