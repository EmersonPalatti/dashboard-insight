import { CalendarRange, X } from "lucide-react";
import type { Recorte } from "@/lib/filters";
import { MultiSelect } from "../ui/MultiSelect";
import { PeriodPresets } from "./PeriodPresets";
import type { Chip, FilterModel } from "./useFilterModel";

/** Período: presets com indicador e datas personalizadas. Usado na barra (desktop) e na folha (mobile). */
export function PeriodFields({ m }: { m: FilterModel }) {
  const { f, presets, activePreset, set, min, max } = m;
  return (
    <fieldset className="flex flex-wrap items-end gap-1.5">
      <legend className="sr-only">Período</legend>
      <PeriodPresets presets={presets} activeId={activePreset} onSelect={(p) => set({ start: p.start, end: p.end })} />
      {/* o anel de foco fica no wrapper: os inputs nativos não mostram foco sozinhos */}
      <div
        role="group"
        aria-label="Período personalizado"
        className="flex items-center gap-1.5 rounded-card border border-rule bg-surface px-2 py-1 text-[0.88rem] has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ink"
      >
        <CalendarRange className="size-4 text-muted" aria-hidden />
        <input
          type="date"
          aria-label="Início"
          min={min}
          max={f.end ?? max}
          value={f.start ?? ""}
          onChange={(e) => set({ start: e.target.value || null })}
          className="bg-transparent outline-none"
        />
        <span className="text-muted">até</span>
        <input
          type="date"
          aria-label="Fim"
          min={f.start ?? min}
          max={max}
          value={f.end ?? ""}
          onChange={(e) => set({ end: e.target.value || null })}
          className="bg-transparent outline-none"
        />
      </div>
    </fieldset>
  );
}

/** Cidade → Hub → Loja, em cascata: cada escolha limpa os níveis de baixo. */
export function PlaceFields({ m }: { m: FilterModel }) {
  const { f, opts, set } = m;
  return (
    <>
      <MultiSelect label="Cidade" options={opts.cities} value={f.city} onChange={(city) => set({ city, hub: [], store: [] })} />
      <MultiSelect label="Hub" options={opts.hubs} value={f.hub} searchable onChange={(hub) => set({ hub, store: [] })} />
      <MultiSelect label="Loja" options={opts.stores} value={f.store} searchable onChange={(store) => set({ store })} />
    </>
  );
}

/** Segmento, Canal e Modal: ficam no "Mais filtros" do desktop e nos campos da folha no mobile. */
export function ExtraFields({ m }: { m: FilterModel }) {
  const { f, opts, set } = m;
  return (
    <>
      <MultiSelect label="Segmento" options={opts.segments} value={f.segment} onChange={(segment) => set({ segment: segment as Recorte["segment"] })} />
      <MultiSelect
        label="Canal"
        options={opts.channels}
        value={f.channel_type}
        onChange={(channel_type) => set({ channel_type: channel_type as Recorte["channel_type"] })}
      />
      <MultiSelect label="Modal" options={opts.modals} value={f.modal} onChange={(modal) => set({ modal: modal as Recorte["modal"] })} />
    </>
  );
}

/** Chips do recorte com entrada suave (starting: sai de opacidade e escala menores). Remoção é instantânea. */
export function ActiveChips({ chips }: { chips: Chip[] }) {
  return (
    <ul aria-label="Filtros ativos" className="flex flex-wrap items-center gap-1.5">
      {chips.map((c) => (
        <li
          key={c.key}
          className="inline-flex max-w-full items-center gap-1 rounded-[4px] border border-ink bg-surface pl-2 pr-0.5 text-[0.85rem] text-ink transition-[opacity,scale] duration-(--duration-fast) ease-(--ease-smooth-out) starting:scale-(--scale-medium) starting:opacity-0 motion-reduce:transition-none"
        >
          <span className="text-muted">{c.dim}</span>
          <span className="max-w-[16rem] truncate" title={c.value}>
            {c.value}
          </span>
          <button
            type="button"
            aria-label={`Remover ${c.dim}: ${c.value}`}
            onClick={c.remove}
            className="inline-flex size-6 shrink-0 items-center justify-center rounded-[4px] text-muted hover:bg-sunken hover:text-ink"
          >
            <X className="size-3.5" aria-hidden />
          </button>
        </li>
      ))}
    </ul>
  );
}
