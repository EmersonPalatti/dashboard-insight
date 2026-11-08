/**
 * Pedidos brutos do recorte: paginação e ordenação no servidor (DuckDB),
 * rolagem infinita com TanStack Query e só as linhas visíveis no DOM via
 * TanStack Virtual. Centenas de milhares de linhas sem travar o navegador.
 */
import { useStore } from "@nanostores/react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { flexRender, getCoreRowModel, useReactTable, createColumnHelper } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowDown, ArrowUp } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { apiGet, type OrderRow } from "@/lib/api/client";
import { $filters, $ready, toQuery } from "@/lib/filters";
import { fmt, label } from "@/lib/format";
import { island } from "@/lib/query";
import { ErrorState, Panel, Skeleton } from "./ui/Panel";

const PAGE = 200;
const ROW_H = 34;
const col = createColumnHelper<OrderRow>();
const SORTABLE = new Set(["created_at", "amount", "delivery_fee", "cycle_min", "production_min", "transit_min", "distance_m", "store_name", "hub_name", "city", "status"]);

const columns = [
  col.accessor("created_at", { header: "Criado em", cell: (c) => fmt.dateTime(c.getValue()), size: 110 }),
  col.accessor("status", {
    header: "Status",
    size: 90,
    cell: (c) =>
      c.getValue() === "canceled" ? (
        <span className="inline-flex items-center gap-1.5 font-semibold text-ink">
          <span className="size-2 rounded-full border-[1.5px] border-ink" aria-hidden />
          {label(c.getValue())}
        </span>
      ) : (
        label(c.getValue())
      ),
  }),
  col.accessor("hub_name", { header: "Hub", size: 140 }),
  col.accessor("store_name", { header: "Loja", size: 160 }),
  col.accessor("segment", { header: "Seg.", size: 60, cell: (c) => label(c.getValue()) }),
  col.accessor("channel", { header: "Canal", size: 110 }),
  col.accessor("modal", { header: "Modal", size: 60, cell: (c) => label(c.getValue()) }),
  col.accessor("amount", { header: "Valor", size: 90, cell: (c) => fmt.brl(c.getValue()) }),
  col.accessor("cycle_min", {
    header: "Ciclo",
    size: 80,
    cell: (c) =>
      c.row.original.on_time === false ? (
        <span className="inline-flex items-center gap-1 font-semibold text-ink">
          <ArrowUp className="size-3" aria-hidden />
          {fmt.min(c.getValue())}
          <span className="sr-only"> fora do SLA</span>
        </span>
      ) : (
        fmt.min(c.getValue())
      ),
  }),
  col.accessor("production_min", { header: "Preparo", size: 80, cell: (c) => fmt.min(c.getValue()) }),
  col.accessor("transit_min", { header: "Trânsito", size: 80, cell: (c) => fmt.min(c.getValue()) }),
  col.accessor("distance_m", { header: "Distância", size: 80, cell: (c) => (c.getValue() === null ? "—" : fmt.km(c.getValue()! / 1000)) }),
];

function OrdersTableInner() {
  const filters = useStore($filters);
  const ready = useStore($ready);
  const [sort, setSort] = useState<{ id: string; desc: boolean }>({ id: "created_at", desc: true });
  const scroller = useRef<HTMLDivElement>(null);

  const query = useInfiniteQuery({
    queryKey: ["/api/orders", filters, sort],
    enabled: ready,
    initialPageParam: 0,
    queryFn: ({ pageParam, signal }) =>
      apiGet("/api/orders", { ...toQuery(filters), offset: pageParam, limit: PAGE, sort: sort.id, desc: sort.desc }, signal),
    getNextPageParam: (last) => (last.offset + last.limit < last.total ? last.offset + last.limit : undefined),
  });

  const rows = useMemo(() => query.data?.pages.flatMap((p) => p.rows) ?? [], [query.data]);
  const total = query.data?.pages[0]?.total ?? 0;

  const table = useReactTable({ data: rows, columns, getCoreRowModel: getCoreRowModel(), manualSorting: true });
  const virtual = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => ROW_H,
    overscan: 12,
  });
  const items = virtual.getVirtualItems();

  // chegou perto do fim do que já foi carregado: busca a próxima página
  const lastIndex = items.at(-1)?.index ?? 0;
  useEffect(() => {
    if (lastIndex >= rows.length - 30 && query.hasNextPage && !query.isFetchingNextPage) query.fetchNextPage();
  }, [lastIndex, rows.length, query.hasNextPage, query.isFetchingNextPage, query.fetchNextPage]);

  // recorte ou ordenação novos: volta ao topo
  useEffect(() => {
    scroller.current?.scrollTo({ top: 0 });
  }, [filters, sort]);

  const width = table.getTotalSize();

  return (
    <Panel
      title="Pedidos do recorte"
      hint={
        query.data
          ? `${fmt.int(total)} pedidos · ${fmt.int(rows.length)} carregados. Role para buscar mais; clique no cabeçalho para ordenar no servidor. Ciclo com seta para cima = fora do SLA.`
          : "Paginação e ordenação no servidor."
      }
      busy={query.isFetching && !query.isFetchingNextPage && Boolean(query.data)}
    >
      {query.isPending ? (
        <Skeleton height={420} />
      ) : query.error ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : (
        <div ref={scroller} className="content-reveal relative h-[460px] min-w-0 overflow-auto rounded-tick border border-rule" role="region" aria-label="Tabela de pedidos" tabIndex={0}>
          <div style={{ width, minWidth: "100%" }} className="text-[0.85rem] tabular-nums" role="table" aria-rowcount={total}>
            <div className="sticky top-0 z-10 flex border-b border-rule bg-sunken" role="row">
              {table.getFlatHeaders().map((h) => {
                const active = sort.id === h.id;
                const sortable = SORTABLE.has(h.id);
                return (
                  <div key={h.id} role="columnheader" style={{ width: h.getSize() }} className="cond shrink-0 px-2 py-2 font-bold">
                    {sortable ? (
                      <button
                        type="button"
                        onClick={() => setSort((s) => ({ id: h.id, desc: s.id === h.id ? !s.desc : true }))}
                        className={`inline-flex items-center gap-1 ${active ? "text-ink" : "text-muted hover:text-ink"}`}
                      >
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {active && (sort.desc ? <ArrowDown className="icon-swap size-3" aria-hidden /> : <ArrowUp className="icon-swap size-3" aria-hidden />)}
                      </button>
                    ) : (
                      <span className="text-muted">{flexRender(h.column.columnDef.header, h.getContext())}</span>
                    )}
                  </div>
                );
              })}
            </div>
            <div style={{ height: virtual.getTotalSize(), position: "relative" }} role="rowgroup">
              {items.map((item) => {
                const row = table.getRowModel().rows[item.index];
                if (!row) return null;
                return (
                  <div
                    key={row.id}
                    role="row"
                    aria-rowindex={item.index + 2}
                    className="absolute left-0 flex w-full border-b border-rule/50 transition-colors duration-(--duration-quick) hover:bg-sunken/60"
                    style={{ height: ROW_H, transform: `translateY(${item.start}px)` }}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <div key={cell.id} role="cell" style={{ width: cell.column.getSize() }} className="flex shrink-0 items-center truncate px-2">
                        <span className="truncate">{flexRender(cell.column.columnDef.cell, cell.getContext())}</span>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
            {query.isFetchingNextPage && <p className="label px-2 py-2">Carregando mais pedidos…</p>}
          </div>
        </div>
      )}
    </Panel>
  );
}

export default island(OrdersTableInner, 540);
