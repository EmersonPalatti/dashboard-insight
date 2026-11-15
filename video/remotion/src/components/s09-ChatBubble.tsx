import type { CSSProperties } from "react";
import { useCurrentFrame } from "remotion";
import { enter } from "../anim";
import { FAST, NUM, SANS, useTokens } from "../theme";

/** Renderiza linha destacando "Ação:" em negrito conforme o roteiro. */
const renderLine = (text: string) => {
  const prefix = "Ação:";
  if (text.startsWith(prefix)) {
    return (
      <>
        <strong style={{ fontWeight: 700 }}>{prefix}</strong>
        {text.slice(prefix.length)}
      </>
    );
  }
  return text;
};

/** Balão genérico de notificação no celular (sem logo nem interface do Telegram). */
export const ChatBubble = ({
  heading,
  lines,
  enterAt,
  style,
}: {
  readonly heading: string;
  readonly lines: readonly string[];
  readonly enterAt: number;
  readonly style?: CSSProperties;
}) => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const anim = enter(frame, enterAt, { dur: FAST, dist: 12 });

  return (
    <div
      style={{
        background: t.surface,
        border: `1px solid ${t.rule}`,
        borderRadius: 8,
        padding: "16px 20px",
        fontFamily: SANS,
        color: t.ink,
        ...NUM,
        ...anim,
        ...style,
      }}
    >
      <div
        style={{
          fontWeight: 700,
          fontSize: 28,
          lineHeight: 1.26,
          marginBottom: 6,
        }}
      >
        {heading}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {lines.map((line, i) => (
          <div
            key={i}
            style={{
              fontWeight: 400,
              fontSize: 28,
              lineHeight: 1.32,
              color: t.ink,
              textWrap: "pretty",
            }}
          >
            {renderLine(line)}
          </div>
        ))}
      </div>
    </div>
  );
};
