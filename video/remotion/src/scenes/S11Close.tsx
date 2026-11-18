import { AbsoluteFill, useCurrentFrame } from "remotion";
import { enter } from "../anim";
import { Logo } from "../components/Logo";
import { LINKS } from "../data";
import type { SceneSfx } from "../sfx";
import { CONTENT_W, DARK, FAST, SANS, SIDE, SLAB, ThemeProvider, useTokens } from "../theme";

/** Frames locais da cena 11 (0:55–0:58, 0–90). */
export const S11 = {
  brandFrom: 0,
  link1From: 4,
  link2From: 7, // termina no frame 15 (8 frames de FAST) → ≥ 2,5 s na tela (75 frames)
  footerFrom: 8,
} as const;

export const sfx: SceneSfx[] = [];

const LinkIcon = ({ color }: { readonly color: string }) => (
  <svg
    width={32}
    height={32}
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    style={{ flexShrink: 0 }}
  >
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
  </svg>
);

const RepoIcon = ({ color }: { readonly color: string }) => (
  <svg
    width={32}
    height={32}
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    style={{ flexShrink: 0 }}
  >
    <circle cx="6" cy="6" r="2.5" />
    <circle cx="18" cy="7" r="2.5" />
    <circle cx="6" cy="18" r="2.5" />
    <path d="M6 8.5v7" />
    <path d="M18 9.5c0 4.5-6 3.5-12 6" />
  </svg>
);

const CloseContent = () => {
  const t = useTokens();
  const frame = useCurrentFrame();

  const brandAnim = enter(frame, S11.brandFrom, { dur: FAST, dist: 10 });
  const link1Anim = enter(frame, S11.link1From, { dur: FAST, dist: 10 });
  const link2Anim = enter(frame, S11.link2From, { dur: FAST, dist: 10 });
  const footerAnim = enter(frame, S11.footerFrom, { dur: FAST, dist: 8 });

  const linkRowStyle = {
    background: t.actionBg,
    border: `1.5px solid ${t.wineRaised}`,
    borderRadius: 8,
    padding: "20px 28px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 16,
    width: CONTENT_W,
    boxSizing: "border-box" as const,
  };

  return (
    <AbsoluteFill style={{ background: t.wine }}>
      {/* Marca + Links centralizados verticalmente no palco principal */}
      <div
        style={{
          position: "absolute",
          left: SIDE,
          top: 250,
          width: CONTENT_W,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 28,
            marginBottom: 72,
            ...brandAnim,
          }}
        >
          <Logo size={112} background={t.wineRaised} />
          <div
            style={{
              fontFamily: SLAB,
              fontWeight: 700,
              fontSize: 84,
              lineHeight: 1.06,
              color: t.onWine,
              textAlign: "center",
              whiteSpace: "nowrap",
              textWrap: "balance",
            }}
          >
            Central de Operações
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20, width: CONTENT_W }}>
          <div style={{ ...linkRowStyle, ...link1Anim }}>
            <LinkIcon color={t.onWine} />
            <span
              style={{
                fontFamily: SANS,
                fontWeight: 600,
                fontSize: 34,
                lineHeight: 1.2,
                color: t.onWine,
                whiteSpace: "nowrap",
              }}
            >
              {LINKS.app}
            </span>
          </div>

          <div style={{ ...linkRowStyle, ...link2Anim }}>
            <RepoIcon color={t.onWine} />
            <span
              style={{
                fontFamily: SANS,
                fontWeight: 600,
                fontSize: 34,
                lineHeight: 1.2,
                color: t.onWine,
                whiteSpace: "nowrap",
              }}
            >
              {LINKS.repo}
            </span>
          </div>
        </div>
      </div>

      {/* Rodapé acima de y 1230, centralizado em 2 linhas, onWine a 60% */}
      <div
        style={{
          position: "absolute",
          left: SIDE,
          top: 1124,
          width: CONTENT_W,
          display: "flex",
          justifyContent: "center",
          textAlign: "center",
          fontFamily: SANS,
          fontWeight: 400,
          fontSize: 24,
          lineHeight: 1.38,
          color: t.onWine,
          textWrap: "balance",
          ...footerAnim,
          opacity: 0.6 * Number(footerAnim.opacity ?? 1),
        }}
      >
        <span style={{ maxWidth: 820 }}>{LINKS.footer}</span>
      </div>
    </AbsoluteFill>
  );
};

/** Cena 11: Fechamento. Fundo vinho escuro #26060F, logo + marca + links + rodapé sem fade no fim. */
export const S11Close = () => (
  <ThemeProvider tokens={DARK}>
    <CloseContent />
  </ThemeProvider>
);
