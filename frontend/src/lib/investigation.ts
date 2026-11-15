/**
 * Contrato da "investigação da comanda" (metade de baixo da página).
 *
 * - A zona de investigação, logo abaixo dos KPIs, mostra o painel que prova a
 *   comanda aberta. Sem comanda aberta (ou comanda do agente), mostra a Tendência.
 * - Os outros gráficos e a tabela de pedidos ficam recolhidos em "Explorar o recorte";
 *   o Ranking fica sempre aberto.
 * - O fechamento operacional, no fim da página, pede a próxima comanda ao trilho.
 *
 * Este módulo só guarda estado e regras puras. Quem move os painéis é
 * `investigationLayout.ts`; quem atende a próxima comanda é o `AlertsPanel`.
 */
import { atom } from "nanostores";
import type { Evidence } from "./api/client";
import type { TrendView } from "./filters";

/** Painéis que podem ocupar a zona de investigação. */
export type InvestigationView = "trend" | "stages" | "heatmap" | "scatter";

/** Recorte sem nenhum pedido: a metade de baixo recolhe (o trilho já mostra "Limpar recorte"). */
export const $recorteEmpty = atom(false);

/** Pedido do fechamento operacional ao trilho: abrir a comanda seguinte. Muda a cada pedido. */
export const $nextComandaRequest = atom(0);

export function requestNextComanda() {
  $nextComandaRequest.set($nextComandaRequest.get() + 1);
}

/** Painel que prova a evidência. `null` (sem comanda, ou comanda do agente) e KPI caem na Tendência. */
export function investigationViewFor(evidence: Evidence | null | undefined): InvestigationView {
  if (!evidence || evidence.view === "kpi") return "trend";
  return evidence.view;
}

/** Métrica da Tendência que acompanha um cartão de KPI. Ciclo mora na vista de SLA (SLA + ciclo). */
export function trendViewForKpi(kpi: Evidence["kpi"]): TrendView | null {
  switch (kpi) {
    case "sla_rate":
    case "cycle_p50":
      return "sla";
    case "cancel_rate":
      return "cancel";
    case "orders":
    case "gmv":
    case "ticket":
      return "volume";
    default:
      return null;
  }
}
