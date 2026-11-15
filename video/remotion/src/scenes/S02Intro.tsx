import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { enter, progress } from "../anim";
import { Logo } from "../components/Logo";
import { HookFinalState } from "../components/s01-HookStage";
import { Caption } from "../components/Text";
import type { SceneSfx } from "../sfx";
import { br, CONTENT_W, EASE_OUT, EASE_TICKET, ms, NUM, SANS, SIDE, SLAB, STAGGER, useTokens } from "../theme";

export const sfx: SceneSfx[] = [];

const WIPE_DUR = ms(400); // 12 frames
const COUNT_DUR = ms(800); // 24 frames
const BRAND_START = 10;
const COUNTER_START = 30;

/** Cena 2: Apresentação (0:05–0:10). Wipe vinho sobre o fim da Cena 1 + nome + números reais do dataset. */
export const S02Intro = () => {
  const t = useTokens();
  const frame = useCurrentFrame();

  const wipe = progress(frame, 0, WIPE_DUR, EASE_TICKET);

  const count = (i: number, target: number) => {
    const p = progress(frame, COUNTER_START + i * STAGGER, COUNT_DUR, EASE_OUT);
    return br(Math.round(target * p));
  };

  const statAnim = (i: number) => enter(frame, COUNTER_START + i * STAGGER, { dist: 10 });

  const numStyle = {
    fontFamily: SLAB,
    fontWeight: 700,
    fontSize: 96,
    lineHeight: 1,
    color: t.onWine,
    ...NUM,
  } as const;

  const labelStyle = {
    fontFamily: SANS,
    fontWeight: 500,
    fontSize: 36,
    lineHeight: 1.2,
    color: t.onWine,
    marginTop: 10,
  } as const;

  return (
    <AbsoluteFill style={{ background: t.field }}>
      {/* Último estado da Cena 1 por baixo do wipe vertical */}
      {frame < WIPE_DUR + 2 ? <HookFinalState /> : null}

      {/* Wipe vertical de baixo para cima pinta a tela de wine (sem fade) */}
      <AbsoluteFill
        style={{
          background: t.wine,
          clipPath: `inset(${(1 - wipe) * 100}% 0 0 0)`,
        }}
      >
        {/* Bloco da marca: Logo + Central de Operações + subtítulo */}
        <div
          style={{
            position: "absolute",
            left: SIDE,
            top: 124,
            width: CONTENT_W,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            textAlign: "center",
          }}
        >
          <div
            style={{
              display: "inline-flex",
              border: `2px solid ${t.wineRaised}`,
              borderRadius: 20,
              ...enter(frame, BRAND_START, { dist: 10 }),
            }}
          >
            <Logo size={96} background={t.wine} />
          </div>

          <div
            style={{
              marginTop: 24,
              fontFamily: SLAB,
              fontWeight: 700,
              fontSize: 84,
              lineHeight: 1.05,
              letterSpacing: "-0.01em",
              color: t.onWine,
              ...enter(frame, BRAND_START + 3, { dist: 10 }),
            }}
          >
            Central de Operações
          </div>

          <div
            style={{
              marginTop: 18,
              fontFamily: SANS,
              fontWeight: 500,
              fontSize: 36,
              lineHeight: 1.25,
              color: t.onWine,
              maxWidth: 820,
              ...enter(frame, BRAND_START + 6, { dist: 8 }),
            }}
          >
            <span style={{ opacity: 0.9 }}>Painel de delivery com alertas e agente de IA</span>
          </div>
        </div>

        {/* Quatro contadores em cascata (stagger 40 ms, contagem 800 ms) */}
        <div
          style={{
            position: "absolute",
            left: SIDE,
            top: 474,
            width: CONTENT_W,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
          }}
        >
          {/* 368.990 pedidos reais */}
          <div
            style={{
              width: "100%",
              paddingBottom: 34,
              borderBottom: `1px solid ${t.wineRaised}`,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              textAlign: "center",
              ...statAnim(0),
            }}
          >
            <div style={numStyle}>{count(0, 368990)}</div>
            <div style={labelStyle}>pedidos reais</div>
          </div>

          {/* 32 hubs · 4 cidades */}
          <div
            style={{
              width: "100%",
              padding: "34px 0",
              borderBottom: `1px solid ${t.wineRaised}`,
              display: "flex",
              justifyContent: "center",
              gap: 120,
              opacity: progress(frame, COUNTER_START + STAGGER, ms(250)),
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", ...statAnim(1) }}>
              <div style={numStyle}>{count(1, 32)}</div>
              <div style={labelStyle}>hubs</div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", ...statAnim(2) }}>
              <div style={numStyle}>{count(2, 4)}</div>
              <div style={labelStyle}>cidades</div>
            </div>
          </div>

          {/* jan–abr 2021 (sem contagem, entra com fade) */}
          <div
            style={{
              width: "100%",
              paddingTop: 34,
              display: "flex",
              justifyContent: "center",
              textAlign: "center",
              opacity: interpolate(frame, [COUNTER_START + 3 * STAGGER, COUNTER_START + 3 * STAGGER + ms(380)], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: EASE_OUT,
              }),
            }}
          >
            <div style={numStyle}>jan–abr 2021</div>
          </div>
        </div>

        {/* Legenda 28 px onWine a 70% */}
        <Caption from={42} size={28} color={t.onWine} align="center">
          <span style={{ opacity: 0.7 }}>Dataset público Delivery Center (Kaggle)</span>
        </Caption>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
