import { useStore } from "@nanostores/react";
import { Bot } from "lucide-react";
import { $agentActivity, $agentOpen, toggleAgent, type AgentActivity } from "@/lib/agentBridge";

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

/** Botão da barra de filtros (lg e acima). Fica preso no topo junto com o recorte. */
export function AgentBarButton() {
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
      className={`btn-ghost ${open ? "border-ink bg-sunken" : ""}`}
    >
      <Bot className="size-3.5 text-series" aria-hidden />
      Agente
      <ActivityDot activity={activity} />
      {activity !== "idle" && <span className="sr-only">: {ACTIVITY_TEXT[activity]}</span>}
      <kbd className="ml-0.5 rounded-tick border border-rule px-1 font-sans text-[0.72rem] text-muted">{shortcutLabel()}</kbd>
    </button>
  );
}

/** Botão flutuante do mobile: na zona do polegar, some enquanto o painel está aberto. */
export function AgentFab() {
  const activity = useStore($agentActivity);
  return (
    <button
      type="button"
      data-agent-launcher
      aria-controls="agente"
      aria-expanded={false}
      onClick={toggleAgent}
      className="agent-fab no-print btn fixed right-4 bottom-[calc(1rem+env(safe-area-inset-bottom))] z-30 min-h-12 border border-wine-raised bg-wine px-4 text-white hover:bg-wine-raised"
    >
      <Bot className="size-4 text-on-wine" aria-hidden />
      Agente
      <ActivityDot activity={activity} onWine />
      {activity !== "idle" && <span className="sr-only">: {ACTIVITY_TEXT[activity]}</span>}
    </button>
  );
}
