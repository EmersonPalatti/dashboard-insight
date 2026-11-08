/*
 * Trocas de estado no lugar (ex.: "Copiar link" → "Link copiado"). Os dois
 * estados dividem uma célula de grid (col/row 1), então nada muda de largura.
 */

/** Ícone: cross-fade com escala e blur (icon swap), --duration-fast, simétrico. */
export const iconSwap = (on: boolean, size = "size-3.5") =>
  `col-start-1 row-start-1 ${size} transition-[opacity,scale,filter] duration-(--duration-fast) ease-(--ease-in-out) motion-reduce:transition-none ${
    on ? "opacity-100 scale-100" : "opacity-0 scale-[0.25] blur-(--blur-small)"
  }`;

/** Rótulo: sobe e some (text swap), --duration-quick. */
export const textSwap = (on: boolean) =>
  `col-start-1 row-start-1 transition-[opacity,translate,visibility] duration-(--duration-quick) ease-(--ease-smooth-out) motion-reduce:transition-none ${
    on ? "" : "invisible translate-y-(--distance-micro) opacity-0"
  }`;
