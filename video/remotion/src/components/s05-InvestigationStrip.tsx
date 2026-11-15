import type { CSSProperties } from "react";
import { COMANDA_01 } from "../data";
import { CONTENT_W, SANS, SIDE, STAGE, useTokens } from "../theme";
import { Button } from "./Button";
import { SeverityMark } from "./SeverityMark";

export const STRIP_TOP = STAGE.top; // 350
export const STRIP_HEIGHT = 88;
export const STRIP_BTN_W = 352;
export const STRIP_PAD_X = 24;

/** Centro exato do botão primário "Ver só Color Shopping" na tira do topo (coordenadas do quadro). */
export const STRIP_PRIMARY_CENTER = {
  x: SIDE + CONTENT_W - STRIP_PAD_X - STRIP_BTN_W / 2, // 72 + 936 - 24 - 176 = 808
  y: STRIP_TOP + STRIP_HEIGHT / 2, // 350 + 44 = 394
};

/**
 * Tira compacta no topo do palco após clicar em "Ver no gráfico":
 * mantém o marcador ●, "Investigação · Comanda Nº 01" e o botão primário à direita
 * para a costura entre as cenas 5 e 6.
 */
export const InvestigationStrip = ({
  pressPrimaryAt,
  style,
}: {
  readonly pressPrimaryAt?: number;
  readonly style?: CSSProperties;
}) => {
  const t = useTokens();
  return (
    <div
      style={{
        position: "absolute",
        left: SIDE,
        top: STRIP_TOP,
        width: CONTENT_W,
        height: STRIP_HEIGHT,
        padding: `0 ${STRIP_PAD_X}px`,
        boxSizing: "border-box",
        background: t.surface,
        border: `1px solid ${t.rule}`,
        borderRadius: 8,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
        ...style,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14, minWidth: 0 }}>
        <SeverityMark severity="high" scale={1.8} />
        <span
          style={{
            fontFamily: SANS,
            fontWeight: 500,
            fontSize: 28,
            color: t.muted,
            whiteSpace: "nowrap",
            lineHeight: 1.1,
          }}
        >
          Investigação · Comanda Nº 01
        </span>
      </div>
      <Button
        variant="primary"
        pressAt={pressPrimaryAt}
        fontSize={26}
        style={{
          width: STRIP_BTN_W,
          height: 58,
          padding: "0 20px",
          flexShrink: 0,
        }}
      >
        {COMANDA_01.buttons.primary}
      </Button>
    </div>
  );
};
