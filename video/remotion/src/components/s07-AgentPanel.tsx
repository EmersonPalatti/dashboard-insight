import type { CSSProperties } from "react";
import { interpolate, interpolateColors, useCurrentFrame } from "remotion";
import { enter, progress } from "../anim";
import { AGENT } from "../data";
import { CONTENT_W, FAST, ms, SANS, useTokens } from "../theme";
import { ActionBlock } from "./ActionBlock";
import { Button } from "./Button";
import { PRINT_DUR, Ticket, TicketHeader } from "./Ticket";

export const S07_TIMING = {
  panelEnter: 0,
  typeStart: 8,
  typeEnd: 42,
  sendAt: 44,
  bubbleAt: 46,
  thinkAt: 60,
  toolStart: 66,
  toolStep: 10,
  collapseAt: 112,
  collapseDur: ms(300),
  printAt: 120,
  detailAt: 120 + PRINT_DUR,
  actionAt: 120 + PRINT_DUR + ms(300),
  buttonsAt: 120 + PRINT_DUR + ms(300) + ms(250),
} as const;

const PANEL_H = 784;
const SHIMMER_FRAMES = Math.round(1.6 * 30); // ciclo de 1,6 s = 48 frames

/** Ícone simples de robô (cabeçalho do agente). */
const BotIcon = ({ color }: { readonly color: string }) => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 8V4H8" />
    <rect width="16" height="12" x="4" y="8" rx="2" />
    <path d="M2 14h2" />
    <path d="M20 14h2" />
    <path d="M15 13v2" />
    <path d="M9 13v2" />
  </svg>
);

/** Ícone simples de cadeado (recorte travado). */
const LockIcon = ({ color }: { readonly color: string }) => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
);

/** Ícone simples de filtro (botão fantasma). */
const FilterIcon = ({ color }: { readonly color: string }) => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
  </svg>
);

/** Ícone simples de envio (input). */
const SendIcon = ({ color }: { readonly color: string }) => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="m22 2-7 20-4-9-9-4Z" />
    <path d="M22 2 11 13" />
  </svg>
);

