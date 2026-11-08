import { CircleAlert, Filter, Info, OctagonAlert, ShieldCheck } from "lucide-react";
import type { Alert } from "@/lib/api/client";
import { applyDrilldown } from "@/lib/filters";
import { island, useRecorteQuery } from "@/lib/query";
import { ErrorState, Panel, Skeleton } from "./ui/Panel";

const SEVERITY = {
  high: { icon: OctagonAlert, label: "Alta", rail: "border-l-chili", tone: "text-chili" },
  medium: { icon: CircleAlert, label: "Média", rail: "border-l-amber", tone: "text-amber" },
  low: { icon: Info, label: "Baixa", rail: "border-l-rule", tone: "text-muted" },
} as const;

const CATEGORY: Record<Alert["category"], string> = {
  sla: "SLA",
  cancelamento: "Cancelamento",
  loja: "Loja",
  frota: "Frota",
  dados: "Dados",
  volume: "Volume",
  custo: "Custo",
};

function AlertCard({ alert }: { alert: Alert }) {
  const s = SEVERITY[alert.severity];
  const Icon = s.icon;
  return (
    <li className={`slip border-l-[3px] ${s.rail} p-3`}>
      <div className="flex items-start gap-2">
        <Icon className={`mt-0.5 size-4 shrink-0 ${s.tone}`} aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-semibold">{alert.title}</span>
            <span className="text-[0.75rem] text-muted">
              {CATEGORY[alert.category]} · severidade {s.label.toLowerCase()}
            </span>
          </p>
          <p className="mt-1 text-[0.95rem]">{alert.detail}</p>
          <p className="mt-1.5 text-[0.95rem]">
            <span className="font-semibold">Ação: </span>
            {alert.action}
          </p>
          {alert.drilldown && (
            <button
              type="button"
              className="btn-ghost no-print mt-2 py-1 text-[0.85rem]"
              onClick={() => applyDrilldown(alert.drilldown!.filters)}
            >
              <Filter className="size-3.5" aria-hidden /> {alert.drilldown.label}
            </button>
          )}
        </div>
      </div>
    </li>
  );
}

function AlertsPanelInner() {
  const { data, error, isPending, refetch, isPlaceholderData } = useRecorteQuery("/api/alerts");
  const alerts = data?.alerts ?? [];
  const high = alerts.filter((a) => a.severity === "high").length;

  return (
    <Panel
      title="Alertas e ações"
      hint={data ? `${alerts.length} alerta(s), ${high} de severidade alta, calculados sobre o recorte atual.` : "Regras sobre SLA, cancelamento, lojas, pico e dados."}
      busy={isPlaceholderData}
      className="h-full"
    >
      {isPending ? (
        <Skeleton height={320} />
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : alerts.length === 0 ? (
        <div className="flex items-center gap-2 py-6">
          <ShieldCheck className="size-5 text-good" aria-hidden />
          <p>Nenhum alerta neste recorte. SLA, cancelamento e lojas dentro do esperado.</p>
        </div>
      ) : (
        <ul className="grid max-h-[560px] gap-2 overflow-auto pr-1">
          {alerts.map((a) => (
            <AlertCard key={a.id} alert={a} />
          ))}
        </ul>
      )}
    </Panel>
  );
}

export default island(AlertsPanelInner, 420);
