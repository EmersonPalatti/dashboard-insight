import type { CSSProperties } from "react";
import { NUM } from "../../theme";

/**
 * "86,1% → 84,9%" em Zilla Slab. A seta (U+2192) não está nos subconjuntos da fonte; o glifo de
 * reserva faz o Chrome perder os algarismos alinhados no trecho inteiro. A seta vira SVG.
 */
export const FromTo = ({
  value,
  style,
  arrowColor,
}: {
  /** Texto no formato "antes → depois". Sem seta, sai como está. */
  readonly value: string;
  readonly style?: CSSProperties;
  readonly arrowColor?: string;
}) => {
  const [from, to] = value.split(" → ");
  if (to === undefined) return <span style={{ ...NUM, ...style }}>{value}</span>;
  return (
    <span style={{ display: "inline-flex", alignItems: "baseline", gap: "0.28em", whiteSpace: "nowrap", ...NUM, ...style }}>
      <span>{from}</span>
      <svg width="0.95em" height="0.5em" viewBox="0 0 38 20" style={{ alignSelf: "center", overflow: "visible" }}>
        <path
          d="M 1 10 H 34 M 26 3 L 35 10 L 26 17"
          fill="none"
          stroke={arrowColor ?? "currentColor"}
          strokeWidth={2.6}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span>{to}</span>
    </span>
  );
};
