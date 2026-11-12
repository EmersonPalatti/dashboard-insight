/**
 * Estado global do recorte (Nanostores) sincronizado com a query string.
 *
 * As ilhas React não compartilham árvore: o FilterBar escreve no átomo e cada
 * gráfico, tabela e o agente escutam o mesmo átomo. A URL usa as mesmas chaves
 * da API (`?city=Curitiba&hub=8&hub=13`), então um link compartilhado reabre o
 * mesmo recorte. Chaves de vista (`rank`, `trend`, `grain`) ficam na URL para
 * o link reproduzir a tela, e nunca entram no corpo do recorte enviado à API.
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

/** Quebra do ranking. Os valores são os da API (`by`), não rótulos. */
export type RankBy = "hub" | "store" | "city" | "channel" | "modal" | "payment_method" | "weekday";
/** Métrica do gráfico de tendência. */
export type TrendView = "volume" | "sla" | "cancel";
/** Grão do gráfico de tendência. */
export type TrendGrain = "hour" | "day" | "week";

export interface PanelView {
  rank: RankBy;
  trend: TrendView;
  grain: TrendGrain;
}

export const DEFAULT_VIEW: PanelView = { rank: "hub", trend: "volume", grain: "day" };

const SEGMENTS: Segment[] = ["food", "good"];
const CHANNELS: ChannelType[] = ["marketplace", "own"];
const MODALS: Modal[] = ["moto", "bike"];
const STATUSES: OrderStatus[] = ["delivered", "canceled"];
const RANKS: RankBy[] = ["hub", "store", "city", "channel", "modal", "payment_method", "weekday"];
const TRENDS: TrendView[] = ["volume", "sla", "cancel"];
const GRAINS: TrendGrain[] = ["hour", "day", "week"];
const DATE = /^\d{4}-\d{2}-\d{2}$/;
/** Mesmos tetos de `Filters` no backend: lista de 50, texto de 80, data entre 2000 e 2100. */
const LIST_CAP = 50;
const TEXT_CAP = 80;
const OWNED_KEYS = [
  "start",
  "end",
  "city",
  "hub",
  "store",
  "segment",
  "channel_type",
  "modal",
  "status",
  "rank",
  "trend",
  "grain",
];

export interface IgnoredValue {
  label: string;
  value: string;
  reason: string;
}

/** Recorte atual. Fica vazio até `initFilters()` ler a URL no navegador. */
export const $filters = atom<Recorte>(EMPTY);
/** Vista que um link compartilhado deve reabrir. Não vai para a API. */
export const $view = atom<PanelView>(DEFAULT_VIEW);
/** Valores da URL que não entraram no recorte. A ilha avisa uma vez. */
export const $ignored = atom<IgnoredValue[]>([]);
/**
 * Incrementa quando o gráfico de lojas pede foco no primeiro filtro de loja
 * do ranking. O ranking consome e não dispara de novo para o mesmo número.
 */
export const $focusRank = atom(0);
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

function note(ignored: IgnoredValue[], label: string, value: string, reason: string) {
  ignored.push({ label, value, reason });
}

function validDate(value: string): boolean {
  if (!DATE.test(value)) return false;
  const [y, m, d] = value.split("-").map(Number);
  if (y < 2000 || y > 2100) return false;
  const dt = new Date(Date.UTC(y, m - 1, d));
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d;
}

function capList<T>(values: T[], label: string, ignored: IgnoredValue[]): T[] {
  if (values.length <= LIST_CAP) return values;
  note(ignored, label, String(values.length), `o recorte aceita no máximo ${LIST_CAP} valores`);
  return values.slice(0, LIST_CAP);
}

function takeEnums<T extends string>(
  values: string[],
  allowed: readonly T[],
  label: string,
  reason: string,
  ignored: IgnoredValue[],
): T[] {
  const out: T[] = [];
  for (const value of values) {
    if ((allowed as readonly string[]).includes(value)) out.push(value as T);
    else note(ignored, label, value, reason);
  }
  return capList(out, label, ignored);
}

