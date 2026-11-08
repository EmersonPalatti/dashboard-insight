import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import type { Metrics } from "@/lib/api/client";
import { fmt } from "@/lib/format";
import { island, useMeta, useRecorteQuery } from "@/lib/query";
import { ErrorState } from "./ui/Panel";

type Key = keyof Metrics;

interface KpiDef {
  key: Key;
  label: string;
  format: (v: number | null | undefined) => string;
  /** "up" = subir é bom; "down" = subir é ruim. */
  better: "up" | "down";
  /** taxa: variação em p.p.; valor: variação relativa. */
  kind: "rate" | "value";
  sub?: (m: Metrics) => string;
}

const OPERATION: KpiDef[] = [
  {
    key: "sla_rate",
    label: "No prazo (SLA)",
    format: fmt.pct,
    better: "up",
    kind: "rate",
    sub: (m) => `${fmt.pct(m.stuck_rate)} presos no fluxo (fora do cálculo)`,
  },
  {
    key: "cycle_p50",
    label: "Ciclo mediano",
    format: fmt.min,
    better: "down",
    kind: "value",
    sub: (m) => `p90 ${fmt.min(m.cycle_p90)}`,
  },
  {
    key: "cancel_rate",
    label: "Cancelamento",
    format: fmt.pct,
    better: "down",
    kind: "rate",
    sub: (m) => `${fmt.int(m.canceled)} pedidos cancelados`,
  },
];

const VOLUME: KpiDef[] = [
  { key: "orders", label: "Pedidos", format: fmt.int, better: "up", kind: "value", sub: (m) => `${fmt.int(m.delivered)} entregues` },
  { key: "gmv", label: "GMV", format: fmt.brlCompact, better: "up", kind: "value", sub: (m) => fmt.brl(m.gmv) },
  {
    key: "ticket",
    label: "Ticket médio",
    format: fmt.brl,
    better: "up",
    kind: "value",
    sub: (m) => `Subsídio de frete ${fmt.brl(m.subsidy)}/entrega`,
  },
];

function Delta({ def, current, previous }: { def: KpiDef; current: Metrics; previous?: Metrics | null }) {
  const a = current[def.key] as number | null;
  const b = previous?.[def.key] as number | null | undefined;
  if (a === null || b === null || b === undefined || (def.kind === "value" && b === 0)) {
    return <span className="text-[0.8rem] text-muted">sem período anterior</span>;
  }
  const delta = def.kind === "rate" ? a - b : a / b - 1;
  const flat = Math.abs(delta) < (def.kind === "rate" ? 0.001 : 0.005);
  const good = flat ? null : (delta > 0) === (def.better === "up");
  const Icon = flat ? Minus : delta > 0 ? ArrowUpRight : ArrowDownRight;
  const text =
    def.kind === "rate"
      ? `${delta > 0 ? "+" : "−"}${fmt.num1(Math.abs(delta) * 100)} p.p.`
      : `${delta > 0 ? "+" : "−"}${fmt.num1(Math.abs(delta) * 100)}%`;
  return (
    <span
      className={`inline-flex items-center gap-0.5 text-[0.8rem] font-semibold ${
        good === null ? "text-muted" : good ? "text-good" : "text-chili"
      }`}
      title="Contra o período anterior de mesmo tamanho"
    >
      <Icon className="size-3.5" aria-hidden />
      {flat ? "estável" : text}
      <span className="sr-only">{good === null ? "" : good ? "(melhorou)" : "(piorou)"}</span>
    </span>
  );
}

function Card({ def, current, previous, hero }: { def: KpiDef; current: Metrics; previous?: Metrics | null; hero?: boolean }) {
  return (
    <div className={`slip relative overflow-hidden px-3.5 py-3 ${hero ? "border-l-[3px] border-l-chili" : ""}`}>
      <p className="label">{def.label}</p>
      <p className={`mt-0.5 font-bold tracking-tight tabular-nums ${hero ? "text-[1.7rem]" : "text-[1.35rem]"}`}>
        {def.format(current[def.key] as number | null)}
      </p>
      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5">
        <Delta def={def} current={current} previous={previous} />
      </div>
      {def.sub && <p className="mt-1 truncate text-[0.8rem] text-muted">{def.sub(current)}</p>}
    </div>
  );
}

function KpiSkeleton() {
  return (
    <div className="grid gap-2">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="skeleton h-[112px]" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="skeleton h-[100px]" />
        ))}
      </div>
    </div>
  );
}

function KpiStripInner() {
  const { data, error, isPending, refetch, isPlaceholderData } = useRecorteQuery("/api/kpis");
  const { data: meta } = useMeta();
  if (isPending) return <KpiSkeleton />;
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  const { current, previous, period, previous_period } = data;

  if (current.orders === 0) {
    return (
      <div className="slip border-l-[3px] border-l-chili p-4">
        <p className="font-semibold">Nenhum pedido neste recorte.</p>
        <p className="label">Afrouxe período, hub ou loja. Os painéis abaixo ficam vazios até lá.</p>
      </div>
    );
  }

  return (
    <div className={`grid gap-2 transition-opacity ${isPlaceholderData ? "opacity-60" : ""}`} aria-live="polite">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="label">
          {fmt.date(period.start)} a {fmt.date(period.end)}
          {previous_period
            ? ` · comparado com ${fmt.date(previous_period.start)} a ${fmt.date(previous_period.end)}`
            : " · sem período anterior no dataset para comparar"}
        </p>
        {meta && (
          <p className="text-[0.8rem] text-muted">
            SLA: food ≤ {meta.sla_food_min} min · goods ≤ {meta.sla_good_min} min
          </p>
        )}
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {OPERATION.map((def) => (
          <Card key={def.key} def={def} current={current} previous={previous} hero />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {VOLUME.map((def) => (
          <Card key={def.key} def={def} current={current} previous={previous} />
        ))}
      </div>
    </div>
  );
}

export default island(KpiStripInner, 236);
