import { AbsoluteFill, useCurrentFrame } from "remotion";
import { enter, exit, progress } from "../../anim";
import { ActionBlock } from "../../components/ActionBlock";
import { Caption, SceneTitle } from "../../components/Text";
import { FromTo } from "../components/FromTo";
import { PRINT_DUR, Ticket, TicketHeader } from "../../components/Ticket";
import type { SceneSfx } from "../../sfx";
import { CONTENT_W, FAST, ms, NUM, SANS, SIDE, SLAB, useTokens } from "../../theme";
import { MARCH } from "../data";

/** Frames locais da cena 5 (0:28–0:35, 0–210). */
export const A05 = {
  titleAt: 4,
  periodAt: 6,
  slaAt: 10,
  driverAt: 26,
  stagesAt: 42,
  barAt: 48,
  barStep: 4,
  focusAt: 66,
  captionStagesAt: 74,
  stepsOutAt: 120,
  printAt: 128,
  captionTicketAt: 138,
} as const;

export const sfx: SceneSfx[] = [{ frame: A05.printAt, kind: "impressora" }];

const BAR = { labelW: 236, deltaW: 150, half: 200, perMin: 200 / 5 };

const StageRow = ({ i }: { readonly i: number }) => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const s = MARCH.stages[i];
  const focus = "focus" in s && s.focus;
  const p = progress(frame, A05.barAt + i * A05.barStep, ms(300));
  const width = Math.abs(s.delta) * BAR.perMin * p;
  const outline = focus ? progress(frame, A05.focusAt, FAST) : 0;
  const worse = s.delta > 0;
  return (
    <div style={{ display: "flex", alignItems: "center", height: 60 }}>
      <span style={{ width: BAR.labelW, flexShrink: 0, fontSize: 30, fontWeight: focus ? 700 : 500, color: t.ink }}>{s.label}</span>
      <div style={{ position: "relative", flex: 1, height: 60 }}>
        {/* Eixo do zero */}
        <div style={{ position: "absolute", left: BAR.half, top: 4, bottom: 4, width: 2, background: t.rule }} />
        <div
          style={{
            position: "absolute",
            top: 12,
            height: 36,
            left: worse ? BAR.half + 1 : BAR.half + 1 - width,
            width,
            borderRadius: 4,
            boxSizing: "border-box",
            background: focus ? t.series : t.seriesSoft,
            outline: outline > 0 ? `${2 * outline}px solid ${t.ink}` : undefined,
            outlineOffset: 2,
          }}
        />
      </div>
      <span
        style={{
          width: BAR.deltaW,
          flexShrink: 0,
          textAlign: "right",
          fontFamily: SLAB,
          fontWeight: 700,
          fontSize: 34,
          color: worse ? t.warn : t.good,
          opacity: p,
          ...NUM,
        }}
      >
        {s.text}
      </span>
    </div>
  );
};

