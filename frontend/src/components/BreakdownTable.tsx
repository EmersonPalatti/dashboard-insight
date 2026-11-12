import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { useStore } from "@nanostores/react";
import { ArrowDown, ArrowUp, ArrowUpDown, Filter } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { BreakdownRow, Dimension } from "@/lib/api/client";
import { $focusRank, $view, applyDrilldown, patchFilters, setView } from "@/lib/filters";
import { fmt, label, WEEKDAYS } from "@/lib/format";
import { GLOSS, STORE_NAMES_HINT } from "@/lib/glossary";
import { island, useRecorteQuery } from "@/lib/query";
import { AskAgentButton } from "./ui/AskAgentButton";
import { AsyncBody, Empty, PanelContent, panelFallback } from "./ui/Panel";
import { Select } from "./ui/Select";
import { Term } from "./ui/Term";

type Tab = Extract<Dimension, "hub" | "store" | "city" | "channel" | "modal" | "payment_method" | "weekday">;
const TABS: { value: Tab; label: string }[] = [
  { value: "hub", label: "Hubs" },
  { value: "store", label: "Lojas" },
  { value: "city", label: "Cidades" },
  { value: "channel", label: "Canais" },
  { value: "modal", label: "Modal" },
  { value: "payment_method", label: "Pagamento" },
  { value: "weekday", label: "Dia da semana" },
];

// Singular para a pergunta ao agente ("canais" não casa a regra de canal; "canal" casa).
const ASK_SUBJECT: Record<Tab, string> = {
  hub: "hub",
  store: "loja",
  city: "cidade",
  channel: "canal",
  modal: "modal",
  payment_method: "forma de pagamento",
  weekday: "dia da semana",
};

const col = createColumnHelper<BreakdownRow>();

const HEADER_HELP: Partial<Record<string, { term: string; definition: string }>> = {
  gmv: { term: "GMV", definition: GLOSS.gmv },
  subsidy: { term: "Subsídio", definition: GLOSS.subsidy },
};

/**
 * Taxa desviada do recorte: o servidor marca a linha; aqui só se mostra com
 * forma (seta) e peso de texto, sem cor, e um rótulo para leitor de tela.
 */
function FlaggedRate({
  value,
  flagged,
  direction,
}: {
  value: number | null;
  flagged?: boolean;
  direction: "above" | "below";
}) {
  if (!flagged) return <span>{fmt.pct(value)}</span>;
  const Icon = direction === "below" ? ArrowDown : ArrowUp;
  return (
    <span className="inline-flex items-center justify-end gap-1 font-semibold text-ink">
      <Icon className="size-3" aria-hidden />
      {fmt.pct(value)}
      <span className="sr-only">{direction === "below" ? " abaixo do recorte" : " acima do recorte"}</span>
    </span>
  );
}

