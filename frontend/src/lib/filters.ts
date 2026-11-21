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
import { label } from "./format";

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
export const LIST_CAP = 50;
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

export interface DrillUndo {
  /** Recorte anterior ao drill-down, restaurado integralmente ao desfazer. */
  previous: Recorte;
  /** Descrição curta em pt-BR do filtro aplicado pelo drill-down (ex.: "Hub 8", "Loja Muspuo Smiru"). */
  description: string;
}

/** Recorte atual. Fica vazio até `initFilters()` ler a URL no navegador. */
export const $filters = atom<Recorte>(EMPTY);
/** Último drill-down aplicado: permite desfazer em um clique até que o recorte mude por outro caminho. */
export const $drillUndo = atom<DrillUndo | null>(null);
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

/** `?hub=8&hub=8` vira um hub só: repetição na URL não gera chip duplicado. Mantém a ordem. */
function unique<T>(values: T[]): T[] {
  return [...new Set(values)];
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
  return capList(unique(out), label, ignored);
}

function takeIds(values: string[], label: string, ignored: IgnoredValue[]): number[] {
  const out: number[] = [];
  for (const value of values) {
    const n = Number(value);
    if (Number.isInteger(n) && n > 0) out.push(n);
    else note(ignored, label, value, "precisa ser um número inteiro maior que zero");
  }
  return capList(unique(out), label, ignored);
}

