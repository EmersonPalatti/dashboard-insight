import { AbsoluteFill, interpolate, interpolateColors, useCurrentFrame } from "remotion";
import { enter, progress } from "../../anim";
import { Caption, SceneTitle } from "../../components/Text";
import type { SceneSfx } from "../../sfx";
import { br, CONTENT_W, EASE_BOUNCE, EASE_OUT, FAST, ms, NUM, SANS, SIDE, SLAB, useTokens } from "../../theme";
import { EVALS } from "../data";

/** Frames locais da cena 7 (0:43–0:51, 0–240). */
export const A07 = {
  titleAt: 4,
  captionAt: 30,
  boardAt: 10,
  countAt: 14,
  countDur: ms(800),
  chipAt: 40,
  chipStep: 3,
  duelAt: 80,
  slotAt: 86,
  slotStep: 3,
  winnerAt: 104,
  statsAt: 114,
  othersAt: 128,
  sealAt: 160,
} as const;

export const sfx: SceneSfx[] = [
  { frame: A07.winnerAt, kind: "tick" },
  { frame: A07.sealAt, kind: "clique" },
];

const Check = ({ color, size, scale = 1 }: { readonly color: string; readonly size: number; readonly scale?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, scale }}>
    <circle cx="12" cy="12" r="10" />
    <path d="m7.5 12.5 3 3 6-6.5" />
  </svg>
);

const BigCount = ({ n, label, at }: { readonly n: number; readonly label: string; readonly at: number }) => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const value = Math.round(n * progress(frame, at, A07.countDur, EASE_OUT));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, ...enter(frame, at, { dist: 10 }) }}>
      <span style={{ fontFamily: SLAB, fontWeight: 700, fontSize: 120, lineHeight: 1, color: t.series, ...NUM }}>{br(value)}</span>
      <span style={{ fontFamily: SANS, fontSize: 32, fontWeight: 500, color: t.ink }}>{label}</span>
    </div>
  );
};

/** Cena 7: o placar do agente. 45 perguntas com gabarito tirado dos dados e o confronto de modelos. */
export const A07Evals = () => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const win = progress(frame, A07.winnerAt, FAST);

  return (
    <AbsoluteFill style={{ background: t.field }}>
      <SceneTitle from={A07.titleAt}>Mudou o agente? Roda o placar.</SceneTitle>

      {/* Tamanho do placar */}
      <div
        style={{
          position: "absolute",
          left: SIDE,
          top: 356,
          width: CONTENT_W,
          boxSizing: "border-box",
          background: t.surface,
          border: `1.5px solid ${t.rule}`,
          borderRadius: 8,
          padding: "24px 28px 26px",
          fontFamily: SANS,
          ...enter(frame, A07.boardAt, { dist: 12 }),
        }}
      >
        <div style={{ display: "flex", gap: 90 }}>
          <BigCount n={EVALS.cases.n} label={EVALS.cases.label} at={A07.countAt} />
          <BigCount n={EVALS.categories.n} label={EVALS.categories.label} at={A07.countAt + 4} />
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 22 }}>
          {EVALS.chips.map((chip, i) => (
            <span
              key={chip}
              style={{
                height: 50,
                display: "inline-flex",
                alignItems: "center",
                padding: "0 16px",
                borderRadius: 4,
                background: t.sunken,
                border: `1px solid ${t.rule}`,
                fontSize: 28,
                fontWeight: 500,
                color: t.ink,
                ...enter(frame, A07.chipAt + i * A07.chipStep, { dur: FAST, dist: 6 }),
              }}
            >
              {chip}
            </span>
          ))}
        </div>
      </div>

      {/* Confronto de modelos gratuitos */}
      <div
        style={{
          position: "absolute",
          left: SIDE,
          top: 726,
          width: CONTENT_W,
          boxSizing: "border-box",
          background: t.surface,
          border: `1.5px solid ${t.rule}`,
          borderRadius: 8,
          padding: "22px 28px 24px",
          fontFamily: SANS,
          ...enter(frame, A07.duelAt, { dist: 12 }),
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontSize: 30, color: t.muted }}>{EVALS.duel.title}</span>
          <span style={{ display: "inline-flex", gap: 10 }}>
            {[0, 1, 2, 3, 4].map((i) => {
              const fill = i === 0 ? win : 0;
              return (
                <span
                  key={i}
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 4,
                    boxSizing: "border-box",
                    border: `2.5px solid ${i === 0 ? interpolateColors(win, [0, 1], [t.rule, t.series]) : t.rule}`,
                    background: interpolateColors(fill, [0, 1], [t.surface, t.series]),
                    ...enter(frame, A07.slotAt + i * A07.slotStep, { dur: FAST, dist: 6 }),
                  }}
                />
              );
            })}
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 18, ...enter(frame, A07.winnerAt, { dist: 8 }) }}>
          <Check color={t.good} size={40} scale={interpolate(progress(frame, A07.winnerAt, ms(300), EASE_BOUNCE), [0, 1], [0.5, 1])} />
          <span style={{ fontSize: 40, fontWeight: 700, color: t.ink }}>{EVALS.duel.winner}</span>
          <span
            style={{
              height: 44,
              display: "inline-flex",
              alignItems: "center",
              padding: "0 14px",
              borderRadius: 4,
              border: `2px solid ${t.series}`,
              fontSize: 28,
              fontWeight: 700,
              color: t.series,
            }}
          >
            {EVALS.duel.tag}
          </span>
        </div>
        <div style={{ fontSize: 34, fontWeight: 500, color: t.ink, marginTop: 12, ...NUM, ...enter(frame, A07.statsAt, { dist: 8 }) }}>{EVALS.duel.stats}</div>
        <div style={{ fontSize: 30, color: t.muted, marginTop: 10, ...enter(frame, A07.othersAt, { dist: 6 }) }}>{EVALS.duel.others}</div>
      </div>

      {/* Piso travado no CI */}
      <div
        style={{
          position: "absolute",
          left: SIDE,
          top: 1046,
          display: "flex",
          alignItems: "center",
          gap: 16,
          fontFamily: SANS,
          fontSize: 36,
          fontWeight: 700,
          color: t.good,
          ...enter(frame, A07.sealAt, { dist: 8 }),
        }}
      >
        <Check color={t.good} size={40} scale={interpolate(progress(frame, A07.sealAt, ms(300), EASE_BOUNCE), [0, 1], [0.5, 1])} />
        <span style={NUM}>{EVALS.seal}</span>
      </div>

      <Caption from={A07.captionAt} size={36}>
        {EVALS.caption}
      </Caption>
    </AbsoluteFill>
  );
};
