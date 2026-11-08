/**
 * Ações de exportação do recorte, compartilhadas pelo modal (ExportDialog, mobile)
 * e pelo menu "Compartilhar" da barra (ShareMenu, desktop).
 */
import type { QueryClient } from "@tanstack/react-query";
import { apiGet, apiUrl, type AlertsResponse, type KpiResponse } from "@/lib/api/client";
import { toQuery, type Recorte } from "@/lib/filters";
import { fmt } from "@/lib/format";

export function briefingMarkdown(kpis: KpiResponse, alerts: AlertsResponse["alerts"], url: string) {
  const m = kpis.current;
  const lines = [
    `# Briefing de operação — ${fmt.date(kpis.period.start)} a ${fmt.date(kpis.period.end)}`,
    "",
    `- Pedidos: ${fmt.int(m.orders)} · GMV ${fmt.brl(m.gmv)} · ticket ${fmt.brl(m.ticket)}`,
    `- SLA no prazo: ${fmt.pct(m.sla_rate)} · ciclo mediano ${fmt.min(m.cycle_p50)} (p90 ${fmt.min(m.cycle_p90)})`,
    `- Cancelamento: ${fmt.pct(m.cancel_rate)} · subsídio de frete ${fmt.brl(m.subsidy)}/entrega`,
    "",
    "## Alertas e ações",
    ...(alerts.length
      ? alerts.flatMap((a) => [`### ${a.title}`, a.detail, `**Ação:** ${a.action}`, ""])
      : ["Nenhum alerta neste recorte."]),
    "",
    `Recorte: ${url}`,
  ];
  return lines.join("\n");
}

/** Busca KPIs e alertas do recorte (pelo cache do QueryClient) e copia o briefing. Lança se falhar. */
export async function copyBriefing(qc: QueryClient, filters: Recorte): Promise<void> {
  const query = toQuery(filters);
  const [kpis, alerts] = await Promise.all([
    qc.query({ queryKey: ["/api/kpis", filters, {}], queryFn: () => apiGet("/api/kpis", query) }),
    qc.query({ queryKey: ["/api/alerts", filters, {}], queryFn: () => apiGet("/api/alerts", query) }),
  ]);
  await navigator.clipboard.writeText(briefingMarkdown(kpis, alerts.alerts, location.href));
}

/** Link do CSV de pedidos com o recorte atual. */
export function csvHref(filters: Recorte): string {
  return apiUrl("/api/orders.csv", toQuery(filters));
}
