/**
 * Ponte entre ilhas: a comanda aberta (AlertsPanel) entrega uma pergunta
 * pronta ao agente (AgentChat) sem enviar por ele. O operador revisa e envia.
 *
 * As ilhas não compartilham árvore React, então o rascunho vive num átomo.
 * O AgentChat hidrata em `client:visible`: se ainda não montou, lê o átomo
 * ao montar.
 */
import { atom } from "nanostores";

/** Pergunta pendente para o campo do agente; `null` quando já foi consumida. */
export const $agentDraft = atom<string | null>(null);

/** Leva o operador ao agente com a pergunta preenchida. */
export function askAgentAbout(question: string) {
  $agentDraft.set(question);
  if (typeof document === "undefined") return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.getElementById("agente")?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
}
