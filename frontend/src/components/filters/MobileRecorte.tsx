import { useStore } from "@nanostores/react";
import { SlidersHorizontal } from "lucide-react";
import type { RefObject } from "react";
import { $railAgentComandas, openComandaCount } from "@/lib/agentBridge";
import { useRecorteQuery } from "@/lib/query";
import { SubtleNumber } from "./SubtleNumber";

interface Props {
  /** Resumo curto do recorte, ex.: "Color Shopping +2" ou "Todos os pedidos". */
  summary: string;
  activeCount: number;
  onOpen: () => void;
  buttonRef: RefObject<HTMLButtonElement | null>;
}

/**
 * Mobile (abaixo de lg): o resumo do recorte ocupa a largura toda e abre a folha.
 * O atalho da fila de comandas fica na linha de baixo, para o período não ser
 * cortado pelo link. A consulta é a mesma de AlertsPanel (mesma chave), então o cache é compartilhado.
 */
export function MobileRecorte({ summary, activeCount, onOpen, buttonRef }: Props) {
  const { data } = useRecorteQuery("/api/alerts");
  const railAgents = useStore($railAgentComandas);
  const alerts = data?.alerts ?? [];
  const total = data ? openComandaCount(alerts.length, railAgents.length) : null;
  const critical = alerts.filter((a) => a.severity === "high").length;
  const filtersText = activeCount === 1 ? "1 filtro ativo" : `${activeCount} filtros ativos`;

  return (
    <div className="flex min-w-0 items-center gap-1.5">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="dialog"
        aria-label={`Recorte: ${summary}${activeCount ? `, ${filtersText}` : ""}. Editar`}
        onClick={onOpen}
        className={`flex min-h-11 min-w-0 flex-1 items-center gap-2 rounded-card border bg-surface px-2.5 py-1 text-left ${
          activeCount ? "border-ink" : "border-rule"
        }`}
      >
        <SlidersHorizontal className="size-4 shrink-0" aria-hidden />
        <span className="flex min-w-0 flex-1 flex-col leading-tight" aria-hidden>
          <span className="text-meta leading-none font-semibold text-muted tabular-nums">
            Recorte{activeCount > 0 ? ` · ${activeCount}` : ""}
          </span>
          <span className="mt-0.5 truncate text-aux font-medium text-ink">{summary}</span>
        </span>
        {/* o verbo da linha: ink, negrito e sublinhado, para ler como ação e não como rótulo */}
        <span aria-hidden className="shrink-0 text-aux font-semibold text-ink underline decoration-muted underline-offset-4">
          Editar
        </span>
      </button>

      {/* atalho compacto em 1 linha, alinhado com o botão Recorte (44px) */}
      <a
        href="#comandas"
        className="inline-flex min-h-11 shrink-0 items-center gap-1 rounded-card border border-rule bg-surface px-2.5 py-1 text-aux whitespace-nowrap"
      >
        <span>
          Comandas
          {total !== null && (
            <>
              {" · "}
              <SubtleNumber value={total} />
            </>
          )}
        </span>
        {critical > 0 && (
          <>
            <span className="font-semibold text-crit tabular-nums" aria-hidden>
              ({critical})
            </span>
            <span className="sr-only">
              , {critical} {critical === 1 ? "crítica" : "críticas"}
            </span>
          </>
        )}
      </a>
    </div>
  );
}
