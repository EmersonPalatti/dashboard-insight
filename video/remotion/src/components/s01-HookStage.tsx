import type { ReactNode } from "react";
import { AbsoluteFill, interpolate, interpolateColors } from "remotion";
import { between, enter, progress } from "../anim";
import { Stamp, Ticket } from "./Ticket";
import { EASE_OUT, EASE_TICKET, ms, SANS, SIDE, TITLE_ZONE, useTokens, W } from "../theme";

/** Alturas relativas das 8 barras genéricas (sem rótulo). */
const BARS = [0.48, 0.76, 0.4, 0.94, 0.62, 0.84, 0.36, 0.68];
const BAR_W = 74;
const BAR_GAP = 30;
const CHART_W = BARS.length * BAR_W + (BARS.length - 1) * BAR_GAP; // 802 px
const CHART_LEFT = (1080 - CHART_W) / 2; // 139 px
const MAX_BAR_H = 380;

const TICKET_W = 860;
const TICKET_LEFT = (1080 - TICKET_W) / 2; // 110 px
const TICKET_H = 264;
const SLOT_Y = 870;

export const S01_TIMING = {
  barsDur: ms(600), // 18 frames
  titleSplit: 75, // 2,5 s
  printStart: 78, // 2,6 s
  mergeDur: 10, // 78 -> 88
  feedStart: 86,
  feedDur: 22, // 86 -> 108
  zoomStart: 114,
  zoomDur: 35, // 114 -> 149
};

/** Título sincronizado pelo `frame` explícito (mesmo layout do SceneTitle, seguro para reusar na Cena 2). */
const FrameTitle = ({
  frame,
  from,
  to,
  children,
}: {
  readonly frame: number;
  readonly from: number;
  readonly to?: number;
  readonly children: ReactNode;
}) => {
  const t = useTokens();
  const anim = to === undefined ? enter(frame, from, { dist: 12 }) : between(frame, from, to, { enter: { dist: 12 } });
  return (
    <div
      style={{
        position: "absolute",
        left: SIDE,
        width: W - SIDE * 2,
        top: TITLE_ZONE.top,
        height: TITLE_ZONE.bottom - TITLE_ZONE.top,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "flex-start",
        textAlign: "left",
        fontFamily: SANS,
        fontWeight: 700,
        fontSize: 72,
        lineHeight: 1.1,
        letterSpacing: "-0.01em",
        color: t.ink,
        textWrap: "balance",
        ...anim,
      }}
    >
      {children}
    </div>
  );
};

/**
 * Conteúdo da Cena 1 parametrizado pelo frame local (0..149).
 * Extraído para que a Cena 2 renderize exatamente o estado final (frame 149) por baixo do wipe.
 */
