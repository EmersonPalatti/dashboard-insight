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
    paper: v("--paper"),
    kraft: v("--kraft"),
    rule: v("--rule"),
    ink: v("--ink"),
    muted: v("--muted"),
    chili: v("--chili"),
    chiliDeep: v("--chili-deep"),
    chiliSoft: v("--chili-soft"),
    amber: v("--amber"),
    good: v("--good"),
  };
}
