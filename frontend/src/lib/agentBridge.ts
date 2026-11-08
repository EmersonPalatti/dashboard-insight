/**
 * Ponte entre ilhas e o painel do agente. As ilhas não compartilham árvore
 * React, então o estado do painel vive em átomos:
 *  - $agentOpen: painel aberto ou fechado (botão da barra, botão flutuante, Ctrl+K)
 *  - $agentDraft: pergunta pronta vinda de uma comanda ou gráfico. Preenche o
 *    campo sem enviar; o operador revisa e aperta Enviar.
 *  - $agentActivity: o que o botão de abrir mostra com o painel fechado.
 */
import { atom } from "nanostores";

/** Pergunta pendente para o campo do agente; `null` quando já foi consumida. */
export const $agentDraft = atom<string | null>(null);

export const $agentOpen = atom(false);

/** `pending`: consultando o recorte. `unread`: chegou resposta com o painel fechado. */
export type AgentActivity = "idle" | "pending" | "unread";
export const $agentActivity = atom<AgentActivity>("idle");

/** Quem abriu o painel recebe o foco de volta quando ele fecha. */
let opener: HTMLElement | null = null;

export function openAgent() {
  if ($agentOpen.get()) return;
  if (typeof document !== "undefined") {
    const el = document.activeElement;
    opener = el instanceof HTMLElement && el !== document.body ? el : null;
  }
  $agentOpen.set(true);
}

export function closeAgent() {
  if (!$agentOpen.get()) return;
  $agentOpen.set(false);
  const from = opener;
  opener = null;
  // o botão flutuante só reaparece depois que o React tira o painel: resolve o alvo dois quadros depois
  requestAnimationFrame(() =>
    requestAnimationFrame(() => {
      const shown = (el: HTMLElement | null) => !!el && el.isConnected && el.getClientRects().length > 0;
      // sem quem abriu (Ctrl+K com foco no corpo), vale o botão de abrir que estiver visível
      const target = shown(from)
        ? from
        : [...document.querySelectorAll<HTMLElement>("[data-agent-launcher]")].find((el) => shown(el));
      target?.focus({ preventScroll: true });
    }),
  );
}

export function toggleAgent() {
  if ($agentOpen.get()) closeAgent();
  else openAgent();
}

/** Abre o painel com a pergunta preenchida. A página fica onde está. */
export function askAgentAbout(question: string) {
  $agentDraft.set(question);
  openAgent();
}
