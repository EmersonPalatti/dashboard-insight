import { useStore } from "@nanostores/react";
import { Undo2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { $drillUndo, undoDrilldown } from "@/lib/filters";
import type { Chip } from "../filters/useFilterModel";

/** Chips do recorte com entrada suave (starting: sai de opacidade e escala menores). Remoção é instantânea. */
export function ActiveChips({ chips }: { chips: Chip[] }) {
  const undo = useStore($drillUndo);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [announcement, setAnnouncement] = useState("");

  useEffect(() => {
    if (!undo) {
      setAnnouncement("");
      return;
    }
    const el = wrapRef.current;
    if (!el) return;
    if (el.closest("#agente") && !el.closest('#agente[aria-modal="true"]')) {
      setAnnouncement("");
      return;
    }
    if (el.closest("dialog:not([open])")) {
      setAnnouncement("");
      return;
    }
    const frame = requestAnimationFrame(() => {
      setAnnouncement(`Filtro aplicado: ${undo.description}. Botão Desfazer filtro disponível.`);
    });
    return () => cancelAnimationFrame(frame);
  }, [undo]);

  return (
    <div ref={wrapRef} className="flex min-w-0 max-w-full flex-wrap items-center gap-1.5">
      <ul aria-label="Filtros ativos" className="flex min-w-0 max-w-full flex-wrap items-center gap-1.5">
        {chips.map((c) => (
          <li
            key={c.key}
            className="inline-flex min-w-0 max-w-full items-center gap-1 rounded-tick border border-ink bg-surface pl-2 pr-0.5 text-aux font-medium text-ink transition-[opacity,scale] duration-(--duration-fast) ease-(--ease-smooth-out) starting:scale-(--scale-medium) starting:opacity-0 motion-reduce:transition-none"
          >
            <span className="shrink-0 text-muted">{c.dim}</span>
            <span className="min-w-0 max-w-[16rem] truncate" title={c.value}>
              {c.value}
            </span>
            <button
              type="button"
              aria-label={`Remover ${c.dim}: ${c.value}`}
              onClick={c.remove}
              className="inline-flex size-6 shrink-0 items-center justify-center rounded-tick text-muted transition-colors duration-(--duration-quick) hover:bg-sunken hover:text-ink max-lg:size-11"
            >
              <X className="size-3.5" aria-hidden />
            </button>
          </li>
        ))}
      </ul>
      {undo && (
        <button
          type="button"
          onClick={undoDrilldown}
          aria-label={`Desfazer filtro: ${undo.description}`}
          title={`Desfazer filtro: ${undo.description}`}
          className="inline-flex h-7 shrink-0 items-center gap-1.5 rounded-card border border-rule bg-surface px-2.5 text-aux font-medium text-ink transition-[color,background-color,opacity,scale] duration-(--duration-fast) ease-(--ease-smooth-out) hover:bg-sunken starting:scale-(--scale-medium) starting:opacity-0 motion-reduce:transition-none max-lg:h-auto max-lg:min-h-11 max-lg:px-3"
        >
          <Undo2 className="size-3.5 shrink-0 text-muted" aria-hidden />
          <span>Desfazer filtro</span>
        </button>
      )}
      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {announcement}
      </p>
    </div>
  );
}
