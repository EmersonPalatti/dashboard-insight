import type { ReactNode } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { EASE_IN } from "../theme";

/**
 * Saída da cena nos últimos `frames` (6 = 200 ms) quando a próxima cena começa vazia,
 * para o corte não sair de um quadro cheio direto para o fundo.
 */
export const FadeOut = ({
  children,
  duration,
  frames = 6,
}: {
  readonly children: ReactNode;
  readonly duration: number;
  readonly frames?: number;
}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        opacity: interpolate(frame, [duration - frames, duration - 1], [1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: EASE_IN,
        }),
      }}
    >
      {children}
    </AbsoluteFill>
  );
};
