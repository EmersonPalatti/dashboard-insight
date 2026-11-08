import { Check, ChevronDown } from "lucide-react";
import {
  useEffect,
  useId,
  useRef,
  useState,
  type FocusEvent as ReactFocusEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
} from "react";

export interface SelectOption<V extends string | number> {
  value: V;
  label: string;
}

interface Props<V extends string | number> {
  /** Rótulo visível ao lado do gatilho; ele também nomeia o gatilho (aria-labelledby). */
  label: string;
  options: SelectOption<V>[];
  value: V;
  onChange: (value: V) => void;
  /** `end` alinha o painel à borda direita do gatilho (seletor à direita do cabeçalho). */
  align?: "start" | "end";
}

/**
 * Fechamento do menu: a transição dura --duration-quick (150ms); se transitionend não
 * disparar, o painel desmonta aqui (um pouco de folga além dos 150ms).
 */
const MENU_CLOSE_FALLBACK_MS = 170;

const fold = (s: string) => s.toLowerCase().normalize("NFD").replace(/\p{M}/gu, "");

/**
 * Seleção única no padrão select-only combobox do WAI-ARIA APG. O foco fica sempre
 * no gatilho; aria-activedescendant aponta a opção ativa do listbox. Visual e
 * fechamento espelham o MultiSelect.
 */
