import { useStore } from "@nanostores/react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, ClipboardCopy, FileSpreadsheet, Printer, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { apiGet, apiUrl, type AlertsResponse, type KpiResponse } from "@/lib/api/client";
import { $filters, toQuery } from "@/lib/filters";
import { fmt } from "@/lib/format";

interface Props {
  open: boolean;
  onClose: () => void;
}

function briefingMarkdown(kpis: KpiResponse, alerts: AlertsResponse["alerts"], url: string) {
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

export function ExportDialog({ open, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const filters = useStore($filters);
  const qc = useQueryClient();
  const [copied, setCopied] = useState<"idle" | "busy" | "done" | "error">("idle");

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const copyBriefing = async () => {
    setCopied("busy");
    try {
      const query = toQuery(filters);
      const [kpis, alerts] = await Promise.all([
        qc.query({ queryKey: ["/api/kpis", filters, {}], queryFn: () => apiGet("/api/kpis", query) }),
        qc.query({ queryKey: ["/api/alerts", filters, {}], queryFn: () => apiGet("/api/alerts", query) }),
      ]);
      await navigator.clipboard.writeText(briefingMarkdown(kpis, alerts.alerts, location.href));
      setCopied("done");
    } catch {
      setCopied("error");
    }
  };

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-fold border border-rule bg-paper p-0 text-ink backdrop:bg-black/40"
    >
      <div className="p-5">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold">Exportar recorte</h2>
            <p className="label">Tudo segue os filtros ativos agora.</p>
          </div>
          <button type="button" onClick={onClose} className="btn-ghost px-2" aria-label="Fechar">
            <X className="size-4" aria-hidden />
          </button>
        </div>
        <div className="grid gap-2">
          <a className="btn-ghost justify-start py-3" href={apiUrl("/api/orders.csv", toQuery(filters))} download>
            <FileSpreadsheet className="size-4 text-chili" aria-hidden />
            <span>
              <span className="block font-semibold">Pedidos em CSV</span>
              <span className="label">Uma linha por pedido, gerado no servidor via DuckDB.</span>
            </span>
          </a>
          <button type="button" className="btn-ghost justify-start py-3 text-left" onClick={copyBriefing} disabled={copied === "busy"}>
            {copied === "done" ? <Check className="size-4 text-chili" aria-hidden /> : <ClipboardCopy className="size-4 text-chili" aria-hidden />}
            <span>
              <span className="block font-semibold">
                {copied === "done" ? "Briefing copiado" : copied === "error" ? "Não deu para copiar" : "Copiar briefing (Markdown)"}
              </span>
              <span className="label">KPIs, alertas e ações, pronto para colar no Slack ou num doc.</span>
            </span>
          </button>
          <button
            type="button"
            className="btn-ghost justify-start py-3 text-left"
            onClick={() => {
              onClose();
              setTimeout(() => window.print(), 150);
            }}
          >
            <Printer className="size-4 text-chili" aria-hidden />
            <span>
              <span className="block font-semibold">PDF da tela</span>
              <span className="label">Abre a impressão do navegador; escolha "Salvar como PDF".</span>
            </span>
          </button>
        </div>
      </div>
    </dialog>
  );
}
