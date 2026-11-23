import { AbsoluteFill, interpolate, interpolateColors, useCurrentFrame } from "remotion";
import { enter, progress } from "../../anim";
import { SceneTitle } from "../../components/Text";
import type { SceneSfx } from "../../sfx";
import { CONTENT_W, EASE_OUT, FAST, ms, NUM, SANS, SIDE, SLAB, useTokens } from "../../theme";
import { GRAPH } from "../data";

/** Frames locais da cena 4 (0:18–0:28, 0–300). */
export const A04 = {
  swapAt: 150,
  nodeAt: 10,
  nodeStep: 10,
  flowAt: 44,
  flowStep: 20,
  serverAt: 102,
  llmNodeAt: 156,
  llmFlowAt: 164,
  llmLabelAt: 172,
  stripAt: 196,
  rowAt: 204,
  rowStep: 8,
  noteAt: 222,
} as const;

export const sfx: SceneSfx[] = [
  ...[0, 1, 2].map((i) => ({ frame: A04.flowAt + i * A04.flowStep, kind: "tick" as const })),
  { frame: A04.llmFlowAt + 12, kind: "tick" },
  ...GRAPH.compare.map((_, i) => ({ frame: A04.rowAt + i * A04.rowStep + 6, kind: "tick" as const })),
];

// Geometria: 4 nós empilhados à esquerda, marcas à direita, faixa comparativa embaixo.
const NODE = { x: SIDE, w: 640, h: 112, gap: 22, top: 356 };
const nodeTop = (i: number) => NODE.top + i * (NODE.h + NODE.gap);
const SIDE_X = NODE.x + NODE.w + 26;
const WIRE_X = NODE.x + 44;

/** Momento em que cada nó acende (o "token" do grafo chega nele). */
const litAt = (i: number) => (i < 3 ? A04.flowAt + i * A04.flowStep : A04.llmFlowAt + 12);

const GraphNode = ({ i }: { readonly i: number }) => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const node = GRAPH.nodes[i];
  const llm = i === 3;
  const lit = progress(frame, litAt(i), FAST);
  const appear = llm ? A04.llmNodeAt : A04.nodeAt + i * A04.nodeStep;
  return (
    <div
      style={{
        position: "absolute",
        left: NODE.x,
        top: nodeTop(i),
        width: NODE.w,
        height: NODE.h,
        boxSizing: "border-box",
        padding: "16px 22px",
        borderRadius: 8,
        background: llm ? t.wine : t.surface,
        border: `2px solid ${llm ? t.wine : interpolateColors(lit, [0, 1], [t.rule, t.series])}`,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        gap: 6,
        fontFamily: SANS,
        ...enter(frame, appear, { dist: 10 }),
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <span style={{ fontSize: 34, fontWeight: 700, lineHeight: 1.1, color: llm ? t.onWine : t.ink }}>{node.id}</span>
        <span
          style={{
            height: 40,
            display: "inline-flex",
            alignItems: "center",
            padding: "0 12px",
            borderRadius: 4,
            background: llm ? t.wineRaised : t.sunken,
            border: llm ? "none" : `1px solid ${t.rule}`,
            fontSize: 28,
            fontWeight: 500,
            color: llm ? t.onWine : t.muted,
            whiteSpace: "nowrap",
          }}
        >
          {node.tag}
        </span>
      </div>
      <div style={{ fontSize: 30, lineHeight: 1.15, color: llm ? t.onWine : t.muted, opacity: llm ? 0.85 : 1 }}>{node.text}</div>
    </div>
  );
};

/** Fio entre o nó `i` e o próximo, desenhado de cima para baixo, com a ponta da seta. */
const Wire = ({ i }: { readonly i: number }) => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const at = i < 2 ? A04.nodeAt + (i + 1) * A04.nodeStep : A04.llmNodeAt;
  const p = progress(frame, at, FAST);
  const y = nodeTop(i) + NODE.h;
  return (
    <svg width={24} height={NODE.gap} style={{ position: "absolute", left: WIRE_X - 12, top: y, overflow: "visible" }}>
      <path d={`M 12 0 V ${NODE.gap * p}`} stroke={t.series} strokeWidth={3} />
      <path d={`M 5 ${NODE.gap - 9} L 12 ${NODE.gap - 1} L 19 ${NODE.gap - 9}`} fill="none" stroke={t.series} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" opacity={p} />
    </svg>
  );
};

/** Ponto que percorre o grafo: mostra a ordem fixa da investigação. */
const FlowDot = () => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const stops = [0, 1, 2].map((i) => ({ f: litAt(i), y: nodeTop(i) + NODE.h / 2 }));
  const synthStart = A04.llmFlowAt;
  let y: number;
  let visible = true;
  if (frame < stops[0].f - 6) {
    visible = false;
    y = stops[0].y;
  } else if (frame <= stops[2].f) {
    y = interpolate(frame, stops.map((s) => s.f), stops.map((s) => s.y), { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE_OUT });
  } else if (frame < synthStart) {
    y = stops[2].y;
    visible = frame < stops[2].f + 14;
  } else {
    y = interpolate(frame, [synthStart, litAt(3)], [stops[2].y, nodeTop(3) + NODE.h / 2], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE_OUT });
    visible = frame < litAt(3) + 10;
  }
  if (!visible) return null;
  return (
    <div
      style={{
        position: "absolute",
        left: NODE.x + NODE.w - 34,
        top: y - 9,
        width: 18,
        height: 18,
        borderRadius: "50%",
        background: t.series,
      }}
    />
  );
};