export const HookStage = ({ frame }: { readonly frame: number }) => {
  const t = useTokens();

  // Zoom suave da câmera no fim da cena (scale 1 → 1.06).
  const camScale = interpolate(
    frame,
    [S01_TIMING.zoomStart, S01_TIMING.zoomStart + S01_TIMING.zoomDur],
    [1, 1.06],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE_OUT },
  );

  // Fase 1 → 2: barras encolhem e se fundem numa tira branca na linha da impressora.
  const mergeP = progress(frame, S01_TIMING.printStart, S01_TIMING.mergeDur, EASE_OUT);
  const barColor = interpolateColors(mergeP, [0, 1], [t.muted, t.surface]);

  // Fase 2: comanda sobe da impressora (86..108).
  const feedP = progress(frame, S01_TIMING.feedStart, S01_TIMING.feedDur, EASE_TICKET);
  const slotFade = 1 - progress(frame, 108, 12, EASE_OUT);

  const showBars = frame < S01_TIMING.feedStart + 3;
  const showTicket = frame >= S01_TIMING.feedStart;

  const mergedSegW = TICKET_W / BARS.length;

  return (
    <AbsoluteFill style={{ background: t.field }}>
      <AbsoluteFill
        style={{
          scale: `${camScale}`,
          transformOrigin: "540px 680px",
        }}
      >

        {/* Linha de base / boca da impressora térmica */}
        {slotFade > 0 ? (
          <div
            style={{
              position: "absolute",
              left: TICKET_LEFT - 16,
              top: SLOT_Y,
              width: TICKET_W + 32,
              height: 3,
              borderRadius: 2,
              background: mergeP > 0 ? interpolateColors(mergeP, [0, 1], [t.rule, t.ink]) : t.rule,
              opacity: slotFade,
            }}
          />
        ) : null}

        {/* 8 barras genéricas em cinza (muted) que se desenham de baixo para cima e se fundem */}
        {showBars
          ? BARS.map((ratio, i) => {
              const barGrow = progress(frame, i, S01_TIMING.barsDur - BARS.length + 1, EASE_OUT);
              const fullH = ratio * MAX_BAR_H * barGrow;
              const h = interpolate(mergeP, [0, 1], [fullH, 14]);
              const origX = CHART_LEFT + i * (BAR_W + BAR_GAP);
              const targetX = TICKET_LEFT + i * mergedSegW;
              const x = interpolate(mergeP, [0, 1], [origX, targetX]);
              const w = interpolate(mergeP, [0, 1], [BAR_W, mergedSegW + 1]);
              const radius = interpolate(mergeP, [0, 1], [4, 0]);
              const barsOut = frame >= S01_TIMING.feedStart ? 1 - progress(frame, S01_TIMING.feedStart, 2) : 1;

              return (
                <div
                  key={i}
                  style={{
                    position: "absolute",
                    left: x,
                    top: SLOT_Y - h,
                    width: w,
                    height: Math.max(0, h),
                    background: barColor,
                    borderRadius: `${radius}px ${radius}px 0 0`,
                    opacity: barsOut,
                  }}
                />
              );
            })
          : null}

        {/* Comanda saindo de baixo para cima como papel da impressora térmica */}
        {showTicket ? (
          <div
            style={{
              position: "absolute",
              left: TICKET_LEFT,
              top: SLOT_Y - TICKET_H - 12,
              width: TICKET_W,
              height: TICKET_H + 12,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                translate: `0px ${interpolate(feedP, [0, 1], [TICKET_H - 2, 12])}px`,
              }}
            >
              <Ticket width={TICKET_W} padding="30px 36px 28px">
                <div style={{ height: TICKET_H - 58, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      paddingBottom: 20,
                      borderBottom: `1.5px dashed ${t.rule}`,
                    }}
                  >
                    <Stamp severity="high" label="Nº 01 · SLA" size={32} markScale={2.4} />
                    <div style={{ width: 96, height: 14, borderRadius: 4, background: t.sunken }} />
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                    <div style={{ width: "68%", height: 18, borderRadius: 4, background: t.sunken }} />
                    <div style={{ width: "44%", height: 14, borderRadius: 4, background: t.rule }} />
                  </div>

                  <div
                    style={{
                      height: 52,
                      borderRadius: 8,
                      background: t.ink,
                      padding: "0 20px",
                      display: "flex",
                      alignItems: "center",
                      gap: 14,
                    }}
                  >
                    <div style={{ width: 64, height: 12, borderRadius: 3, background: "rgba(255,255,255,0.45)" }} />
                    <div style={{ width: "52%", height: 14, borderRadius: 3, background: "rgba(255,255,255,0.88)" }} />
                  </div>
                </div>
              </Ticket>
            </div>
          </div>
        ) : null}
      </AbsoluteFill>
      {/* Títulos fora do zoom da câmera, para manter a margem lateral de 72 px. */}
      {/* Títulos (72 px, ink): 0–75 e 75–150 */}
      <FrameTitle frame={frame} from={0} to={S01_TIMING.titleSplit}>
        <span>Gráfico mostra o problema.</span>
      </FrameTitle>
      <FrameTitle frame={frame} from={S01_TIMING.titleSplit}>
        <span>
          Não diz o que fazer <span style={{ color: t.crit }}>hoje</span>.
        </span>
      </FrameTitle>
    </AbsoluteFill>
  );
};

/** Estado final da Cena 1 (frame 149), renderizado por baixo do wipe de abertura da Cena 2. */
export const HookFinalState = () => <HookStage frame={149} />;
