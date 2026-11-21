import { afterEach, describe, expect, it, vi } from "vitest";
import { toSearchParams } from "./api/client";
import {
  $activeCount,
  $drillUndo,
  $filters,
  $ignored,
  $view,
  applyDrilldown,
  catalogFromMeta,
  DEFAULT_VIEW,
  EMPTY,
  ignoredMessage,
  LIST_CAP,
  patchFilters,
  readSearch,
  resetFilters,
  toBody,
  toQuery,
  undoDrilldown,
  withoutUnknownIds,
  type DimensionLists,
  type IgnoredValue,
  type Recorte,
} from "./filters";

const SAMPLE_META: DimensionLists = {
  cities: [
    { value: "Cidade A", label: "Cidade A" },
    { value: "Cidade B", label: "Cidade B" },
  ],
  hubs: [
    { value: 101, label: "Hub Alfa", parent: "Cidade A" },
    { value: 102, label: "Hub Beta", parent: "Cidade B" },
  ],
  stores: [
    { value: 201, label: "Loja Alfa", parent: 101 },
    { value: 202, label: "Loja Beta", parent: 102 },
  ],
  segments: [
    { value: "food", label: "Food" },
    { value: "good", label: "Goods" },
  ],
  channel_types: [
    { value: "marketplace", label: "Marketplace" },
    { value: "own", label: "Canal próprio" },
  ],
  modals: [
    { value: "moto", label: "Moto" },
    { value: "bike", label: "Bike" },
  ],
};

function installBrowserStub(initialSearch: string) {
  const loc = {
    pathname: "/",
    search: initialSearch,
    hash: "",
    href: `http://localhost/${initialSearch}`,
  };
  const pushCalls: string[] = [];
  const replaceCalls: string[] = [];
  const updateUrl = (url: string) => {
    const parsed = new URL(url, "http://localhost");
    loc.pathname = parsed.pathname;
    loc.search = parsed.search;
    loc.hash = parsed.hash;
    loc.href = parsed.href;
  };
  const hist = {
    pushState: (_data: unknown, _unused: string, url: string) => {
      pushCalls.push(url);
      updateUrl(url);
    },
    replaceState: (_data: unknown, _unused: string, url: string) => {
      replaceCalls.push(url);
      updateUrl(url);
    },
  };
  // guarda os listeners para o teste disparar popstate (Voltar do navegador) à mão
  const listeners = new Map<string, ((event: unknown) => void)[]>();
  const win = {
    addEventListener: (type: string, fn: (event: unknown) => void) => {
      listeners.set(type, [...(listeners.get(type) ?? []), fn]);
    },
  };
  vi.stubGlobal("window", win);
  vi.stubGlobal("location", loc);
  vi.stubGlobal("history", hist);
  /** Simula o Voltar: o navegador já trocou a URL quando o popstate chega. */
  const back = (url: string) => {
    updateUrl(url);
    for (const fn of listeners.get("popstate") ?? []) fn({ type: "popstate" });
  };
  return { loc, pushCalls, replaceCalls, back, listeners };
}

