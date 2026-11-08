import { Check, ChevronDown, Search, X } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

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
  const [term, setTerm] = useState("");
  const root = useRef<HTMLDivElement>(null);
  const listId = useId();

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const selected = useMemo(() => new Set(value), [value]);
  const filtered = useMemo(() => {
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

  const toggle = (v: V) => onChange(selected.has(v) ? value.filter((x) => x !== v) : [...value, v]);
  const summary =
    value.length === 0
      ? "Todos"
      : value.length === 1
        ? (options.find((o) => o.value === value[0])?.label ?? "1 selecionado")
        : `${value.length} selecionados`;

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((o) => !o)}
        className={`flex w-full min-w-36 items-center justify-between gap-2 rounded-fold border px-2.5 py-1.5 text-left text-[0.92rem] transition-colors disabled:opacity-50 ${
          value.length ? "border-chili bg-paper" : "border-rule bg-paper hover:border-muted"
        }`}
      >
        <span className="min-w-0">
          <span className="block text-[0.72rem] leading-none text-muted">{label}</span>
          <span className="mt-0.5 block truncate">{summary}</span>
        </span>
        <ChevronDown className="size-4 shrink-0 text-muted" aria-hidden />
      </button>

      {open && (
        <div className="absolute left-0 z-30 mt-1 w-72 max-w-[calc(100vw-2rem)] rounded-fold border border-rule bg-paper p-1.5">
          {searchable && (
            <label className="mb-1 flex items-center gap-1.5 rounded-[4px] border border-rule px-2 py-1">
              <Search className="size-3.5 text-muted" aria-hidden />
              <input
                autoFocus
                value={term}
                onChange={(e) => setTerm(e.target.value)}
                placeholder={`Buscar ${label.toLowerCase()}`}
                className="w-full bg-transparent text-[0.9rem] outline-none placeholder:text-muted"
              />
            </label>
          )}
          <ul id={listId} role="listbox" aria-multiselectable aria-label={label} className="max-h-72 overflow-auto">
            {filtered.slice(0, maxVisible).map((o) => {
              const on = selected.has(o.value);
              return (
                <li key={String(o.value)}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={on}
                    onClick={() => toggle(o.value)}
                    className="flex w-full items-center gap-2 rounded-[4px] px-2 py-1.5 text-left text-[0.9rem] hover:bg-kraft"
                  >
                    <span
                      className={`flex size-4 shrink-0 items-center justify-center rounded-clip border ${
                        on ? "border-chili bg-chili text-paper" : "border-rule"
                      }`}
                    >
                      {on && <Check className="size-3" strokeWidth={3} aria-hidden />}
                    </span>
                    <span className="min-w-0 flex-1 truncate">{o.label}</span>
                    {o.hint && <span className="shrink-0 text-[0.78rem] text-muted">{o.hint}</span>}
                  </button>
                </li>
              );
            })}
            {filtered.length === 0 && <li className="label px-2 py-2">Nada encontrado.</li>}
            {filtered.length > maxVisible && (
              <li className="px-2 py-1.5 text-[0.78rem] text-muted">
                +{filtered.length - maxVisible} opções. Refine a busca.
              </li>
            )}
          </ul>
          {value.length > 0 && (
            <button type="button" onClick={() => onChange([])} className="btn mt-1 w-full justify-center text-muted hover:text-ink">
              <X className="size-3.5" aria-hidden /> Limpar {label.toLowerCase()}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