export const AgentPanel = ({ style }: { readonly style?: CSSProperties }) => {
  const t = useTokens();
  const frame = useCurrentFrame();

  const panelIn = enter(frame, S07_TIMING.panelEnter, { dur: ms(400), dist: 12, axis: "x" });

  // Digitação determinística da pergunta
  const typedChars = Math.floor(
    interpolate(frame, [S07_TIMING.typeStart, S07_TIMING.typeEnd], [0, AGENT.question.length], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  );
  const isSent = frame >= S07_TIMING.sendAt;
  const showTyping = frame >= S07_TIMING.typeStart && !isSent;
  const typedText = showTyping ? AGENT.question.slice(0, typedChars) : "";

  const sendScale = interpolate(
    frame,
    [S07_TIMING.sendAt, S07_TIMING.sendAt + 2, S07_TIMING.sendAt + 6],
    [1, 0.93, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Recolhimento suave da pergunta/ferramentas quando a resposta imprime
  const collapse = progress(frame, S07_TIMING.collapseAt, S07_TIMING.collapseDur);
  const bodyBg = interpolateColors(collapse, [0, 1], [t.surface, t.field]);

  // Shimmer determinístico (ciclo de 1,6 s)
  const shimmerCycle = Math.max(0, frame - S07_TIMING.thinkAt) % SHIMMER_FRAMES;
  const shimmerPos = interpolate(shimmerCycle, [0, SHIMMER_FRAMES], [110, -20]);

  const bubbleIn = enter(frame, S07_TIMING.bubbleAt, { dur: ms(280), dist: 12 });
  const thinkIn = enter(frame, S07_TIMING.thinkAt, { dur: FAST, dist: 8 });

  // Animações internas da comanda impressa
  const showDetail = enter(frame, S07_TIMING.detailAt, { dist: 10 });
  const showAction = enter(frame, S07_TIMING.actionAt, { dist: 10 });
  const showButtons = enter(frame, S07_TIMING.buttonsAt, { dist: 6 });

  const innerW = CONTENT_W - 56;

  return (
    <div
      style={{
        width: CONTENT_W,
        height: PANEL_H,
        background: t.surface,
        border: `1.5px solid ${t.rule}`,
        borderRadius: 8,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        boxSizing: "border-box",
        fontFamily: SANS,
        color: t.ink,
        ...panelIn,
        ...style,
      }}
    >
      {/* Cabeçalho do painel */}
      <div
        style={{
          padding: "18px 28px 14px",
          borderBottom: `1px solid ${t.rule}`,
          background: t.surface,
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <BotIcon color={t.series} />
          <span style={{ fontSize: 32, fontWeight: 700, lineHeight: 1.2, color: t.ink }}>
            {AGENT.header}
          </span>
        </div>
        <div style={{ fontSize: 28, lineHeight: 1.25, color: t.muted, marginTop: 4 }}>
          {AGENT.context}
        </div>
      </div>

      {/* Corpo do painel */}
      <div
        style={{
          position: "relative",
          flex: 1,
          background: bodyBg,
          overflow: "hidden",
          padding: "16px 26px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
        }}
      >
        {/* Fase 1 & 2: Pergunta + Consultando + Ferramentas + Input (sobe/recolhe ao imprimir) */}
        {collapse < 1 ? (
          <div
            style={{
              position: "absolute",
              inset: "18px 26px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              opacity: 1 - collapse,
              translate: `0px ${-collapse * 48}px`,
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
              {/* Balão da pergunta */}
              {frame >= S07_TIMING.bubbleAt ? (
                <div
                  style={{
                    alignSelf: "flex-end",
                    maxWidth: "86%",
                    background: t.sunken,
                    border: `1px solid ${t.rule}`,
                    borderRadius: 8,
                    padding: "16px 22px",
                    fontSize: 30,
                    lineHeight: 1.3,
                    fontWeight: 500,
                    color: t.ink,
                    ...bubbleIn,
                  }}
                >
                  {AGENT.question}
                </div>
              ) : null}

              {/* Consultando + Shimmer + 5 ferramentas + cadeado */}
              {frame >= S07_TIMING.thinkAt ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 16, ...thinkIn }}>
                  <div
                    style={{
                      fontSize: 30,
                      fontWeight: 600,
                      lineHeight: 1.25,
                      backgroundImage: `linear-gradient(90deg, ${t.muted} 0%, ${t.muted} 35%, ${t.ink} 50%, ${t.muted} 65%, ${t.muted} 100%)`,
                      backgroundSize: "220% 100%",
                      backgroundPosition: `${shimmerPos}% 0%`,
                      WebkitBackgroundClip: "text",
                      backgroundClip: "text",
                      color: "transparent",
                    }}
                  >
                    {AGENT.thinking}
                  </div>

                  {/* Faixa de ferramentas + cadeado ao lado */}
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
                    <div style={{ flex: 1, display: "flex", flexWrap: "wrap", gap: 10 }}>
                      {AGENT.tools.map((tool, i) => {
                        const activeP = progress(
                          frame,
                          S07_TIMING.toolStart + i * S07_TIMING.toolStep,
                          FAST,
                        );
                        const borderColor = interpolateColors(activeP, [0, 1], [t.rule, t.series]);
                        const textColor = interpolateColors(activeP, [0, 1], [t.muted, t.ink]);
                        return (
                          <span
                            key={tool}
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 8,
                              padding: "8px 14px",
                              borderRadius: 4,
                              background: t.sunken,
                              border: `2px solid ${borderColor}`,
                              fontSize: 28,
                              lineHeight: 1.2,
                              fontWeight: activeP > 0.5 ? 600 : 500,
                              color: textColor,
                              whiteSpace: "nowrap",
                            }}
                          >
                            {tool}
                          </span>
                        );
                      })}
                    </div>

                    {/* Cadeado pequeno + "recorte: Color Shopping" */}
                    <div
                      style={{
                        flexShrink: 0,
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 8,
                        padding: "8px 14px",
                        borderRadius: 4,
                        background: t.sunken,
                        border: `1.5px solid ${t.rule}`,
                        fontSize: 28,
                        lineHeight: 1.2,
                        fontWeight: 600,
                        color: t.ink,
                        whiteSpace: "nowrap",
                      }}
                    >
                      <LockIcon color={t.series} />
                      <span>{AGENT.lock}</span>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>

            {/* Campo de pergunta na base */}
            <div
              style={{
                height: 76,
                borderRadius: 8,
                border: `1.5px solid ${showTyping ? t.ink : t.rule}`,
                background: t.surface,
                padding: "0 12px 0 20px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                boxSizing: "border-box",
              }}
            >
              <div
                style={{
                  flex: 1,
                  fontSize: 28,
                  lineHeight: 1.2,
                  color: showTyping ? t.ink : t.muted,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  display: "flex",
                  justifyContent: "flex-end",
                }}
              >
                <span style={{ width: "100%", textAlign: "left" }}>
                  {showTyping ? (
                    <>
                      {typedText}
                      <span
                        style={{
                          display: "inline-block",
                          width: 2,
                          height: 28,
                          background: t.series,
                          verticalAlign: "-4px",
                          marginLeft: 2,
                        }}
                      />
                    </>
                  ) : (
                    "Pergunte sobre este recorte…"
                  )}
                </span>
              </div>
              <div
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: 8,
                  background: showTyping ? t.ink : t.muted,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  scale: sendScale,
                }}
              >
                <SendIcon color="#FFFFFF" />
              </div>
            </div>
          </div>
        ) : null}

        {/* Fase 3: Resposta impressa como Comanda Nº A01 */}
        {frame >= S07_TIMING.printAt ? (
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "center" }}>
            <Ticket width={innerW} printAt={S07_TIMING.printAt} padding="22px 26px 20px">
              <TicketHeader severity="low" label={AGENT.stamp} right={null} />
              <div style={{ fontSize: 40, fontWeight: 600, lineHeight: 1.15, marginBottom: 10 }}>
                {AGENT.title}
              </div>
              <div style={{ fontSize: 30, lineHeight: 1.26, color: t.ink, marginBottom: 14, ...showDetail }}>
                {AGENT.detail}
              </div>
              <ActionBlock fontSize={29} padding={18} style={{ marginBottom: 16, ...showAction }}>
                {AGENT.action}
              </ActionBlock>
              <div style={{ display: "flex", alignItems: "center", gap: 14, ...showButtons }}>
                <Button style={{ gap: 10 }}>
                  <FilterIcon color={t.ink} />
                  <span>{AGENT.buttons.ghost}</span>
                </Button>
                <Button>{AGENT.buttons.pin}</Button>
              </div>
            </Ticket>
          </div>
        ) : null}
      </div>
    </div>
  );
};
