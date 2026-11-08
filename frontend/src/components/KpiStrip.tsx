import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { Fragment, useState, type CSSProperties } from "react";
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
  // A explicação "sem período anterior" fica uma vez, na linha do recorte; aqui só um traço mudo.
  if (a === null || b === null || b === undefined || (def.kind === "value" && b === 0)) {
    return (
      <span className="text-[0.8rem] text-muted" aria-hidden title="Sem período anterior para comparar">
        —
      </span>
    );
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
      className={`inline-flex items-center gap-0.5 text-[0.82rem] font-semibold ${
        good === null ? "text-muted" : good ? "text-good" : "text-crit"
      }`}
      title="Contra o período anterior de mesmo tamanho"
    >
      <Icon className="size-3.5" aria-hidden />
      {flat ? "estável" : text}
      <span className="sr-only">{good === null ? "" : good ? "(melhorou)" : "(piorou)"}</span>
    </span>
  );
}

type SeriesKey = "sla_rate" | "cycle_p50" | "cancel_rate";

/** Histórico diário do próprio recorte (mesma consulta da Tendência, já em cache). */
function Trail({ values, label }: { values: (number | null)[]; label: string }) {
  const pts = values.map((v, i) => [i, v] as const).filter((p): p is readonly [number, number] => p[1] !== null);
  if (pts.length < 2) return <div className="h-7" aria-hidden />;
  const ys = pts.map((p) => p[1]);
  const lo = Math.min(...ys);
  const hi = Math.max(...ys);
  const w = 100;
  const h = 28;
  const n = values.length - 1 || 1;
  const d = pts
    .map(([i, v], k) => `${k ? "L" : "M"}${((i / n) * w).toFixed(2)},${(h - 3 - ((v - lo) / (hi - lo || 1)) * (h - 6)).toFixed(2)}`)
    .join("");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="mt-2 block h-7 w-full" role="img" aria-label={label}>
      <path d={d} fill="none" stroke="var(--ink)" strokeWidth="1.6" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
    </svg>
  );
}

interface FigureState {
  value: number | null | undefined;
  text: string;
  /** Texto anterior: os dígitos que mudaram saem dele. Null na primeira renderização (sem animação). */
  prev: string | null;
  dir: 1 | -1;
  /** Muda a cada troca de texto: a chave remonta os dígitos e a animação roda de novo. */
  run: number;
}

/** Dígitos iguais ficam parados; os que mudaram trocam no lugar. Tamanho diferente: o texto inteiro sobe. */
function Digits({ prev, next }: { prev: string; next: string }) {
  if (prev === next) return <>{next}</>;
  const from = Array.from(prev);
  const to = Array.from(next);
  if (from.length !== to.length) return <span className="digit-rise inline-block">{next}</span>;
  return (
    <>
      {to.map((ch, i) =>
        ch === from[i] ? (
          <Fragment key={i}>{ch}</Fragment>
        ) : (
          <span key={i} className="relative inline-block">
            <span className="digit-fall absolute inset-0 text-center">{from[i]}</span>
            <span className="digit-rise inline-block">{ch}</span>
          </span>
        ),
      )}
    </>
  );
}

/**
 * Valor do KPI que muda no lugar quando o recorte muda. Sobe se o número aumentou, desce se caiu.
 * A primeira renderização não anima. O leitor de tela lê o texto completo uma vez (sr-only);
 * a parte animada é aria-hidden, então não há fragmentos de dígito.
 */
function KpiFigure({ value, format, className }: { value: number | null | undefined; format: KpiDef["format"]; className: string }) {
  const [state, setState] = useState<FigureState>(() => ({ value, text: format(value), prev: null, dir: 1, run: 0 }));
  let view = state;
  if (value !== state.value) {
    const text = format(value);
    const dir = value == null || state.value == null || value >= state.value ? 1 : -1;
    view = text === state.text ? { ...state, value } : { value, text, prev: state.text, dir, run: state.run + 1 };
    setState(view);
  }
  const { text, prev, dir, run } = view;
  return (
    <span className={className}>
      <span aria-hidden="true" style={{ "--digit-dir": dir } as CSSProperties}>
        {prev === null ? text : <Digits key={run} prev={prev} next={text} />}
      </span>
      <span className="sr-only">{text}</span>
    </span>
  );
}

