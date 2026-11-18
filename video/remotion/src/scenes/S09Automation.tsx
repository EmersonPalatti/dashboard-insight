import { AbsoluteFill, useCurrentFrame } from "remotion";
import { enter, exit, mergeStyles } from "../anim";
import { ChatBubble } from "../components/s09-ChatBubble";
import { FlowConnector, FlowNode, type FlowIconKind } from "../components/s09-FlowNode";
import { Caption, SceneTitle } from "../components/Text";
import { BRIEFING } from "../data";
import type { SceneSfx } from "../sfx";
import { CONTENT_W, MEDIUM, ms, NUM, SIDE, SLAB, useTokens } from "../theme";

/** Frames locais da cena 9 (0:45–0:51, 0–180). */
export const S09 = {
  flowExit: 56,
  phoneEnter: 60,
  msg1: 74,
  msg2: 104,
  msg3: 134,
  titleTo: 90,
  captionFrom: 90,
} as const;

export const sfx: SceneSfx[] = [
  { frame: S09.msg1, kind: "notificacao" },
  { frame: S09.msg2, kind: "notificacao" },
  { frame: S09.msg3, kind: "notificacao" },
];

const FLOW_NODES: { width: number; icon: FlowIconKind; enterAt: number }[] = [
  { width: 194, icon: "clock", enterAt: 4 },
  { width: 154, icon: "api", enterAt: 16 },
  { width: 246, icon: "route", enterAt: 28 },
  { width: 192, icon: "send", enterAt: 40 },
];

const CONNECTOR_STARTS = [10, 22, 34];

/** Cena 9: Automação diária. Relógio 08:00 + fluxo n8n -> celular com briefing e roteamento. */
export const S09Automation = () => {
  const t = useTokens();
  const frame = useCurrentFrame();

  const part1Exit = exit(frame, S09.flowExit, { dur: ms(200), dist: -10 });
  const clockAnim = mergeStyles(enter(frame, 0, { dur: ms(280), dist: 10 }), part1Exit);
  const phoneAnim = enter(frame, S09.phoneEnter, { dur: MEDIUM, dist: 12 });

  const msgFrames = [S09.msg1, S09.msg2, S09.msg3];

  return (
    <AbsoluteFill style={{ background: t.field }}>
      {/* Parte 1 (0–60): relógio 08:00 + fluxo horizontal de 4 nós */}
      {frame < 64 ? (
        <div
          style={{
            position: "absolute",
            left: SIDE,
            top: 430,
            width: CONTENT_W,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 48,
          }}
        >
          <div
            style={{
              background: t.surface,
              border: `1px solid ${t.rule}`,
              borderRadius: 8,
              padding: "22px 52px",
              display: "inline-flex",
              alignItems: "center",
              gap: 20,
              ...clockAnim,
            }}
          >
            <span
              style={{
                width: 14,
                height: 14,
                borderRadius: "50%",
                background: t.series,
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontFamily: SLAB,
                fontWeight: 700,
                fontSize: 104,
                lineHeight: 1,
                color: t.ink,
                letterSpacing: "0.02em",
                ...NUM,
              }}
            >
              {BRIEFING.clock}
            </span>
          </div>

          <div
            style={{
              width: CONTENT_W,
              display: "flex",
              alignItems: "center",
              ...part1Exit,
            }}
          >
            {BRIEFING.flow.map((label, i) => {
              const cfg = FLOW_NODES[i];
              return (
                <div key={label} style={{ display: "flex", alignItems: "center" }}>
                  <FlowNode label={label} icon={cfg.icon} width={cfg.width} enterAt={cfg.enterAt} />
                  {i < BRIEFING.flow.length - 1 ? (
                    <FlowConnector width={50} from={CONNECTOR_STARTS[i]} dur={7} />
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      {/* Parte 2 (60–180): celular neutro com 3 balões genéricos */}
      {frame >= S09.phoneEnter ? (
        <div
          style={{
            position: "absolute",
            left: 110,
            top: 356,
            width: 860,
            height: 778,
            boxSizing: "border-box",
            background: t.surface,
            border: `2px solid ${t.rule}`,
            borderRadius: 36,
            padding: "20px 20px 24px",
            display: "flex",
            flexDirection: "column",
            ...phoneAnim,
          }}
        >
          <div
            style={{
              width: 88,
              height: 6,
              borderRadius: 3,
              background: t.rule,
              alignSelf: "center",
              marginBottom: 16,
              flexShrink: 0,
            }}
          />
          <div
            style={{
              flex: 1,
              background: t.field,
              border: `1px solid ${t.rule}`,
              borderRadius: 20,
              overflow: "hidden",
              padding: "18px 20px",
              position: "relative",
            }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
            >
              {BRIEFING.messages.map((msg, i) =>
                frame >= msgFrames[i] ? (
                  <ChatBubble key={msg.heading} heading={msg.heading} lines={msg.lines} enterAt={msgFrames[i]} />
                ) : null,
              )}
            </div>
          </div>
        </div>
      ) : null}

      <SceneTitle from={0} to={S09.titleTo} size={64}>
        Todo dia às 8h, o&nbsp;briefing chega.
      </SceneTitle>

      <Caption from={S09.captionFrom} size={36}>
        Cada alerta vai direto para quem resolve.
      </Caption>
    </AbsoluteFill>
  );
};
