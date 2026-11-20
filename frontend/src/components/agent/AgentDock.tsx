import { useStore } from "@nanostores/react";
import { Component, lazy, Suspense, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode, type Ref } from "react";
import { Bot, TriangleAlert, X } from "lucide-react";
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

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

function getFocusable(container: HTMLElement): HTMLElement[] {
  return [...container.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
    (el) => !el.closest("[hidden],[inert]") && el.getClientRects().length > 0,
  );
}

// React.lazy guarda a rejeição: cada nova tentativa cria outro lazy, e prefetchAgentChat
// já esquece a Promise que falhou (chunk velho depois de um deploy, rede caída).
const loadConversation = () =>
  lazy(() => prefetchAgentChat().then((m) => ({ default: m.AgentConversation })));

/** Título e fechar da folha enquanto a conversa não montou (carregando ou com erro). */
function AgentHeader({ onClose, closeRef }: { onClose: () => void; closeRef?: Ref<HTMLButtonElement> }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <h2 id="agent-title" className="section-title flex min-w-0 items-center gap-1.5 whitespace-nowrap">
        <Bot className="size-4 shrink-0 text-series" aria-hidden /> <span className="truncate">Agente do recorte</span>
      </h2>
      <button
        ref={closeRef}
        type="button"
        onClick={onClose}
        aria-label="Fechar agente"
        title="Fechar (Esc)"
        className="inline-flex size-8 items-center justify-center rounded-card text-muted hover:bg-sunken hover:text-ink max-lg:size-11"
      >
        <X className="size-4" aria-hidden />
      </button>
    </div>
  );
}

function AgentLoadingState({ open, onClose }: { open: boolean; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (open) closeRef.current?.focus({ preventScroll: true });
  }, [open]);
  return (
    <div className="flex h-full min-h-0 flex-col" aria-busy="true">
      <header className="grid gap-2 border-b border-rule px-4 pt-3 pb-3">
        <AgentHeader onClose={onClose} closeRef={closeRef} />
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
          <span className="shimmer-text text-aux" data-text="Carregando agente…">
            Carregando agente…
          </span>
        </div>
        <div className="h-10 w-full rounded-card border border-rule bg-surface/50" />
      </div>
    </div>
  );
}

function AgentErrorState({
  open,
  attempts,
  onClose,
  onRetry,
}: {
  open: boolean;
  attempts: number;
  onClose: () => void;
  onRetry: () => void;
}) {
  const retryRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (open) retryRef.current?.focus({ preventScroll: true });
  }, [open]);
  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="grid gap-2 border-b border-rule px-4 pt-3 pb-3">
        <AgentHeader onClose={onClose} />
      </header>
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
        <TriangleAlert className="size-5 text-ink" aria-hidden />
        <p role="alert" className="max-w-xs text-pretty text-aux text-ink">
          Não deu para carregar o agente. Se a página ficou aberta durante uma atualização, tente de novo.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <button ref={retryRef} type="button" className="btn-ghost max-lg:min-h-11" onClick={onRetry}>
            Tentar de novo
          </button>
          {attempts > 0 && (
            <button type="button" className="btn-ghost max-lg:min-h-11" onClick={() => window.location.reload()}>
              Recarregar página
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

interface BoundaryProps {
  resetKey: number;
  open: boolean;
  onClose: () => void;
  onReset: () => void;
  children: ReactNode;
}

class AgentErrorBoundary extends Component<BoundaryProps, { error: unknown }> {
  state: { error: unknown } = { error: null };

  static getDerivedStateFromError(error: unknown) {
    return { error };
  }

  componentDidUpdate(prevProps: BoundaryProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.error !== null) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error !== null) {
      return (
        <AgentErrorState
          open={this.props.open}
          attempts={this.props.resetKey}
          onClose={this.props.onClose}
          onRetry={this.props.onReset}
        />
      );
    }
    return this.props.children;
  }
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
  const [chatAttempt, setChatAttempt] = useState(() => ({
    id: 0,
    Component: loadConversation(),
  }));
  const retryChat = () => {
    setChatAttempt((prev) => ({ id: prev.id + 1, Component: loadConversation() }));
  };

  useEffect(() => {
    if (open || draft !== null) {
      setHasMountedChat(true);
    }
  }, [open, draft]);

  // Prefetch do chunk em idle após o carregamento da casca
  useEffect(() => {
    if (typeof window === "undefined") return;
    const warm = () => {
      void prefetchAgentChat().catch(() => {});
    };
    if ("requestIdleCallback" in window) {
      const id = (window as Window & { requestIdleCallback: (cb: () => void, opts?: { timeout: number }) => number })
        .requestIdleCallback(warm, { timeout: 3000 });
      return () => {
        (window as Window & { cancelIdleCallback: (id: number) => void }).cancelIdleCallback(id);
      };
    }
    const id = setTimeout(warm, 1500);
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

  // Esc com o foco fora do painel e fora de qualquer controle (cai no body quando o botão focado some,
  // como a pergunta sugerida depois de enviada): fecha do mesmo jeito. Com foco em outro controle da
  // página, Esc é dele (menus, popovers), e o painel lateral fica.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented) return;
      if (document.activeElement !== document.body || document.querySelector("dialog[open]")) return;
      e.preventDefault();
      closeAgent();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  // Modo lateral ou flutuante: a página abre espaço no mesmo quadro em que o painel entra.
  useLayoutEffect(() => {
    const root = document.documentElement;
    if (open && (mode === "dock" || mode === "float")) root.dataset.agentDock = mode;
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
    if (e.key === "Escape" && !e.defaultPrevented) {
      e.preventDefault();
      closeAgent();
      return;
    }
    if (e.key !== "Tab" || mode !== "sheet" || !open || !panelRef.current) return;
    const focusable = getFocusable(panelRef.current);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    if (e.shiftKey) {
      if (active === first || !panelRef.current.contains(active)) {
        e.preventDefault();
        last.focus();
      }
    } else if (active === last || !panelRef.current.contains(active)) {
      e.preventDefault();
      first.focus();
    }
  };

  const ActiveConversation = chatAttempt.Component;

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
          <AgentErrorBoundary resetKey={chatAttempt.id} open={open} onClose={closeAgent} onReset={retryChat}>
            <Suspense fallback={<AgentLoadingState open={open} onClose={closeAgent} />}>
              <ActiveConversation visible={open} onClose={closeAgent} />
            </Suspense>
          </AgentErrorBoundary>
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
