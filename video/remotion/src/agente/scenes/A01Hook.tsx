import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { enter, progress } from "../../anim";
import { SeverityMark } from "../../components/SeverityMark";
import { SceneTitle } from "../../components/Text";
import type { SceneSfx } from "../../sfx";
import { CONTENT_W, EASE_IN, FAST, H, ms, SANS, SIDE, useTokens } from "../../theme";
import { HOOK } from "../data";

/** Frames locais da cena 1 (0:00–0:05, 0–150). */
export const A01 = {
  cardAt: 4,
  bubbleAt: 10,
  linesAt: 16,
  failAt: 34,
  failStep: 8,
  swapAt: 75,
  wipeAt: 116,
  wipeDur: ms(700),
} as const;

export const sfx: SceneSfx[] = [
  { frame: 0, kind: "tick" },
  ...HOOK.failures.map((_, i) => ({ frame: A01.failAt + i * A01.failStep, kind: "clique" as const })),
];

const LINES = [0.92, 0.78, 0.86, 0.54];

/** Cena 1: gancho. Resposta genérica de um agente v1, três falhas e a varredura vinho que limpa a tela. */
export const A01Hook = () => {
  const t = useTokens();
  const frame = useCurrentFrame();

  // Linha vinho varre de baixo para cima e leva tudo o que fica abaixo dela.
  const wipe = progress(frame, A01.wipeAt, A01.wipeDur, EASE_IN);
  const lineY = H - wipe * (H + 12);

  return (
    <AbsoluteFill style={{ background: t.field }}>
      <AbsoluteFill style={{ clipPath: `inset(0 0 ${wipe * 100}% 0)` }}>
        <SceneTitle from={2} to={A01.swapAt} size={68}>
          {HOOK.first}
        </SceneTitle>
        <SceneTitle from={A01.swapAt} size={68}>
          <span>
            <span style={{ color: t.crit }}>{HOOK.second.accent}</span>
            {HOOK.second.rest}
          </span>
        </SceneTitle>

        {/* Cartão de resposta do agente v1 */}
        <div
          style={{
            position: "absolute",
            left: SIDE,
            top: 380,
            width: CONTENT_W,
            background: t.surface,
            border: `1.5px solid ${t.rule}`,
            borderRadius: 8,
            padding: "26px 30px 30px",
            boxSizing: "border-box",
            fontFamily: SANS,
            ...enter(frame, A01.cardAt, { dist: 12 }),
          }}
        >
          <div style={{ fontSize: 28, fontWeight: 600, color: t.muted, marginBottom: 22 }}>{HOOK.header}</div>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 26 }}>
            <div
              style={{
                background: t.sunken,
                border: `1px solid ${t.rule}`,
                borderRadius: 8,
                padding: "16px 22px",
                fontSize: 32,
                fontWeight: 500,
                color: t.ink,
                ...enter(frame, A01.bubbleAt, { dist: 10 }),
              }}
            >
              {HOOK.question}
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {LINES.map((w, i) => (
              <div
                key={w}
                style={{
                  height: 22,
                  borderRadius: 4,
                  background: t.rule,
                  width: `${w * 100 * progress(frame, A01.linesAt + i * 3, FAST)}%`,
                }}
              />
            ))}
          </div>
        </div>

        {/* Três falhas que todo mundo que já plugou um LLM conhece */}
        <div
          style={{
            position: "absolute",
            left: SIDE,
            top: 812,
            width: CONTENT_W,
            display: "flex",
            flexDirection: "column",
            gap: 16,
          }}
        >
          {HOOK.failures.map((label, i) => (
            <div
              key={label}
              style={{
                alignSelf: "flex-start",
                display: "inline-flex",
                alignItems: "center",
                gap: 18,
                height: 76,
                padding: "0 26px",
                background: t.surface,
                border: `1.5px solid ${t.rule}`,
                borderRadius: 8,
                fontFamily: SANS,
                fontSize: 36,
                fontWeight: 600,
                color: t.ink,
                ...enter(frame, A01.failAt + i * A01.failStep, { dist: 10, axis: "x" }),
              }}
            >
              <SeverityMark severity="medium" scale={2.2} />
              {label}
            </div>
          ))}
        </div>
      </AbsoluteFill>

      {/* Linha vinho da varredura */}
      {wipe > 0 && wipe < 1 ? (
        <div
          style={{
            position: "absolute",
            left: 0,
            width: "100%",
            top: lineY,
            height: 12,
            background: t.wine,
            opacity: interpolate(wipe, [0, 0.9, 1], [1, 1, 0]),
          }}
        />
      ) : null}
    </AbsoluteFill>
  );
};
