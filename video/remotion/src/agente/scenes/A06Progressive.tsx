import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { enter, exit, mergeStyles, progress } from "../../anim";
import { ActionBlock } from "../../components/ActionBlock";
import { Caption, SceneTitle } from "../../components/Text";
import { PRINT_DUR, Ticket, TicketHeader } from "../../components/Ticket";
import type { SceneSfx } from "../../sfx";
import { CONTENT_W, EASE_BOUNCE, FAST, ms, SANS, SIDE, useTokens } from "../../theme";
import { MARCH, PROGRESSIVE } from "../data";

/** Frames locais da cena 6 (0:35–0:43, 0–240). */
export const A06 = {
  swapAt: 120,
  panelAt: 0,
  bubbleAt: 6,
  printAt: 16,
  noteAt: 16 + PRINT_DUR,
  upgradeAt: 80,
  panelOutAt: 112,
  guardAt: 128,
  guardStep: 8,
  captionAt: 160,
} as const;

export const sfx: SceneSfx[] = [
  { frame: A06.printAt, kind: "impressora" },
  { frame: A06.upgradeAt, kind: "notificacao" },
  ...PROGRESSIVE.guards.map((_, i) => ({ frame: A06.guardAt + i * A06.guardStep, kind: "clique" as const })),
];

const SHIMMER = 48; // ciclo de 1,6 s

type GuardIcon = (typeof PROGRESSIVE.guards)[number]["icon"];

const Icon = ({ kind, color }: { readonly kind: GuardIcon; readonly color: string }) => {
  const common = { width: 40, height: 40, viewBox: "0 0 24 24", fill: "none", stroke: color, strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  switch (kind) {
    case "clock":
      return (
        <svg {...common}>
          <circle cx="12" cy="13" r="8" />
          <path d="M12 9v4l2.5 2" />
          <path d="M9.5 2.5h5" />
        </svg>
      );
    case "breaker":
      return (
        <svg {...common}>
          <path d="M13 2 4.5 13.5H12l-1 8.5 8.5-11.5H12l1-8.5Z" />
        </svg>
      );
    case "gate":
      return (
        <svg {...common}>
          <rect x="7" y="2.5" width="10" height="19" rx="3" />
          <circle cx="12" cy="7.5" r="1.6" />
          <circle cx="12" cy="12" r="1.6" />
          <circle cx="12" cy="16.5" r="1.6" />
        </svg>
      );
    case "shield":
      return (
        <svg {...common}>
          <path d="M12 2.5 4.5 5.5v6c0 4.6 3.2 8.2 7.5 10 4.3-1.8 7.5-5.4 7.5-10v-6L12 2.5Z" />
          <path d="m8.8 12 2.2 2.2 4.4-4.6" />
        </svg>
      );
  }
};

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

/** Nota de leitura do app: primeiro "pelas regras" com brilho, depois "do modelo" com check. */
const ReadingNote = () => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const swap = progress(frame, A06.upgradeAt, FAST);
  const cycle = Math.max(0, frame - A06.noteAt) % SHIMMER;
  const pos = interpolate(cycle, [0, SHIMMER], [110, -20]);
  const check = interpolate(progress(frame, A06.upgradeAt, ms(300), EASE_BOUNCE), [0, 1], [0.5, 1]);
  return (
    <div style={{ position: "relative", minHeight: 76, fontSize: 30, lineHeight: 1.25, ...enter(frame, A06.noteAt, { dur: FAST, dist: 6 }) }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          fontWeight: 600,
          opacity: 1 - swap,
          backgroundImage: `linear-gradient(90deg, ${t.muted} 0%, ${t.muted} 35%, ${t.ink} 50%, ${t.muted} 65%, ${t.muted} 100%)`,
          backgroundSize: "220% 100%",
          backgroundPosition: `${pos}% 0%`,
          WebkitBackgroundClip: "text",
          backgroundClip: "text",
          color: "transparent",
        }}
      >
        {PROGRESSIVE.rulesNote}
      </div>
      {swap > 0 ? (
        <div style={{ position: "absolute", inset: 0, display: "flex", gap: 14, alignItems: "flex-start", opacity: swap, color: t.ink }}>
          <svg width={34} height={34} viewBox="0 0 24 24" fill="none" stroke={t.good} strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, scale: check, marginTop: 2 }}>
            <circle cx="12" cy="12" r="10" />
            <path d="m7.5 12.5 3 3 6-6.5" />
          </svg>
          <span>{PROGRESSIVE.llmNote}</span>
        </div>
      ) : null}
    </div>
  );
};

