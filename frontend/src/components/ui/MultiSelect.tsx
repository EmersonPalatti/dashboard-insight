import { Check, ChevronDown, Search, X } from "lucide-react";
import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type FocusEvent as ReactFocusEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
} from "react";

export interface SelectOption<V extends string | number> {
  value: V;
  label: string;
  hint?: string;
}

interface Props<V extends string | number> {
  label: string;
  options: SelectOption<V>[];
  value: V[];
  onChange: (value: V[]) => void;
  searchable?: boolean;
  /** Limita a lista renderizada (lojas têm ~950 opções). */
  maxVisible?: number;
  disabled?: boolean;
}

/**
 * Fechamento do menu: a transição dura --duration-quick (150ms); se transitionend não
 * disparar, o painel desmonta aqui (um pouco de folga além dos 150ms).
 */
const MENU_CLOSE_FALLBACK_MS = 170;

/**
 * Multiseleção no padrão listbox do WAI-ARIA APG (popup com listbox).
 * Com `searchable`, o foco fica no campo de busca (combobox) e as setas
 * movem o descendente ativo; sem busca, o próprio listbox recebe o foco.
 */
export function MultiSelect<V extends string | number>({
  label,
  options,
  value,
  onChange,
  searchable = false,
  maxVisible = 80,
  disabled,
}: Props<V>) {
  const [open, setOpen] = useState(false);
  // Painel fechando: segue montado para a animação, mas já está fechado para ARIA e foco (open false).
  const [closing, setClosing] = useState(false);
  const [wasOpen, setWasOpen] = useState(open);
  // Ajuste durante a renderização (sem effect): o painel não desmonta no commit em que fecha.
  if (wasOpen !== open) {
    setWasOpen(open);
    setClosing(!open);
  }
  const [term, setTerm] = useState("");
  // Guarda a opção ativa pelo valor (não pelo índice): ao marcar, a opção sobe
  // para o topo (selecionados primeiro) e o foco do teclado deve acompanhá-la.
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const uid = useId();
  const listId = `${uid}-list`;
  const labelId = `${uid}-label`;
  const summaryId = `${uid}-summary`;
  const optionId = (i: number) => `${uid}-option-${i}`;

  const selected = useMemo(() => new Set(value), [value]);
  const ordered = useMemo(() => {
    const q = term
      .trim()
      .toLowerCase()
      .normalize("NFD")
      .replace(/\p{M}/gu, "");
    const list = q
      ? options.filter((o) =>
          o.label
            .toLowerCase()
            .normalize("NFD")
            .replace(/\p{M}/gu, "")
            .includes(q),
        )
      : options;
    // selecionados primeiro, para não "sumirem" além do limite
    return [...list.filter((o) => selected.has(o.value)), ...list.filter((o) => !selected.has(o.value))];
  }, [options, term, selected]);

  const visible = ordered.slice(0, maxVisible);
  const activeIdx = visible.length === 0 ? -1 : Math.max(0, visible.findIndex((o) => String(o.value) === activeKey));
  const keyAt = (i: number) => (visible[i] ? String(visible[i].value) : null);

  const toggle = (v: V) => onChange(selected.has(v) ? value.filter((x) => x !== v) : [...value, v]);
  const summary =
    value.length === 0
      ? "Todos"
      : value.length === 1
        ? (options.find((o) => o.value === value[0])?.label ?? "1 selecionado")
        : `${value.length} selecionados`;

  // Foco entra no campo de busca (ou no listbox) ao abrir.
  useEffect(() => {
    if (open) (searchable ? inputRef.current : listRef.current)?.focus();
  }, [open, searchable]);

  // Fallback do fechamento: se transitionend não disparar, o painel desmonta no mesmo tempo.
  useEffect(() => {
    if (!closing) return;
    const t = window.setTimeout(() => setClosing(false), MENU_CLOSE_FALLBACK_MS);
    return () => window.clearTimeout(t);
  }, [closing]);

  // Clique fora fecha (o foco sair do componente também fecha, via onBlur abaixo).
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  useEffect(() => {
    if (disabled) setOpen(false);
  }, [disabled]);

  // Mantém a opção ativa visível na rolagem do listbox.
  useEffect(() => {
    if (!open || activeIdx < 0) return;
    listRef.current?.querySelectorAll<HTMLElement>('[role="option"]')[activeIdx]?.scrollIntoView({ block: "nearest" });
  }, [open, activeIdx]);

  /** Abre (ou só move a opção ativa, se já aberto) e foca o painel. */
  const openAt = (i: number) => {
    setActiveKey(keyAt(i));
    if (open) (searchable ? inputRef.current : listRef.current)?.focus();
    else setOpen(true);
  };

  const onTriggerKeyDown = (e: ReactKeyboardEvent<HTMLButtonElement>) => {
    switch (e.key) {
      case "Enter":
      case " ":
        e.preventDefault();
        if (open) setOpen(false);
        else openAt(0);
        break;
      case "ArrowDown":
        e.preventDefault();
        openAt(0);
        break;
      case "ArrowUp":
        e.preventDefault();
        openAt(visible.length - 1);
        break;
      case "Escape":
        if (open) {
          e.preventDefault();
          setOpen(false);
        }
        break;
    }
  };

  const onPanelKeyDown = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      setOpen(false);
      triggerRef.current?.focus();
      return;
    }
    // Só o campo de busca e o listbox tratam teclas; Tab e o botão "Limpar" seguem o navegador.
    const onInput = e.target === inputRef.current;
    if (!onInput && e.target !== listRef.current) return;
    const last = visible.length - 1;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActiveKey(keyAt(Math.min(activeIdx + 1, last)));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActiveKey(keyAt(Math.max(activeIdx - 1, 0)));
        break;
      case "Home":
        if (!onInput) {
          e.preventDefault();
          setActiveKey(keyAt(0));
        }
        break;
      case "End":
        if (!onInput) {
          e.preventDefault();
          setActiveKey(keyAt(last));
        }
        break;
      case " ":
        // no campo de busca o espaço digita
        if (!onInput && visible[activeIdx]) {
          e.preventDefault();
          toggle(visible[activeIdx].value);
        }
        break;
      case "Enter":
        if (visible[activeIdx]) {
          e.preventDefault();
          toggle(visible[activeIdx].value);
        }
        break;
    }
  };

  // Mousedown dentro do painel não tira o foco do listbox/busca (senão o onBlur fecharia).
  const onPanelMouseDown = (e: ReactMouseEvent<HTMLDivElement>) => {
    if (!(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLButtonElement)) e.preventDefault();
  };

  const onRootBlur = (e: ReactFocusEvent<HTMLDivElement>) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOpen(false);
  };

  const clear = () => {
    onChange([]);
    triggerRef.current?.focus();
  };

  const activeDescendant = activeIdx >= 0 ? optionId(activeIdx) : undefined;

  return (
    <div ref={root} className="relative" onBlur={onRootBlur}>
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-labelledby={`${labelId} ${summaryId}`}
        onClick={() => (open ? setOpen(false) : openAt(0))}
        onKeyDown={onTriggerKeyDown}
        className={`flex w-full min-w-0 items-center justify-between gap-2 rounded-card border px-2.5 py-1.5 text-left text-[0.92rem] transition-colors duration-(--duration-quick) disabled:opacity-50 ${
          value.length ? "border-ink bg-surface" : "border-rule bg-surface hover:border-muted"
        }`}
      >
        <span className="min-w-0">
          <span id={labelId} className="block text-[0.72rem] leading-none text-muted">
            {label}
          </span>
          <span id={summaryId} className="mt-0.5 block truncate">
            {summary}
          </span>
        </span>
        <ChevronDown
          className={`size-4 shrink-0 text-muted transition-[rotate] duration-(--duration-fast) ease-(--ease-smooth-out) motion-reduce:transition-none ${
            open ? "rotate-180" : ""
          }`}
          aria-hidden
        />
      </button>

      {(open || closing) && (
        <div
          // Fechando, o painel já está inert: sem foco, sem clique e fora da árvore de acessibilidade.
          inert={!open}
          onTransitionEnd={(e) => {
            if (e.target === e.currentTarget && !open) setClosing(false);
          }}
          onKeyDown={onPanelKeyDown}
          onMouseDown={onPanelMouseDown}
          className={`absolute left-0 z-30 mt-1 w-72 max-w-[calc(100vw-2rem)] origin-top-left rounded-card border border-rule bg-surface p-1.5 transition-[opacity,scale,translate] duration-(--duration-fast) ease-(--ease-smooth-out) ${
            open
              ? "starting:opacity-0 motion-safe:starting:translate-y-[calc(var(--distance-micro)*-1)] motion-safe:starting:scale-(--scale-medium) motion-reduce:duration-(--duration-quick)"
              : "pointer-events-none opacity-0 duration-(--duration-quick) motion-safe:scale-(--scale-tiny)"
          }`}
        >
          {searchable && (
            <div className="mb-1 flex items-center gap-1.5 rounded-[4px] border border-rule px-2 py-1">
              <Search className="size-3.5 text-muted" aria-hidden />
              <input
                ref={inputRef}
                type="text"
                role="combobox"
                aria-label={`Buscar ${label.toLowerCase()}`}
                aria-expanded="true"
                aria-controls={listId}
                aria-autocomplete="list"
                aria-activedescendant={activeDescendant}
                value={term}
                onChange={(e) => {
                  setTerm(e.target.value);
                  setActiveKey(null);
                }}
                placeholder={`Buscar ${label.toLowerCase()}`}
                className="w-full bg-transparent text-[0.9rem] outline-none placeholder:text-muted"
              />
            </div>
          )}
          <ul
            ref={listRef}
            id={listId}
            role="listbox"
            aria-multiselectable="true"
            aria-label={label}
            tabIndex={searchable ? -1 : 0}
            aria-activedescendant={searchable ? undefined : activeDescendant}
            className="max-h-72 overflow-auto outline-none"
          >
            {visible.map((o, i) => {
              const on = selected.has(o.value);
              const active = i === activeIdx;
              return (
                <li
                  key={String(o.value)}
                  id={optionId(i)}
                  role="option"
                  aria-selected={on}
                  onClick={() => {
                    setActiveKey(String(o.value));
                    toggle(o.value);
                  }}
                  className={`flex w-full items-center gap-2 rounded-[4px] px-2 py-1.5 text-[0.9rem] transition-colors duration-(--duration-quick) hover:bg-sunken ${
                    active ? "bg-sunken outline outline-1 -outline-offset-1 outline-ink" : ""
                  }`}
                >
                  <span
                    aria-hidden
                    className={`flex size-4 shrink-0 items-center justify-center rounded-tick border transition-colors duration-(--duration-quick) ${
                      on ? "border-ink bg-ink text-surface" : "border-rule"
                    }`}
                  >
                    {on && (
                      <Check
                        className="size-3 transition-[opacity,scale] duration-(--duration-quick) ease-(--ease-smooth-out) starting:opacity-0 motion-safe:starting:scale-[0.8] motion-reduce:transition-none"
                        strokeWidth={3}
                        aria-hidden
                      />
                    )}
                  </span>
                  <span className="min-w-0 flex-1 truncate">{o.label}</span>
                  {o.hint && <span className="shrink-0 text-[0.78rem] text-muted">{o.hint}</span>}
                </li>
              );
            })}
          </ul>
          {visible.length === 0 && (
            <p role="status" className="label px-2 py-2">
              Nada encontrado.
            </p>
          )}
          {ordered.length > maxVisible && (
            <p className="px-2 py-1.5 text-[0.78rem] text-muted">+{ordered.length - maxVisible} opções. Refine a busca.</p>
          )}
          {value.length > 0 && (
            <button type="button" onClick={clear} className="btn mt-1 w-full justify-center text-muted hover:text-ink">
              <X className="size-3.5" aria-hidden /> Limpar {label.toLowerCase()}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
