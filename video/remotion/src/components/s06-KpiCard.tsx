import type { CSSProperties } from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { enter, progress } from "../anim";
import type { KPIS } from "../data";
import { CONTENT_W, FAST, NUM, SANS, SLAB, useTokens } from "../theme";
import { RollingDigits } from "./s06-RollingDigits";
import { SeverityMark } from "./SeverityMark";

type KpiItem = (typeof KPIS)[number];

// Curvas determinísticas (7 pontos) por KPI: [antes (rede), depois (Color Shopping)].
// Baseline "rede" fica em y = 74 no SVG de altura 144.
const BASELINE_Y = 74;
const SPARK_W = 264;
const SPARK_H = 144;
const SPARK_X = [8, 50, 92, 134, 176, 218, 256] as const;

const SPARK_SERIES: Record<string, { before: readonly number[]; after: readonly number[] }> = {
  "No prazo (SLA)": {
    before: [76, 72, 75, 71, 74, 73, 72],
    after: [92, 98, 108, 102, 114, 110, 116], // cai abaixo da rede (80,0% vs 86,2%)
  },
  "Ciclo mediano": {
    before: [75, 73, 76, 72, 74, 73, 75],
    after: [54, 48, 42, 46, 38, 40, 34], // sobe acima da rede (44,3 vs 41,2 min)
  },
  Cancelamento: {
    before: [72, 75, 73, 76, 74, 75, 73],
    after: [88, 94, 90, 98, 96, 102, 100], // abaixo da rede (3,4% vs 4,6%)
  },
};

const smoothPath = (pts: readonly { x: number; y: number }[]) => {
  if (pts.length === 0) return "";
  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i];
    const p1 = pts[i + 1];
    const mx = (p0.x + p1.x) / 2;
    d += ` C ${mx} ${p0.y}, ${mx} ${p1.y}, ${p1.x} ${p1.y}`;
  }
  return d;
};

/**
 * Cartão de KPI da cena 6: rótulo 28 px, valor Zilla Slab 96 px com RollingDigits,
 * veredito + referência e minigráfico em `series` com linha tracejada "rede".
 */
export const KpiCard = ({
  kpi,
  rollAt,
  style,
}: {
  readonly kpi: KpiItem;
  readonly rollAt: number;
  readonly style?: CSSProperties;
}) => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const rollP = progress(frame, rollAt, FAST);
  const verdictAnim = enter(frame, rollAt + 2, { dist: 6, dur: FAST });

  const series = SPARK_SERIES[kpi.label] ?? SPARK_SERIES["No prazo (SLA)"];
  const pts = SPARK_X.map((x, idx) => ({
    x,
    y: interpolate(rollP, [0, 1], [series.before[idx], series.after[idx]]),
  }));
  const linePath = smoothPath(pts);
  const areaPath = `${linePath} L ${pts[pts.length - 1].x} ${SPARK_H - 6} L ${pts[0].x} ${SPARK_H - 6} Z`;
  const last = pts[pts.length - 1];

  return (
    <div
      style={{
        width: CONTENT_W,
        height: 224,
        background: t.surface,
        border: `1px solid ${t.rule}`,
        borderRadius: 8,
        padding: "22px 32px",
        boxSizing: "border-box",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 24,
        fontFamily: SANS,
        color: t.ink,
        ...style,
      }}
    >
      {/* Coluna esquerda: rótulo, número Zilla Slab 96 px, veredito + referência */}
      <div style={{ display: "flex", flexDirection: "column", minWidth: 0, flex: 1 }}>
        <div
          style={{
            fontSize: 28,
            fontWeight: 600,
            color: t.muted,
            lineHeight: 1.15,
            marginBottom: 8,
          }}
        >
          {kpi.label}
        </div>

        <RollingDigits
          from={kpi.before}
          to={kpi.after}
          at={rollAt}
          style={{
            fontFamily: SLAB,
            fontWeight: 700,
            fontSize: 96,
            lineHeight: 0.98,
            color: t.ink,
            ...NUM,
          }}
        />

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginTop: 12,
            minHeight: 34,
            whiteSpace: "nowrap",
            ...verdictAnim,
          }}
        >
          {kpi.severity === "high" ? (
            <>
              <SeverityMark severity="high" scale={1.7} />
              <span style={{ fontSize: 28, fontWeight: 700, color: t.crit }}>{kpi.verdict}</span>
              <span style={{ fontSize: 28, color: t.muted }}>·</span>
            </>
          ) : null}
          {kpi.severity === "good" ? (
            <>
              <SeverityMark severity="low" tone="good" scale={1.7} />
              <span style={{ fontSize: 28, fontWeight: 700, color: t.good }}>{kpi.verdict}</span>
              <span style={{ fontSize: 28, color: t.muted }}>·</span>
            </>
          ) : null}
          <span style={{ fontSize: 28, fontWeight: 500, color: t.muted }}>{kpi.ref}</span>
        </div>
      </div>

      {/* Coluna direita: minigráfico diário em `series` com linha tracejada "rede" */}
      <div
        style={{
          position: "relative",
          width: SPARK_W,
          height: SPARK_H,
          flexShrink: 0,
        }}
      >
        <span
          style={{
            position: "absolute",
            right: 4,
            top: kpi.label === "Ciclo mediano" ? BASELINE_Y + 8 : BASELINE_Y - 32,
            fontSize: 28,
            fontWeight: 500,
            color: t.muted,
            lineHeight: 1,
            pointerEvents: "none",
          }}
        >
          rede
        </span>
        <svg width={SPARK_W} height={SPARK_H} viewBox={`0 0 ${SPARK_W} ${SPARK_H}`}>
          <line
            x1={4}
            y1={BASELINE_Y}
            x2={SPARK_W - 4}
            y2={BASELINE_Y}
            stroke={t.muted}
            strokeWidth={2}
            strokeDasharray="6 5"
            opacity={0.75}
          />
          <path d={areaPath} fill={t.series} fillOpacity={0.1} />
          <path
            d={linePath}
            fill="none"
            stroke={t.series}
            strokeWidth={4}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx={last.x} cy={last.y} r={5.5} fill={t.series} />
        </svg>
      </div>
    </div>
  );
};
