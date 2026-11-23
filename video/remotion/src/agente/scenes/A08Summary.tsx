import { AbsoluteFill, interpolate, interpolateColors, useCurrentFrame } from "remotion";
import { enter, progress } from "../../anim";
import { SceneTitle } from "../../components/Text";
import type { SceneSfx } from "../../sfx";
import { CONTENT_W, DARK, EASE_OUT, LIGHT, ms, SANS, SIDE, SLAB, ThemeProvider, useTokens } from "../../theme";
import { FromTo } from "../components/FromTo";
import { SUMMARY } from "../data";

/** Frames locais da cena 8 (0:51–0:56, 0–150). */
export const A08 = {
  themeDur: ms(400),
  titleAt: 6,
  cardAt: 14,
  cardStep: 6,
  testsCountAt: 36,
  testsCountDur: ms(800),
} as const;

export const sfx: SceneSfx[] = SUMMARY.cards.map((_, i) => ({ frame: A08.cardAt + i * A08.cardStep, kind: "tick" as const }));

/** "202 → 875": o segundo número conta a partir do primeiro. */
const valueAt = (value: string, frame: number) => {
  const m = value.match(/^(\d+) → (\d+)$/);
  if (!m) return value;
  const from = Number(m[1]);
  const to = Number(m[2]);
  const n = Math.round(interpolate(progress(frame, A08.testsCountAt, A08.testsCountDur, EASE_OUT), [0, 1], [from, to]));
  return `${from} → ${n}`;
};

const SummaryContent = () => {
  const t = useTokens();
  const frame = useCurrentFrame();
  return (
    <>
      <SceneTitle from={A08.titleAt} size={60}>
        {SUMMARY.title}
      </SceneTitle>
      <div
        style={{
          position: "absolute",
          left: SIDE,
          top: 380,
          width: CONTENT_W,
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: 22,
        }}
      >
        {SUMMARY.cards.map((c, i) => (
          <div
            key={c.label}
            style={{
              height: 300,
              boxSizing: "border-box",
              background: t.surface,
              border: `1px solid ${t.rule}`,
              borderRadius: 8,
              padding: "30px 28px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              ...enter(frame, A08.cardAt + i * A08.cardStep, { dist: 10 }),
            }}
          >
            <FromTo value={valueAt(c.value, frame)} style={{ fontFamily: SLAB, fontWeight: 700, fontSize: 64, lineHeight: 1.05, color: t.series, whiteSpace: "nowrap" }} />
            <span style={{ fontFamily: SANS, fontWeight: 500, fontSize: 32, lineHeight: 1.22, color: t.ink }}>{c.label}</span>
          </div>
        ))}
      </div>
    </>
  );
};

/** Cena 8: resumo do antes e depois, com a troca para o tema escuro (como no 1º vídeo). */
export const A08Summary = () => {
  const frame = useCurrentFrame();
  const background = interpolateColors(progress(frame, 0, A08.themeDur, EASE_OUT), [0, 1], [LIGHT.field, DARK.field]);
  return (
    <AbsoluteFill style={{ background }}>
      <ThemeProvider tokens={DARK}>
        <SummaryContent />
      </ThemeProvider>
    </AbsoluteFill>
  );
};
