import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { enter } from "../anim";
import { ActionBlock } from "../components/ActionBlock";
import { Caption, SceneTitle } from "../components/Text";
import { Ticket, TicketHeader } from "../components/Ticket";
import { DATA_CARE } from "../data";
import type { SceneSfx } from "../sfx";
import { local } from "../timing";
import { CONTENT_W, EASE_OUT, ms, NUM, SANS, SIDE, SLAB, STAGE, useTokens } from "../theme";

export const S08 = {
  cardAt: 2,
  stampAt: local("s08Data", 42.5), // frame local 45
  ticketAt: 54,
} as const;

/** Efeitos sonoros da cena 8 (frames locais). */
export const sfx: SceneSfx[] = [{ frame: S08.ticketAt, kind: "impressora" }];

/** Cena 8 (0:41–0:45, locais 0–120): cuidado com o dado. Dado quebrado não vira culpa da frota. */
export const S08Data = () => {
  const t = useTokens();
  const frame = useCurrentFrame();

  const cardIn = enter(frame, S08.cardAt, { dist: 12 });

  const stampProgress = interpolate(frame, [S08.stampAt, S08.stampAt + ms(220)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE_OUT,
  });
  const stampScale = interpolate(stampProgress, [0, 1], [1.1, 1]);

  return (
    <AbsoluteFill style={{ background: t.field }}>
      <SceneTitle from={0} size={60}>
        Dado quebrado não vira culpa da frota.
      </SceneTitle>

      {/* Palco (y 350–1150): cartão grande com 98,5% + carimbo DADOS + comanda Nº 06 em miniatura */}
      <div
        style={{
          position: "absolute",
          left: SIDE,
          top: STAGE.top,
          width: CONTENT_W,
          height: STAGE.bottom - STAGE.top,
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-start",
          paddingTop: 28,
          boxSizing: "border-box",
          gap: 30,
        }}
      >
        {/* Cartão grande */}
        <div
          style={{
            position: "relative",
            width: CONTENT_W,
            background: t.surface,
            border: `1.5px solid ${t.rule}`,
            borderRadius: 8,
            padding: "32px 36px 34px",
            boxSizing: "border-box",
            fontFamily: SANS,
            ...cardIn,
          }}
        >
          <div
            style={{
              fontFamily: SLAB,
              fontWeight: 700,
              fontSize: 160,
              lineHeight: 0.96,
              color: t.series,
              letterSpacing: "-0.02em",
              ...NUM,
            }}
          >
            {DATA_CARE.figure}
          </div>
          <div
            style={{
              fontSize: 34,
              lineHeight: 1.28,
              fontWeight: 500,
              color: t.ink,
              marginTop: 18,
              maxWidth: 820,
            }}
          >
            {DATA_CARE.line}
          </div>

          {/* Carimbo diagonal discreto "DADOS" (frame 45) */}
          <div
            style={{
              position: "absolute",
              top: 38,
              right: 36,
              border: `3px solid ${t.ink}`,
              borderRadius: 4,
              padding: "10px 24px",
              fontFamily: SLAB,
              fontWeight: 700,
              fontSize: 34,
              letterSpacing: "0.08em",
              lineHeight: 1,
              color: t.ink,
              textTransform: "uppercase",
              rotate: "-4deg",
              scale: stampScale,
              opacity: stampProgress,
            }}
          >
            {DATA_CARE.stamp}
          </div>
        </div>

        {/* Comanda Nº 06 em miniatura */}
        {frame >= S08.ticketAt ? (
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <Ticket width={880} printAt={S08.ticketAt} padding="26px 30px 24px">
              <TicketHeader severity="medium" label="Nº 06 · DADOS" />
              <ActionBlock fontSize={29} padding={22}>
                {DATA_CARE.action}
              </ActionBlock>
            </Ticket>
          </div>
        ) : null}
      </div>

      <Caption from={S08.stampAt} size={32}>
        Hub com mais de 30% de pedidos presos sai da comparação de SLA.
      </Caption>
    </AbsoluteFill>
  );
};
