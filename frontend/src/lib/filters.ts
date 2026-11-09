/**
 * Estado global do recorte (Nanostores) sincronizado com a query string.
 *
 * As ilhas React não compartilham árvore: o FilterBar escreve no átomo e cada
 * gráfico, tabela e o agente escutam o mesmo átomo. A URL usa as mesmas chaves
 * da API (`?city=Curitiba&hub=8&hub=13`), então um link compartilhado reabre o
 * mesmo recorte.
 */
import { atom, computed } from "nanostores";
import type { Filters } from "./api/client";

type Segment = NonNullable<Filters["segment"]>[number];
type ChannelType = NonNullable<Filters["channel_type"]>[number];
type Modal = NonNullable<Filters["modal"]>[number];
type OrderStatus = NonNullable<Filters["status"]>[number];

export interface Recorte {
  start: string | null;
  end: string | null;
  city: string[];
  hub: number[];
  store: number[];
  segment: Segment[];
  channel_type: ChannelType[];
  modal: Modal[];
  status: OrderStatus[];
}

export const EMPTY: Recorte = {
  start: null,
  end: null,
  city: [],
  hub: [],
  store: [],
  segment: [],
  channel_type: [],
  modal: [],
  status: [],
};

const SEGMENTS: Segment[] = ["food", "good"];
const CHANNELS: ChannelType[] = ["marketplace", "own"];
const MODALS: Modal[] = ["moto", "bike"];
const STATUSES: OrderStatus[] = ["delivered", "canceled"];
const DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Recorte atual. Fica vazio até `initFilters()` ler a URL no navegador. */
export const $filters = atom<Recorte>(EMPTY);
/** Falso no SSR e até a URL ser lida: as queries esperam por ele. */
export const $ready = atom(false);

export const $activeCount = computed($filters, (f) =>
  [
    f.start || f.end ? 1 : 0,
    f.city.length,
    f.hub.length,
    f.store.length,
    f.segment.length,
    f.channel_type.length,
    f.modal.length,
    f.status.length,
  ].reduce((a, b) => a + (b ? 1 : 0), 0),
);

function ints(values: string[]): number[] {
  return values.map(Number).filter((n) => Number.isInteger(n) && n > 0);
}

function oneOf<T extends string>(values: string[], allowed: T[]): T[] {
  return values.filter((v): v is T => (allowed as string[]).includes(v));
}

export function parseSearch(search: string): Recorte {
  const p = new URLSearchParams(search);
  const start = p.get("start");
  const end = p.get("end");
  return {
    start: start && DATE.test(start) ? start : null,
    end: end && DATE.test(end) ? end : null,
    city: p.getAll("city"),
    hub: ints(p.getAll("hub")),
    store: ints(p.getAll("store")),
    segment: oneOf(p.getAll("segment"), SEGMENTS),
    channel_type: oneOf(p.getAll("channel_type"), CHANNELS),
    modal: oneOf(p.getAll("modal"), MODALS),
    status: oneOf(p.getAll("status"), STATUSES),
  };
}

export function toQuery(f: Recorte): Record<string, string | (string | number)[] | null> {
  return {
    start: f.start,
    end: f.end,
    city: f.city,
    hub: f.hub,
    store: f.store,
    segment: f.segment,
    channel_type: f.channel_type,
    modal: f.modal,
    status: f.status,
  };
}

/** Corpo JSON do recorte para o POST do agente. */
export function toBody(f: Recorte): Filters {
  return {
    ...(f.start ? { start: f.start } : {}),
    ...(f.end ? { end: f.end } : {}),
    city: f.city,
    hub: f.hub,
    store: f.store,
    segment: f.segment,
    channel_type: f.channel_type,
    modal: f.modal,
    status: f.status,
  };
}

function writeUrl(f: Recorte) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(toQuery(f))) {
    if (Array.isArray(value)) value.forEach((v) => params.append(key, String(v)));
    else if (value) params.set(key, value);
  }
  const qs = params.toString();
  const next = `${location.pathname}${qs ? `?${qs}` : ""}${location.hash}`;
  if (next !== `${location.pathname}${location.search}${location.hash}`) history.pushState(null, "", next);
}

let started = false;

/** Chamado uma vez por qualquer ilha; idempotente. */
export function initFilters() {
  if (started || typeof window === "undefined") return;
  started = true;
  $filters.set(parseSearch(location.search));
  $ready.set(true);
  $filters.listen(writeUrl);
  window.addEventListener("popstate", () => $filters.set(parseSearch(location.search)));
}

export function patchFilters(patch: Partial<Recorte>) {
  $filters.set({ ...$filters.get(), ...patch });
}

export function resetFilters() {
  $filters.set(EMPTY);
}

/** Aplica o drill-down de um alerta (ex.: `{hub: [55]}`) por cima do recorte atual. */
export function applyDrilldown(filters: Record<string, (string | number)[]>) {
  const patch: Partial<Recorte> = {};
  if (filters.hub) patch.hub = ints(filters.hub.map(String));
  if (filters.store) patch.store = ints(filters.store.map(String));
  if (filters.city) patch.city = filters.city.map(String);
  patchFilters(patch);
}

export function shareUrl(): string {
  return typeof window === "undefined" ? "" : location.href;
}
