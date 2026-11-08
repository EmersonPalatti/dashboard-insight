import { useEffect, useLayoutEffect, useRef, type KeyboardEvent, type ReactNode } from "react";
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
            {busy && <LoaderCircle aria-label="Atualizando" className="size-3.5 animate-spin text-muted motion-reduce:animate-none" />}
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
    <div className="flex min-h-32 flex-col items-center justify-center gap-2 text-center transition-opacity duration-(--duration-fast) starting:opacity-0 motion-reduce:transition-none">
      <TriangleAlert className="size-5 text-crit" aria-hidden />
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
  return (
    <div className="label flex min-h-32 items-center justify-center text-center transition-opacity duration-(--duration-fast) starting:opacity-0 motion-reduce:transition-none">
      {children}
    </div>
  );
}

interface SegmentedProps<T extends string> {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  label: string;
}

export function Segmented<T extends string>({ value, options, onChange, label }: SegmentedProps<T>) {
  const groupRef = useRef<HTMLDivElement>(null);
  const indicatorRef = useRef<HTMLSpanElement>(null);
  // Última posição escrita: se nada mudou (ex.: fonte carregou e o grupo redimensionou), o indicador não mexe.
  const placedKey = useRef<string | null>(null);
  const started = useRef(false);
  // Só o botão marcado entra na ordem de Tab; as setas trocam a seleção (radiogroup).
  const tabStop = Math.max(
    0,
    options.findIndex((o) => o.value === value),
  );

  /**
   * Leva o indicador ao botão marcado: mede offsetLeft/Top/Width/Height e grava em --seg-*
   * no grupo. Sem animar (primeira pintura, redimensionamento), suspende a transição e
   * força um reflow antes de restaurá-la, então o indicador "nasce" já no lugar.
   */
  const place = (animate: boolean) => {
    const group = groupRef.current;
    const indicator = indicatorRef.current;
    if (!group || !indicator) return;
    const active = group.querySelector<HTMLElement>('[aria-checked="true"]');
    if (!active) {
      indicator.style.opacity = "0";
      return;
    }
    indicator.style.opacity = "";
    const key = [active.offsetLeft, active.offsetTop, active.offsetWidth, active.offsetHeight].join(",");
    if (key === placedKey.current) return;
    placedKey.current = key;
    if (!animate) indicator.style.transition = "none";
    group.style.setProperty("--seg-x", `${active.offsetLeft}px`);
    group.style.setProperty("--seg-y", `${active.offsetTop}px`);
    group.style.setProperty("--seg-w", `${active.offsetWidth}px`);
    group.style.setProperty("--seg-h", `${active.offsetHeight}px`);
    if (!animate) {
      void indicator.offsetWidth;
      indicator.style.transition = "";
    }
  };

  // Antes da pintura: primeira posição sem transição; trocas de valor deslizam.
  useLayoutEffect(() => {
    place(started.current);
    started.current = true;
  }, [value, options]);

  // Redimensionar (quebra de linha, zoom) reposiciona sem deslizar.
  useEffect(() => {
    const group = groupRef.current;
    if (!group || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => place(false));
    ro.observe(group);
    return () => ro.disconnect();
  }, []);

  const onArrowKey = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    const last = options.length - 1;
    let next: number;
    switch (e.key) {
      case "ArrowRight":
      case "ArrowDown":
        next = i === last ? 0 : i + 1;
        break;
      case "ArrowLeft":
      case "ArrowUp":
        next = i === 0 ? last : i - 1;
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = last;
        break;
      default:
        return;
    }
    e.preventDefault();
    onChange(options[next].value);
    groupRef.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[next]?.focus();
  };

  return (
    <div
      ref={groupRef}
      role="radiogroup"
      aria-label={label}
      className="relative inline-flex max-w-full flex-wrap rounded-card border border-rule bg-sunken p-0.5"
    >
      <span
        ref={indicatorRef}
        aria-hidden
        className="seg-indicator pointer-events-none absolute top-0 left-0 z-0 rounded-t-[4px] border-b-2 border-ink bg-surface"
      />
      {options.map((o, i) => {
        const checked = value === o.value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={i === tabStop ? 0 : -1}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => onArrowKey(e, i)}
            className={`relative z-[1] rounded-t-[4px] border-b-2 border-transparent px-2.5 py-1 text-[0.85rem] transition-colors duration-(--duration-quick) ${
              checked ? "font-semibold text-ink" : "text-muted hover:text-ink"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