function Hero({ def, current, previous, trail }: { def: KpiDef; current: Metrics; previous?: Metrics | null; trail?: (number | null)[] }) {
  return (
    <div className="min-w-0 bg-surface px-4 pt-3.5 pb-3">
      <p className="cond text-[0.78rem] font-bold text-muted">{def.label}</p>
      <KpiFigure className="figure mt-1.5 block text-[2.6rem]" value={current[def.key] as number | null} format={def.format} />
      <div className="mt-1">
        <Delta def={def} current={current} previous={previous} />
      </div>
      {trail && <Trail values={trail} label={`${def.label} por dia no recorte`} />}
      {def.sub && <p className="mt-1.5 truncate text-[0.8rem] text-muted">{def.sub(current)}</p>}
    </div>
  );
}

function Volume({ def, current, previous }: { def: KpiDef; current: Metrics; previous?: Metrics | null }) {
  return (
    <div className="min-w-0 px-4 py-3">
      <p className="flex flex-wrap items-baseline gap-x-2">
        <span className="text-[0.88rem] text-muted">{def.label}</span>
        <KpiFigure className="figure text-[1.45rem]" value={current[def.key] as number | null} format={def.format} />
        <Delta def={def} current={current} previous={previous} />
      </p>
      {def.sub && <p className="mt-0.5 truncate text-[0.8rem] text-muted">{def.sub(current)}</p>}
    </div>
  );
}

function KpiSkeleton() {
  return (
    <div className="grid gap-2.5">
      <div className="skeleton h-[188px]" />
      <div className="skeleton h-[72px]" />
    </div>
  );
}

function KpiStripInner() {
  const { data, error, isPending, refetch, isPlaceholderData } = useRecorteQuery("/api/kpis");
  const { data: series } = useRecorteQuery("/api/timeseries", { grain: "day" });
  const { data: meta } = useMeta();
  if (isPending) return <KpiSkeleton />;
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  const { current, previous, period, previous_period } = data;

  if (current.orders === 0) {
    return (
      <div className="tile p-4">
        <p className="font-semibold">Nenhum pedido neste recorte.</p>
        <p className="label">Afrouxe período, hub ou loja. Os painéis abaixo ficam vazios até lá.</p>
      </div>
    );
  }

  const trail = (k: SeriesKey) => (series && series.length > 1 ? series.map((p) => p[k]) : undefined);
  // Resumo para leitor de tela: só os três KPIs de operação, com os mesmos formatadores dos cartões.
  const summary = `Recorte atualizado: SLA ${fmt.pct(current.sla_rate)}, ciclo mediano ${fmt.min(current.cycle_p50)}, cancelamento ${fmt.pct(current.cancel_rate)}.`;

  return (
    <div className={`content-reveal grid gap-2.5 transition-opacity ${isPlaceholderData ? "opacity-60" : ""}`}>
      {/* Vazio durante o dim: o recorte antigo não é anunciado como se fosse o novo. */}
      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {isPlaceholderData ? "" : summary}
      </p>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 px-0.5">
        <p className="text-[0.88rem] text-muted">
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
      <div className="grid grid-cols-1 gap-px overflow-hidden rounded-card border border-rule bg-rule sm:grid-cols-3">
        {OPERATION.map((def) => (
          <Hero key={def.key} def={def} current={current} previous={previous} trail={trail(def.key as SeriesKey)} />
        ))}
      </div>
      <div className="tile grid grid-cols-1 divide-y divide-rule sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        {VOLUME.map((def) => (
          <Volume key={def.key} def={def} current={current} previous={previous} />
        ))}
      </div>
    </div>
  );
}

export default island(KpiStripInner, 300);
