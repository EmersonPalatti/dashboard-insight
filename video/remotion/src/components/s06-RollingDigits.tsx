import type { CSSProperties } from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { progress } from "../anim";
import { FAST, NUM } from "../theme";

const parseNumeric = (raw: string): number => {
  const match = raw.match(/-?\d+(?:[.,]\d+)?/);
  return match ? parseFloat(match[0].replace(",", ".")) : 0;
};

/**
 * Compara `from` e `to` caractere a caractere.
 * Apenas os caracteres que mudam deslizam 4 px na direção da variação (250 ms);
 * dígitos e símbolos idênticos permanecem imóveis.
 */
export const RollingDigits = ({
  from,
  to,
  at,
  style,
}: {
  readonly from: string;
  readonly to: string;
  readonly at: number;
  readonly style?: CSSProperties;
}) => {
  const frame = useCurrentFrame();
  const p = progress(frame, at, FAST);
  const dir = parseNumeric(to) >= parseNumeric(from) ? 1 : -1;
  const len = Math.max(from.length, to.length);

  return (
    <span style={{ display: "inline-flex", alignItems: "baseline", ...NUM, ...style }}>
      {Array.from({ length: len }, (_, i) => {
        const a = from[i] ?? "";
        const b = to[i] ?? "";
        if (a === b) {
          return (
            <span key={i} style={{ whiteSpace: "pre" }}>
              {b}
            </span>
          );
        }
        const outY = -dir * 4 * p;
        const inY = dir * 4 * (1 - p);
        return (
          <span
            key={i}
            style={{
              position: "relative",
              display: "inline-block",
              whiteSpace: "pre",
            }}
          >
            {/* Reserva exatamente a largura tabular do dígito sem mover nada */}
            <span style={{ opacity: 0 }} aria-hidden>
              {b || a}
            </span>
            <span
              style={{
                position: "absolute",
                left: 0,
                top: 0,
                opacity: interpolate(p, [0, 1], [1, 0]),
                translate: `0px ${outY}px`,
              }}
            >
              {a}
            </span>
            <span
              style={{
                position: "absolute",
                left: 0,
                top: 0,
                opacity: p,
                translate: `0px ${inY}px`,
              }}
            >
              {b}
            </span>
          </span>
        );
      })}
    </span>
  );
};
