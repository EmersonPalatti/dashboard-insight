import type { CSSProperties, ReactNode } from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { ms, SANS, useTokens } from "../theme";

/**
 * Botão do app. `primary` = fundo `crit` (o único vermelho de ação); `ghost` = `surface` com fio `rule`.
 * `pressAt` (frame local) aplica a compressão de 0,97 do clique.
 */
export const Button = ({
  children,
  variant = "ghost",
  pressAt,
  fontSize = 28,
  style,
}: {
  readonly children: ReactNode;
  readonly variant?: "primary" | "ghost";
  readonly pressAt?: number;
  readonly fontSize?: number;
  readonly style?: CSSProperties;
}) => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const scale =
    pressAt === undefined
      ? 1
      : interpolate(frame, [pressAt, pressAt + ms(80), pressAt + ms(250)], [1, 0.97, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
  const primary = variant === "primary";
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        height: 68,
        padding: "0 26px",
        borderRadius: 8,
        boxSizing: "border-box",
        fontFamily: SANS,
        fontWeight: 600,
        fontSize,
        whiteSpace: "nowrap",
        background: primary ? t.crit : t.surface,
        color: primary ? "#FFFFFF" : t.ink,
        border: primary ? `1.5px solid ${t.crit}` : `1.5px solid ${t.rule}`,
        scale,
        ...style,
      }}
    >
      {children}
    </div>
  );
};
