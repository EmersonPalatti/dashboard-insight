// Ajudantes de entrada e saída. Todos recebem o frame local da cena.
import type { CSSProperties } from "react";
import { interpolate } from "remotion";
import { EASE_IN, EASE_OUT, MEDIUM, ms } from "./theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** 0 → 1 entre `start` e `start + dur`, com easing. */
export const progress = (
  frame: number,
  start: number,
  dur: number,
  easing = EASE_OUT,
) => interpolate(frame, [start, start + dur], [0, 1], { ...clamp, easing });

type EnterOpts = {
  dur?: number;
  /** Deslocamento em px (6–12 no roteiro). Positivo = vem de baixo / da direita. */
  dist?: number;
  axis?: "x" | "y";
  blur?: number;
};

/** Entrada padrão do app: desloca 6–12 px + fade + blur de 2 px. */
export const enter = (
  frame: number,
  start: number,
  { dur = MEDIUM, dist = 10, axis = "y", blur = 2 }: EnterOpts = {},
): CSSProperties => {
  const p = progress(frame, start, dur);
  const d = (1 - p) * dist;
  return {
    opacity: p,
    translate: axis === "y" ? `0px ${d}px` : `${d}px 0px`,
    filter: blur ? `blur(${(1 - p) * blur}px)` : undefined,
  };
};

/** Saída: mais rápida que a entrada. Combine com `enter` usando `mergeStyles`. */
export const exit = (
  frame: number,
  start: number,
  { dur = ms(200), dist = -6, axis = "y", blur = 2 }: EnterOpts = {},
): CSSProperties => {
  const p = progress(frame, start, dur, EASE_IN);
  const d = p * dist;
  return {
    opacity: 1 - p,
    translate: axis === "y" ? `0px ${d}px` : `${d}px 0px`,
    filter: blur ? `blur(${p * blur}px)` : undefined,
  };
};

/** Junta entrada e saída: multiplica opacidade e soma deslocamentos e blur. */
export const mergeStyles = (a: CSSProperties, b: CSSProperties): CSSProperties => {
  const parse = (t?: CSSProperties["translate"]) =>
    String(t ?? "0px 0px")
      .split(" ")
      .map((s) => parseFloat(s) || 0);
  const blurOf = (f?: string) => (f ? parseFloat(f.replace("blur(", "")) || 0 : 0);
  const [ax, ay] = parse(a.translate);
  const [bx, by] = parse(b.translate);
  return {
    opacity: (Number(a.opacity ?? 1) * Number(b.opacity ?? 1)) as number,
    translate: `${ax + bx}px ${(ay ?? 0) + (by ?? 0)}px`,
    filter: `blur(${blurOf(a.filter as string) + blurOf(b.filter as string)}px)`,
  };
};

/** Visível só dentro de [from, to): entra em `from` e sai em `to - dur de saída`. */
export const between = (
  frame: number,
  from: number,
  to: number,
  opts: { enter?: EnterOpts; exit?: EnterOpts } = {},
) => {
  const outDur = opts.exit?.dur ?? ms(200);
  return mergeStyles(
    enter(frame, from, opts.enter),
    exit(frame, to - outDur, { ...opts.exit, dur: outDur }),
  );
};
