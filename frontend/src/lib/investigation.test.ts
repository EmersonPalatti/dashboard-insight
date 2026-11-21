import { afterEach, describe, expect, it } from "vitest";
import {
  $nextComandaRequest,
  $recorteEmpty,
  investigationViewFor,
  requestNextComanda,
  trendViewForKpi,
} from "./investigation";

afterEach(() => {
  $recorteEmpty.set(false);
  $nextComandaRequest.set(0);
});

describe("investigationViewFor", () => {
  it("cai em trend quando não há evidência ou quando a evidência é um KPI", () => {
    expect(investigationViewFor(null)).toBe("trend");
    expect(investigationViewFor(undefined)).toBe("trend");
    expect(investigationViewFor({ view: "kpi", kpi: "sla_rate" })).toBe("trend");
    expect(investigationViewFor({ view: "kpi", kpi: null })).toBe("trend");
  });

  it("retorna o painel correspondente para stages, heatmap e scatter", () => {
    expect(investigationViewFor({ view: "stages", hubs: [8] })).toBe("stages");
    expect(investigationViewFor({ view: "heatmap", hours: [19, 20], metric: "cancel_rate" })).toBe(
      "heatmap",
    );
    expect(investigationViewFor({ view: "scatter", stores: [10], metric: "sla_rate" })).toBe(
      "scatter",
    );
  });
});

describe("trendViewForKpi", () => {
  it("mapeia cada cartão de KPI para a métrica certa da tendência", () => {
    expect(trendViewForKpi("sla_rate")).toBe("sla");
    expect(trendViewForKpi("cycle_p50")).toBe("sla");
    expect(trendViewForKpi("cancel_rate")).toBe("cancel");
    expect(trendViewForKpi("orders")).toBe("volume");
    expect(trendViewForKpi("gmv")).toBe("volume");
    expect(trendViewForKpi("ticket")).toBe("volume");
    expect(trendViewForKpi(null)).toBeNull();
    expect(trendViewForKpi(undefined)).toBeNull();
  });
});

describe("atoms de estado da investigação", () => {
  it("controla $recorteEmpty e incrementa $nextComandaRequest", () => {
    expect($recorteEmpty.get()).toBe(false);
    $recorteEmpty.set(true);
    expect($recorteEmpty.get()).toBe(true);

    expect($nextComandaRequest.get()).toBe(0);
    requestNextComanda();
    expect($nextComandaRequest.get()).toBe(1);
    requestNextComanda();
    expect($nextComandaRequest.get()).toBe(2);
  });
});