/** Cena 4: o grafo LangGraph. Três nós determinísticos no servidor e uma única chamada ao LLM. */
export const A04Graph = () => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const bracket = progress(frame, A04.serverAt, ms(300));
  const bracketTop = nodeTop(0) + 8;
  const bracketBottom = nodeTop(2) + NODE.h - 8;

  return (
    <AbsoluteFill style={{ background: t.field }}>
      <SceneTitle from={2} to={A04.swapAt}>
        <span>
          Por que mudou?
          <br />O servidor investiga.
        </span>
      </SceneTitle>
      <SceneTitle from={A04.swapAt}>O LLM só redige, com a prova.</SceneTitle>

      {[0, 1, 2].map((i) => (
        <Wire key={`w${i}`} i={i} />
      ))}
      {[0, 1, 2, 3].map((i) => (
        <GraphNode key={i} i={i} />
      ))}
      <FlowDot />

      {/* Chave dos três nós do servidor */}
      <svg width={30} height={bracketBottom - bracketTop} style={{ position: "absolute", left: SIDE_X, top: bracketTop, overflow: "visible", opacity: bracket > 0 ? 1 : 0 }}>
        <path
          d={`M 0 0 H 14 V ${(bracketBottom - bracketTop) * bracket} ${bracket >= 1 ? "H 0" : ""}`}
          fill="none"
          stroke={t.series}
          strokeWidth={3}
          strokeLinejoin="round"
        />
      </svg>
      <div
        style={{
          position: "absolute",
          left: SIDE_X + 36,
          top: (bracketTop + bracketBottom) / 2 - 70,
          width: SIDE + CONTENT_W - (SIDE_X + 36),
          display: "flex",
          flexDirection: "column",
          gap: 8,
          ...enter(frame, A04.serverAt + 4, { dist: 8, axis: "x" }),
        }}
      >
        <span style={{ fontFamily: SLAB, fontWeight: 700, fontSize: 60, lineHeight: 1, color: t.series, ...NUM }}>{GRAPH.server.figure}</span>
        <div style={{ fontFamily: SANS, fontSize: 28, lineHeight: 1.2, color: t.muted }}>
          {GRAPH.server.line.map((l) => (
            <div key={l}>{l}</div>
          ))}
        </div>
      </div>

      {/* Marca da única chamada ao modelo */}
      <div
        style={{
          position: "absolute",
          left: SIDE_X + 36,
          top: nodeTop(3) + 14,
          display: "flex",
          flexDirection: "column",
          gap: 6,
          ...enter(frame, A04.llmLabelAt, { dist: 8, axis: "x" }),
        }}
      >
        <span style={{ fontFamily: SLAB, fontWeight: 700, fontSize: 44, lineHeight: 1, color: t.series, ...NUM }}>{GRAPH.llm.figure}</span>
        <span style={{ fontFamily: SANS, fontSize: 28, lineHeight: 1.2, color: t.muted }}>{GRAPH.llm.line}</span>
      </div>

      {/* Faixa comparativa: loop de tools × grafo */}
      <div
        style={{
          position: "absolute",
          left: SIDE,
          top: 892,
          width: CONTENT_W,
          boxSizing: "border-box",
          background: t.surface,
          border: `1.5px solid ${t.rule}`,
          borderRadius: 8,
          padding: "18px 26px 20px",
          fontFamily: SANS,
          ...enter(frame, A04.stripAt, { dist: 12 }),
        }}
      >
        <div style={{ display: "grid", gridTemplateColumns: "1fr 210px 170px", alignItems: "baseline", rowGap: 6 }}>
          <span />
          <span style={{ fontSize: 28, color: t.muted }}>{GRAPH.compareHead.before}</span>
          <span style={{ fontSize: 28, fontWeight: 700, color: t.ink }}>{GRAPH.compareHead.after}</span>
          {GRAPH.compare.map((row, i) => {
            const at = A04.rowAt + i * A04.rowStep;
            return [
              <span key={`l${i}`} style={{ fontSize: 32, fontWeight: 500, color: t.ink, ...enter(frame, at, { dist: 6 }) }}>
                {row.label}
              </span>,
              <span key={`b${i}`} style={{ fontFamily: SLAB, fontWeight: 600, fontSize: 46, color: t.muted, ...NUM, ...enter(frame, at, { dist: 6 }) }}>
                {row.before}
              </span>,
              <span key={`a${i}`} style={{ fontFamily: SLAB, fontWeight: 700, fontSize: 56, color: t.good, ...NUM, ...enter(frame, at + 6, { dist: 8 }) }}>
                {row.after}
              </span>,
            ];
          })}
        </div>
        <div style={{ marginTop: 8, fontSize: 28, color: t.muted, ...enter(frame, A04.noteAt, { dist: 6 }) }}>{GRAPH.compareNote}</div>
      </div>
    </AbsoluteFill>
  );
};
