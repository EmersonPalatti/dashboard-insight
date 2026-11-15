// Tokens do mundo "Comanda" (roteiro, seção 2). Só use estes valores nas cenas.
import { createContext, createElement, useContext, type ReactNode } from "react";
import { Easing } from "remotion";
import { loadFont as loadFranklin } from "@remotion/google-fonts/LibreFranklin";
import { loadFont as loadZilla } from "@remotion/google-fonts/ZillaSlab";

export const { fontFamily: SANS } = loadFranklin("normal", {
  weights: ["400", "500", "600", "700"],
  subsets: ["latin", "latin-ext"],
});
export const { fontFamily: SLAB } = loadZilla("normal", {
  weights: ["600", "700"],
  subsets: ["latin", "latin-ext"],
});

export type Tokens = {
  mode: "light" | "dark";
  field: string;
  surface: string;
  sunken: string;
  rule: string;
  ink: string;
  muted: string;
  crit: string;
  warn: string;
  good: string;
  wine: string;
  wineRaised: string;
  onWine: string;
  series: string;
  seriesDeep: string;
  seriesSoft: string;
  /** Fundo e borda do bloco Ação. */
  actionBg: string;
  actionBorder: string;
  actionText: string;
  /** Traço do logo sobre o quadrado vinho. */
  logoStroke: string;
};

export const LIGHT: Tokens = {
  mode: "light",
  field: "#ECECEC",
  surface: "#FFFFFF",
  sunken: "#F5F5F5",
  rule: "#DCDCDC",
  ink: "#1A1A1A",
  muted: "#666666",
  crit: "#D92B20",
  warn: "#946000",
  good: "#46700F",
  wine: "#3D0B1F",
  wineRaised: "#5A1730",
  onWine: "#F1DBE3",
  series: "#7A1E3D",
  seriesDeep: "#4A0F25",
  seriesSoft: "#C07D93",
  actionBg: "#1A1A1A",
  actionBorder: "#1A1A1A",
  actionText: "#FFFFFF",
  logoStroke: "#F2E6EA",
};

export const DARK: Tokens = {
  mode: "dark",
  field: "#111111",
  surface: "#1B1B1B",
  sunken: "#232323",
  rule: "#353535",
  ink: "#F2F2F2",
  muted: "#A6A6A6",
  crit: "#FF5D50",
  warn: "#F0A93B",
  good: "#9BC75A",
  wine: "#26060F",
  wineRaised: "#45112A",
  onWine: "#E6C3CF",
  series: "#E0789A",
  seriesDeep: "#F4B8CB",
  seriesSoft: "#A3516C",
  actionBg: "#27131A",
  actionBorder: "#45112A",
  actionText: "#F2F2F2",
  logoStroke: "#F2E6EA",
};

const ThemeCtx = createContext<Tokens>(LIGHT);

export const ThemeProvider = ({
  tokens,
  children,
}: {
  readonly tokens: Tokens;
  readonly children: ReactNode;
}) => createElement(ThemeCtx.Provider, { value: tokens }, children);

export const useTokens = () => useContext(ThemeCtx);

// Movimento (roteiro, seção 2 "Movimento").
export const FPS = 30;
/** Milissegundos → frames a 30 fps (arredondado, mínimo 1). */
export const ms = (v: number) => Math.max(1, Math.round((v / 1000) * FPS));
/** Segundos do roteiro (ex.: 19.5 = 0:19,5) → frame absoluto do vídeo. */
export const sec = (v: number) => Math.round(v * FPS);

export const EASE_OUT = Easing.bezier(0.22, 1, 0.36, 1);
export const EASE_TICKET = Easing.bezier(0.16, 1, 0.3, 1);
export const EASE_BOUNCE = Easing.bezier(0.34, 1.36, 0.64, 1);
export const EASE_IN = Easing.bezier(0.4, 0, 1, 1);

export const STAGGER = ms(40); // 1 frame
export const FAST = ms(250); // 8 frames
export const MEDIUM = ms(380); // 11 frames

// Áreas seguras (roteiro, seção 1).
export const W = 1080;
export const H = 1350;
export const SIDE = 72;
export const CONTENT_W = W - SIDE * 2; // 936
export const TITLE_ZONE = { top: 96, bottom: 330 };
export const STAGE = { top: 350, bottom: 1150 };
export const CAPTION_ZONE = { top: 1160, bottom: 1230 };

/** Números em pt-BR. */
export const br = (v: number, digits = 0) =>
  v.toLocaleString("pt-BR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

/** Zilla Slab tem algarismos de estilo antigo por padrão: números sempre alinhados e tabulares. */
export const NUM = { fontVariantNumeric: "lining-nums tabular-nums" } as const;
