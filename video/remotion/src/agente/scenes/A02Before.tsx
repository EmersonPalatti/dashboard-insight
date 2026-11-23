import { AbsoluteFill, interpolateColors, useCurrentFrame } from "remotion";
import { enter, progress } from "../../anim";
import { SeverityMark } from "../../components/SeverityMark";
import { Caption, SceneTitle } from "../../components/Text";
import { Stamp } from "../../components/Ticket";
import type { SceneSfx } from "../../sfx";
import { CONTENT_W, FAST, SANS, SIDE, useTokens } from "../../theme";
import { BEFORE } from "../data";

/** Frames locais da cena 2 (0:05–0:11, 0–180). */
export const A02 = {
  titleAt: 4,
  cardAt: 6,
  bubbleAt: 14,
  diagramAt: 22,
  walkAt: 40,
  walkStep: 14,
  painsAt: 64,
  painStep: 8,
  captionAt: 92,
} as const;

export const sfx: SceneSfx[] = BEFORE.walk.map((_, i) => ({ frame: A02.walkAt + i * A02.walkStep, kind: "tick" as const }));

// Geometria do diagrama (relativa à caixa de 880 × 310 dentro do cartão).
const DIAGRAM = { w: 880, h: 310, node: 150, tagX: 470, tagH: 64, tagGap: 18 };
const tagY = (i: number) => i * (DIAGRAM.tagH + DIAGRAM.tagGap);

/** Cena 2: o agente v1. Um LLM no centro passeando por 4 ferramentas, sem mapa nem placar. */
export const A02Before = () => {
  const t = useTokens();
  const frame = useCurrentFrame();

  const step = Math.floor((frame - A02.walkAt) / A02.walkStep);
  const active = frame >= A02.walkAt && step < BEFORE.walk.length ? BEFORE.walk[step] : -1;
  const stepP = progress(frame, A02.walkAt + Math.max(0, step) * A02.walkStep, FAST);
  const diagramP = progress(frame, A02.diagramAt, FAST);
  const nodeCy = DIAGRAM.node / 2 + 40;

  return (
    <AbsoluteFill style={{ background: t.field }}>
      <SceneTitle from={A02.titleAt}>Antes: um loop livre de ferramentas.</SceneTitle>

      <div
        style={{
          position: "absolute",
          left: SIDE,
          top: 360,
          width: CONTENT_W,
          background: t.surface,
          border: `1.5px solid ${t.rule}`,
          borderRadius: 8,
          padding: 28,
          boxSizing: "border-box",
          fontFamily: SANS,
          ...enter(frame, A02.cardAt, { dist: 12 }),
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
          <Stamp severity="low" label={BEFORE.stamp} color={t.muted} />
          <div
            style={{
              background: t.sunken,
              border: `1px solid ${t.rule}`,
              borderRadius: 8,
              padding: "14px 22px",
              fontSize: 32,
              fontWeight: 500,
              color: t.ink,
              ...enter(frame, A02.bubbleAt, { dist: 10 }),
            }}
          >
            {BEFORE.question}
          </div>
        </div>

        <div style={{ position: "relative", width: DIAGRAM.w, height: DIAGRAM.h, opacity: diagramP }}>
          {/* Fios do LLM até cada ferramenta */}
          <svg width={DIAGRAM.w} height={DIAGRAM.h} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
            {BEFORE.tools.map((tool, i) => {
              const y2 = tagY(i) + DIAGRAM.tagH / 2;
              const on = i === active;
              const d = `M ${DIAGRAM.node} ${nodeCy} C ${DIAGRAM.node + 160} ${nodeCy}, ${DIAGRAM.tagX - 160} ${y2}, ${DIAGRAM.tagX} ${y2}`;
              return (
                <path
                  key={tool}
                  d={d}
                  fill="none"
                  stroke={on ? t.series : t.rule}
                  strokeWidth={on ? 4 : 2}
                  strokeDasharray={on ? "12 10" : "6 8"}
                  strokeDashoffset={on ? -stepP * 44 : 0}
                />
              );
            })}
          </svg>

          {/* O modelo decide a rota sozinho */}
          <div style={{ position: "absolute", left: 0, top: 40, width: DIAGRAM.node, display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
            <div
              style={{
                width: DIAGRAM.node,
                height: DIAGRAM.node,
                borderRadius: 8,
                background: t.wine,
                color: t.onWine,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 44,
                fontWeight: 700,
              }}
            >
              {BEFORE.model}
            </div>
            <div style={{ fontSize: 28, color: t.muted, whiteSpace: "nowrap" }}>decide a rota</div>
          </div>

          {BEFORE.tools.map((tool, i) => {
            const on = i === active;
            const glow = on ? stepP : 0;
            return (
              <div
                key={tool}
                style={{
                  position: "absolute",
                  left: DIAGRAM.tagX,
                  top: tagY(i),
                  width: DIAGRAM.w - DIAGRAM.tagX,
                  height: DIAGRAM.tagH,
                  boxSizing: "border-box",
                  display: "flex",
                  alignItems: "center",
                  padding: "0 22px",
                  borderRadius: 4,
                  background: t.sunken,
                  border: `2px solid ${interpolateColors(glow, [0, 1], [t.rule, t.series])}`,
                  fontSize: 30,
                  fontWeight: 600,
                  color: interpolateColors(glow, [0, 1], [t.muted, t.ink]),
                  ...enter(frame, A02.diagramAt + i * 2, { dur: FAST, dist: 8, axis: "x" }),
                }}
              >
                {tool}
              </div>
            );
          })}
        </div>
      </div>

      {/* O que faltava */}
      <div style={{ position: "absolute", left: SIDE, top: 930, width: CONTENT_W, display: "flex", flexDirection: "column", gap: 14 }}>
        {BEFORE.pains.map((pain, i) => (
          <div
            key={pain}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 18,
              fontFamily: SANS,
              fontSize: 36,
              fontWeight: 500,
              color: t.ink,
              ...enter(frame, A02.painsAt + i * A02.painStep, { dist: 8 }),
            }}
          >
            <SeverityMark severity="low" scale={2.4} />
            {pain}
          </div>
        ))}
      </div>

      <Caption from={A02.captionAt} size={34}>
        O modelo escolhia a rota e a conta.
      </Caption>
    </AbsoluteFill>
  );
};
