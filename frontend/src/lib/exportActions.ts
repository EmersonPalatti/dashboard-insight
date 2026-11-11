/**
 * Ações de exportação do recorte, compartilhadas pelo modal (ExportDialog, mobile),
 * pelo menu "Compartilhar" da barra (ShareMenu, desktop) e pelo botão "Copiar link"
 * (CopyLinkButton, folha mobile). Rótulos, feedback e tempos vivem aqui, num lugar só.
 */
import { useStore } from "@nanostores/react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { apiGet, apiUrl, type AlertsResponse, type KpiResponse } from "@/lib/api/client";
import { $filters, shareUrl, toQuery, type Recorte } from "@/lib/filters";
import { fmt } from "@/lib/format";

/** O estado "copiado" (link e briefing) dura 1,8 s e volta sozinho ao normal. */
export const FEEDBACK_MS = 1800;

/** A impressão espera o modal ou o menu fechar (--duration-quick, 150 ms) com folga, para ele não sair no PDF. */
export const PRINT_DELAY_MS = 250;

/** Rótulos e descrições de cada ação, na voz da interface. */
export const EXPORT_ACTIONS = {
  link: {
    title: "Copiar link",
    copiedTitle: "Link copiado",
    detail: "Quem abrir vê o mesmo recorte.",
  },
  csv: {
    title: "Pedidos em CSV",
    detail: "Uma linha por pedido, com o recorte atual.",
  },
  briefing: {
    title: "Copiar briefing (Markdown)",
    busyTitle: "Copiando briefing…",
    doneTitle: "Briefing copiado",
    errorTitle: "Não deu para copiar",
    detail: "KPIs, alertas e ações, pronto para colar no Slack ou num doc.",
  },
  print: {
    title: "PDF da tela",
    detail: 'Abre a impressão do navegador; escolha "Salvar como PDF".',
  },
} as const;

export type BriefingState = "idle" | "busy" | "done" | "error";

/** Título do item de briefing conforme o estado da cópia. */
export function briefingTitle(state: BriefingState): string {
  const a = EXPORT_ACTIONS.briefing;
  switch (state) {
    case "busy":
      return a.busyTitle;
    case "done":
      return a.doneTitle;
    case "error":
      return a.errorTitle;
    default:
      return a.title;
  }
}

export function briefingMarkdown(kpis: KpiResponse, alerts: AlertsResponse["alerts"], url: string) {
  const m = kpis.current;
  const lines = [
    `# Briefing de operação — ${fmt.date(kpis.period.start)} a ${fmt.date(kpis.period.end)}`,
    "",
    `- Pedidos: ${fmt.int(m.orders)} · GMV ${fmt.brl(m.gmv)} · ticket ${fmt.brl(m.ticket)}`,
    `- SLA no prazo: ${fmt.pct(m.sla_rate)} · ciclo mediano ${fmt.min(m.cycle_p50)} (p90 ${fmt.min(m.cycle_p90)})`,
    `- Cancelamento: ${fmt.pct(m.cancel_rate)} · subsídio de frete ${fmt.brl(m.subsidy)}/entrega`,
    "",
    "## Alertas e ações",
    ...(alerts.length
      ? alerts.flatMap((a) => [`### ${a.title}`, a.detail, `**Ação:** ${a.action}`, ""])
      : ["Nenhum alerta neste recorte."]),
    "",
    `Recorte: ${url}`,
  ];
  return lines.join("\n");
}

/** Busca KPIs e alertas do recorte (pelo cache do QueryClient) e copia o briefing. Lança se falhar. */
export async function copyBriefing(qc: QueryClient, filters: Recorte): Promise<void> {
  const query = toQuery(filters);
  const [kpis, alerts] = await Promise.all([
    qc.query({ queryKey: ["/api/kpis", filters, {}], queryFn: () => apiGet("/api/kpis", query) }),
    qc.query({ queryKey: ["/api/alerts", filters, {}], queryFn: () => apiGet("/api/alerts", query) }),
  ]);
  await navigator.clipboard.writeText(briefingMarkdown(kpis, alerts.alerts, location.href));
}

/** Link do CSV de pedidos com o recorte atual. */
export function csvHref(filters: Recorte): string {
  return apiUrl("/api/orders.csv", toQuery(filters));
}

export type CsvState = "idle" | "busy" | "error";

/**
 * Baixa o CSV do recorte. Se a API recusar (recorte grande demais, cota),
 * devolve a mensagem em pt-BR em vez de salvar o JSON de erro como arquivo.
 */
export function useCsvDownload() {
  const filters = useStore($filters);
  const [state, setState] = useState<CsvState>("idle");
  const [message, setMessage] = useState<string | null>(null);

  const download = async (): Promise<boolean> => {
    setState("busy");
    setMessage(null);
    try {
      const res = await fetch(csvHref(filters));
      if (!res.ok) {
        let detail = "Não deu para exportar o CSV.";
        try {
          const body = await res.json();
          if (typeof body.detail === "string" && body.detail) detail = body.detail;
        } catch {
          /* corpo não-JSON */
        }
        setState("error");
        setMessage(detail);
        return false;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "pedidos-recorte.csv";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setState("idle");
      return true;
    } catch {
      setState("error");
      setMessage("Não deu para exportar o CSV.");
      return false;
    }
  };

  return {
    download,
    busy: state === "busy",
    error: state === "error",
    title:
      state === "busy" ? "Exportando CSV…" : state === "error" ? "Não deu para exportar" : EXPORT_ACTIONS.csv.title,
    detail: message ?? EXPORT_ACTIONS.csv.detail,
  };
}

/** Abre a impressão do navegador depois de o modal ou menu começar a fechar. */
export function printAfterClose() {
  window.setTimeout(() => window.print(), PRINT_DELAY_MS);
}

/** Copia o link do recorte. `copied` vale por FEEDBACK_MS após cada cópia bem-sucedida. */
export function useCopyLink() {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl());
      setCopied(true);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), FEEDBACK_MS);
    } catch {
      /* clipboard negado: o link continua na barra de endereço */
    }
  };

  return { copied, copy };
}

/**
 * Copia o briefing do recorte atual. O estado volta a "idle" FEEDBACK_MS depois de
 * terminar, com sucesso ou erro (o ExportDialog e o ShareMenu mostram o mesmo feedback).
 */
export function useBriefingCopy() {
  const [state, setState] = useState<BriefingState>("idle");
  const filters = useStore($filters);
  const qc = useQueryClient();
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const copy = async () => {
    window.clearTimeout(timer.current);
    setState("busy");
    try {
      await copyBriefing(qc, filters);
      setState("done");
    } catch {
      setState("error");
    }
    timer.current = window.setTimeout(() => setState("idle"), FEEDBACK_MS);
  };

  return { state, copy, title: briefingTitle(state) };
}