afterEach(() => {
  $filters.set(EMPTY);
  $view.set(DEFAULT_VIEW);
  $ignored.set([]);
  $drillUndo.set(null);
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("readSearch", () => {
  it("devolve recorte vazio e vista padrão para query vazia", () => {
    expect(readSearch("")).toEqual({ recorte: EMPTY, view: DEFAULT_VIEW, ignored: [] });
    expect(readSearch("?")).toEqual({ recorte: EMPTY, view: DEFAULT_VIEW, ignored: [] });
  });

  it("lê query completa válida sem gerar notas ignoradas", () => {
    const parsed = readSearch(
      "?start=2021-01-01&end=2021-03-31&city=Cidade+A&hub=101&store=201&segment=food&channel_type=own&modal=moto&status=delivered&rank=store&trend=sla&grain=hour",
    );
    expect(parsed).toEqual({
      recorte: {
        start: "2021-01-01",
        end: "2021-03-31",
        city: ["Cidade A"],
        hub: [101],
        store: [201],
        segment: ["food"],
        channel_type: ["own"],
        modal: ["moto"],
        status: ["delivered"],
      },
      view: { rank: "store", trend: "sla", grain: "hour" },
      ignored: [],
    });
  });

  it("aceita segment=goods como alias de good e deduplica repetidos", () => {
    const aliasOnly = readSearch("?segment=goods");
    expect(aliasOnly.recorte.segment).toEqual(["good"]);
    expect(aliasOnly.ignored).toEqual([]);

    const mixed = readSearch("?segment=good&segment=goods&segment=food&segment=good");
    expect(mixed.recorte.segment).toEqual(["good", "food"]);
    expect(mixed.ignored).toEqual([]);
  });

  it("deduplica parâmetros repetidos na URL preservando a ordem", () => {
    const parsed = readSearch(
      "?hub=13&hub=8&hub=13&hub=8&store=202&store=201&store=202&city=Cidade+B&city=Cidade+A&city=Cidade+B&channel_type=own&channel_type=own&modal=bike&modal=moto&modal=bike&status=canceled&status=canceled",
    );
    expect(parsed.recorte.hub).toEqual([13, 8]);
    expect(parsed.recorte.store).toEqual([202, 201]);
    expect(parsed.recorte.city).toEqual(["Cidade B", "Cidade A"]);
    expect(parsed.recorte.channel_type).toEqual(["own"]);
    expect(parsed.recorte.modal).toEqual(["bike", "moto"]);
    expect(parsed.recorte.status).toEqual(["canceled"]);
    expect(parsed.ignored).toEqual([]);
  });

  it("valida datas, ano bissexto e intervalo invertido", () => {
    expect(readSearch("?start=2024-02-29&end=2024-02-29")).toEqual({
      recorte: { ...EMPTY, start: "2024-02-29", end: "2024-02-29" },
      view: DEFAULT_VIEW,
      ignored: [],
    });

    for (const bad of ["2021-02-29", "2021-04-31", "15/03/2021", "1999-12-31", "2101-01-01"]) {
      const res = readSearch(`?start=${encodeURIComponent(bad)}`);
      expect(res.recorte.start).toBeNull();
      expect(res.ignored).toHaveLength(1);
      expect(res.ignored[0]?.label).toBe("Início");
    }

    const inverted = readSearch("?start=2021-03-10&end=2021-03-01");
    expect(inverted.recorte.start).toBe("2021-03-10");
    expect(inverted.recorte.end).toBeNull();
    expect(inverted.ignored).toEqual([
      { label: "Fim", value: "2021-03-01", reason: "é anterior ao início" },
    ]);
  });

  it("ignora valores inválidos mantendo irmãos válidos e ignora params desconhecidos", () => {
    const longCity = "A".repeat(81);
    const parsed = readSearch(
      `?utm_source=test&foo=bar&city=&city=Cidade+A&city=${longCity}&hub=0&hub=-3&hub=1.5&hub=abc&hub=8&segment=other&channel_type=direct&modal=drone&status=pending&rank=bad&trend=bad&grain=month`,
    );
    expect(parsed.recorte).toEqual({
      ...EMPTY,
      city: ["Cidade A"],
      hub: [8],
    });
    expect(parsed.view).toEqual(DEFAULT_VIEW);
    expect(parsed.ignored).toHaveLength(12);
    expect(parsed.ignored[0]).toEqual({
      label: "Cidade",
      value: `${"A".repeat(24)}…`,
      reason: "passa de 80 caracteres",
    });
  });

  it("aplica o teto LIST_CAP após deduplicação", () => {
    const repeated = new URLSearchParams(Array.from({ length: 60 }, () => ["hub", "8"]));
    const resRepeated = readSearch(`?${repeated.toString()}`);
    expect(resRepeated.recorte.hub).toEqual([8]);
    expect(resRepeated.ignored).toEqual([]);

    const distinct = new URLSearchParams(Array.from({ length: 52 }, (_, i) => ["hub", String(i + 1)]));
    const resDistinct = readSearch(`?${distinct.toString()}`);
    expect(resDistinct.recorte.hub).toHaveLength(LIST_CAP);
    expect(resDistinct.recorte.hub[0]).toBe(1);
    expect(resDistinct.recorte.hub[LIST_CAP - 1]).toBe(LIST_CAP);
    expect(resDistinct.ignored).toEqual([
      { label: "Hub", value: "52", reason: `o recorte aceita no máximo ${LIST_CAP} valores` },
    ]);
  });
});

describe("serialização e round-trip", () => {
  it("converte Recorte para toQuery, toBody e fecha o round-trip via URLSearchParams", () => {
    const recorte: Recorte = {
      start: "2021-02-01",
      end: "2021-02-28",
      city: ["Cidade São José", "Cidade B"],
      hub: [101, 102],
      store: [201],
      segment: ["food", "good"],
      channel_type: ["marketplace"],
      modal: ["moto", "bike"],
      status: ["delivered"],
    };

    const qs = toSearchParams(toQuery(recorte)).toString();
    const roundTripped = readSearch(`?${qs}`);
    expect(roundTripped.recorte).toEqual(recorte);
    expect(roundTripped.ignored).toEqual([]);

    expect(toBody(EMPTY)).toEqual({
      city: [],
      hub: [],
      store: [],
      segment: [],
      channel_type: [],
      modal: [],
      status: [],
    });
    expect(toBody(recorte)).toEqual(recorte);
  });
});

describe("ignoredMessage e catálogo /api/meta", () => {
  it("formata mensagens de valores ignorados no singular e no plural", () => {
    expect(ignoredMessage([])).toBe("");

    const oneContract: IgnoredValue[] = [
      { label: "Hub", value: "abc", reason: "precisa ser um número inteiro maior que zero" },
    ];
    expect(ignoredMessage(oneContract)).toBe(
      'Hub "abc" ficou de fora do recorte: precisa ser um número inteiro maior que zero.',
    );

    const oneMissing: IgnoredValue[] = [
      { label: "Hub", value: "999", reason: "não existe nesta base" },
    ];
    expect(ignoredMessage(oneMissing)).toBe(
      "Hub 999 não existe nesta base e ficou de fora do recorte.",
    );

    const multi: IgnoredValue[] = [...oneMissing, ...oneContract];
    expect(ignoredMessage(multi)).toBe(
      'Alguns valores da URL ficaram de fora do recorte: Hub 999 (não existe nesta base); Hub "abc" (precisa ser um número inteiro maior que zero).',
    );
  });

  it("remove ids/tokens desconhecidos preservando status e hub de outra cidade", () => {
    const catalog = catalogFromMeta(SAMPLE_META);
    const input: Recorte = {
      start: "2021-01-01",
      end: "2021-01-31",
      city: ["Cidade A", "Inexistente", "Inexistente"],
      hub: [102, 999],
      store: [201, 888],
      segment: ["food"],
      channel_type: ["own"],
      modal: ["moto"],
      status: ["delivered"],
    };

    const { recorte, ignored } = withoutUnknownIds(input, catalog);
    expect(recorte).toEqual({
      ...input,
      city: ["Cidade A"],
      hub: [102],
      store: [201],
      status: ["delivered"],
    });
    expect(ignored).toEqual([
      { label: "Cidade", value: "Inexistente", reason: "não existe nesta base" },
      { label: "Hub", value: "999", reason: "não existe nesta base" },
      { label: "Loja", value: "888", reason: "não existe nesta base" },
    ]);
  });
});

describe("estado reativo e drill-down", () => {
  it("conta grupos ativos e gerencia drill-down com desfazer", () => {
    expect($activeCount.get()).toBe(0);

    patchFilters({ start: "2021-01-01", end: "2021-01-10", hub: [101, 102], modal: ["moto"] });
    expect($activeCount.get()).toBe(3);

    applyDrilldown({ hub: [101], store: [201] });
    expect($filters.get().hub).toEqual([101]);
    expect($filters.get().store).toEqual([201]);
    expect($drillUndo.get()?.description).toBe("Loja 201");

    // No-op quando o drill-down não altera o recorte atual
    const undoBefore = $drillUndo.get();
    applyDrilldown({ hub: [101], store: [201] });
    expect($drillUndo.get()).toBe(undoBefore);

    undoDrilldown();
    expect($drillUndo.get()).toBeNull();
    expect($filters.get().hub).toEqual([101, 102]);
    expect($filters.get().store).toEqual([]);

    // Mudança manual após drill-down descarta o histórico de desfazer
    applyDrilldown({ city: ["Cidade A"] });
    expect($drillUndo.get()).not.toBeNull();
    patchFilters({ modal: ["bike"] });
    expect($drillUndo.get()).toBeNull();

    resetFilters();
    expect($filters.get()).toEqual(EMPTY);
    expect($activeCount.get()).toBe(0);
  });

  it("sincroniza URL canônica, histórico de vista e reconciliação de pais no initFilters", async () => {
    const browser = installBrowserStub("?utm=1&hub=8&hub=8&rank=hub&trend=cancel");
    const mod = await import("./filters");

    mod.initFilters();
    expect(browser.replaceCalls).toEqual(["/?utm=1&hub=8&trend=cancel"]);
    expect(browser.pushCalls).toEqual([]);
    expect(mod.isTrendFromUrl()).toBe(true);
    expect(mod.shareUrl()).toBe("http://localhost/?utm=1&hub=8&trend=cancel");

    const fromPublished = mod.readSearch(browser.loc.search);
    expect(fromPublished.recorte.hub).toEqual([8]);
    expect(fromPublished.view).toEqual({ rank: "hub", trend: "cancel", grain: "day" });

    // Troca programática com replace preserva isTrendFromUrl e não empurra histórico
    mod.setView({ trend: "sla" }, { history: "replace" });
    expect(browser.replaceCalls).toEqual([
      "/?utm=1&hub=8&trend=cancel",
      "/?utm=1&hub=8&trend=sla",
    ]);
    expect(browser.pushCalls).toEqual([]);
    expect(mod.isTrendFromUrl()).toBe(true);

    // Troca do operador volta para default (omite trend) via pushState e limpa trendFromUrl
    mod.setView({ trend: "volume" });
    expect(browser.pushCalls).toEqual(["/?utm=1&hub=8"]);
    expect(mod.isTrendFromUrl()).toBe(false);
  });

  it("setView com replace chamado de dentro de outro listener não vira push", async () => {
    // A comanda escolhe a métrica dentro do listener do $evidence. Ali o nanostores enfileira
    // os listeners do $view e só roda depois do retorno do setView.
    const browser = installBrowserStub("?hub=8");
    const mod = await import("./filters");
    const { atom } = await import("nanostores");

    mod.initFilters();
    const $trigger = atom(0);
    const off = $trigger.listen(() => mod.setView({ trend: "sla" }, { history: "replace" }));
    $trigger.set(1);
    off();

    expect(browser.pushCalls).toEqual([]);
    expect(browser.replaceCalls.at(-1)).toBe("/?hub=8&trend=sla");
    expect(mod.$view.get().trend).toBe("sla");
  });

  it("popstate restaura recorte e vista da URL, sem empurrar histórico, e solta o trend do link", async () => {
    const browser = installBrowserStub("?hub=101&trend=cancel");
    const mod = await import("./filters");

    mod.initFilters();
    expect(browser.listeners.get("popstate")).toHaveLength(1);
    expect(mod.isTrendFromUrl()).toBe(true);

    mod.patchFilters({ hub: [102] });
    expect(browser.pushCalls).toEqual(["/?hub=102&trend=cancel"]);

    // entrada de histórico com hub repetido: volta canônica, por replace
    browser.back("/?hub=101&hub=101&trend=cancel");
    expect(mod.$filters.get()).toEqual({ ...mod.EMPTY, hub: [101] });
    expect(mod.$view.get()).toEqual({ ...mod.DEFAULT_VIEW, trend: "cancel" });
    // Voltar já é navegação do operador: a Tendência deixa de seguir o link
    expect(mod.isTrendFromUrl()).toBe(false);
    // aplicar a URL não vira um novo push (senão o Voltar entra em laço)
    expect(browser.pushCalls).toEqual(["/?hub=102&trend=cancel"]);
    expect(browser.replaceCalls.at(-1)).toBe("/?hub=101&trend=cancel");
  });

  it("popstate depois do catálogo descarta ids que não existem e avisa", async () => {
    const browser = installBrowserStub("");
    const mod = await import("./filters");

    mod.initFilters();
    mod.applyDimensionCatalog(mod.catalogFromMeta(SAMPLE_META));
    browser.back("/?hub=101&hub=999");
    expect(mod.$filters.get().hub).toEqual([101]);
    expect(mod.$ignored.get()).toEqual([{ label: "Hub", value: "999", reason: "não existe nesta base" }]);
    expect(browser.replaceCalls.at(-1)).toBe("/?hub=101");
  });

  it("applyDimensionCatalog poda ids desconhecidos da URL com replace e mantém o aviso", async () => {
    const browser = installBrowserStub("?city=Cidade+A&hub=101&hub=999&store=888&segment=food");
    const mod = await import("./filters");

    mod.initFilters();
    // antes do catálogo a URL já é canônica: nada a reescrever
    expect(browser.replaceCalls).toEqual([]);

    mod.applyDimensionCatalog(mod.catalogFromMeta(SAMPLE_META));
    expect(mod.$filters.get()).toEqual({ ...mod.EMPTY, city: ["Cidade A"], hub: [101], segment: ["food"] });
    expect(browser.replaceCalls.at(-1)).toBe("/?city=Cidade+A&hub=101&segment=food");
    expect(browser.pushCalls).toEqual([]);
    expect(mod.$ignored.get()).toEqual([
      { label: "Hub", value: "999", reason: "não existe nesta base" },
      { label: "Loja", value: "888", reason: "não existe nesta base" },
    ]);

    // catálogo sem nada a podar: não reescreve a URL de novo
    const before = browser.replaceCalls.length;
    mod.applyDimensionCatalog(mod.catalogFromMeta(SAMPLE_META));
    expect(browser.replaceCalls).toHaveLength(before);
  });

  it("reconcilia cidade/hub incompatíveis no applyDrilldown após carregar catálogo", async () => {
    const browser = installBrowserStub("?city=Cidade+A&city=Cidade+B&hub=101&hub=102&store=201");
    const mod = await import("./filters");

    mod.initFilters();
    mod.applyDimensionCatalog(mod.catalogFromMeta(SAMPLE_META));
    expect(mod.$ignored.get()).toEqual([]);

    mod.applyDrilldown({ store: [201] });
    expect(mod.$filters.get()).toEqual({
      ...mod.EMPTY,
      city: ["Cidade A"],
      hub: [101],
      store: [201],
    });
    expect(mod.$drillUndo.get()?.description).toBe("Loja Loja Alfa");
    expect(browser.pushCalls.at(-1)).toBe("/?city=Cidade+A&hub=101&store=201");

    mod.undoDrilldown();
    expect(mod.$filters.get()).toEqual({
      ...mod.EMPTY,
      city: ["Cidade A", "Cidade B"],
      hub: [101, 102],
      store: [201],
    });
    expect(mod.$drillUndo.get()).toBeNull();
  });
});
