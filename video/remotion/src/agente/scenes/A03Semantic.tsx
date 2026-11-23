import { AbsoluteFill, interpolate, interpolateColors, useCurrentFrame } from "remotion";
import { enter, progress } from "../../anim";
import { Caption, SceneTitle } from "../../components/Text";
import type { SceneSfx } from "../../sfx";
import { br, CONTENT_W, EASE_BOUNCE, EASE_OUT, FAST, ms, NUM, SANS, SIDE, SLAB, useTokens } from "../../theme";
import { SEMANTIC } from "../data";

/** Frames locais da cena 3 (0:11–0:18, 0–210). */
export const A03 = {
  titleAt: 4,
  barAt: 8,
  typeStart: 12,
  typeEnd: 40,
  cardAt: 44,
  rowAt: 54,
  rowStep: 10,
  countAt: 96,
  countStep: 4,
  countDur: ms(800),
  sealAt: 120,
  captionAt: 128,
} as const;

export const sfx: SceneSfx[] = SEMANTIC.maps.map((_, i) => ({ frame: A03.rowAt + i * A03.rowStep, kind: "tick" as const }));

const SearchIcon = ({ color }: { readonly color: string }) => (
  <svg width={34} height={34} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2.2} strokeLinecap="round">
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);

const CheckIcon = ({ color, scale }: { readonly color: string; readonly scale: number }) => (
  <svg width={36} height={36} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" style={{ scale }}>
    <circle cx="12" cy="12" r="10" />
    <path d="m7.5 12.5 3 3 6-6.5" />
  </svg>
);

