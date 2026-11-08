import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, Filter } from "lucide-react";
import { useMemo, useState } from "react";
import type { BreakdownRow, Dimension } from "@/lib/api/client";
import { applyDrilldown, patchFilters } from "@/lib/filters";
import { fmt, label, WEEKDAYS } from "@/lib/format";
import { island, useRecorteQuery } from "@/lib/query";
import { Empty, ErrorState, Panel, Segmented, Skeleton } from "./ui/Panel";

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

function rateCell(v: number | null, warnAbove?: number, warnBelow?: number) {
  const bad = v !== null && ((warnAbove !== undefined && v > warnAbove) || (warnBelow !== undefined && v < warnBelow));
  return <span className={bad ? "font-semibold text-chili" : ""}>{fmt.pct(v)}</span>;
}

function BreakdownTableInner() {
  const [tab, setTab] = useState<Tab>("hub");
  const [sorting, setSorting] = useState<SortingState>([{ id: "orders", desc: true }]);
  const { data, error, isPending, refetch, isPlaceholderData } = useRecorteQuery("/api/breakdown", {
    by: tab,
    sort: "orders",
    limit: tab === "store" ? 300 : 100,
    min_orders: tab === "store" ? 30 : 0,
  });
  const rows = data?.rows ?? [];
  const kpis = useRecorteQuery("/api/kpis").data?.current;

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
        cell: (c) => rateCell(c.getValue(), undefined, kpis?.sla_rate ? kpis.sla_rate - 0.05 : undefined),
        sortUndefined: "last",
      }),
      col.accessor("cycle_p50", { header: "Ciclo", cell: (c) => fmt.min(c.getValue()) }),
      col.accessor("cancel_rate", {
        header: "Cancel.",
        cell: (c) => rateCell(c.getValue(), kpis?.cancel_rate ? Math.max(kpis.cancel_rate * 1.6, 0.06) : 0.06),
      }),
      col.accessor("production_p50", { header: "Preparo", cell: (c) => fmt.min(c.getValue()) }),
      col.accessor("transit_p50", { header: "Trânsito", cell: (c) => fmt.min(c.getValue()) }),
      col.accessor("subsidy", { header: "Subsídio", cell: (c) => fmt.brl(c.getValue()) }),
    ],
    [tab, kpis],
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
      hint={`Ordene pelas colunas. Em vermelho: abaixo/acima do recorte.${tab === "store" ? " Lojas com 30+ pedidos." : ""}`}
      busy={isPlaceholderData}
      actions={<Segmented label="Quebrar por" value={tab} onChange={setTab} options={TABS} />}
    >
      {isPending ? (
        <Skeleton height={360} />
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : rows.length === 0 ? (
        <Empty />
      ) : (
        <div className="max-h-[420px] overflow-auto rounded-clip border border-rule">
          <table className="w-full border-collapse text-[0.88rem] tabular-nums">
            <thead className="sticky top-0 z-10 bg-kraft">
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
                        className={`border-b border-rule px-2.5 py-2 font-semibold whitespace-nowrap ${i === 0 ? "text-left" : "text-right"}`}
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
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="border-b border-rule/60 last:border-0 hover:bg-kraft/60">
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
                        className="rounded-[4px] p-1 text-muted hover:bg-kraft-strong hover:text-chili"
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
