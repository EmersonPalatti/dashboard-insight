import { Calendar, ChevronLeft, ChevronRight } from "lucide-react";
import {
  useEffect,
  useId,
  useRef,
  useState,
  type FocusEvent as ReactFocusEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
} from "react";

export interface DatePickerProps {
  /** Nome curto do campo ("Início", "Fim"): entra no nome acessível e no título do diálogo. */
  label: string;
  /** Data ISO yyyy-mm-dd, ou null quando vazio. */
  value: string | null;
  /** Limites ISO yyyy-mm-dd; dias fora deles ficam desabilitados. */
  min: string;
  max: string;
  /** Outra ponta do intervalo: fica marcada no calendário e os dias entre as duas ganham tinta. */
  rangeOther?: string | null;
  onChange: (value: string | null) => void;
}

/** Fechamento: a transição dura --duration-quick (150ms); se transitionend não disparar, o painel desmonta aqui. */
const CLOSE_FALLBACK_MS = 170;

const DAY_MS = 86_400_000;
const pad = (n: number) => String(n).padStart(2, "0");

// Datas são strings yyyy-mm-dd. A aritmética vai por UTC para o fuso do navegador não mudar o dia.
const utc = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  return Date.UTC(y, m - 1, d);
};
const isoOf = (ms: number) => {
  const d = new Date(ms);
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
};
const addDays = (iso: string, n: number) => isoOf(utc(iso) + n * DAY_MS);
const weekdayOf = (iso: string) => new Date(utc(iso)).getUTCDay();
/** m é 1-based. */
const daysInMonth = (y: number, m: number) => new Date(Date.UTC(y, m, 0)).getUTCDate();
const addMonths = (iso: string, n: number) => {
  const [y, m, d] = iso.split("-").map(Number);
  const idx = y * 12 + (m - 1) + n;
  const ny = Math.floor(idx / 12);
  const nm = ((idx % 12) + 12) % 12 + 1;
  return `${ny}-${pad(nm)}-${pad(Math.min(d, daysInMonth(ny, nm)))}`;
};
const clampIso = (iso: string, min: string, max: string) => (iso < min ? min : iso > max ? max : iso);
const todayIso = () => {
  const n = new Date();
  return `${n.getFullYear()}-${pad(n.getMonth() + 1)}-${pad(n.getDate())}`;
};
/** ISO → dd/mm/aaaa, sem passar por Date: só separa a string. */
const formatBr = (iso: string) => {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
};

const monthFmt = new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric", timeZone: "UTC" });
const longDateFmt = new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const weekdayLongFmt = new Intl.DateTimeFormat("pt-BR", { weekday: "long", timeZone: "UTC" });
const weekdayNarrowFmt = new Intl.DateTimeFormat("pt-BR", { weekday: "narrow", timeZone: "UTC" });
/** 3 de janeiro de 2021 foi domingo: a grade começa no domingo, como no pt-BR. */
const SUNDAY_MS = Date.UTC(2021, 0, 3);
const WEEKDAYS = Array.from({ length: 7 }, (_, i) => ({
  letter: weekdayNarrowFmt.format(SUNDAY_MS + i * DAY_MS).toLocaleUpperCase("pt-BR"),
  name: weekdayLongFmt.format(SUNDAY_MS + i * DAY_MS),
}));

/** "janeiro de 2021", com a primeira letra maiúscula. */
const monthTitle = (iso: string) => {
  const s = monthFmt.format(utc(iso));
  return s.charAt(0).toLocaleUpperCase("pt-BR") + s.slice(1);
};

/**
 * Campo de data no padrão "dialog" do WAI-ARIA APG: botão com dd/mm/aaaa e um painel
 * de calendário (grid com roving tabindex). Ao lado de fora de lg o painel abre em fluxo,
 * sem absolute, para não ser cortado pela rolagem da folha do mobile.
 */
