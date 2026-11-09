import { Calendar } from "lucide-react";
import { useState } from "react";
import type { Recorte } from "@/lib/filters";
import { DatePicker } from "../ui/DatePicker";
import { MultiSelect } from "../ui/MultiSelect";
import { PeriodPresets, presetClass } from "./PeriodPresets";
import { Popover } from "./Popover";
import type { FilterModel, PresetOption } from "./useFilterModel";

/** Início e Fim empilhados, cada um um campo de 40px que abre o próprio calendário. */
function DateRange({ m }: { m: FilterModel }) {
  const { f, set, min, max } = m;
  // DatePicker precisa dos limites do dataset (vêm de /api/meta); antes deles não há calendário
  if (!min || !max) return null;
  return (
    <div role="group" aria-label="Período personalizado" className="grid gap-1.5">
      <DatePicker label="Início" min={min} max={f.end ?? max} value={f.start} rangeOther={f.end} onChange={(start) => set({ start })} />
      <DatePicker label="Fim" min={f.start ?? min} max={max} value={f.end} rangeOther={f.start} onChange={(end) => set({ end })} />
    </div>
  );
}

/**
 * Período num controle só: Tudo | 30 dias | 7 dias | Datas, com o mesmo indicador.
 * Na barra (desktop), Datas abre um popover com Início e Fim; na folha (mobile),
 * abre os dois campos logo abaixo, em fluxo, para o calendário não ser cortado.
 */
export function PeriodFields({ m, variant = "bar" }: { m: FilterModel; variant?: "bar" | "sheet" }) {
  const { presets, activePreset, customDates, datesLabel, datesReady, set } = m;
  const [sheetDates, setSheetDates] = useState(false);
  const activeId = activePreset ?? (customDates ? "dates" : undefined);
  const datesInner = (
    <>
      <Calendar className="size-3.5 shrink-0" aria-hidden />
      <span className="tabular-nums">{datesLabel}</span>
    </>
  );
  const pick = (p: PresetOption) => {
    setSheetDates(false);
    set({ start: p.start, end: p.end });
  };

  if (variant === "sheet") {
    const showDates = datesReady && (sheetDates || customDates);
    return (
      <fieldset className="grid">
        <legend className="sr-only">Período</legend>
        <PeriodPresets
          presets={presets}
          activeId={activeId}
          onSelect={pick}
          extra={
            <button
              type="button"
              data-preset="dates"
              aria-pressed={customDates}
              aria-expanded={showDates}
              aria-controls="periodo-datas"
              disabled={!datesReady}
              onClick={() => setSheetDates((v) => !v)}
              className={presetClass(customDates)}
            >
              {datesInner}
            </button>
          }
        />
        {/* accordion: a linha da grade vai de 0fr a 1fr (sem animar altura), mesma duração nos dois sentidos */}
        <div
          id="periodo-datas"
          inert={!showDates}
          className={`grid transition-[grid-template-rows,opacity] duration-(--duration-fast) ease-(--ease-smooth-out) motion-reduce:transition-none ${
            showDates ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
          }`}
        >
          {/* o respiro acompanha a linha: com 0fr o padding não encolhe, então ele também vai a zero */}
          <div
            className={`min-h-0 transition-[padding] duration-(--duration-fast) ease-(--ease-smooth-out) motion-reduce:transition-none ${
              showDates ? "pt-2" : "overflow-hidden pt-0"
            }`}
          >
            <DateRange m={m} />
          </div>
        </div>
      </fieldset>
    );
  }

  return (
    <fieldset className="flex">
      <legend className="sr-only">Período</legend>
      <PeriodPresets
        presets={presets}
        activeId={activeId}
        onSelect={pick}
        extra={
          <Popover
            id="periodo-datas"
            align="left"
            panelClassName="w-[18rem] p-2"
            triggerClassName={`${presetClass(customDates)} h-full`}
            triggerProps={{
              "data-preset": "dates",
              "aria-pressed": customDates,
              "aria-label": `Datas: ${customDates ? datesLabel : "escolher início e fim"}`,
              disabled: !datesReady,
            }}
            trigger={datesInner}
          >
            <DateRange m={m} />
          </Popover>
        }
      />
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
