import type { CSSProperties } from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { progress } from "../anim";
import { STAGES, STAGES_LEGEND } from "../data";
import { CONTENT_W, EASE_BOUNCE, FAST, ms, NUM, SANS, STAGGER, useTokens } from "../theme";
import { SeverityMark } from "./SeverityMark";

const VISIBLE_ROWS = 8;
const AXIS_MAX = 44; // Máximo dos 8 primeiros hubs = 42,7 min (Coffee Shopping); escala ≈ 42–44 min
const AXIS_TICKS = [0, 10, 20, 30, 40] as const;

const CARD_PAD_X = 32;
const INNER_W = CONTENT_W - CARD_PAD_X * 2; // 872 px
const LABEL_COL_W = 282;
const COL_GAP = 16;
const TRACK_W = INNER_W - LABEL_COL_W - COL_GAP; // 574 px
const BAR_H = 44;
const ROW_GAP = 12;

/**
 * Gráfico "Onde o tempo vai, por hub" (cena 5).
 * Barras horizontais empilhadas com 4 segmentos: Preparo na loja (`seriesDeep`),
 * Coleta (`series`), Expedição (`seriesSoft`) e Trânsito (`muted`).
 */
export const StagesChart = ({
  barsAt = 0,
  highlightAt = 75,
  style,
}: {
  readonly barsAt?: number;
  readonly highlightAt?: number;
  readonly style?: CSSProperties;
}) => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const rows = STAGES.slice(0, VISIBLE_ROWS);

  const legendColors = [t.seriesDeep, t.series, t.seriesSoft, t.muted] as const;

  const hp = progress(frame, highlightAt, FAST);
  const dotScale = progress(frame, highlightAt, FAST, EASE_BOUNCE);

  return (
    <div
      style={{
        width: CONTENT_W,
        background: t.surface,
        border: `1px solid ${t.rule}`,
        borderRadius: 8,
        padding: `26px ${CARD_PAD_X}px 22px`,
        boxSizing: "border-box",
        fontFamily: SANS,
        color: t.ink,
        ...style,
      }}
    >
      {/* Cabeçalho do gráfico */}
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 16,
        }}
      >
        <div style={{ fontSize: 34, fontWeight: 700, lineHeight: 1.15 }}>
          Onde o tempo vai, por hub
        </div>
        <div style={{ fontSize: 28, fontWeight: 500, color: t.muted, whiteSpace: "nowrap" }}>
          Mediana (min)
        </div>
      </div>

      {/* Legenda das 4 etapas (≥ 28 px) */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "8px 24px",
          marginBottom: 22,
        }}
      >
        {STAGES_LEGEND.map((label, idx) => (
          <div key={label} style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
            <span
              style={{
                width: 18,
                height: 18,
                borderRadius: 4,
                background: legendColors[idx],
                flexShrink: 0,
              }}
            />
            <span style={{ fontSize: 28, fontWeight: 500, color: t.ink, lineHeight: 1.15 }}>
              {label}
            </span>
          </div>
        ))}
      </div>

      {/* Área das 8 barras + linhas de grade */}
      <div style={{ position: "relative" }}>
        {/* Linhas de grade verticais atrás das barras */}
        {AXIS_TICKS.map((tick) => {
          const x = LABEL_COL_W + COL_GAP + (tick / AXIS_MAX) * TRACK_W;
          return (
            <div
              key={tick}
              style={{
                position: "absolute",
                left: x,
                top: 0,
                bottom: 0,
                width: 1,
                background: t.rule,
                opacity: 0.7,
                pointerEvents: "none",
              }}
            />
          );
        })}

        {/* Linhas */}
        <div style={{ display: "flex", flexDirection: "column", gap: ROW_GAP, position: "relative" }}>
          {rows.map((row, i) => {
            const isTarget = i === 0; // Color Shopping
            const grow = progress(frame, barsAt + i * STAGGER, ms(300));
            const rowOpacity = isTarget ? 1 : interpolate(hp, [0, 1], [1, 0.25]);

            const total = row.prep + row.pickup + row.dispatch + row.transit;
            const fullW = (total / AXIS_MAX) * TRACK_W;
            const segs = [
              { key: "prep", w: (row.prep / total) * fullW, color: t.seriesDeep },
              { key: "pickup", w: (row.pickup / total) * fullW, color: t.series },
              { key: "dispatch", w: (row.dispatch / total) * fullW, color: t.seriesSoft },
              { key: "transit", w: (row.transit / total) * fullW, color: t.muted },
            ];

            return (
              <div
                key={row.hub}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: COL_GAP,
                  height: BAR_H,
                  opacity: rowOpacity,
                }}
              >
                {/* Rótulo do hub (28 px) + marcador ● para Color Shopping */}
                <div
                  style={{
                    width: LABEL_COL_W,
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                  }}
                >
                  <div
                    style={{
                      width: 22,
                      height: 22,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                      opacity: isTarget ? hp : 0,
                      scale: isTarget ? dotScale : 0,
                    }}
                  >
                    <SeverityMark severity="high" scale={1.7} />
                  </div>
                  <span
                    style={{
                      fontSize: 28,
                      fontWeight: isTarget && hp > 0.35 ? 700 : 500,
                      color: t.ink,
                      whiteSpace: "nowrap",
                      lineHeight: 1.15,
                    }}
                  >
                    {row.hub}
                  </span>
                </div>

                {/* Barra empilhada crescendo da esquerda */}
                <div style={{ width: TRACK_W, height: BAR_H, position: "relative" }}>
                  <div
                    style={{
                      width: fullW * grow,
                      height: BAR_H,
                      overflow: "hidden",
                      borderRadius: 4,
                    }}
                  >
                    <div style={{ display: "flex", width: fullW, height: BAR_H }}>
                      {segs.map((seg) => {
                        const isExpedicaoFocus = isTarget && seg.key === "dispatch";
                        return (
                          <div
                            key={seg.key}
                            style={{
                              width: seg.w,
                              height: BAR_H,
                              background: seg.color,
                              position: "relative",
                              flexShrink: 0,
                            }}
                          >
                            {isExpedicaoFocus && hp > 0 ? (
                              <div
                                style={{
                                  position: "absolute",
                                  inset: 0,
                                  border: `2px solid ${t.ink}`,
                                  borderRadius: 2,
                                  boxSizing: "border-box",
                                  opacity: hp,
                                }}
                              />
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Eixo X (minutos) */}
      <div
        style={{
          position: "relative",
          height: 32,
          marginTop: 12,
          marginLeft: LABEL_COL_W + COL_GAP,
          width: TRACK_W,
        }}
      >
        {AXIS_TICKS.map((tick) => {
          const left = (tick / AXIS_MAX) * TRACK_W;
          return (
            <span
              key={tick}
              style={{
                position: "absolute",
                left,
                top: 0,
                translate: tick === 0 ? "0% 0%" : "-50% 0%",
                fontSize: 28,
                fontWeight: 500,
                color: t.muted,
                lineHeight: 1.1,
                whiteSpace: "nowrap",
                ...NUM,
              }}
            >
              {tick === 40 ? "40 min" : tick}
            </span>
          );
        })}
      </div>
    </div>
  );
};
