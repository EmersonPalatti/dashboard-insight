import { useStore } from "@nanostores/react";
import type { Evidence } from "@/lib/api/client";
import { $evidence, type FocusedEvidence } from "@/lib/evidence";

/** Severidade também por forma (cheia, vazada, traço), nunca só por cor. */
export const SEVERITY = {
  high: { label: "Crítico", mark: "size-3 rounded-full bg-crit", tone: "text-crit" },
  medium: { label: "Atenção", mark: "size-3 rounded-full border-[2.5px] border-warn", tone: "text-warn" },
  low: { label: "Observar", mark: "h-[3px] w-3 rounded-full bg-muted", tone: "text-muted" },
} as const;

/** Comanda aberta cuja evidência mora nesta vista; null quando a comanda aberta aponta para outro lugar. */
export function useEvidence(view: Evidence["view"]): FocusedEvidence | null {
  const focus = useStore($evidence);
  return focus && focus.evidence.view === view ? focus : null;
}

/**
 * Etiqueta "Comanda Nº 02 · …" no gráfico ou cartão que prova a comanda aberta.
 * Remonta a cada comanda (key no alertId), então entra de novo quando a comanda muda.
 */
type TagProps = { focus: FocusedEvidence; note?: string; className?: string; compact?: boolean };

export function EvidenceTag(props: TagProps) {
  return <Tag key={props.focus.alertId} {...props} />;
}

function Tag({ focus, note, className = "", compact = false }: TagProps) {
  const s = SEVERITY[focus.severity];
  const caption = note ?? focus.title;
  if (compact) {
    // Só marca + Nº: cabe na linha do número sem mudar a altura do cartão.
    return (
      <span
        title={`Comanda ${focus.number} · ${focus.title}`}
        className={`inline-flex shrink-0 items-center gap-1 rounded-tick bg-sunken px-1.5 py-0.5 text-meta leading-snug transition-[opacity,translate] duration-(--duration-fast) ease-(--ease-smooth-out) starting:translate-y-(--distance-micro) starting:opacity-0 motion-reduce:transition-none ${className}`}
      >
        <span className={`inline-block shrink-0 ${s.mark}`} aria-hidden />
        <span className="sr-only">Comanda </span>
        <span className="cond font-bold whitespace-nowrap">{focus.number}</span>
      </span>
    );
  }
  return (
    <span
      className={`inline-flex max-w-full items-center gap-1.5 rounded-tick bg-sunken px-2 py-0.5 text-meta leading-snug transition-[opacity,translate] duration-(--duration-fast) ease-(--ease-smooth-out) starting:translate-y-(--distance-micro) starting:opacity-0 motion-reduce:transition-none ${caption ? "min-w-0" : "shrink-0"} ${className}`}
    >
      <span className={`inline-block shrink-0 ${s.mark}`} aria-hidden />
      <span className="cond shrink-0 font-bold whitespace-nowrap">Comanda {focus.number}</span>
      {caption && <span className="min-w-0 truncate text-muted max-sm:line-clamp-2 max-sm:whitespace-normal">{caption}</span>}
    </span>
  );
}
