import { SlidersHorizontal } from "lucide-react";
import type { RefObject } from "react";
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
 * Mobile (abaixo de lg): uma faixa de 44px com o resumo do recorte, que abre a
 * folha de filtros, e à direita o atalho para a fila de comandas. Cada bloco é
 * rótulo em cima e valor embaixo, para o resumo caber numa linha sem cortar a
 * palavra. A consulta é a mesma de AlertsPanel (mesma chave), então o cache é compartilhado.
 */
export function MobileRecorte({ summary, activeCount, onOpen, buttonRef }: Props) {
  const { data } = useRecorteQuery("/api/alerts");
  const alerts = data?.alerts ?? [];
  const total = data ? alerts.length : null;
  const critical = alerts.filter((a) => a.severity === "high").length;
  const filtersText = activeCount === 1 ? "1 filtro ativo" : `${activeCount} filtros ativos`;

  return (
    <div className="flex min-w-0 items-stretch gap-2">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="dialog"
        aria-label={`Recorte: ${summary}${activeCount ? `, ${filtersText}` : ""}. Editar`}
        onClick={onOpen}
        className={`flex min-h-11 min-w-0 flex-1 items-center gap-2 rounded-card border bg-surface px-3 py-1.5 text-left ${
          activeCount ? "border-ink" : "border-rule"
        }`}
      >
        <SlidersHorizontal className="size-4 shrink-0" aria-hidden />
        <span className="flex min-w-0 flex-1 flex-col leading-tight" aria-hidden>
          <span className="cond text-[0.7rem] leading-none font-bold text-muted">
            Recorte{activeCount > 0 ? ` · ${activeCount}` : ""}
          </span>
          <span className="mt-0.5 truncate text-[0.92rem] font-medium">{summary}</span>
        </span>
        {/* o verbo da linha: ink, negrito e sublinhado, para ler como ação e não como rótulo */}
        <span aria-hidden className="shrink-0 text-[0.85rem] font-semibold text-ink underline decoration-muted underline-offset-4">
          Editar
        </span>
      </button>

      {/* "Comandas · N" na primeira linha; "X críticas" embaixo, só quando há críticas */}
      <a
        href="#comandas"
        className="flex min-h-11 shrink-0 flex-col justify-center rounded-card border border-rule bg-surface px-3 py-1 leading-tight whitespace-nowrap"
      >
        <span className="text-[0.92rem]">
          Comandas
          {total !== null && (
            <>
              {" · "}
              <SubtleNumber value={total} />
            </>
          )}
        </span>
        {critical > 0 && (
          <span className="text-[0.78rem] font-medium text-crit">
            <SubtleNumber value={critical} /> {critical === 1 ? "crítica" : "críticas"}
          </span>
        )}
      </a>
    </div>
  );
}
