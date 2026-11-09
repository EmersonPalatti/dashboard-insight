import { useStore } from "@nanostores/react";
import { Bot } from "lucide-react";
import type { KeyboardEvent } from "react";
import {
  $agentActivity,
  $agentOpen,
  askAgentAbout,
  prefetchAgentChat,
  toggleAgent,
  type AgentActivity,
} from "@/lib/agentBridge";

const ACTIVITY_TEXT: Record<AgentActivity, string> = {
  idle: "",
  pending: "consultando o recorte",
  unread: "resposta nova",
};

/** Atalho conforme o sistema: ⌘K no Mac, Ctrl K no resto. */
function shortcutLabel() {
  return typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.userAgent) ? "⌘K" : "Ctrl K";
}

/**
 * Ponto de status no botão de abrir: pulsa enquanto consulta, fica cheio quando
 * chegou resposta com o painel fechado. A cor é a da série (vinho), não o vermelho
 * de alerta: resposta nova não é problema.
 */
function ActivityDot({ activity, onWine = false }: { activity: AgentActivity; onWine?: boolean }) {
  if (activity === "idle") return null;
  return (
    <span
      aria-hidden
      data-pending={activity === "pending" ? "" : undefined}
      className={`agent-dot size-2 shrink-0 rounded-full ${onWine ? "bg-on-wine" : "bg-series"}`}
    />
  );
}

/**
 * Entrada do agente na barra de filtros (lg e acima). Tem cara de campo de
 * pergunta, porque é isso que o agente faz: responde sobre o recorte na tela.
 * É um botão: clicar (ou Ctrl K) abre o painel; começar a digitar aqui abre o
 * painel com a letra já no campo. Largo, mostra o convite; estreito (painel
 * lateral aberto ou janela menor, pela container query da barra), vira "Agente".
 */
export function AgentAskButton() {
  const open = useStore($agentOpen);
  const activity = useStore($agentActivity);

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (open || e.key.length !== 1 || e.key === " " || e.ctrlKey || e.metaKey || e.altKey) return;
    e.preventDefault();
    askAgentAbout(e.key);
  };

  return (
    <button
      type="button"
      data-agent-launcher
      aria-controls="agente"
      aria-expanded={open}
      aria-keyshortcuts="Control+K Meta+K"
      aria-label={open ? "Fechar agente" : "Perguntar ao agente sobre este recorte"}
      onClick={toggleAgent}
      onKeyDown={onKeyDown}
      onPointerEnter={prefetchAgentChat}
      onFocus={prefetchAgentChat}
      className={`agent-ask flex h-10 min-w-0 items-center gap-2 rounded-card border px-3 text-left text-body whitespace-nowrap transition-colors duration-(--duration-quick) @6xl:w-[20.5rem] ${
        open ? "border-series bg-sunken" : "border-series bg-surface hover:bg-sunken"
      }`}
    >
      <Bot className="size-4 shrink-0 text-series" aria-hidden />
      {/* estreito (painel lateral aberto, janela menor): só "Agente"; largo: o convite, ou "Conversa aberta" */}
      <span className="min-w-0 flex-1 truncate font-medium text-ink @6xl:hidden">Agente</span>
      <span className={`hidden min-w-0 flex-1 truncate @6xl:inline ${open ? "text-ink" : "text-muted"}`}>
        {open ? "Conversa aberta" : "Pergunte sobre este recorte…"}
      </span>
      <ActivityDot activity={activity} />
      {activity !== "idle" && <span className="sr-only">: {ACTIVITY_TEXT[activity]}</span>}
      <kbd aria-hidden className="hidden shrink-0 rounded-tick border border-rule px-1 font-sans text-meta text-muted @6xl:inline">
        {shortcutLabel()}
      </kbd>
    </button>
  );
}

/** Botão flutuante do mobile: na zona do polegar, some enquanto o painel está aberto. */
export function AgentFab() {
  const open = useStore($agentOpen);
  const activity = useStore($agentActivity);
  return (
    <button
      type="button"
      data-agent-launcher
      aria-controls="agente"
      aria-expanded={open}
      onClick={toggleAgent}
      onPointerEnter={prefetchAgentChat}
      onFocus={prefetchAgentChat}
      className="agent-fab no-print btn fixed right-4 bottom-[calc(1rem+env(safe-area-inset-bottom))] z-30 min-h-12 border border-wine-raised bg-wine px-4 text-white hover:bg-wine-raised"
    >
      <Bot className="size-4 text-on-wine" aria-hidden />
      Agente
      <ActivityDot activity={activity} onWine />
      {activity !== "idle" && <span className="sr-only">: {ACTIVITY_TEXT[activity]}</span>}
    </button>
  );
}
