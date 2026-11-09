import { useStore } from "@nanostores/react";
import { useMemo } from "react";
import { $activeCount, $filters, patchFilters, type Recorte } from "@/lib/filters";
import { fmt, label } from "@/lib/format";
import { useMeta } from "@/lib/query";

function shiftDays(iso: string, days: number) {
  const d = new Date(`${iso}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** ISO → dd/mm/aaaa sem converter fuso: só separa a string. */
function brDate(iso: string) {
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

function periodLabel(start: string | null, end: string | null) {
  if (start && end) return `${brDate(start)} – ${brDate(end)}`;
  if (start) return `a partir de ${brDate(start)}`;
  return `até ${brDate(end ?? "")}`;
}

/** ISO → dd/mm, para o segmento Datas (o dataset cabe num ano só). */
function dayMonth(iso: string) {
  const [, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}`;
}

const nameOf = (names: Map<string, string>, v: string | number) => names.get(String(v)) ?? `ID ${v}`;

export interface Chip {
  key: string;
  dim: string;
  value: string;
  remove: () => void;
}

/** Até 3 valores geram um chip cada; mais que isso, um chip "N selecionados" que limpa a dimensão. */
function chipsOf<V extends string | number>(
  dim: string,
  values: V[],
  name: (v: V) => string,
  removeOne: (v: V) => void,
  clearAll: () => void,
): Chip[] {
  if (values.length > 3) return [{ key: dim, dim, value: `${values.length} selecionados`, remove: clearAll }];
  return values.map((v) => ({ key: `${dim}-${v}`, dim, value: name(v), remove: () => removeOne(v) }));
}

export interface PresetOption {
  id: "all" | "30d" | "7d";
  /** Nome completo (chip, leitor de tela). */
  label: string;
  /** Nome no segmento da barra. */
  short: string;
  start: string | null;
  end: string | null;
  /** Precisa da última data do dataset, que só chega com /api/meta. */
  disabled?: boolean;
}

/**
 * Estado derivado do recorte para os controles: opções em cascata, nomes para
 * os chips, presets de período. Os dois layouts (barra e folha) usam o mesmo.
 */
export function useFilterModel() {
  const f = useStore($filters);
  const active = useStore($activeCount);
  const { data: meta } = useMeta();

  // limites do dataset vêm só de /api/meta (regra: sem nomes ou datas fixas no código).
  // Antes dele chegar, min e max são undefined: presets e Datas ficam desabilitados.
  const min = meta?.min_date;
  const max = meta?.max_date;
  const datesReady = Boolean(min && max);
  const presets: PresetOption[] = [
    { id: "all", label: "Tudo", short: "Tudo", start: null, end: null },
    { id: "30d", label: "Últimos 30 dias", short: "30 dias", start: max ? shiftDays(max, -29) : null, end: max ?? null, disabled: !max },
    { id: "7d", label: "Últimos 7 dias", short: "7 dias", start: max ? shiftDays(max, -6) : null, end: max ?? null, disabled: !max },
  ];
  const activePreset = presets.find((p) => !p.disabled && p.start === f.start && p.end === f.end)?.id;

  // dimensões do "Mais filtros" (desktop) que têm algum valor selecionado
  const extraCount = [f.segment, f.channel_type, f.modal].filter((v) => v.length > 0).length;

  const opts = useMemo(() => {
    const hubCity = new Map(meta?.hubs.map((h) => [Number(h.value), String(h.parent)]) ?? []);
    const toOpt = <V extends string | number>(o: { value: string | number; label: string; orders: number }) =>
      ({ value: o.value as V, label: label(o.label), hint: fmt.intCompact(o.orders) });
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

  // nomes dos valores selecionados vêm dos metadados sem filtro: o cascade pode ter escondido a opção
  const names = useMemo(() => {
    const by = (list?: { value: string | number; label: string }[]) => new Map((list ?? []).map((o) => [String(o.value), label(o.label)]));
    return {
      city: by(meta?.cities),
      hub: by(meta?.hubs),
      store: by(meta?.stores),
      segment: by(meta?.segments),
      channel: by(meta?.channel_types),
      modal: by(meta?.modals),
    };
  }, [meta]);

  const set = (patch: Partial<Recorte>) => patchFilters(patch);

  // mesmos cascades dos onChange dos seletores: cidade limpa hub e loja, hub limpa loja
  const presetName = presets.find((p) => p.id === activePreset)?.label;
  const chips: Chip[] = [
    ...(f.start || f.end
      ? [{ key: "period", dim: "Período", value: presetName ?? periodLabel(f.start, f.end), remove: () => set({ start: null, end: null }) }]
      : []),
    ...chipsOf(
      "Cidade",
      f.city,
      (c) => nameOf(names.city, c),
      (c) => set({ city: f.city.filter((x) => x !== c), hub: [], store: [] }),
      () => set({ city: [], hub: [], store: [] }),
    ),
    ...chipsOf(
      "Hub",
      f.hub,
      (h) => nameOf(names.hub, h),
      (h) => set({ hub: f.hub.filter((x) => x !== h), store: [] }),
      () => set({ hub: [], store: [] }),
    ),
    ...chipsOf(
      "Loja",
      f.store,
      (s) => nameOf(names.store, s),
      (s) => set({ store: f.store.filter((x) => x !== s) }),
      () => set({ store: [] }),
    ),
    ...chipsOf(
      "Segmento",
      f.segment,
      (s) => nameOf(names.segment, s),
      (s) => set({ segment: f.segment.filter((x) => x !== s) }),
      () => set({ segment: [] }),
    ),
    ...chipsOf(
      "Canal",
      f.channel_type,
      (c) => nameOf(names.channel, c),
      (c) => set({ channel_type: f.channel_type.filter((x) => x !== c) }),
      () => set({ channel_type: [] }),
    ),
    ...chipsOf(
      "Modal",
      f.modal,
      (m) => nameOf(names.modal, m),
      (m) => set({ modal: f.modal.filter((x) => x !== m) }),
      () => set({ modal: [] }),
    ),
    ...chipsOf(
      "Status",
      f.status,
      (s) => label(s),
      (s) => set({ status: f.status.filter((x) => x !== s) }),
      () => set({ status: [] }),
    ),
  ];

  // período personalizado: datas que não batem com nenhum preset
  const customDates = !activePreset && Boolean(f.start || f.end);
  const datesLabel = !customDates
    ? "Datas"
    : f.start && f.end
      ? `${dayMonth(f.start)} – ${dayMonth(f.end)}`
      : f.start
        ? `desde ${dayMonth(f.start)}`
        : `até ${dayMonth(f.end ?? "")}`;

  return { f, active, min, max, datesReady, presets, activePreset, customDates, datesLabel, extraCount, opts, chips, set };
}

export type FilterModel = ReturnType<typeof useFilterModel>;
