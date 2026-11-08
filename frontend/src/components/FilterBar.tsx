import { useStore } from "@nanostores/react";
import { CalendarRange, Check, Download, Link2, RotateCcw } from "lucide-react";
import { useMemo, useState } from "react";
import { $activeCount, $filters, patchFilters, resetFilters, shareUrl, type Recorte } from "@/lib/filters";
import { fmt, label } from "@/lib/format";
import { island, useMeta } from "@/lib/query";
import { ExportDialog } from "./ExportDialog";
import { MultiSelect, type SelectOption } from "./ui/MultiSelect";

function shiftDays(iso: string, days: number) {
  const d = new Date(`${iso}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function FilterBarInner() {
  const f = useStore($filters);
  const active = useStore($activeCount);
  const { data: meta } = useMeta();
  const [copied, setCopied] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);

  const max = meta?.max_date ?? "2021-04-30";
  const min = meta?.min_date ?? "2021-01-01";
  const presets = [
    { id: "all", label: "Tudo", start: null, end: null },
    { id: "30d", label: "Últimos 30 dias", start: shiftDays(max, -29), end: max },
    { id: "7d", label: "Últimos 7 dias", start: shiftDays(max, -6), end: max },
  ] as const;
  const activePreset = presets.find((p) => p.start === f.start && p.end === f.end)?.id;

  const opts = useMemo(() => {
    const hubCity = new Map(meta?.hubs.map((h) => [Number(h.value), String(h.parent)]) ?? []);
    const toOpt = <V extends string | number>(o: { value: string | number; label: string; orders: number }) =>
      ({ value: o.value as V, label: label(o.label), hint: fmt.intCompact(o.orders) }) satisfies SelectOption<V>;
    return {
      cities: meta?.cities.map((o) => toOpt<string>(o)) ?? [],
      hubs:
        meta?.hubs
          .filter((h) => !f.city.length || f.city.includes(String(h.parent)))
          .map((o) => ({ ...toOpt<number>(o), hint: `${String(o.parent)} · ${fmt.intCompact(o.orders)}` })) ?? [],
      stores:
        meta?.stores
          .filter((s) => (!f.hub.length || f.hub.includes(Number(s.parent))) && (!f.city.length || f.city.includes(hubCity.get(Number(s.parent)) ?? "")))
          .map((o) => toOpt<number>(o)) ?? [],
      segments: meta?.segments.map((o) => toOpt<string>(o)) ?? [],
      channels: meta?.channel_types.map((o) => toOpt<string>(o)) ?? [],
      modals: meta?.modals.map((o) => toOpt<string>(o)) ?? [],
    };
  }, [meta, f.city, f.hub]);

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl());
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard negado: o link continua na barra de endereço */
    }
  };

  const set = (patch: Partial<Recorte>) => patchFilters(patch);

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-end gap-2">
        <fieldset className="flex flex-wrap items-end gap-1.5">
          <legend className="sr-only">Período</legend>
          <div className="inline-flex rounded-fold border border-rule bg-kraft p-0.5">
            {presets.map((p) => (
              <button
                key={p.id}
                type="button"
                aria-pressed={activePreset === p.id}
                onClick={() => set({ start: p.start, end: p.end })}
                className={`rounded-[4px] px-2.5 py-1.5 text-[0.85rem] ${
                  activePreset === p.id ? "bg-paper text-ink shadow-[inset_0_-2px_0_var(--chili)]" : "text-muted hover:text-ink"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-1.5 rounded-fold border border-rule bg-paper px-2 py-1 text-[0.88rem]">
            <CalendarRange className="size-4 text-muted" aria-hidden />
            <span className="sr-only">Início</span>
            <input
              type="date"
              min={min}
              max={f.end ?? max}
              value={f.start ?? ""}
              onChange={(e) => set({ start: e.target.value || null })}
              className="bg-transparent outline-none"
            />
            <span className="text-muted">até</span>
            <span className="sr-only">Fim</span>
            <input
              type="date"
              min={f.start ?? min}
              max={max}
              value={f.end ?? ""}
              onChange={(e) => set({ end: e.target.value || null })}
              className="bg-transparent outline-none"
            />
          </label>
        </fieldset>

        <div className="grid flex-1 grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-6">
          <MultiSelect label="Cidade" options={opts.cities} value={f.city} onChange={(city) => set({ city, hub: [], store: [] })} />
          <MultiSelect label="Hub" options={opts.hubs} value={f.hub} searchable onChange={(hub) => set({ hub, store: [] })} />
          <MultiSelect label="Loja" options={opts.stores} value={f.store} searchable onChange={(store) => set({ store })} />
          <MultiSelect
            label="Segmento"
            options={opts.segments}
            value={f.segment}
            onChange={(segment) => set({ segment: segment as Recorte["segment"] })}
          />
          <MultiSelect
            label="Canal"
            options={opts.channels}
            value={f.channel_type}
            onChange={(channel_type) => set({ channel_type: channel_type as Recorte["channel_type"] })}
          />
          <MultiSelect
            label="Modal"
            options={opts.modals}
            value={f.modal}
            onChange={(modal) => set({ modal: modal as Recorte["modal"] })}
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <p className="label mr-auto">
          {active === 0 ? "Recorte completo: todos os pedidos do período." : `${active} filtro(s) ativo(s). Tudo abaixo segue este recorte.`}
        </p>
        {active > 0 && (
          <button type="button" className="btn-ghost" onClick={resetFilters}>
            <RotateCcw className="size-3.5" aria-hidden /> Limpar
          </button>
        )}
        <button type="button" className="btn-ghost" onClick={copyLink}>
          {copied ? <Check className="size-3.5" aria-hidden /> : <Link2 className="size-3.5" aria-hidden />}
          {copied ? "Link copiado" : "Copiar link do recorte"}
        </button>
        <button type="button" className="btn-primary" onClick={() => setExportOpen(true)}>
          <Download className="size-3.5" aria-hidden /> Exportar
        </button>
      </div>
      <ExportDialog open={exportOpen} onClose={() => setExportOpen(false)} />
    </div>
  );
}

export default island(FilterBarInner, 96);