function BreakdownTableInner() {
  const tab = useStore($view).rank;
  const focusTick = useStore($focusRank);
  const focused = useRef(0);
  const [sorting, setSorting] = useState<SortingState>([{ id: "orders", desc: true }]);
  const { data, error, isPending, refetch, isPlaceholderData, waking, down } = useRecorteQuery("/api/breakdown", {
    by: tab,
    sort: "orders",
    limit: tab === "store" ? 300 : 100,
    min_orders: tab === "store" ? 30 : 0,
  });
  const rows = data?.rows ?? [];
  // Aba cujas linhas estão na tela. Troca só quando o recorte novo chega (keepPreviousData mantém as antigas),
  // então o cross-fade da tabela acontece junto com as linhas novas, não antes delas.
  const [shownTab, setShownTab] = useState<Tab>(tab);
  useEffect(() => {
    if (!isPlaceholderData && !isPending) setShownTab(tab);
  }, [tab, isPlaceholderData, isPending]);

  const columns = useMemo(
    () => [
      col.accessor("label", {
        header: TABS.find((t) => t.value === tab)?.label.replace(/s$/, "") ?? "Grupo",
        cell: (c) => (
          <span className="block max-w-56 truncate">
            {tab === "weekday" ? WEEKDAYS[Number(c.row.original.key)] : label(c.getValue())}
            {c.row.original.parent && tab !== "channel" && (
              <span className="ml-1.5 text-meta text-muted">{label(c.row.original.parent)}</span>
            )}
          </span>
        ),
      }),
      col.accessor("orders", { header: "Pedidos", cell: (c) => fmt.int(c.getValue()) }),
      col.accessor("gmv", { header: "GMV", cell: (c) => fmt.brlCompact(c.getValue()) }),
      col.accessor("ticket", { header: "Ticket", cell: (c) => fmt.brl(c.getValue()) }),
      col.accessor("sla_rate", {
        header: "No prazo",
        cell: (c) => <FlaggedRate value={c.getValue()} flagged={c.row.original.sla_below} direction="below" />,
        sortUndefined: "last",
      }),
      col.accessor("cycle_p50", { header: "Ciclo", cell: (c) => fmt.min(c.getValue()) }),
      col.accessor("cancel_rate", {
        header: "Cancel.",
        cell: (c) => <FlaggedRate value={c.getValue()} flagged={c.row.original.cancel_above} direction="above" />,
      }),
      col.accessor("production_p50", { header: "Preparo", cell: (c) => fmt.min(c.getValue()) }),
      col.accessor("transit_p50", { header: "Trânsito", cell: (c) => fmt.min(c.getValue()) }),
      col.accessor("subsidy", { header: "Subsídio", cell: (c) => fmt.brl(c.getValue()) }),
    ],
    [tab],
  );

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  useEffect(() => {
    if (!focusTick || focused.current === focusTick) return;
    if (tab !== "store" || isPlaceholderData || isPending) return;
    focused.current = focusTick;
    const root = document.getElementById("ranking-recorte");
    const button = root?.querySelector<HTMLButtonElement>('tbody button[aria-label^="Filtrar"]');
    (button ?? root)?.focus();
  }, [focusTick, tab, isPlaceholderData, isPending, rows.length]);

  const canDrill = tab === "hub" || tab === "store" || tab === "city" || tab === "modal";
  const drill = (r: BreakdownRow) => {
    if (r.key == null) return;
    if (tab === "hub") applyDrilldown({ hub: [Number(r.key)] });
    else if (tab === "store") applyDrilldown({ store: [Number(r.key)] });
    else if (tab === "city") applyDrilldown({ city: [String(r.key)] });
    else if (tab === "modal" && (r.key === "moto" || r.key === "bike")) patchFilters({ modal: [r.key] });
  };

  return (
    <PanelContent
      hint={`Ordene pelas colunas. Seta para baixo: no prazo abaixo do recorte. Seta para cima: cancelamento acima do recorte.${tab === "store" ? ` Lojas com 30+ pedidos. ${STORE_NAMES_HINT}` : ""}`}
      busy={isPlaceholderData}
      actions={
        <>
          <Select label="Quebrar por" value={tab} options={TABS} onChange={(value) => setView({ rank: value })} align="end" />
          <AskAgentButton
            subject={`o ranking por ${ASK_SUBJECT[tab]}`}
            question={`No ranking por ${ASK_SUBJECT[tab]}, quem está pior e o que fazer?`}
          />
        </>
      }
    >
      <AsyncBody
        waking={waking}
        pending={isPending}
        error={error}
        down={down}
        onRetry={() => refetch()}
        what="o ranking"
        height={420}
        empty={rows.length === 0 ? <Empty /> : null}
      >
        <div
          id="ranking-recorte"
          tabIndex={-1}
          className="content-reveal relative max-h-[420px] min-w-0 scroll-mt-32 overflow-auto rounded-tick border border-rule"
        >
          <table className="w-full border-collapse text-aux tabular-nums">
            <thead className="sticky top-0 z-10 bg-sunken">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((h, i) => {
                    const dir = h.column.getIsSorted();
                    const Icon = dir === "asc" ? ArrowUp : dir === "desc" ? ArrowDown : ArrowUpDown;
                    const help = HEADER_HELP[h.column.id];
                    const tone = dir ? "text-ink" : "text-muted hover:text-ink";
                    return (
                      <th
                        key={h.id}
                        scope="col"
                        aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : "none"}
                        className={`border-b border-rule px-2.5 py-2 text-aux font-semibold whitespace-nowrap ${i === 0 ? "text-left" : "text-right tabular-nums"}`}
                      >
                        {help ? (
                          <span className={`inline-flex items-center gap-1 ${dir ? "text-ink" : "text-muted"}`}>
                            <Term term={help.term} definition={help.definition} />
                            <button
                              type="button"
                              onClick={h.column.getToggleSortingHandler()}
                              className="inline-flex items-center hover:text-ink"
                              aria-label={`Ordenar por ${help.term}`}
                            >
                              <Icon className="size-3" aria-hidden />
                            </button>
                          </span>
                        ) : (
                          <button
                            type="button"
                            onClick={h.column.getToggleSortingHandler()}
                            className={`inline-flex items-center gap-1 ${tone}`}
                          >
                            {flexRender(h.column.columnDef.header, h.getContext())}
                            <Icon className="size-3" aria-hidden />
                          </button>
                        )}
                      </th>
                    );
                  })}
                  {canDrill && <th className="border-b border-rule px-2 py-2" aria-label="Filtrar" />}
                </tr>
              ))}
            </thead>
            <tbody key={shownTab} className="content-swap">
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="border-b border-rule/60 last:border-0 hover:bg-sunken/60">
                  {row.getVisibleCells().map((cell, i) => (
                    <td key={cell.id} className={`px-2.5 py-1.5 whitespace-nowrap ${i === 0 ? "text-left" : "text-right"}`}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                  {canDrill && (
                    <td className="px-2 py-1 text-right">
                      {row.original.key != null && (
                        <button
                          type="button"
                          onClick={() => drill(row.original)}
                          className="rounded-[4px] p-1 text-muted hover:bg-sunken-strong hover:text-ink"
                          aria-label={`Filtrar por ${row.original.label}`}
                          title="Filtrar o painel por este grupo"
                        >
                          <Filter className="size-3.5" aria-hidden />
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AsyncBody>
    </PanelContent>
  );
}

export default island(BreakdownTableInner, panelFallback(420, { hint: true }));