function takeCities(values: string[], ignored: IgnoredValue[]): string[] {
  const out: string[] = [];
  for (const value of values) {
    if (!value) continue;
    if (value.length > TEXT_CAP) note(ignored, "Cidade", `${value.slice(0, 24)}…`, "passa de 80 caracteres");
    else out.push(value);
  }
  return capList(unique(out), "Cidade", ignored);
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
      // A API aceita o token `good`. O rodapé e o produto chamam esse segmento de goods,
      // então `goods` na URL vale como `good` e o aviso não promete um valor que seria recusado.
      segment: takeEnums(
        p.getAll("segment").map((s) => (s === "goods" ? "good" : s)),
        SEGMENTS,
        "Segmento",
        "o valor aceito é food ou goods",
        ignored,
      ),
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

/** Valor que passou no contrato, mas não está nas opções de /api/meta. */
const NOT_IN_BASE = "não existe nesta base";

function ignoredBit(item: IgnoredValue): string {
  if (item.reason === NOT_IN_BASE) return `${item.label} ${item.value} (${item.reason})`;
  return `${item.label} "${item.value}" (${item.reason})`;
}

/** Uma frase, ou a lista, para o aviso que aparece uma vez. */
export function ignoredMessage(items: IgnoredValue[]): string {
  if (items.length === 0) return "";
  if (items.length === 1) {
    const item = items[0];
    if (item.reason === NOT_IN_BASE) return `${item.label} ${item.value} não existe nesta base e ficou de fora do recorte.`;
    return `${item.label} "${item.value}" ficou de fora do recorte: ${item.reason}.`;
  }
  return `Alguns valores da URL ficaram de fora do recorte: ${items.map(ignoredBit).join("; ")}.`;
}

/** Opção de /api/meta. O valor é o id ou o token, não o rótulo. */
export interface CatalogOption {
  value: string | number;
  label?: string;
  parent?: string | number | null;
}

/** Listas completas do dataset, as mesmas que alimentam os seletores antes do cascade. */
export interface DimensionLists {
  cities: readonly CatalogOption[];
  hubs: readonly CatalogOption[];
  stores: readonly CatalogOption[];
  segments: readonly CatalogOption[];
  channel_types: readonly CatalogOption[];
  modals: readonly CatalogOption[];
}

interface DimensionCatalog {
  city: ReadonlySet<string>;
  hub: ReadonlySet<number>;
  store: ReadonlySet<number>;
  segment: ReadonlySet<string>;
  channel_type: ReadonlySet<string>;
  modal: ReadonlySet<string>;
  hubCity: ReadonlyMap<number, string>;
  storeHub: ReadonlyMap<number, number>;
  labels: {
    city: ReadonlyMap<string, string>;
    hub: ReadonlyMap<string, string>;
    store: ReadonlyMap<string, string>;
    segment: ReadonlyMap<string, string>;
    channel_type: ReadonlyMap<string, string>;
    modal: ReadonlyMap<string, string>;
  };
}

function textValues(options: readonly CatalogOption[]): Set<string> {
  return new Set(options.map((option) => String(option.value)));
}

function idValues(options: readonly CatalogOption[]): Set<number> {
  const ids = new Set<number>();
  for (const option of options) {
    const n = Number(option.value);
    if (Number.isInteger(n) && n > 0) ids.add(n);
  }
  return ids;
}

function parentTextMap(options: readonly CatalogOption[]): Map<number, string> {
  const map = new Map<number, string>();
  for (const option of options) {
    const id = Number(option.value);
    if (Number.isInteger(id) && id > 0 && option.parent != null && option.parent !== "") {
      map.set(id, String(option.parent));
    }
  }
  return map;
}

function parentIdMap(options: readonly CatalogOption[]): Map<number, number> {
  const map = new Map<number, number>();
  for (const option of options) {
    const id = Number(option.value);
    const parentId = Number(option.parent);
    if (Number.isInteger(id) && id > 0 && Number.isInteger(parentId) && parentId > 0) {
      map.set(id, parentId);
    }
  }
  return map;
}

function labelMap(options: readonly CatalogOption[]): Map<string, string> {
  const map = new Map<string, string>();
  for (const option of options) {
    if (option.label !== undefined) {
      map.set(String(option.value), label(option.label));
    }
  }
  return map;
}

export function catalogFromMeta(lists: DimensionLists): DimensionCatalog {
  return {
    city: textValues(lists.cities),
    hub: idValues(lists.hubs),
    store: idValues(lists.stores),
    segment: textValues(lists.segments),
    channel_type: textValues(lists.channel_types),
    modal: textValues(lists.modals),
    hubCity: parentTextMap(lists.hubs),
    storeHub: parentIdMap(lists.stores),
    labels: {
      city: labelMap(lists.cities),
      hub: labelMap(lists.hubs),
      store: labelMap(lists.stores),
      segment: labelMap(lists.segments),
      channel_type: labelMap(lists.channel_types),
      modal: labelMap(lists.modals),
    },
  };
}

function dropListed<T extends string | number>(
  values: readonly T[],
  known: (value: T) => boolean,
  label: string,
  ignored: IgnoredValue[],
  show: (value: T) => string,
): T[] {
  const kept: T[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    if (known(value)) {
      kept.push(value);
      continue;
    }
    const shown = show(value);
    if (seen.has(shown)) continue;
    seen.add(shown);
    note(ignored, label, shown, NOT_IN_BASE);
  }
  return kept;
}

/**
 * Tira cidade, hub, loja, segmento, canal e modal que não existem na base.
 * Hub e loja usam a lista inteira: um hub que existe fora da cidade escolhida
 * continua no recorte, como hoje. Status não entra: /api/meta não lista status.
 */
export function withoutUnknownIds(recorte: Recorte, catalog: DimensionCatalog): { recorte: Recorte; ignored: IgnoredValue[] } {
  const ignored: IgnoredValue[] = [];
  return {
    recorte: {
      ...recorte,
      city: dropListed(recorte.city, (value) => catalog.city.has(value), "Cidade", ignored, (value) => value),
      hub: dropListed(recorte.hub, (value) => catalog.hub.has(value), "Hub", ignored, (value) => String(value)),
      store: dropListed(recorte.store, (value) => catalog.store.has(value), "Loja", ignored, (value) => String(value)),
      segment: dropListed(recorte.segment, (value) => catalog.segment.has(value), "Segmento", ignored, (value) => value),
      channel_type: dropListed(recorte.channel_type, (value) => catalog.channel_type.has(value), "Canal", ignored, (value) => value),
      modal: dropListed(recorte.modal, (value) => catalog.modal.has(value), "Modal", ignored, (value) => value),
    },
    ignored,
  };
}

function sameNote(a: IgnoredValue, b: IgnoredValue) {
  return a.label === b.label && a.value === b.value && a.reason === b.reason;
}

function mergeIgnored(prev: readonly IgnoredValue[], extra: readonly IgnoredValue[]): IgnoredValue[] {
  const merged = [...prev];
  for (const item of extra) {
    if (!merged.some((have) => sameNote(have, item))) merged.push(item);
  }
  return merged;
}

/** Null até /api/meta responder. Enquanto isso o id da URL fica; não se descarta no escuro. */
let catalog: DimensionCatalog | null = null;

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
let preserveUndo = false;
/**
 * Verdadeiro quando a métrica da Tendência veio explícita no link aberto (`?trend=`)
 * e o operador ainda não a trocou. A abertura automática da primeira comanda não a sobrescreve.
 */
let trendFromUrl = false;

$filters.listen(() => {
  if (!preserveUndo && $drillUndo.get() !== null) {
    $drillUndo.set(null);
  }
});

function applySearch(search: string) {
  const parsed = readSearch(search);
  let recorte = parsed.recorte;
  let ignored = parsed.ignored;
  if (catalog) {
    const dropped = withoutUnknownIds(recorte, catalog);
    recorte = dropped.recorte;
    ignored = mergeIgnored(ignored, dropped.ignored);
  }
  applying = true;
  $filters.set(recorte);
  $view.set(parsed.view);
  $ignored.set(ignored);
  applying = false;
}

/** A Tendência ainda mostra a métrica que o link compartilhado pediu. */
export function isTrendFromUrl(): boolean {
  return trendFromUrl;
}

/** Segunda passagem, quando as opções do dataset chegam. Reescreve a URL sem empurrar histórico. */
export function applyDimensionCatalog(next: DimensionCatalog) {
  catalog = next;
  const dropped = withoutUnknownIds($filters.get(), next);
  if (dropped.ignored.length === 0) return;
  applying = true;
  $filters.set(dropped.recorte);
  $ignored.set(mergeIgnored($ignored.get(), dropped.ignored));
  applying = false;
  if (typeof window !== "undefined") publish("replace");
}

/** Chamado uma vez por qualquer ilha; idempotente. */
export function initFilters() {
  if (started || typeof window === "undefined") return;
  started = true;
  applySearch(location.search);
  trendFromUrl = new URLSearchParams(location.search).get("trend") === $view.get().trend;
  $ready.set(true);
  publish("replace");
  // Só a edição do operador passa por aqui com `applying` falso. A leitura da URL
  // e o catálogo (`applyDimensionCatalog`) reescrevem o recorte com a flag ligada
  // e podem acrescentar ao aviso; essa reescrita não apaga o que acabou de avisar.
  const onFiltersChange = () => {
    if (applying) return;
    if ($ignored.get().length > 0) $ignored.set([]);
    publish("push");
  };
  $filters.listen(onFiltersChange);
  window.addEventListener("popstate", () => {
    // voltar no histórico já é navegação do operador: a vista dali em diante segue as comandas
    trendFromUrl = false;
    applySearch(location.search);
    publish("replace");
  });
  window.addEventListener("keydown", (e) => {
    if (!(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey || e.key.toLowerCase() !== "z") return;
    if (!$drillUndo.get()) return;
    const target = e.target as HTMLElement | null;
    if (
      target &&
      (target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable)
    ) {
      return;
    }
    if (document.querySelector("dialog[open]")) return;
    e.preventDefault();
    undoDrilldown();
  });
}

export function patchFilters(patch: Partial<Recorte>) {
  $filters.set({ ...$filters.get(), ...patch });
}

/**
 * Troca a vista. Clique do operador empurra histórico (Voltar desfaz); mudança
 * programática, como a comanda aberta escolhendo a métrica, passa `history: "replace"`.
 * Publica aqui, e não num listener do `$view`: a comanda chama isto de dentro do listener
 * do `$evidence`, e ali o nanostores só roda os listeners do `$view` depois do retorno.
 */
export function setView(patch: Partial<PanelView>, opts: { history?: "push" | "replace" } = {}) {
  const prev = $view.get();
  const next = { ...prev, ...patch };
  if (next.rank === prev.rank && next.trend === prev.trend && next.grain === prev.grain) return;
  const mode = opts.history ?? "push";
  if (mode === "push" && next.trend !== prev.trend) trendFromUrl = false;
  $view.set(next);
  if (started) publish(mode);
}

/** O gráfico de lojas manda o foco para o filtro de cada loja no ranking. */
export function requestStoreRankingFocus() {
  setView({ rank: "store" });
  $focusRank.set($focusRank.get() + 1);
}

export function resetFilters() {
  $drillUndo.set(null);
  $filters.set(EMPTY);
}

function sameList<T>(a: readonly T[], b: readonly T[]): boolean {
  return a.length === b.length && a.every((v, i) => v === b[i]);
}

function sameRecorte(a: Recorte, b: Recorte): boolean {
  return (
    a.start === b.start &&
    a.end === b.end &&
    sameList(a.city, b.city) &&
    sameList(a.hub, b.hub) &&
    sameList(a.store, b.store) &&
    sameList(a.segment, b.segment) &&
    sameList(a.channel_type, b.channel_type) &&
    sameList(a.modal, b.modal) &&
    sameList(a.status, b.status)
  );
}

/**
 * Remove pais ou filhos incompatíveis quando o drill-down fixa loja, hub ou cidade,
 * usando os mesmos vínculos `parent` de /api/meta (sem nomes fixos no código).
 */
function reconcileParents(next: Recorte, patch: Partial<Recorte>, cat: DimensionCatalog): Recorte {
  let { city, hub, store } = next;

  if (patch.store && patch.store.length > 0) {
    const storeHubs = new Set<number>();
    const storeCities = new Set<string>();
    for (const id of store) {
      const parentHub = cat.storeHub.get(id);
      if (parentHub !== undefined) {
        storeHubs.add(parentHub);
        const parentCity = cat.hubCity.get(parentHub);
        if (parentCity !== undefined) storeCities.add(parentCity);
      }
    }
    if (!patch.hub && hub.length > 0 && storeHubs.size > 0) {
      hub = hub.filter((id) => storeHubs.has(id));
    }
    if (!patch.city && city.length > 0 && storeCities.size > 0) {
      city = city.filter((name) => storeCities.has(name));
    }
  } else if (patch.hub && patch.hub.length > 0) {
    const hubCities = new Set<string>();
    for (const id of hub) {
      const parentCity = cat.hubCity.get(id);
      if (parentCity !== undefined) hubCities.add(parentCity);
    }
    if (!patch.city && city.length > 0 && hubCities.size > 0) {
      city = city.filter((name) => hubCities.has(name));
    }
    if (!patch.store && store.length > 0) {
      const hubSet = new Set(hub);
      store = store.filter((id) => {
        const parentHub = cat.storeHub.get(id);
        return parentHub === undefined || hubSet.has(parentHub);
      });
    }
  } else if (patch.city && patch.city.length > 0) {
    const citySet = new Set(city);
    if (!patch.hub && hub.length > 0) {
      hub = hub.filter((id) => {
        const parentCity = cat.hubCity.get(id);
        return parentCity === undefined || citySet.has(parentCity);
      });
    }
    if (!patch.store && store.length > 0) {
      store = store.filter((id) => {
        const parentHub = cat.storeHub.get(id);
        const parentCity = parentHub !== undefined ? cat.hubCity.get(parentHub) : undefined;
        return parentCity === undefined || citySet.has(parentCity);
      });
    }
  }

  return { ...next, city, hub, store };
}

function drillDescription(patch: Partial<Recorte>, cat: DimensionCatalog | null): string {
  const parts: string[] = [];
  if (patch.store?.length) {
    if (patch.store.length === 1) {
      const id = patch.store[0];
      const name = cat?.labels.store.get(String(id));
      parts.push(name ? `Loja ${name}` : `Loja ${id}`);
    } else {
      parts.push(`${patch.store.length} lojas`);
    }
  } else if (patch.hub?.length) {
    if (patch.hub.length === 1) {
      const id = patch.hub[0];
      const name = cat?.labels.hub.get(String(id));
      parts.push(name ? `Hub ${name}` : `Hub ${id}`);
    } else {
      parts.push(`${patch.hub.length} hubs`);
    }
  } else if (patch.city?.length) {
    if (patch.city.length === 1) {
      const name = cat?.labels.city.get(patch.city[0]) ?? patch.city[0];
      parts.push(`Cidade ${name}`);
    } else {
      parts.push(`${patch.city.length} cidades`);
    }
  }
  if (patch.segment?.length) {
    parts.push(
      patch.segment.length === 1
        ? `Segmento ${cat?.labels.segment.get(patch.segment[0]) ?? label(patch.segment[0])}`
        : `${patch.segment.length} segmentos`,
    );
  }
  if (patch.channel_type?.length) {
    parts.push(
      patch.channel_type.length === 1
        ? `Canal ${cat?.labels.channel_type.get(patch.channel_type[0]) ?? label(patch.channel_type[0])}`
        : `${patch.channel_type.length} canais`,
    );
  }
  if (patch.modal?.length) {
    parts.push(
      patch.modal.length === 1
        ? `Modal ${cat?.labels.modal.get(patch.modal[0]) ?? label(patch.modal[0])}`
        : `${patch.modal.length} modais`,
    );
  }
  if (patch.status?.length) {
    parts.push(
      patch.status.length === 1 ? `Status ${label(patch.status[0])}` : `${patch.status.length} status`,
    );
  }
  return parts.join(" · ") || "Recorte";
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

  const prev = $filters.get();
  let next: Recorte = { ...prev, ...patch };
  if (catalog) {
    next = reconcileParents(next, patch, catalog);
  }
  if (sameRecorte(prev, next)) return;

  const description = drillDescription(patch, catalog);
  preserveUndo = true;
  try {
    $drillUndo.set({ previous: prev, description });
    $filters.set(next);
  } finally {
    preserveUndo = false;
  }
}

/** Restaura exatamente o recorte anterior ao último drill-down. */
export function undoDrilldown() {
  const undo = $drillUndo.get();
  if (!undo) return;
  $drillUndo.set(null);
  $filters.set(undo.previous);
}

export function shareUrl(): string {
  return typeof window === "undefined" ? "" : location.href;
}