function takeIds(values: string[], label: string, ignored: IgnoredValue[]): number[] {
  const out: number[] = [];
  for (const value of values) {
    const n = Number(value);
    if (Number.isInteger(n) && n > 0) out.push(n);
    else note(ignored, label, value, "precisa ser um número inteiro maior que zero");
  }
  return capList(out, label, ignored);
}

function takeCities(values: string[], ignored: IgnoredValue[]): string[] {
  const out: string[] = [];
  for (const value of values) {
    if (!value) continue;
    if (value.length > TEXT_CAP) note(ignored, "Cidade", `${value.slice(0, 24)}…`, "passa de 80 caracteres");
    else out.push(value);
  }
  return capList(out, "Cidade", ignored);
}

function takeDate(value: string | null, label: string, ignored: IgnoredValue[]): string | null {
  if (!value) return null;
  if (validDate(value)) return value;
  note(ignored, label, value, "a data precisa existir, no formato aaaa-mm-dd, entre 2000 e 2100");
  return null;
}

function takeOne<T extends string>(
  value: string | null,
  allowed: readonly T[],
  fallback: T,
  label: string,
  reason: string,
  ignored: IgnoredValue[],
): T {
  if (!value) return fallback;
  if ((allowed as readonly string[]).includes(value)) return value as T;
  note(ignored, label, value, reason);
  return fallback;
}

export interface ParsedSearch {
  recorte: Recorte;
  view: PanelView;
  ignored: IgnoredValue[];
}

/** Lê a query string. Valor fora do contrato vira nota, não entra no recorte nem na vista. */
export function readSearch(search: string): ParsedSearch {
  const p = new URLSearchParams(search);
  const ignored: IgnoredValue[] = [];
  const start = takeDate(p.get("start"), "Início", ignored);
  let end = takeDate(p.get("end"), "Fim", ignored);
  if (start && end && end < start) {
    note(ignored, "Fim", end, "é anterior ao início");
    end = null;
  }
  return {
    recorte: {
      start,
      end,
      city: takeCities(p.getAll("city"), ignored),
      hub: takeIds(p.getAll("hub"), "Hub", ignored),
      store: takeIds(p.getAll("store"), "Loja", ignored),
      segment: takeEnums(p.getAll("segment"), SEGMENTS, "Segmento", "o valor aceito é food ou good", ignored),
      channel_type: takeEnums(
        p.getAll("channel_type"),
        CHANNELS,
        "Canal",
        "o valor aceito é marketplace ou own",
        ignored,
      ),
      modal: takeEnums(p.getAll("modal"), MODALS, "Modal", "o valor aceito é moto ou bike", ignored),
      status: takeEnums(
        p.getAll("status"),
        STATUSES,
        "Status",
        "o valor aceito é delivered ou canceled",
        ignored,
      ),
    },
    view: {
      rank: takeOne(
        p.get("rank"),
        RANKS,
        DEFAULT_VIEW.rank,
        "Quebrar por",
        "o valor aceito é hub, store, city, channel, modal, payment_method ou weekday",
        ignored,
      ),
      trend: takeOne(
        p.get("trend"),
        TRENDS,
        DEFAULT_VIEW.trend,
        "Métrica da tendência",
        "o valor aceito é volume, sla ou cancel",
        ignored,
      ),
      grain: takeOne(
        p.get("grain"),
        GRAINS,
        DEFAULT_VIEW.grain,
        "Granularidade",
        "o valor aceito é hour, day ou week",
        ignored,
      ),
    },
    ignored,
  };
}

export function parseSearch(search: string): Recorte {
  return readSearch(search).recorte;
}