/** Cena 5: março/2021 no dado real. Decomposição, etapa que explica e a comanda com a ação. */
export const A05March = () => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const stepsOut = exit(frame, A05.stepsOutAt, { dur: ms(220), dist: -16 });

  return (
    <AbsoluteFill style={{ background: t.field }}>
      <SceneTitle from={A05.titleAt}>Causa exata, não palpite.</SceneTitle>

      {/* Recorte: março contra o período anterior de mesmo tamanho */}
      <div
        style={{
          position: "absolute",
          left: SIDE,
          top: 352,
          height: 52,
          display: "inline-flex",
          alignItems: "center",
          padding: "0 18px",
          borderRadius: 4,
          background: t.sunken,
          border: `1px solid ${t.rule}`,
          fontFamily: SANS,
          fontSize: 28,
          fontWeight: 500,
          color: t.ink,
          ...enter(frame, A05.periodAt, { dist: 8 }),
        }}
      >
        {MARCH.period}
      </div>

      {frame < A05.stepsOutAt + ms(220) ? (
        <div style={{ position: "absolute", left: SIDE, top: 424, width: CONTENT_W, display: "flex", flexDirection: "column", gap: 16, fontFamily: SANS, ...stepsOut }}>
          {/* Passo 1: decomposição */}
          <div style={{ background: t.surface, border: `1.5px solid ${t.rule}`, borderRadius: 8, padding: "22px 28px", ...enter(frame, A05.slaAt, { dist: 10 }) }}>
            <div style={{ fontSize: 28, color: t.muted }}>{MARCH.sla.label}</div>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginTop: 4 }}>
              <FromTo value={`${MARCH.sla.before} → ${MARCH.sla.after}`} style={{ fontFamily: SLAB, fontWeight: 700, fontSize: 64, lineHeight: 1.05, color: t.ink }} />
              <span style={{ fontFamily: SLAB, fontWeight: 700, fontSize: 44, color: t.warn, ...NUM }}>{MARCH.sla.delta}</span>
            </div>
            <div style={{ height: 1, background: t.rule, margin: "18px 0" }} />
            <div style={enter(frame, A05.driverAt, { dist: 8 })}>
              <div style={{ fontSize: 28, color: t.muted }}>{MARCH.driver.label}</div>
              <div style={{ display: "flex", alignItems: "center", gap: 18, marginTop: 6, flexWrap: "wrap" }}>
                <span style={{ fontSize: 36, fontWeight: 700, color: t.ink }}>{MARCH.driver.name}</span>
                <FromTo value={`${MARCH.driver.before} → ${MARCH.driver.after}`} style={{ fontFamily: SLAB, fontWeight: 700, fontSize: 40, color: t.series }} />
                <span
                  style={{
                    height: 46,
                    display: "inline-flex",
                    alignItems: "center",
                    padding: "0 14px",
                    borderRadius: 4,
                    background: t.sunken,
                    border: `1px solid ${t.rule}`,
                    fontFamily: SLAB,
                    fontWeight: 600,
                    fontSize: 28,
                    color: t.ink,
                    ...NUM,
                  }}
                >
                  {MARCH.driver.evidence}
                </span>
              </div>
            </div>
          </div>

          {/* Passo 2: etapa que explica */}
          <div style={{ background: t.surface, border: `1.5px solid ${t.rule}`, borderRadius: 8, padding: "20px 28px 22px", ...enter(frame, A05.stagesAt, { dist: 10 }) }}>
            <div style={{ fontSize: 28, color: t.muted, marginBottom: 12 }}>{MARCH.stagesTitle}</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {MARCH.stages.map((s, i) => (
                <StageRow key={s.label} i={i} />
              ))}
            </div>
          </div>
        </div>
      ) : null}

      {/* Passo 3: a comanda impressa com a ação real do agente */}
      {frame >= A05.printAt ? (
        <div style={{ position: "absolute", left: SIDE, top: 430 }}>
          <Ticket printAt={A05.printAt} padding="28px 30px 30px">
            <TicketHeader severity="low" label={MARCH.ticket.stamp} right={null} />
            <div style={{ fontSize: 44, fontWeight: 600, lineHeight: 1.15, marginBottom: 12 }}>{MARCH.ticket.title}</div>
            <div style={{ fontSize: 30, lineHeight: 1.3, color: t.ink, marginBottom: 20, ...NUM, ...enter(frame, A05.printAt + PRINT_DUR, { dist: 8 }) }}>
              {MARCH.ticket.detail}
            </div>
            <ActionBlock fontSize={32} padding={26} style={enter(frame, A05.printAt + PRINT_DUR + ms(250), { dist: 8 })}>
              {MARCH.ticket.action}
            </ActionBlock>
          </Ticket>
        </div>
      ) : null}

      <Caption from={A05.captionStagesAt} to={A05.stepsOutAt + 4} size={36} color={t.ink}>
        {MARCH.captions.stages}
      </Caption>
      <Caption from={A05.captionTicketAt} size={36} color={t.ink}>
        {MARCH.captions.ticket}
      </Caption>
    </AbsoluteFill>
  );
};
