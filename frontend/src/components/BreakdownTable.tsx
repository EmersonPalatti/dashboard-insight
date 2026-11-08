import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, Filter } from "lucide-react";
import { useEffect, useId, useMemo, useState } from "react";
import type { BreakdownRow, Dimension } from "@/lib/api/client";
import { applyDrilldown, patchFilters } from "@/lib/filters";
import { fmt, label, WEEKDAYS } from "@/lib/format";
import { island, useRecorteQuery } from "@/lib/query";
import { Empty, ErrorState, Panel, Skeleton } from "./ui/Panel";

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

const col = createColumnHelper<BreakdownRow>();

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
  const [tab, setTab] = useState<Tab>("hub");
  const selectId = useId();
  const [sorting, setSorting] = useState<SortingState>([{ id: "orders", desc: true }]);
  const { data, error, isPending, refetch, isPlaceholderData } = useRecorteQuery("/api/breakdown", {
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
              <span className="ml-1.5 text-[0.8rem] text-muted">{label(c.row.original.parent)}</span>
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

  const canDrill = tab === "hub" || tab === "store" || tab === "city" || tab === "modal";
  const drill = (r: BreakdownRow) => {
    if (tab === "hub") applyDrilldown({ hub: [Number(r.key)] });
    else if (tab === "store") applyDrilldown({ store: [Number(r.key)] });
    else if (tab === "city") applyDrilldown({ city: [String(r.key)] });
    else if (tab === "modal") patchFilters({ modal: [r.key as "moto" | "bike"] });
  };

  return (
    <Panel
      title="Ranking do recorte"
      hint={`Ordene pelas colunas. Seta para baixo: no prazo abaixo do recorte. Seta para cima: cancelamento acima do recorte.${tab === "store" ? " Lojas com 30+ pedidos." : ""}`}
      busy={isPlaceholderData}
      actions={
        <div className="flex items-center gap-2">
          <label htmlFor={selectId} className="text-[0.85rem] text-muted">
            Quebrar por
          </label>
          <select
            id={selectId}
            value={tab}
            onChange={(e) => setTab(e.target.value as Tab)}
            className="min-h-10 rounded-card border border-rule bg-surface px-2.5 py-1.5 text-[0.92rem] text-ink"
          >
            {TABS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      }
    >
      {isPending ? (
        <Skeleton height={360} />
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : rows.length === 0 ? (
        <Empty />
      ) : (
        <div className="content-reveal relative max-h-[420px] min-w-0 overflow-auto rounded-tick border border-rule">
          <table className="w-full border-collapse text-[0.88rem] tabular-nums">
            <thead className="sticky top-0 z-10 bg-sunken">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((h, i) => {
                    const dir = h.column.getIsSorted();
                    const Icon = dir === "asc" ? ArrowUp : dir === "desc" ? ArrowDown : ArrowUpDown;
                    return (
                      <th
                        key={h.id}
                        scope="col"
                        aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : "none"}
                        className={`cond border-b border-rule px-2.5 py-2 font-bold whitespace-nowrap ${i === 0 ? "text-left" : "text-right"}`}
                      >
                        <button
                          type="button"
                          onClick={h.column.getToggleSortingHandler()}
                          className={`inline-flex items-center gap-1 ${dir ? "text-ink" : "text-muted hover:text-ink"}`}
                        >
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          <Icon className="size-3" aria-hidden />
                        </button>
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
                      <button
                        type="button"
                        onClick={() => drill(row.original)}
                        className="rounded-[4px] p-1 text-muted hover:bg-sunken-strong hover:text-ink"
                        aria-label={`Filtrar por ${row.original.label}`}
                        title="Filtrar o painel por este grupo"
                      >
                        <Filter className="size-3.5" aria-hidden />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

export default island(BreakdownTableInner);
