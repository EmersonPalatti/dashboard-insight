import { X } from "lucide-react";
import type { Chip } from "../filters/useFilterModel";

/** Chips do recorte com entrada suave (starting: sai de opacidade e escala menores). Remoção é instantânea. */
export function ActiveChips({ chips }: { chips: Chip[] }) {
  return (
    <ul aria-label="Filtros ativos" className="flex flex-wrap items-center gap-1.5">
      {chips.map((c) => (
        <li
          key={c.key}
          className="inline-flex max-w-full items-center gap-1 rounded-[4px] border border-ink bg-surface pl-2 pr-0.5 text-aux font-medium text-ink transition-[opacity,scale] duration-(--duration-fast) ease-(--ease-smooth-out) starting:scale-(--scale-medium) starting:opacity-0 motion-reduce:transition-none"
        >
          <span className="text-muted">{c.dim}</span>
          <span className="max-w-[16rem] truncate" title={c.value}>
            {c.value}
          </span>
          <button
            type="button"
            aria-label={`Remover ${c.dim}: ${c.value}`}
            onClick={c.remove}
            className="inline-flex size-6 shrink-0 items-center justify-center rounded-[4px] text-muted transition-colors duration-(--duration-quick) hover:bg-sunken hover:text-ink max-lg:size-11"
          >
            <X className="size-3.5" aria-hidden />
          </button>
        </li>
      ))}
    </ul>
  );
}
