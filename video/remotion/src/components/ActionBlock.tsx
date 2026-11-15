import type { CSSProperties, ReactNode } from "react";
import { SANS, useTokens } from "../theme";

/** Bloco "Ação": fundo `ink` e texto branco no claro; `#27131A` com borda `wine-raised` no escuro. */
export const ActionBlock = ({
  children,
  fontSize = 34,
  padding = 28,
  style,
}: {
  readonly children: ReactNode;
  readonly fontSize?: number;
  readonly padding?: number;
  readonly style?: CSSProperties;
}) => {
  const t = useTokens();
  return (
    <div
      style={{
        background: t.actionBg,
        border: `1.5px solid ${t.actionBorder}`,
        color: t.actionText,
        borderRadius: 8,
        padding,
        fontFamily: SANS,
        ...style,
      }}
    >
      <div style={{ fontWeight: 600, fontSize: Math.max(28, fontSize - 4), marginBottom: 10, lineHeight: 1.2, opacity: 0.75 }}>
        Ação
      </div>
      <div style={{ fontSize, lineHeight: 1.32, fontWeight: 400 }}>{children}</div>
    </div>
  );
};
