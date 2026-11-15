import type { CSSProperties } from "react";
import { useCurrentFrame } from "remotion";
import { enter, progress } from "../anim";
import { EASE_OUT, ms, SANS, useTokens } from "../theme";

export type FlowIconKind = "clock" | "api" | "route" | "send";

const FlowIcon = ({ kind, color }: { readonly kind: FlowIconKind; readonly color: string }) => {
  const common = {
    width: 36,
    height: 36,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: color,
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };

  switch (kind) {
    case "clock":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 2" />
        </svg>
      );
    case "api":
      return (
        <svg {...common}>
          <path d="M8 5c-2 0-3 1-3 3v2c0 1.2-.8 2-2 2 1.2 0 2 .8 2 2v2c0 2 1 3 3 3" />
          <path d="M16 5c2 0 3 1 3 3v2c0 1.2.8 2 2 2-1.2 0-2 .8-2 2v2c0 2-1 3-3 3" />
          <circle cx="12" cy="12" r="1.2" fill={color} />
        </svg>
      );
    case "route":
      return (
        <svg {...common}>
          <circle cx="5" cy="12" r="2.2" />
          <circle cx="19" cy="6.5" r="2.2" />
          <circle cx="19" cy="17.5" r="2.2" />
          <path d="M7.2 12H11c1.5 0 2-1 2.5-2.5S14.5 6.5 16.8 6.5" />
          <path d="M7.2 12H11c1.5 0 2 1 2.5 2.5s1 3 3.3 3" />
        </svg>
      );
    case "send":
      return (
        <svg {...common}>
          <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v10a1.5 1.5 0 0 1-1.5 1.5H9l-5 3.5v-15Z" />
          <path d="M8.5 9.5h7" />
          <path d="M8.5 13h4.5" />
        </svg>
      );
  }
};

/** Nó do fluxo de automação (superfície `surface`, cantos 8 px, ícone SVG simples, texto ≥ 28 px). */
export const FlowNode = ({
  label,
  icon,
  width,
  height = 176,
  enterAt = 0,
  style,
}: {
  readonly label: string;
  readonly icon: FlowIconKind;
  readonly width: number;
  readonly height?: number;
  readonly enterAt?: number;
  readonly style?: CSSProperties;
}) => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const anim = enter(frame, enterAt, { dur: ms(280), dist: 10 });

  return (
    <div
      style={{
        width,
        height,
        boxSizing: "border-box",
        background: t.surface,
        border: `1px solid ${t.rule}`,
        borderRadius: 8,
        padding: "20px 14px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 14,
        textAlign: "center",
        ...anim,
        ...style,
      }}
    >
      <div
        style={{
          width: 56,
          height: 56,
          borderRadius: 8,
          background: t.sunken,
          border: `1px solid ${t.rule}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <FlowIcon kind={icon} color={t.series} />
      </div>
      <div
        style={{
          fontFamily: SANS,
          fontWeight: 600,
          fontSize: 28,
          lineHeight: 1.15,
          color: t.ink,
          textWrap: "balance",
        }}
      >
        {label}
      </div>
    </div>
  );
};

/** Linha horizontal com seta desenhando da esquerda para a direita. */
export const FlowConnector = ({
  width,
  from,
  dur = ms(220),
}: {
  readonly width: number;
  readonly from: number;
  readonly dur?: number;
}) => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const p = progress(frame, from, dur, EASE_OUT);
  const lineEnd = width - 8;
  const currentX = 4 + p * (lineEnd - 4);
  const arrowOpacity = progress(frame, from + Math.max(1, dur - 3), 3, EASE_OUT);

  return (
    <svg width={width} height={24} viewBox={`0 0 ${width} 24`} style={{ flexShrink: 0, overflow: "visible" }}>
      <circle cx={4} cy={12} r={3.5} fill={t.series} opacity={p > 0 ? 1 : 0} />
      <line
        x1={4}
        y1={12}
        x2={currentX}
        y2={12}
        stroke={t.series}
        strokeWidth={2.5}
        strokeLinecap="round"
        opacity={p > 0 ? 1 : 0}
      />
      <path
        d={`M ${lineEnd - 6} 7 L ${lineEnd} 12 L ${lineEnd - 6} 17`}
        fill="none"
        stroke={t.series}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={arrowOpacity}
      />
    </svg>
  );
};
