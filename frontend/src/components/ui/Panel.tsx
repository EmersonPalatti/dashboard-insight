import type { ReactNode } from "react";
import { LoaderCircle, TriangleAlert } from "lucide-react";

interface PanelProps {
  title: string;
  hint?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  /** Mostra um indicador discreto enquanto o recorte novo carrega por cima do antigo. */
  busy?: boolean;
}

export function Panel({ title, hint, actions, children, className = "", busy }: PanelProps) {
  return (
    <section className={`panel flex min-w-0 flex-col p-4 ${className}`}>
      <header className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="section-title flex items-center gap-2">
            {title}
            {busy && <LoaderCircle aria-label="Atualizando" className="size-3.5 animate-spin text-muted" />}
          </h2>
          {hint && <p className="label mt-0.5">{hint}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-1.5">{actions}</div>}
      </header>
      {children}
    </section>
  );
}

export function Skeleton({ height = 280 }: { height?: number }) {
  return <div className="skeleton w-full" style={{ height }} aria-hidden />;
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Falha ao consultar a API";
  return (
    <div className="flex min-h-32 flex-col items-center justify-center gap-2 text-center">
      <TriangleAlert className="size-5 text-chili" aria-hidden />
      <p className="label">Não deu para carregar: {message}</p>
      {onRetry && (
        <button type="button" className="btn-ghost" onClick={onRetry}>
          Tentar de novo
        </button>
      )}
    </div>
  );
}

export function Empty({ children = "Sem dados no recorte." }: { children?: ReactNode }) {
  return <div className="label flex min-h-32 items-center justify-center text-center">{children}</div>;
}

interface SegmentedProps<T extends string> {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  label: string;
}

export function Segmented<T extends string>({ value, options, onChange, label }: SegmentedProps<T>) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex max-w-full flex-wrap rounded-fold border border-rule bg-kraft p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-[4px] px-2.5 py-1 text-[0.85rem] transition-colors ${
            value === o.value ? "bg-paper text-ink shadow-[inset_0_-2px_0_var(--chili)]" : "text-muted hover:text-ink"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
