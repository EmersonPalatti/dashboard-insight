import { useStore } from "@nanostores/react";
import { lazy, Suspense, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { Bot, X } from "lucide-react";
import { $agentDraft, $agentOpen, closeAgent, prefetchAgentChat, toggleAgent } from "@/lib/agentBridge";
import { island } from "@/lib/query";
import { useMediaQuery } from "@/lib/media";
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

const AgentConversation = lazy(() => prefetchAgentChat().then((m) => ({ default: m.AgentConversation })));

function AgentLoadingState({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex h-full min-h-0 flex-col" aria-busy="true">
      <header className="grid gap-2 border-b border-rule px-4 pt-3 pb-3">
        <div className="flex items-center justify-between gap-2">
          <h2 id="agent-title" className="section-title flex items-center gap-2">
            <Bot className="size-4 text-series" aria-hidden /> Agente do recorte
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar agente"
            title="Fechar (Esc)"
            className="inline-flex size-8 items-center justify-center rounded-card text-muted hover:bg-sunken hover:text-ink max-lg:size-11"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
        <div className="grid gap-1.5">
          <div className="h-4 w-44 skeleton" />
          <div className="h-3 w-56 skeleton" />
        </div>
      </header>
      <div className="flex min-h-0 flex-1 flex-col justify-between p-4">
        <div className="space-y-3">
          <div className="h-4 w-52 skeleton" />
          <div className="space-y-1.5 pt-1">
            <div className="h-9 w-full skeleton" />
            <div className="h-9 w-full skeleton" />
          </div>
        </div>
        <div className="flex items-center justify-center py-6 text-muted">
          <span className="shimmer-text text-[0.88rem]" data-text="Carregando agente…">
            Carregando agente…
          </span>
        </div>
        <div className="h-10 w-full rounded-card border border-rule bg-surface/50" />
      </div>
    </div>
  );
}

function AgentDockInner() {
  const open = useStore($agentOpen);
  const draft = useStore($agentDraft);
  const dock = useMediaQuery(DOCK_QUERY);
  const desktop = useMediaQuery(DESKTOP_QUERY);
  const mode: Mode = dock ? "dock" : desktop ? "float" : "sheet";
  const panelRef = useRef<HTMLDivElement>(null);

  // Monta a conversa só após o primeiro open (ou pergunta engatilhada). Depois disso, mantém montada.
  const [hasMountedChat, setHasMountedChat] = useState(() => open || draft !== null);

  useEffect(() => {
    if (open || draft !== null) {
      setHasMountedChat(true);
    }
  }, [open, draft]);

  // Prefetch do chunk em idle após o carregamento da casca
  useEffect(() => {
    if (typeof window === "undefined") return;
    if ("requestIdleCallback" in window) {
      const id = (window as Window & { requestIdleCallback: (cb: () => void, opts?: { timeout: number }) => number })
        .requestIdleCallback(() => prefetchAgentChat(), { timeout: 3000 });
      return () => {
        (window as Window & { cancelIdleCallback: (id: number) => void }).cancelIdleCallback(id);
      };
    }
    const id = setTimeout(() => prefetchAgentChat(), 1500);
    return () => clearTimeout(id);
  }, []);

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
        {hasMountedChat ? (
          <Suspense fallback={<AgentLoadingState onClose={closeAgent} />}>
            <AgentConversation visible={open} onClose={closeAgent} />
          </Suspense>
        ) : (
          <h2 id="agent-title" className="sr-only">
            Agente do recorte
          </h2>
        )}
      </div>
    </>
  );
}

export default island(AgentDockInner, 0);
