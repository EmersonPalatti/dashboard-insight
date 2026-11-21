import { describe, expect, it } from "vitest";
import { fmt, label, LABELS, WEEKDAYS } from "./format";

/** Intl pt-BR usa espaço não-quebrável (\u00a0) após R$ e antes de mil/mi. */
const normSpace = (s: string) => s.replace(/[\u00a0\u202f]/g, " ");

describe("fmt números pt-BR", () => {
  it("formata inteiros, compactos e devolve traço para ausentes", () => {
    expect(fmt.int(0)).toBe("0");
    expect(fmt.int(1234)).toBe("1.234");
    expect(fmt.int(368990)).toBe("368.990");
    expect(fmt.int(12.6)).toBe("13");
    expect(fmt.int(null)).toBe("—");
    expect(fmt.int(undefined)).toBe("—");
    expect(fmt.int(Number.NaN)).toBe("—");

    expect(normSpace(fmt.intCompact(12500))).toBe("12,5 mil");
    expect(normSpace(fmt.intCompact(1500000))).toBe("1,5 mi");
    expect(fmt.intCompact(null)).toBe("—");
    expect(fmt.intCompact(undefined)).toBe("—");
    expect(fmt.intCompact(Number.NaN)).toBe("—");
  });

  it("formata moeda BRL completa e compacta", () => {
    expect(normSpace(fmt.brl(1234.56))).toBe("R$ 1.234,56");
    expect(normSpace(fmt.brl(0))).toBe("R$ 0,00");
    expect(normSpace(fmt.brl(-42.5))).toBe("-R$ 42,50");
    expect(fmt.brl(null)).toBe("—");
    expect(fmt.brl(undefined)).toBe("—");
    expect(fmt.brl(Number.NaN)).toBe("—");

    expect(normSpace(fmt.brlCompact(12500))).toBe("R$ 12,5 mil");
    expect(normSpace(fmt.brlCompact(1500000))).toBe("R$ 1,5 mi");
    expect(fmt.brlCompact(null)).toBe("—");
    expect(fmt.brlCompact(undefined)).toBe("—");
    expect(fmt.brlCompact(Number.NaN)).toBe("—");
  });

  it("formata percentuais, minutos, distância e decimal com 1 casa", () => {
    expect(fmt.pct(0.046)).toBe("4,6%");
    expect(fmt.pct(0.8623)).toBe("86,2%");
    expect(fmt.pct(0)).toBe("0,0%");
    expect(fmt.pct(1)).toBe("100,0%");
    expect(fmt.pct(null)).toBe("—");
    expect(fmt.pct(undefined)).toBe("—");
    expect(fmt.pct(Number.NaN)).toBe("—");

    expect(fmt.min(41.23)).toBe("41,2 min");
    expect(fmt.min(0)).toBe("0,0 min");
    expect(fmt.min(null)).toBe("—");
    expect(fmt.min(Number.NaN)).toBe("—");

    expect(fmt.km(3.45)).toBe("3,5 km");
    expect(fmt.km(0)).toBe("0,0 km");
    expect(fmt.km(null)).toBe("—");
    expect(fmt.km(Number.NaN)).toBe("—");

    expect(fmt.num1(1234.5)).toBe("1.234,5");
    expect(fmt.num1(4)).toBe("4,0");
    expect(fmt.num1(null)).toBe("—");
    expect(fmt.num1(Number.NaN)).toBe("—");
  });
});

describe("fmt datas e horários de Brasília", () => {
  it("formata datas YYYY-MM-DD sem deslocar fuso", () => {
    expect(fmt.date("2021-03-15")).toBe("15/03/2021");
    expect(fmt.date("2021-01-05T10:30:00")).toBe("05/01/2021");
    expect(fmt.date(null)).toBe("—");
    expect(fmt.date(undefined)).toBe("—");
    expect(fmt.date("")).toBe("—");
  });

  it("mantém horários naive em Brasília verbatim em qualquer timezone", () => {
    expect(fmt.dateTime("2021-01-05T10:00:00")).toBe("05/01, 10:00");
    expect(fmt.dateTime("2021-01-05 21:45:00")).toBe("05/01, 21:45");
    expect(fmt.dateTime("2021-01-01T00:00:00")).toBe("01/01, 00:00");
  });

  it("converte timestamps com offset explícito para America/Sao_Paulo", () => {
    expect(fmt.dateTime("2021-01-05T10:00:00-03:00")).toBe("05/01, 10:00");
    expect(fmt.dateTime("2021-01-05T10:00:00-0300")).toBe("05/01, 10:00");
    expect(fmt.dateTime("2021-01-05T13:00:00Z")).toBe("05/01, 10:00");
    expect(fmt.dateTime("2021-01-05T01:30:00Z")).toBe("04/01, 22:30");
    expect(fmt.dateTime("2021-01-05T22:00:00+09:00")).toBe("05/01, 10:00");
  });

  it("devolve traço para datas vazias ou inválidas sem lançar erro", () => {
    expect(fmt.dateTime("")).toBe("—");
    expect(fmt.dateTime("invalid")).toBe("—");
    expect(fmt.dateTime("2021-99-99T00:00:00")).toBe("—");
    expect(fmt.dateTime("not-a-dateZ")).toBe("—");
    expect(fmt.dateTime("2021-99-99T00:00:00-03:00")).toBe("—");
  });
});

describe("rótulos e dias da semana", () => {
  it("traduz tokens conhecidos e formata desconhecidos", () => {
    expect(LABELS.food).toBe("Food");
    expect(label("food")).toBe("Food");
    expect(label("good")).toBe("Goods");
    expect(label("own")).toBe("Canal próprio");
    expect(label("delivered")).toBe("Entregue");
    expect(label("meal_benefit")).toBe("Vale-refeição");
    expect(label("custom_mode_x")).toBe("custom mode x");
    expect(label(42)).toBe("42");
    expect(label(null)).toBe("—");
    expect(label(undefined)).toBe("—");
  });

  it("expõe os dias da semana de segunda a domingo em pt-BR", () => {
    expect(WEEKDAYS).toEqual(["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]);
  });
});
