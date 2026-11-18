import type { CSSProperties, ReactNode } from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { EASE_TICKET, ms, SLAB, SANS, useTokens, CONTENT_W } from "../theme";
import { SEVERITY_WORD, SeverityMark, type Severity } from "./SeverityMark";

/**
 * Picote do topo. O app usa meio-furos de 5 px a cada 14 px; no vídeo a escala
 * sobe 1,4× (7 px a cada 20 px) para o recorte continuar visível a ~550 px de
 * largura no desktop do LinkedIn.
 */
export const PICOTE = { radius: 7, step: 20 };
const picoteMask = `radial-gradient(circle ${PICOTE.radius}px at ${PICOTE.step / 2}px 0, #0000 98%, #000) 0 0 / ${PICOTE.step}px 100% repeat-x`;

/** Frames da animação "printing" (280 ms). */
export const PRINT_DUR = ms(280);

/**
 * Progresso 0 → 1 da comanda "saindo da impressora", a partir de `start` (frame local).
 * Use para sincronizar outros elementos com a impressão.
 */
export const usePrint = (start: number | undefined) => {
  const frame = useCurrentFrame();
  if (start === undefined) return 1;
  return interpolate(frame, [start, start + PRINT_DUR], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE_TICKET,
  });
};

/**
 * Casca da comanda: papel `surface`, picote no topo, cantos 0 0 8 8.
 * `printAt` (frame local) anima a saída da impressora: desce de −6 px e o papel
 * é revelado de cima para baixo. Sem `printAt`, a comanda já está impressa.
 */
export const Ticket = ({
  children,
  width = CONTENT_W,
  printAt,
  padding = "30px 32px 28px",
  style,
}: {
  readonly children: ReactNode;
  readonly width?: number | string;
  readonly printAt?: number;
  readonly padding?: CSSProperties["padding"];
  readonly style?: CSSProperties;
}) => {
  const t = useTokens();
  const p = usePrint(printAt);
  return (
    <div
      style={{
        width,
        clipPath: printAt === undefined ? undefined : `inset(0 0 ${(1 - p) * 100}% 0)`,
        translate: `0px ${(1 - p) * -6}px`,
        opacity: interpolate(p, [0, 1], [0.45, 1]),
        ...style,
      }}
    >
      <div
        style={{
          background: t.surface,
          borderRadius: "0 0 8px 8px",
          WebkitMask: picoteMask,
          mask: picoteMask,
          padding,
          boxSizing: "border-box",
          fontFamily: SANS,
          color: t.ink,
        }}
      >
        {children}
      </div>
    </div>
  );
};

/** Carimbo `● Nº 01 · SLA` em Zilla Slab caixa alta. */
export const Stamp = ({
  severity,
  label,
  size = 28,
  color,
  markScale = 2.2,
}: {
  readonly severity: Severity;
  /** Ex.: "Nº 01 · SLA" */
  readonly label: string;
  readonly size?: number;
  readonly color?: string;
  readonly markScale?: number;
}) => {
  const t = useTokens();
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 14 }}>
      <SeverityMark severity={severity} scale={markScale} />
      <span
        style={{
          fontFamily: SLAB,
          fontWeight: 700,
          fontSize: size,
          letterSpacing: "0.03em",
          textTransform: "uppercase",
          color: color ?? t.ink,
          lineHeight: 1,
          fontVariantNumeric: "lining-nums tabular-nums",
        }}
      >
        {label}
      </span>
    </span>
  );
};

/** Cabeçalho da comanda aberta: carimbo à esquerda, severidade por extenso à direita, fio tracejado embaixo. */
export const TicketHeader = ({
  severity,
  label,
  right,
}: {
  readonly severity: Severity;
  readonly label: string;
  /** Texto à direita; padrão é a palavra da severidade (CRÍTICO, ATENÇÃO…). Passe null para omitir. */
  readonly right?: string | null;
}) => {
  const t = useTokens();
  const word = right === undefined ? SEVERITY_WORD[severity] : right;
  const color = severity === "high" ? t.crit : severity === "medium" ? t.warn : t.muted;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        paddingBottom: 22,
        marginBottom: 26,
        borderBottom: `1.5px dashed ${t.rule}`,
      }}
    >
      <Stamp severity={severity} label={label} />
      {word ? (
        <span
          style={{
            fontFamily: SLAB,
            fontWeight: 700,
            fontSize: 28,
            letterSpacing: "0.03em",
            textTransform: "uppercase",
            color,
          }}
        >
          {word}
        </span>
      ) : null}
    </div>
  );
};

/**
 * Comanda fechada (stub) da fila: linha 1 = carimbo + número · referência,
 * linha 2 = título. 936 × 116 px.
 */
export const TicketStub = ({
  severity,
  number,
  category,
  title,
  figure,
  figureRef,
  printAt,
  height = 116,
  style,
}: {
  readonly severity: Severity;
  readonly number: string;
  readonly category: string;
  readonly title: string;
  readonly figure: string;
  readonly figureRef?: string;
  readonly printAt?: number;
  readonly height?: number;
  readonly style?: CSSProperties;
}) => {
  const t = useTokens();
  return (
    <Ticket printAt={printAt} padding="22px 28px 0" style={style}>
      <div style={{ height: height - 22, display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 16 }}>
          <Stamp severity={severity} label={`Nº ${number} · ${category}`} size={26} markScale={2} />
          <span style={{ whiteSpace: "nowrap", display: "inline-flex", alignItems: "baseline", gap: 10 }}>
            <span
              style={{
                fontFamily: SLAB,
                fontWeight: 700,
                fontSize: 34,
                fontVariantNumeric: "lining-nums tabular-nums",
                color: t.ink,
                lineHeight: 1,
              }}
            >
              {figure}
            </span>
            {figureRef ? (
              <span style={{ fontSize: 26, color: t.muted, lineHeight: 1 }}>· {figureRef}</span>
            ) : null}
          </span>
        </div>
        <div
          style={{
            fontSize: 32,
            fontWeight: 600,
            lineHeight: 1.15,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {title}
        </div>
      </div>
    </Ticket>
  );
};
