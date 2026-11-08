import { useSyncExternalStore } from "react";

/**
 * Assina uma media query no cliente. A ilha só monta o conteúdo depois do
 * mount, então o valor do navegador nunca diverge do HTML do servidor.
 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (notify) => {
      const mql = window.matchMedia(query);
      mql.addEventListener("change", notify);
      return () => mql.removeEventListener("change", notify);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}

/** Movimento reduzido do sistema: as transições de entrada e saída viram instantâneas. */
export function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
