import { atom } from "nanostores";

export type Theme = "light" | "dark";

function current(): Theme {
  if (typeof document === "undefined") return "light";
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

/** Tema resolvido. Os gráficos ECharts escutam para reler os tokens CSS. */
export const $theme = atom<Theme>(current());

export function syncTheme() {
  $theme.set(current());
}

export function setTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem("theme", theme);
  } catch {
    /* storage bloqueado: vale só nesta aba */
  }
  $theme.set(theme);
}

/** Lê os tokens do DESIGN.md já resolvidos para o tema atual. */
export function tokens() {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string) => css.getPropertyValue(name).trim();
  return {
    surface: v("--surface"),
    sunken: v("--sunken"),
    rule: v("--rule"),
    ink: v("--ink"),
    muted: v("--muted"),
    crit: v("--crit"),
    warn: v("--warn"),
    good: v("--good"),
    series: v("--series"),
    seriesDeep: v("--series-deep"),
    seriesSoft: v("--series-soft"),
  };
}