/** Uma frase, ou a lista, para o aviso que aparece uma vez. */
export function ignoredMessage(items: IgnoredValue[]): string {
  if (items.length === 0) return "";
  if (items.length === 1) {
    const item = items[0];
    return `${item.label} "${item.value}" ficou de fora do recorte: ${item.reason}.`;
  }
  const bits = items.map((item) => `${item.label} "${item.value}" (${item.reason})`);
  return `Alguns valores da URL ficaram de fora do recorte: ${bits.join("; ")}.`;
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

/** Corpo JSON do recorte para o POST do agente. Sem as chaves de vista. */
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

function canonicalParams(f: Recorte, view: PanelView, current: URLSearchParams): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of current.entries()) {
    if (!OWNED_KEYS.includes(key)) params.append(key, value);
  }
  const add = (key: string, value: string | number | null | undefined) => {
    if (value !== null && value !== undefined && value !== "") params.append(key, String(value));
  };
  add("start", f.start);
  add("end", f.end);
  f.city.forEach((value) => add("city", value));
  f.hub.forEach((value) => add("hub", value));
  f.store.forEach((value) => add("store", value));
  f.segment.forEach((value) => add("segment", value));
  f.channel_type.forEach((value) => add("channel_type", value));
  f.modal.forEach((value) => add("modal", value));
  f.status.forEach((value) => add("status", value));
  if (view.rank !== DEFAULT_VIEW.rank) add("rank", view.rank);
  if (view.trend !== DEFAULT_VIEW.trend) add("trend", view.trend);
  if (view.grain !== DEFAULT_VIEW.grain) add("grain", view.grain);
  return params;
}

function publish(mode: "push" | "replace") {
  const next = canonicalParams($filters.get(), $view.get(), new URLSearchParams(location.search));
  if (next.toString() === new URLSearchParams(location.search).toString()) return;
  const qs = next.toString();
  const url = `${location.pathname}${qs ? `?${qs}` : ""}${location.hash}`;
  if (mode === "push") history.pushState(null, "", url);
  else history.replaceState(null, "", url);
}

let started = false;
let applying = false;

function applySearch(search: string) {
  const parsed = readSearch(search);
  applying = true;
  $filters.set(parsed.recorte);
  $view.set(parsed.view);
  $ignored.set(parsed.ignored);
  applying = false;
}

/** Chamado uma vez por qualquer ilha; idempotente. */
export function initFilters() {
  if (started || typeof window === "undefined") return;
  started = true;
  applySearch(location.search);
  $ready.set(true);
  publish("replace");
  const onChange = () => {
    if (!applying) publish("push");
  };
  $filters.listen(onChange);
  $view.listen(onChange);
  window.addEventListener("popstate", () => {
    applySearch(location.search);
    publish("replace");
  });
}

export function patchFilters(patch: Partial<Recorte>) {
  $filters.set({ ...$filters.get(), ...patch });
}

export function setView(patch: Partial<PanelView>) {
  const prev = $view.get();
  const next = { ...prev, ...patch };
  if (next.rank === prev.rank && next.trend === prev.trend && next.grain === prev.grain) return;
  $view.set(next);
}

/** O gráfico de lojas manda o foco para o filtro de cada loja no ranking. */
export function requestStoreRankingFocus() {
  setView({ rank: "store" });
  $focusRank.set($focusRank.get() + 1);
}

export function resetFilters() {
  $filters.set(EMPTY);
}

/** Aplica o drill-down de uma comanda (alerta ou agente) por cima do recorte atual. */
export function applyDrilldown(filters: Record<string, (string | number)[]>) {
  const patch: Partial<Recorte> = {};
  if (filters.hub) patch.hub = takeIds(filters.hub.map(String), "Hub", []);
  if (filters.store) patch.store = takeIds(filters.store.map(String), "Loja", []);
  if (filters.city) patch.city = takeCities(filters.city.map(String), []);
  if (filters.segment) patch.segment = takeEnums(filters.segment.map(String), SEGMENTS, "Segmento", "", []);
  if (filters.channel_type) patch.channel_type = takeEnums(filters.channel_type.map(String), CHANNELS, "Canal", "", []);
  if (filters.modal) patch.modal = takeEnums(filters.modal.map(String), MODALS, "Modal", "", []);
  if (filters.status) patch.status = takeEnums(filters.status.map(String), STATUSES, "Status", "", []);
  patchFilters(patch);
}

export function shareUrl(): string {
  return typeof window === "undefined" ? "" : location.href;
}
