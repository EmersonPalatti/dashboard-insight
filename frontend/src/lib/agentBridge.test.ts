import { describe, expect, it } from "vitest";
import { sanitizeMessages, type AgentTicket } from "./agentBridge";

const TICKET: AgentTicket = {
  id: "A01",
  series: 1,
  title: "SLA abaixo da meta",
  detail: "No prazo em 71,2% do recorte.",
  action: "Coordenador do hub revisa a expedição hoje.",
  drilldowns: [{ label: "Ver hub", filters: { hub: [8] } }],
  n: 1200,
  measured: 1100,
  lowSample: false,
  source: "local",
  status: "rules",
  toolLabels: ["KPIs"],
  scope: "{}",
  onRail: true,
};

const user = (id: number, content = "Por que o SLA caiu?") => ({ id, role: "user", content, scope: "{}" });

describe("sanitizeMessages", () => {
  it("devolve lista vazia para o que não é array", () => {
    expect(sanitizeMessages(null)).toEqual([]);
    expect(sanitizeMessages({ messages: [] })).toEqual([]);
    expect(sanitizeMessages("[]")).toEqual([]);
  });

  it("descarta mensagens com forma inválida e mantém as válidas na ordem", () => {
    const out = sanitizeMessages([
      user(1),
      { id: 0, role: "user", content: "id zero", scope: "{}" },
      { id: 2.5, role: "user", content: "id fracionado", scope: "{}" },
      { id: 3, role: "system", content: "papel desconhecido", scope: "{}" },
      { id: 4, role: "assistant", content: 42, scope: "{}" },
      { id: 5, role: "assistant", content: "sem escopo" },
      { id: 6, role: "assistant", content: "erro não booleano", scope: "{}", error: "sim" },
      "texto solto",
      { id: 7, role: "assistant", content: "Resposta.", scope: "{}", error: true },
    ]);
    expect(out.map((m) => m.id)).toEqual([1, 7]);
    expect(out[1]).toEqual({ id: 7, role: "assistant", content: "Resposta.", scope: "{}", error: true });
  });

  it("remove id repetido ficando com a primeira ocorrência", () => {
    const out = sanitizeMessages([user(1, "primeira"), user(1, "repetida"), user(2)]);
    expect(out.map((m) => m.content)).toEqual(["primeira", "Por que o SLA caiu?"]);
  });

  it("guarda só as 40 últimas", () => {
    const out = sanitizeMessages(Array.from({ length: 45 }, (_, i) => user(i + 1)));
    expect(out).toHaveLength(40);
    expect(out[0].id).toBe(6);
    expect(out.at(-1)?.id).toBe(45);
  });

  it("valida a comanda: inválida derruba a mensagem, válida volta sem campos estranhos", () => {
    const broken = { ...TICKET, series: -1 };
    const out = sanitizeMessages([
      { id: 1, role: "assistant", content: "ok", scope: "{}", comanda: { ...TICKET, extra: "<script>" } },
      { id: 2, role: "assistant", content: "quebrada", scope: "{}", comanda: broken },
    ]);
    expect(out).toHaveLength(1);
    expect(out[0].comanda).toEqual(TICKET);
    expect(out[0].comanda).not.toHaveProperty("extra");
  });

  it("limpa drill-downs e rótulos inválidos e ignora fallback desconhecido", () => {
    const [msg] = sanitizeMessages([
      {
        id: 1,
        role: "assistant",
        content: "ok",
        scope: "{}",
        comanda: {
          ...TICKET,
          fallback: "inventado",
          drilldowns: [
            { label: "Ver hub", filters: { hub: [8, Number.NaN, "13", null] } },
            { label: "", filters: { hub: [1] } },
            { label: "Sem filtros" },
          ],
          toolLabels: ["KPIs", 3, null],
        },
      },
    ]);
    expect(msg.comanda?.drilldowns).toEqual([{ label: "Ver hub", filters: { hub: [8, "13"] } }]);
    expect(msg.comanda?.toolLabels).toEqual(["KPIs"]);
    expect(msg.comanda).not.toHaveProperty("fallback");
  });
});
