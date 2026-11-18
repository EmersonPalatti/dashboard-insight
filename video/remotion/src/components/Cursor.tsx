import { interpolate, useCurrentFrame } from "remotion";
import { EASE_OUT, ms, useTokens } from "../theme";

type Point = { x: number; y: number };

/**
 * Seta `ink` com borda branca. Anda de `from` até `to` entre `moveStart` e
 * `moveStart + moveDur` (frames locais) e clica em `clickAt`: anel que expande e
 * some em 250 ms. Coordenadas = ponta da seta, em px do quadro.
 */
export const Cursor = ({
  from,
  to,
  moveStart,
  moveDur = ms(500),
  clickAt,
  appearAt = moveStart - ms(200),
  hideAt,
}: {
  readonly from: Point;
  readonly to: Point;
  readonly moveStart: number;
  readonly moveDur?: number;
  readonly clickAt?: number;
  readonly appearAt?: number;
  readonly hideAt?: number;
}) => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
  const p = interpolate(frame, [moveStart, moveStart + moveDur], [0, 1], { ...clamp, easing: EASE_OUT });
  const x = from.x + (to.x - from.x) * p;
  const y = from.y + (to.y - from.y) * p;
  const opacity =
    interpolate(frame, [appearAt, appearAt + ms(150)], [0, 1], clamp) *
    (hideAt === undefined ? 1 : interpolate(frame, [hideAt, hideAt + ms(150)], [1, 0], clamp));
  const pressScale =
    clickAt === undefined
      ? 1
      : interpolate(frame, [clickAt, clickAt + ms(80), clickAt + ms(200)], [1, 0.88, 1], clamp);
  const ring = clickAt === undefined ? 0 : interpolate(frame, [clickAt, clickAt + ms(250)], [0, 1], clamp);
  const ringVisible = clickAt !== undefined && frame >= clickAt && ring < 1;

  return (
    <div style={{ position: "absolute", left: 0, top: 0, width: "100%", height: "100%", pointerEvents: "none", opacity }}>
      {ringVisible ? (
        <div
          style={{
            position: "absolute",
            left: x - 36,
            top: y - 36,
            width: 72,
            height: 72,
            borderRadius: "50%",
            border: `3px solid ${t.ink}`,
            boxSizing: "border-box",
            scale: 0.3 + ring * 0.9,
            opacity: 1 - ring,
          }}
        />
      ) : null}
      <svg
        width={44}
        height={54}
        viewBox="0 0 22 27"
        style={{ position: "absolute", left: x - 3, top: y - 2, scale: pressScale, transformOrigin: "3px 2px" }}
      >
        <path
          d="M2 1.5 L2 21.5 L7.2 16.8 L10.6 24.8 L14 23.3 L10.7 15.6 L17.6 15.6 Z"
          fill={t.ink}
          stroke="#FFFFFF"
          strokeWidth={1.6}
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
};
