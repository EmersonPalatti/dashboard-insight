import type { CSSProperties } from "react";
import { useTokens } from "../theme";

export type Severity = "high" | "medium" | "low";

/**
 * Severidade também pela forma: ● cheio = crítico, ○ vazado = atenção, — traço = observar.
 * Medidas do app (12 px, aro 2,5 px, traço 3 × 12) escaladas 2,5× para o vídeo.
 * `tone="good"` desenha o traço em verde (veredito "Dentro" dos KPIs).
 */
export const SeverityMark = ({
  severity,
  scale = 2.5,
  tone,
  style,
}: {
  readonly severity: Severity;
  readonly scale?: number;
  readonly tone?: "good";
  readonly style?: CSSProperties;
}) => {
  const t = useTokens();
  const size = 12 * scale;
  if (severity === "low") {
    return (
      <span
        style={{
          display: "inline-block",
          width: size,
          height: 3 * scale,
          borderRadius: 1.5 * scale,
          background: tone === "good" ? t.good : t.muted,
          flexShrink: 0,
          ...style,
        }}
      />
    );
  }
  return (
    <span
      style={{
        display: "inline-block",
        width: size,
        height: size,
        borderRadius: "50%",
        boxSizing: "border-box",
        background: severity === "high" ? t.crit : "transparent",
        border: severity === "medium" ? `${2.5 * scale}px solid ${t.warn}` : undefined,
        flexShrink: 0,
        ...style,
      }}
    />
  );
};

export const SEVERITY_WORD: Record<Severity, string> = {
  high: "CRÍTICO",
  medium: "ATENÇÃO",
  low: "OBSERVAR",
};