export function DatePicker({ label, value, min, max, rangeOther = null, onChange }: DatePickerProps) {
  const [open, setOpen] = useState(false);
  // Painel fechando: segue montado para a animação, mas já está inert (sem foco, sem clique, fora da árvore de acessibilidade).
  const [closing, setClosing] = useState(false);
  const [wasOpen, setWasOpen] = useState(open);
  // Ajuste durante a renderização (sem effect): o painel não desmonta no commit em que fecha.
  if (wasOpen !== open) {
    setWasOpen(open);
    setClosing(!open);
  }
  // Dia com foco de teclado (roving tabindex). Ele também define o mês exibido.
  const [cursor, setCursor] = useState(() => clampIso(value ?? min, min, max));
  const root = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const gridRef = useRef<HTMLTableElement>(null);
  // Foco vai para o dia do cursor só depois de abrir ou de uma tecla que move o cursor.
  const focusPending = useRef(false);
  const uid = useId();
  const dialogId = `${uid}-dialog`;
  const titleId = `${uid}-title`;

  const openPicker = () => {
    // sem data, o foco vai para o primeiro dia habilitado (min); com data, para o dia selecionado
    setCursor(clampIso(value ?? min, min, max));
    focusPending.current = true;
    setOpen(true);
  };
  const close = (restoreFocus: boolean) => {
    setOpen(false);
    if (restoreFocus) triggerRef.current?.focus();
  };
  const choose = (iso: string | null) => {
    onChange(iso);
    close(true);
  };
  const moveTo = (iso: string) => {
    if (iso === cursor) return;
    focusPending.current = true;
    setCursor(iso);
  };

  // Clique fora fecha (o foco sair do componente também fecha, via onBlur abaixo).
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  // Fallback do fechamento: se transitionend não disparar, o painel desmonta no mesmo tempo.
  useEffect(() => {
    if (!closing) return;
    const t = window.setTimeout(() => setClosing(false), CLOSE_FALLBACK_MS);
    return () => window.clearTimeout(t);
  }, [closing]);

  useEffect(() => {
    if (!open || !focusPending.current) return;
    focusPending.current = false;
    gridRef.current?.querySelector<HTMLButtonElement>('button[tabindex="0"]')?.focus();
  }, [open, cursor]);

  const onRootBlur = (e: ReactFocusEvent<HTMLDivElement>) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOpen(false);
  };

  const onTriggerKeyDown = (e: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (e.key === "Escape" && open) {
      e.preventDefault();
      close(true);
    }
  };

  const onPanelKeyDown = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      // o Esc fecha só o calendário, não a folha do mobile que o contém
      e.preventDefault();
      e.stopPropagation();
      close(true);
    }
  };

  const onGridKeyDown = (e: ReactKeyboardEvent<HTMLTableElement>) => {
    let next: string;
    switch (e.key) {
      case "ArrowLeft":
        next = addDays(cursor, -1);
        break;
      case "ArrowRight":
        next = addDays(cursor, 1);
        break;
      case "ArrowUp":
        next = addDays(cursor, -7);
        break;
      case "ArrowDown":
        next = addDays(cursor, 7);
        break;
      case "Home":
        next = addDays(cursor, -weekdayOf(cursor));
        break;
      case "End":
        next = addDays(cursor, 6 - weekdayOf(cursor));
        break;
      case "PageUp":
        next = addMonths(cursor, e.shiftKey ? -12 : -1);
        break;
      case "PageDown":
        next = addMonths(cursor, e.shiftKey ? 12 : 1);
        break;
      default:
        return;
    }
    e.preventDefault();
    moveTo(clampIso(next, min, max));
  };

  // Mousedown dentro do painel não tira o foco do dia atual (senão o onBlur fecharia).
  const onPanelMouseDown = (e: ReactMouseEvent<HTMLDivElement>) => {
    if (!(e.target instanceof HTMLButtonElement)) e.preventDefault();
  };

  // Cursor sempre dentro de [min, max]: o mês exibido e os dias habilitados seguem dele.
  const viewYm = cursor.slice(0, 7);
  const prevDisabled = viewYm <= min.slice(0, 7);
  const nextDisabled = viewYm >= max.slice(0, 7);
  const shiftMonth = (n: number) => setCursor(clampIso(addMonths(cursor, n), min, max));

  const [vy, vm] = cursor.split("-").map(Number);
  const cells: (string | null)[] = [];
  for (let i = 0; i < weekdayOf(`${vy}-${pad(vm)}-01`); i++) cells.push(null);
  for (let d = 1; d <= daysInMonth(vy, vm); d++) cells.push(`${vy}-${pad(vm)}-${pad(d)}`);
  while (cells.length % 7) cells.push(null);
  const weeks = Array.from({ length: cells.length / 7 }, (_, r) => cells.slice(r * 7, r * 7 + 7));

  // Faixa entre as duas pontas (só quando há as duas).
  const lo = value && rangeOther ? (value < rangeOther ? value : rangeOther) : null;
  const hi = value && rangeOther ? (value < rangeOther ? rangeOther : value) : null;
  const today = todayIso();

  const dayClass = (iso: string) => {
    const selected = iso === value;
    const other = iso === rangeOther && iso !== value;
    const between = lo !== null && hi !== null && iso > lo && iso < hi;
    return [
      "flex size-10 lg:size-9 items-center justify-center rounded-tick text-[0.9rem] tabular-nums transition-colors duration-(--duration-quick) disabled:cursor-default disabled:text-muted disabled:opacity-40 disabled:hover:bg-transparent",
      selected
        ? "bg-ink font-semibold text-surface"
        : other
          ? "bg-sunken-strong font-semibold text-ink hover:bg-sunken-strong"
          : between
            ? "bg-sunken text-ink hover:bg-sunken-strong"
            : "text-ink hover:bg-sunken",
      iso === today ? "underline decoration-ink underline-offset-4" : "",
    ].join(" ");
  };

  const selectedText = value ? formatBr(value) : null;

  return (
    <div ref={root} className="relative max-lg:contents" onBlur={onRootBlur}>
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? dialogId : undefined}
        aria-label={`${label}, ${selectedText ?? "sem data"}`}
        onClick={() => (open ? close(true) : openPicker())}
        onKeyDown={onTriggerKeyDown}
        className="flex h-7 max-lg:min-h-11 shrink-0 items-center gap-1.5 rounded-tick px-1.5 text-[0.88rem] transition-colors duration-(--duration-quick) hover:bg-sunken"
      >
        <Calendar className="size-3.5 shrink-0 text-muted" aria-hidden />
        <span className={`tabular-nums ${selectedText ? "text-ink" : "text-muted"}`}>{selectedText ?? "dd/mm/aaaa"}</span>
      </button>

      {(open || closing) && (
        <div
          id={dialogId}
          role="dialog"
          aria-modal="false"
          aria-label={`Escolher data de ${label.toLowerCase()}`}
          inert={!open}
          onTransitionEnd={(e) => {
            if (e.target === e.currentTarget && !open) setClosing(false);
          }}
          onKeyDown={onPanelKeyDown}
          onMouseDown={onPanelMouseDown}
          className={`z-30 mt-1 w-full max-w-[calc(100vw-2rem)] rounded-card border border-rule bg-surface p-1.5 transition-[opacity,scale,translate] duration-(--duration-fast) ease-(--ease-smooth-out) max-lg:static max-lg:mt-2 max-lg:basis-full lg:absolute lg:top-full lg:left-0 lg:w-[16.5rem] lg:origin-top-left ${
            open
              ? "starting:opacity-0 motion-safe:starting:translate-y-[calc(var(--distance-micro)*-1)] motion-safe:starting:scale-(--scale-medium) motion-reduce:duration-(--duration-quick)"
              : "pointer-events-none opacity-0 duration-(--duration-quick) motion-safe:scale-(--scale-tiny)"
          }`}
        >
          <div className="mb-1 flex items-center justify-between gap-2">
            <button
              type="button"
              aria-label="Mês anterior"
              disabled={prevDisabled}
              onClick={() => shiftMonth(-1)}
              className="inline-flex size-10 lg:size-8 shrink-0 items-center justify-center rounded-tick text-ink transition-colors hover:bg-sunken disabled:text-muted disabled:opacity-40 disabled:hover:bg-transparent"
            >
              <ChevronLeft className="size-4" aria-hidden />
            </button>
            <p id={titleId} className="min-w-0 truncate text-center text-[0.95rem] font-semibold text-ink">
              {monthTitle(cursor)}
            </p>
            <button
              type="button"
              aria-label="Próximo mês"
              disabled={nextDisabled}
              onClick={() => shiftMonth(1)}
              className="inline-flex size-10 lg:size-8 shrink-0 items-center justify-center rounded-tick text-ink transition-colors hover:bg-sunken disabled:text-muted disabled:opacity-40 disabled:hover:bg-transparent"
            >
              <ChevronRight className="size-4" aria-hidden />
            </button>
          </div>

          <table
            ref={gridRef}
            role="grid"
            aria-labelledby={titleId}
            onKeyDown={onGridKeyDown}
            className="w-full border-separate border-spacing-0 text-center"
          >
            <thead>
              <tr>
                {WEEKDAYS.map((w) => (
                  <th key={w.name} scope="col" className="pb-1 text-[0.78rem] font-semibold text-muted">
                    <abbr title={w.name} className="no-underline">
                      {w.letter}
                    </abbr>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {weeks.map((week, r) => (
                <tr key={r}>
                  {week.map((iso, c) =>
                    iso === null ? (
                      <td key={c} aria-hidden="true" />
                    ) : (
                      <td key={iso} role="gridcell" aria-selected={iso === value} className="p-0">
                        <button
                          type="button"
                          tabIndex={iso === cursor ? 0 : -1}
                          disabled={iso < min || iso > max}
                          aria-label={longDateFmt.format(utc(iso))}
                          onClick={() => choose(iso)}
                          className={dayClass(iso)}
                        >
                          {Number(iso.slice(8))}
                        </button>
                      </td>
                    ),
                  )}
                </tr>
              ))}
            </tbody>
          </table>

          <div className="mt-1 flex justify-end border-t border-rule pt-1">
            <button
              type="button"
              disabled={value === null}
              onClick={() => choose(null)}
              className="rounded-tick px-2 py-1 text-[0.9rem] text-muted transition-colors hover:bg-sunken hover:text-ink disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-muted"
            >
              Limpar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
