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
 * painel com a letra já no campo. O slot cede largura antes do nome do lugar:
 * abaixo de 22rem o rótulo visível é "Agente" (o nome acessível continua inteiro).
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
      className={`agent-ask @container/ask flex h-10 w-full min-w-0 items-center gap-2 rounded-card border px-3 text-left text-body whitespace-nowrap transition-colors duration-(--duration-quick) ${
        open ? "border-series bg-sunken" : "border-series bg-surface hover:bg-sunken"
      }`}
    >
      <Bot className="size-4 shrink-0 text-series" aria-hidden />
      {/* o slot estreito (a barra cedeu a largura ao lugar) mostra "Agente"; 18rem+ de miolo: o convite */}
      <span className="min-w-0 flex-1 truncate font-medium text-ink @min-[18rem]/ask:hidden">Agente</span>
      <span className={`hidden min-w-0 flex-1 truncate @min-[18rem]/ask:inline ${open ? "text-ink" : "text-muted"}`}>
        {open ? "Conversa aberta" : "Pergunte sobre este recorte…"}
      </span>
      <ActivityDot activity={activity} />
      {activity !== "idle" && <span className="sr-only">: {ACTIVITY_TEXT[activity]}</span>}
      <kbd aria-hidden className="shrink-0 rounded-tick border border-rule px-1 font-sans text-meta text-muted">
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
      aria-keyshortcuts="Control+K Meta+K"
      onClick={toggleAgent}
      onPointerEnter={prefetchAgentChat}
      onFocus={prefetchAgentChat}
      className="agent-fab no-print btn fixed right-4 bottom-[calc(1rem+env(safe-area-inset-bottom))] z-30 min-h-12 border border-wine-raised bg-wine px-4 text-white hover:bg-wine-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-on-wine"
    >
      <Bot className="size-4 text-on-wine" aria-hidden />
      <span className="flex flex-col items-start leading-none">
        <span>Agente</span>
        <kbd className="border-0 bg-transparent p-0 font-sans text-meta font-medium text-on-wine">{shortcutLabel()}</kbd>
      </span>
      <ActivityDot activity={activity} onWine />
      {activity !== "idle" && <span className="sr-only">: {ACTIVITY_TEXT[activity]}</span>}
    </button>
  );
}
