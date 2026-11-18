import type { CSSProperties, ReactNode } from "react";
import { useCurrentFrame } from "remotion";
import { between, enter } from "../anim";
import { CAPTION_ZONE, H, SANS, SIDE, TITLE_ZONE, useTokens, W } from "../theme";

/**
 * Título da cena na zona y 96–330 (no máximo 2 linhas, ≥ 64 px).
 * `from`/`to` em frames locais da cena; sem `to`, fica até o fim da cena.
 * Para trocar de frase na mesma zona, use dois <SceneTitle> com janelas encadeadas.
 */
export const SceneTitle = ({
  children,
  from = 0,
  to,
  size = 64,
  color,
  align = "left",
  style,
}: {
  readonly children: ReactNode;
  readonly from?: number;
  readonly to?: number;
  readonly size?: number;
  readonly color?: string;
  readonly align?: "left" | "center";
  readonly style?: CSSProperties;
}) => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const anim = to === undefined ? enter(frame, from, { dist: 12 }) : between(frame, from, to, { enter: { dist: 12 } });
  return (
    <div
      style={{
        position: "absolute",
        left: SIDE,
        width: W - SIDE * 2,
        top: TITLE_ZONE.top,
        height: TITLE_ZONE.bottom - TITLE_ZONE.top,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: align === "center" ? "center" : "flex-start",
        textAlign: align,
        fontFamily: SANS,
        fontWeight: 700,
        fontSize: size,
        lineHeight: 1.1,
        letterSpacing: "-0.01em",
        color: color ?? t.ink,
        textWrap: "balance",
        ...anim,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

/** Legenda de apoio na zona y 1160–1230 (≥ 28 px; 32–36 px no roteiro). */
export const Caption = ({
  children,
  from = 0,
  to,
  size = 32,
  color,
  align = "left",
  style,
}: {
  readonly children: ReactNode;
  readonly from?: number;
  readonly to?: number;
  readonly size?: number;
  readonly color?: string;
  readonly align?: "left" | "center";
  readonly style?: CSSProperties;
}) => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const anim = to === undefined ? enter(frame, from, { dist: 8 }) : between(frame, from, to, { enter: { dist: 8 } });
  return (
    <div
      style={{
        position: "absolute",
        left: SIDE,
        width: W - SIDE * 2,
        // Ancorada na base da zona (y 1230): legenda de 2 linhas cresce para cima, nunca invade os 120 px livres.
        bottom: H - CAPTION_ZONE.bottom,
        minHeight: CAPTION_ZONE.bottom - CAPTION_ZONE.top,
        display: "flex",
        alignItems: "center",
        justifyContent: align === "center" ? "center" : "flex-start",
        textAlign: align,
        fontFamily: SANS,
        fontWeight: 500,
        fontSize: size,
        lineHeight: 1.2,
        color: color ?? t.muted,
        ...anim,
        ...style,
      }}
    >
      {children}
    </div>
  );
};
