import { useEffect, useLayoutEffect, useRef, type KeyboardEvent, type ReactNode } from "react";
import { LoaderCircle, TriangleAlert } from "lucide-react";

interface PanelContentProps {
  /** Ações à direita do título (Segmented, Pergunte ao agente…). */
  actions?: ReactNode;
  /** Dica que depende do estado da ilha. Dica fixa vai em `<Panel hint>` na casca. */
  hint?: ReactNode;
  /** Linha abaixo da dica, ex.: a etiqueta da comanda que este gráfico prova. */
  note?: ReactNode;
  /** Indicador discreto enquanto o recorte novo carrega por cima do antigo. Reserva o espaço sempre. */
  busy?: boolean;
  children: ReactNode;
}

/**
 * Parte interativa de um painel cuja moldura (seção e título) está em `ui/Panel.astro`.
 * Devolve itens soltos, sem wrapper: eles se encaixam no flex da moldura.
 */
export function PanelContent({ actions, hint, note, busy, children }: PanelContentProps) {
  return (
    <>
      {(actions || busy !== undefined) && (
        <div className="panel-actions">
          {busy !== undefined && (
            <LoaderCircle
              aria-label={busy ? "Atualizando" : undefined}
              aria-hidden={!busy}
              className={`size-3.5 text-muted ${busy ? "animate-spin motion-reduce:animate-none" : "invisible"}`}
            />
          )}
          {actions}
        </div>
      )}
      {(hint || note) && (
        <div className="panel-sub">
          {hint && <p className="label text-pretty">{hint}</p>}
          {note && <div className="mt-1.5 flex min-w-0">{note}</div>}
        </div>
      )}
      <div className="panel-body">{children}</div>
    </>
  );
}

/**
 * Fallback de `island()` para painéis: ocupa o lugar do corpo com a altura do estado carregando.
 * `hint: true` reserva também a linha da dica dinâmica (uma linha de `label`), para o corpo
 * não descer quando a ilha monta.
 */
export function panelFallback(height: number, { hint = false }: { hint?: boolean } = {}) {
  return (
    <>
      {hint && (
        <div className="panel-sub" aria-hidden>
          <p className="label">
            <span className="skeleton inline-block h-3 w-2/3 max-w-md align-middle" />
          </p>
        </div>
      )}
      <div className="panel-body skeleton" style={{ height }} aria-hidden />
    </>
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
      <p className="label text-pretty">Não deu para carregar: {message}</p>
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
            className={`relative z-[1] rounded-t-[4px] border-b-2 border-transparent px-2.5 py-1 text-aux transition-colors duration-(--duration-quick) ${
              checked ? "font-medium text-ink" : "text-muted hover:text-ink"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
