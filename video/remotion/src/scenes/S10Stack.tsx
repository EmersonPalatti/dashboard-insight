import { AbsoluteFill, interpolate, interpolateColors, useCurrentFrame } from "remotion";
import { enter, progress } from "../anim";
import { SceneTitle } from "../components/Text";
import { STACK_CHIPS } from "../data";
import type { SceneSfx } from "../sfx";
import { CONTENT_W, DARK, EASE_OUT, FAST, LIGHT, ms, NUM, SANS, SIDE, SLAB, ThemeProvider, useTokens } from "../theme";

/** Frames locais da cena 10 (0:51–0:55, 0–120). */
export const S10 = {
  themeDur: ms(400), // 12 frames (#ECECEC -> #111111)
  titleFrom: 6,
  colsFrom: 10,
  chipsFrom: 14,
  metric1From: 44,
  metric2From: 48,
  countDur: ms(700),
} as const;

export const sfx: SceneSfx[] = [];

const StackContent = () => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const columns = Object.entries(STACK_CHIPS);

  const countP = progress(frame, S10.metric2From, S10.countDur, EASE_OUT);
  const testCount = Math.round(interpolate(countP, [0, 1], [0, 202]));

  return (
    <>
      <SceneTitle from={S10.titleFrom} size={60}>
        Deploy real: Vercel + Render.
      </SceneTitle>

      {/* Três colunas de chips em cascata */}
      <div
        style={{
          position: "absolute",
          left: SIDE,
          top: 348,
          width: CONTENT_W,
          display: "grid",
          gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
          gap: 20,
          alignItems: "start",
        }}
      >
        {columns.map(([group, items], colIdx) => {
          const colAnim = enter(frame, S10.colsFrom + colIdx * 3, { dur: FAST, dist: 8 });
          return (
            <div key={group} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div
                style={{
                  fontFamily: SANS,
                  fontWeight: 600,
                  fontSize: 28,
                  lineHeight: 1.2,
                  color: t.muted,
                  paddingBottom: 10,
                  borderBottom: `1px solid ${t.rule}`,
                  marginBottom: 2,
                  ...colAnim,
                }}
              >
                {group}
              </div>

              {items.map((item, itemIdx) => {
                const chipAt = S10.chipsFrom + (colIdx * 4 + itemIdx) * 2;
                const chipAnim = enter(frame, chipAt, { dur: FAST, dist: 8 });
                return (
                  <div
                    key={item}
                    style={{
                      background: t.surface,
                      border: `1px solid ${t.rule}`,
                      borderRadius: 4,
                      padding: "13px 16px",
                      fontFamily: SANS,
                      fontWeight: 500,
                      fontSize: 30,
                      lineHeight: 1.22,
                      color: t.ink,
                      boxSizing: "border-box",
                      ...chipAnim,
                    }}
                  >
                    {item}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      {/* Dois números de destaque em Zilla Slab 72 px (#E0789A) */}
      <div
        style={{
          position: "absolute",
          left: SIDE,
          top: 860,
          width: CONTENT_W,
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: 24,
        }}
      >
        <div
          style={{
            background: t.surface,
            border: `1px solid ${t.rule}`,
            borderRadius: 8,
            padding: "26px 28px",
            display: "flex",
            flexDirection: "column",
            gap: 10,
            ...enter(frame, S10.metric1From, { dist: 10 }),
          }}
        >
          <div
            style={{
              fontFamily: SLAB,
              fontWeight: 700,
              fontSize: 72,
              lineHeight: 1.05,
              color: t.series,
              ...NUM,
            }}
          >
            {"< 100 ms"}
          </div>
          <div
            style={{
              fontFamily: SANS,
              fontWeight: 500,
              fontSize: 32,
              lineHeight: 1.22,
              color: t.ink,
            }}
          >
            KPIs sobre 369 mil linhas
          </div>
        </div>

        <div
          style={{
            background: t.surface,
            border: `1px solid ${t.rule}`,
            borderRadius: 8,
            padding: "26px 28px",
            display: "flex",
            flexDirection: "column",
            gap: 10,
            ...enter(frame, S10.metric2From, { dist: 10 }),
          }}
        >
          <div
            style={{
              fontFamily: SLAB,
              fontWeight: 700,
              fontSize: 72,
              lineHeight: 1.05,
              color: t.series,
              ...NUM,
            }}
          >
            {testCount}
          </div>
          <div
            style={{
              fontFamily: SANS,
              fontWeight: 500,
              fontSize: 32,
              lineHeight: 1.22,
              color: t.ink,
            }}
          >
            testes automatizados
          </div>
        </div>
      </div>
    </>
  );
};

/** Cena 10: Stack. Transição para tema escuro + 3 colunas de chips + 2 métricas. */
export const S10Stack = () => {
  const frame = useCurrentFrame();
  const bgProgress = progress(frame, 0, S10.themeDur, EASE_OUT);
  const background = interpolateColors(bgProgress, [0, 1], [LIGHT.field, DARK.field]);

  return (
    <AbsoluteFill style={{ background }}>
      <ThemeProvider tokens={DARK}>
        <StackContent />
      </ThemeProvider>
    </AbsoluteFill>
  );
};