/** Ato A: a comanda pelas regras aparece na hora e o modelo atualiza a leitura depois. */
const ProgressiveChat = () => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const style = mergeStyles(enter(frame, A06.panelAt, { dur: ms(400), dist: 12, axis: "x" }), exit(frame, A06.panelOutAt, { dur: ms(260), dist: -14 }));
  const sweep = progress(frame, A06.upgradeAt - 2, ms(500));
  const innerW = CONTENT_W - 56;
  return (
    <div
      style={{
        position: "absolute",
        left: SIDE,
        top: 356,
        width: CONTENT_W,
        height: 790,
        boxSizing: "border-box",
        background: t.surface,
        border: `1.5px solid ${t.rule}`,
        borderRadius: 8,
        overflow: "hidden",
        fontFamily: SANS,
        color: t.ink,
        ...style,
      }}
    >
      <div style={{ padding: "18px 28px 16px", borderBottom: `1px solid ${t.rule}`, display: "flex", alignItems: "center", gap: 12 }}>
        <BotIcon color={t.series} />
        <span style={{ fontSize: 32, fontWeight: 700 }}>{PROGRESSIVE.header}</span>
      </div>

      <div style={{ background: t.field, height: "100%", padding: "20px 28px", boxSizing: "border-box", display: "flex", flexDirection: "column", gap: 18 }}>
        <div
          style={{
            alignSelf: "flex-end",
            background: t.surface,
            border: `1px solid ${t.rule}`,
            borderRadius: 8,
            padding: "14px 22px",
            fontSize: 30,
            fontWeight: 500,
            ...enter(frame, A06.bubbleAt, { dur: ms(280), dist: 10 }),
          }}
        >
          {PROGRESSIVE.question}
        </div>

        {frame >= A06.printAt ? (
          <div style={{ position: "relative", width: innerW }}>
            <Ticket width={innerW} printAt={A06.printAt} padding="22px 26px 24px">
              <TicketHeader severity="low" label={MARCH.ticket.stamp} right={null} />
              <div style={{ fontSize: 40, fontWeight: 600, lineHeight: 1.15, marginBottom: 14 }}>{MARCH.ticket.title}</div>
              <ActionBlock fontSize={29} padding={20}>
                {MARCH.ticket.action}
              </ActionBlock>
            </Ticket>
            {/* Brilho que passa quando a leitura do modelo chega */}
            {sweep > 0 && sweep < 1 ? (
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  pointerEvents: "none",
                  background: `linear-gradient(100deg, transparent ${sweep * 130 - 30}%, ${t.seriesSoft} ${sweep * 130 - 15}%, transparent ${sweep * 130}%)`,
                  opacity: 0.35,
                }}
              />
            ) : null}
          </div>
        ) : null}

        {frame >= A06.noteAt ? <ReadingNote /> : null}
      </div>
    </div>
  );
};

/** Ato B: os quatro limites que seguram o agente em produção. */
const Guards = () => {
  const t = useTokens();
  const frame = useCurrentFrame();
  return (
    <div style={{ position: "absolute", left: SIDE, top: 364, width: CONTENT_W, display: "flex", flexDirection: "column", gap: 16, fontFamily: SANS }}>
      {PROGRESSIVE.guards.map((g, i) => (
        <div
          key={g.title}
          style={{
            height: 158,
            boxSizing: "border-box",
            display: "flex",
            alignItems: "center",
            gap: 26,
            padding: "0 28px",
            background: t.surface,
            border: `1.5px solid ${t.rule}`,
            borderRadius: 8,
            ...enter(frame, A06.guardAt + i * A06.guardStep, { dist: 10 }),
          }}
        >
          <div style={{ width: 76, height: 76, flexShrink: 0, borderRadius: 8, background: t.sunken, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Icon kind={g.icon} color={t.series} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={{ fontSize: 38, fontWeight: 700, lineHeight: 1.1, color: t.ink }}>{g.title}</span>
            <span style={{ fontSize: 31, lineHeight: 1.2, color: t.muted }}>{g.text}</span>
          </div>
        </div>
      ))}
    </div>
  );
};

/** Cena 6: leitura progressiva (regras na hora, modelo depois) e os limites de produção. */
export const A06Progressive = () => {
  const t = useTokens();
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: t.field }}>
      <SceneTitle from={2} to={A06.swapAt}>
        <span>
          Resposta na hora.
          <br />O modelo aprofunda depois.
        </span>
      </SceneTitle>
      <SceneTitle from={A06.swapAt}>
        <span>
          Se o modelo falhar,
          <br />a operação não para.
        </span>
      </SceneTitle>

      {frame < A06.panelOutAt + ms(260) ? <ProgressiveChat /> : null}
      {frame >= A06.guardAt - 2 ? <Guards /> : null}

      <Caption from={A06.captionAt} size={36} color={t.ink}>
        {PROGRESSIVE.caption}
      </Caption>
    </AbsoluteFill>
  );
};