/** Pergunta digitada; cada termo reconhecido ganha sublinhado `series` quando a linha dele entra no cartão. */
const TypedQuery = () => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const q = SEMANTIC.query;
  const typed = Math.floor(interpolate(frame, [A03.typeStart, A03.typeEnd], [0, q.length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const terms = SEMANTIC.maps.map((m) => m.term);

  // Fatia a pergunta em termos e conectores, preservando a ordem.
  const parts: { text: string; term: number }[] = [];
  let rest = q;
  while (rest.length) {
    const hit = terms
      .map((term, i) => ({ i, at: rest.indexOf(term) }))
      .filter((h) => h.at >= 0)
      .sort((a, b) => a.at - b.at)[0];
    if (!hit) {
      parts.push({ text: rest, term: -1 });
      break;
    }
    if (hit.at > 0) parts.push({ text: rest.slice(0, hit.at), term: -1 });
    parts.push({ text: terms[hit.i], term: hit.i });
    rest = rest.slice(hit.at + terms[hit.i].length);
  }

  let shown = 0;
  return (
    <span style={{ whiteSpace: "pre" }}>
      {parts.map((p, k) => {
        const visible = p.text.slice(0, Math.max(0, typed - shown));
        shown += p.text.length;
        if (p.term < 0) return <span key={k}>{visible}</span>;
        const mark = progress(frame, A03.rowAt + p.term * A03.rowStep, FAST);
        return (
          <span
            key={k}
            style={{
              color: interpolateColors(mark, [0, 1], [t.ink, t.series]),
              fontWeight: mark > 0.5 ? 700 : 500,
              textDecorationLine: mark > 0 ? "underline" : "none",
              textDecorationColor: t.series,
              textDecorationThickness: `${Math.max(1, mark * 5)}px`,
              textUnderlineOffset: 10,
            }}
          >
            {visible}
          </span>
        );
      })}
      {frame >= A03.typeStart && typed < q.length ? (
        <span style={{ display: "inline-block", width: 3, height: 36, background: t.series, verticalAlign: "-6px", marginLeft: 2 }} />
      ) : null}
    </span>
  );
};

/** Cena 3: a camada semântica traduz a fala do operador em chaves que o backend valida. */
export const A03Semantic = () => {
  const t = useTokens();
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{ background: t.field }}>
      <SceneTitle from={A03.titleAt}>Agora: camada semântica única.</SceneTitle>

      {/* Campo de pergunta do operador */}
      <div
        style={{
          position: "absolute",
          left: SIDE,
          top: 360,
          width: CONTENT_W,
          height: 92,
          boxSizing: "border-box",
          background: t.surface,
          border: `1.5px solid ${t.ink}`,
          borderRadius: 8,
          padding: "0 26px",
          display: "flex",
          alignItems: "center",
          gap: 18,
          fontFamily: SANS,
          fontSize: 36,
          fontWeight: 500,
          color: t.ink,
          ...enter(frame, A03.barAt, { dist: 10 }),
        }}
      >
        <SearchIcon color={t.muted} />
        <TypedQuery />
      </div>

      {/* Fio do campo até o arquivo */}
      <div
        style={{
          position: "absolute",
          left: SIDE + 60,
          top: 452,
          width: 3,
          height: 36 * progress(frame, A03.cardAt - 4, FAST),
          background: t.series,
        }}
      />

      {/* semantic.toml */}
      <div
        style={{
          position: "absolute",
          left: SIDE,
          top: 488,
          width: CONTENT_W,
          boxSizing: "border-box",
          background: t.surface,
          border: `1.5px solid ${t.rule}`,
          borderRadius: 8,
          padding: "26px 28px 28px",
          fontFamily: SANS,
          color: t.ink,
          ...enter(frame, A03.cardAt, { dist: 12 }),
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 16, marginBottom: 22 }}>
          <span style={{ fontSize: 36, fontWeight: 700 }}>{SEMANTIC.file}</span>
          <span style={{ fontSize: 28, color: t.muted }}>{SEMANTIC.note}</span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16, paddingBottom: 26, borderBottom: `1px solid ${t.rule}` }}>
          {SEMANTIC.maps.map((m, i) => {
            const at = A03.rowAt + i * A03.rowStep;
            const arrow = progress(frame, at + 2, FAST);
            return (
              <div key={m.term} style={{ display: "flex", alignItems: "center", gap: 16, height: 68, ...enter(frame, at, { dist: 8 }) }}>
                <span
                  style={{
                    width: 160,
                    flexShrink: 0,
                    height: 60,
                    boxSizing: "border-box",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    borderRadius: 4,
                    background: t.sunken,
                    border: `1px solid ${t.rule}`,
                    fontSize: 30,
                    fontWeight: 500,
                  }}
                >
                  {m.term}
                </span>
                <svg width={44} height={24} viewBox="0 0 44 24" style={{ flexShrink: 0 }}>
                  <path d={`M 2 12 H ${2 + 34 * arrow}`} stroke={t.series} strokeWidth={3} strokeLinecap="round" />
                  <path d="M 30 5 L 38 12 L 30 19" fill="none" stroke={t.series} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" opacity={arrow} />
                </svg>
                <span
                  style={{
                    flexShrink: 0,
                    height: 60,
                    boxSizing: "border-box",
                    display: "inline-flex",
                    alignItems: "center",
                    padding: "0 18px",
                    borderRadius: 4,
                    background: t.surface,
                    border: `2px solid ${t.series}`,
                    fontSize: 30,
                    fontWeight: 700,
                    color: t.series,
                    whiteSpace: "nowrap",
                  }}
                >
                  {m.key}
                </span>
                <span style={{ fontSize: 28, color: t.muted, whiteSpace: "nowrap" }}>{m.detail}</span>
              </div>
            );
          })}
        </div>

        {/* Tamanho da camada */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 12, paddingTop: 24 }}>
          {SEMANTIC.counts.map((c, i) => {
            const at = A03.countAt + i * A03.countStep;
            const n = Math.round(c.n * progress(frame, at, A03.countDur, EASE_OUT));
            return (
              <div key={c.label} style={{ display: "flex", flexDirection: "column", gap: 6, ...enter(frame, at, { dist: 8 }) }}>
                <span style={{ fontFamily: SLAB, fontWeight: 700, fontSize: 68, lineHeight: 1, color: t.series, ...NUM }}>{br(n)}</span>
                <span style={{ fontSize: 28, color: t.muted, whiteSpace: "nowrap" }}>{c.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Selo: a camada é conferida com o SQL nos testes */}
      <div
        style={{
          position: "absolute",
          left: SIDE,
          top: 1044,
          display: "flex",
          alignItems: "center",
          gap: 16,
          fontFamily: SANS,
          fontSize: 34,
          fontWeight: 600,
          color: t.good,
          ...enter(frame, A03.sealAt, { dist: 8 }),
        }}
      >
        <CheckIcon color={t.good} scale={interpolate(progress(frame, A03.sealAt, ms(300), EASE_BOUNCE), [0, 1], [0.6, 1])} />
        {SEMANTIC.seal}
      </div>

      <Caption from={A03.captionAt} size={36} color={t.ink}>
        Sem SQL livre. Sem média de cabeça.
      </Caption>
    </AbsoluteFill>
  );
};