export function Select<V extends string | number>({ label, options, value, onChange, align = "start" }: Props<V>) {
  const [open, setOpen] = useState(false);
  // Painel fechando: segue montado para a animação, mas já está fechado para ARIA e foco (open false).
  const [closing, setClosing] = useState(false);
  const [wasOpen, setWasOpen] = useState(open);
  // Ajuste durante a renderização (sem effect): o painel não desmonta no commit em que fecha.
  if (wasOpen !== open) {
    setWasOpen(open);
    setClosing(!open);
  }
  // Índice da opção ativa (visual e aria-activedescendant). As opções são fixas, então o índice basta.
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const uid = useId();
  const triggerId = `${uid}-trigger`;
  const labelId = `${uid}-label`;
  const valueId = `${uid}-value`;
  const listId = `${uid}-list`;
  const optionId = (i: number) => `${uid}-option-${i}`;

  const selectedIdx = options.findIndex((o) => o.value === value);
  const selectedLabel = options[selectedIdx]?.label ?? "";
  const last = options.length - 1;

  // Fallback do fechamento: se transitionend não disparar, o painel desmonta no mesmo tempo.
  useEffect(() => {
    if (!closing) return;
    const t = window.setTimeout(() => setClosing(false), MENU_CLOSE_FALLBACK_MS);
    return () => window.clearTimeout(t);
  }, [closing]);

  // Clique fora fecha (Safari não foca botões ao clicar, então o onBlur sozinho não basta).
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  // Mantém a opção ativa visível na rolagem do listbox.
  useEffect(() => {
    if (!open) return;
    listRef.current?.querySelectorAll<HTMLElement>('[role="option"]')[active]?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  const openMenu = () => {
    setActive(selectedIdx < 0 ? 0 : selectedIdx);
    setOpen(true);
  };

  const choose = (i: number) => {
    const o = options[i];
    if (!o) return;
    setActive(i);
    setOpen(false);
    if (o.value !== value) onChange(o.value);
  };

  /** Próxima opção (a partir de `from`, com volta) cujo rótulo começa com a letra digitada. */
  const findByLetter = (letter: string, from: number) => {
    const c = fold(letter);
    for (let k = 1; k <= options.length; k++) {
      const i = (from + k) % options.length;
      if (fold(options[i].label).startsWith(c)) return i;
    }
    return -1;
  };

  const onTriggerKeyDown = (e: ReactKeyboardEvent<HTMLButtonElement>) => {
    switch (e.key) {
      case "Enter":
      case " ":
        e.preventDefault();
        if (open) choose(active);
        else openMenu();
        break;
      case "ArrowDown":
        e.preventDefault();
        if (open) setActive(Math.min(active + 1, last));
        else openMenu();
        break;
      case "ArrowUp":
        e.preventDefault();
        if (open) setActive(Math.max(active - 1, 0));
        else openMenu();
        break;
      case "Home":
        if (open) {
          e.preventDefault();
          setActive(0);
        }
        break;
      case "End":
        if (open) {
          e.preventDefault();
          setActive(last);
        }
        break;
      case "Escape":
        // Só consome o Escape se o menu estava aberto (senão um diálogo pai pode fechar).
        if (open) {
          e.preventDefault();
          e.stopPropagation();
          setOpen(false);
        }
        break;
      case "Tab":
        // Sem preventDefault: o foco segue para o próximo controle da página.
        if (open) setOpen(false);
        break;
      default:
        // Digitar uma letra: no menu aberto move a opção ativa; fechado, troca a seleção.
        if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
          if (open) {
            const i = findByLetter(e.key, active);
            if (i >= 0) setActive(i);
          } else {
            const i = findByLetter(e.key, selectedIdx);
            if (i >= 0 && i !== selectedIdx) onChange(options[i].value);
          }
        }
    }
  };

  // Mousedown dentro do painel não tira o foco do gatilho (senão o onBlur fecharia antes do clique).
  const onPanelMouseDown = (e: ReactMouseEvent<HTMLDivElement>) => e.preventDefault();

  const onRootBlur = (e: ReactFocusEvent<HTMLDivElement>) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOpen(false);
  };

  const activeDescendant = open && active >= 0 ? optionId(active) : undefined;

  return (
    <div className="inline-flex items-center gap-2">
      <label id={labelId} htmlFor={triggerId} className="text-[0.85rem] text-muted">
        {label}
      </label>
      <div ref={root} className="relative" onBlur={onRootBlur}>
        <button
          id={triggerId}
          type="button"
          role="combobox"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          aria-labelledby={`${labelId} ${valueId}`}
          aria-activedescendant={activeDescendant}
          onClick={() => (open ? setOpen(false) : openMenu())}
          onKeyDown={onTriggerKeyDown}
          className="btn-ghost min-h-10 min-w-40 justify-between text-left max-lg:min-h-11"
        >
          <span id={valueId} className="min-w-0 flex-1 truncate">
            {selectedLabel}
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
            // Fechando, o painel já está inert: sem clique e fora da árvore de acessibilidade.
            inert={!open}
            onTransitionEnd={(e) => {
              if (e.target === e.currentTarget && !open) setClosing(false);
            }}
            onMouseDown={onPanelMouseDown}
            className={`absolute z-30 mt-1 w-max min-w-full max-w-[calc(100vw-2rem)] rounded-card border border-rule bg-surface p-1.5 transition-[opacity,scale,translate] duration-(--duration-fast) ease-(--ease-smooth-out) ${
              align === "end" ? "right-0 origin-top-right" : "left-0 origin-top-left"
            } ${
              open
                ? "starting:opacity-0 motion-safe:starting:translate-y-[calc(var(--distance-micro)*-1)] motion-safe:starting:scale-(--scale-medium) motion-reduce:duration-(--duration-quick)"
                : "pointer-events-none opacity-0 duration-(--duration-quick) motion-safe:scale-(--scale-tiny)"
            }`}
          >
            <ul
              ref={listRef}
              id={listId}
              role="listbox"
              aria-labelledby={labelId}
              className="max-h-72 overflow-auto outline-none"
            >
              {options.map((o, i) => {
                const on = o.value === value;
                const isActive = open && i === active;
                return (
                  <li
                    key={String(o.value)}
                    id={optionId(i)}
                    role="option"
                    aria-selected={on}
                    onClick={() => choose(i)}
                    className={`flex w-full items-center gap-2 rounded-[4px] px-2 py-1.5 text-[0.9rem] transition-colors duration-(--duration-quick) hover:bg-sunken ${
                      isActive ? "bg-sunken outline outline-1 -outline-offset-1 outline-ink" : ""
                    }`}
                  >
                    <span aria-hidden className="flex size-3.5 shrink-0 items-center justify-center">
                      {on && (
                        <Check
                          className="size-3.5 text-ink transition-[opacity,scale] duration-(--duration-quick) ease-(--ease-smooth-out) starting:opacity-0 motion-safe:starting:scale-[0.8] motion-reduce:transition-none"
                          strokeWidth={3}
                          aria-hidden
                        />
                      )}
                    </span>
                    <span className="min-w-0 flex-1 truncate">{o.label}</span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
