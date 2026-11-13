/**
 * Pedidos brutos do recorte: paginação e ordenação no servidor (DuckDB),
 * rolagem infinita com TanStack Query e só as linhas visíveis no DOM via
 * TanStack Virtual. Centenas de milhares de linhas sem travar o navegador.
 */
import { useStore } from "@nanostores/react";
import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";
import { flexRender, getCoreRowModel, useReactTable, createColumnHelper } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowDown, ArrowUp } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { apiGet, type OrderRow } from "@/lib/api/client";
import { $filters, $ready, toQuery } from "@/lib/filters";
import { fmt, label } from "@/lib/format";
import { STORE_NAMES_HINT } from "@/lib/glossary";
import { gated, island, useApiGate } from "@/lib/query";
import { AskAgentButton } from "./ui/AskAgentButton";
import { AsyncBody, PanelContent, panelFallback } from "./ui/Panel";

// Pergunta pela coluna de ordenação atual (ids de SORTABLE); "Resumo" é o fallback do agente.
const ASK_BY_SORT: Record<string, string> = {
  created_at: "Onde estão os picos de horário dos pedidos do recorte e o que fazer?",
  amount: "Explique a receita dos pedidos do recorte e o que fazer?",
  delivery_fee: "Explique o frete dos pedidos do recorte e o que fazer?",
  cycle_min: "Explique o ciclo dos pedidos do recorte e o que fazer?",
  production_min: "Explique o preparo dos pedidos do recorte e o que fazer?",
  transit_min: "Explique o trânsito dos pedidos do recorte e o que fazer?",
  distance_m: "Explique o custo de entrega por distância dos pedidos do recorte e o que fazer?",
  store_name: "Quais lojas aparecem mais nos pedidos do recorte e o que fazer?",
  hub_name: "Quais hubs aparecem mais nos pedidos do recorte e o que fazer?",
  city: "Quais cidades aparecem mais nos pedidos do recorte e o que fazer?",
  status: "Explique os cancelamentos entre os pedidos do recorte e o que fazer?",
};

const PAGE = 200;
const ROW_H = 34;
const col = createColumnHelper<OrderRow>();
const SORTABLE = new Set(["created_at", "amount", "delivery_fee", "cycle_min", "production_min", "transit_min", "distance_m", "store_name", "hub_name", "city", "status"]);
const NUMERIC_COLS = new Set(["amount", "cycle_min", "production_min", "transit_min", "distance_m"]);

const columns = [
  col.accessor("created_at", { header: "Criado em", cell: (c) => fmt.dateTime(c.getValue()), size: 110 }),
  col.accessor("status", {
    header: "Status",
    size: 110,
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
  col.accessor("hub_name", { header: "Hub", size: 160 }),
  col.accessor("store_name", { header: "Loja", size: 170 }),
  col.accessor("segment", { header: "Segmento", size: 118, cell: (c) => label(c.getValue()) }),
  col.accessor("channel", { header: "Canal", size: 125 }),
  col.accessor("modal", { header: "Modal", size: 90, cell: (c) => label(c.getValue()) }),
  col.accessor("amount", { header: "Valor", size: 95, cell: (c) => fmt.brl(c.getValue()) }),
  col.accessor("cycle_min", {
    header: "Ciclo",
    size: 92,
    cell: (c) =>
      c.row.original.on_time === false ? (
        <span className="inline-flex items-center gap-1 font-semibold text-ink" title="Fora do SLA">
          <ArrowUp className="size-3" aria-hidden />
          {fmt.min(c.getValue())}
          <span className="sr-only"> fora do SLA</span>
        </span>
      ) : (
        fmt.min(c.getValue())
      ),
  }),
  col.accessor("production_min", { header: "Preparo", size: 85, cell: (c) => fmt.min(c.getValue()) }),
  col.accessor("transit_min", { header: "Trânsito", size: 85, cell: (c) => fmt.min(c.getValue()) }),
  col.accessor("distance_m", { header: "Distância", size: 85, cell: (c) => (c.getValue() === null ? "—" : fmt.km(c.getValue()! / 1000)) }),
];

function OrdersTableInner() {
  const filters = useStore($filters);
  const ready = useStore($ready);
  const gate = useApiGate();
  const [sort, setSort] = useState<{ id: string; desc: boolean }>({ id: "created_at", desc: true });
  const scroller = useRef<HTMLDivElement>(null);

  const pages = useInfiniteQuery({
    queryKey: ["/api/orders", filters, sort],
    enabled: ready && gate.up,
    placeholderData: keepPreviousData,
    initialPageParam: 0,
    queryFn: ({ pageParam, signal }) =>
      apiGet("/api/orders", { ...toQuery(filters), offset: pageParam, limit: PAGE, sort: sort.id, desc: sort.desc }, signal),
    getNextPageParam: (last) => (last.offset + last.limit < last.total ? last.offset + last.limit : undefined),
  });
  const query = gated(gate, pages);

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
    if (lastIndex >= rows.length - 30 && query.hasNextPage && !query.isFetchingNextPage && !query.isFetchNextPageError) {
      query.fetchNextPage();
    }
  }, [lastIndex, rows.length, query.hasNextPage, query.isFetchingNextPage, query.isFetchNextPageError, query.fetchNextPage]);

  // recorte ou ordenação novos: volta ao topo
  useEffect(() => {
    scroller.current?.scrollTo({ top: 0 });
  }, [filters, sort]);

  const width = table.getTotalSize();

  return (
    <PanelContent
      hint={
        query.data
          ? `${fmt.int(total)} pedidos · ${fmt.int(rows.length)} carregados. Role para buscar mais; clique nos cabeçalhos para ordenar. ↑ fora do SLA. ${STORE_NAMES_HINT}`
          : `Paginação e ordenação no servidor. ↑ fora do SLA. ${STORE_NAMES_HINT}`
      }
      busy={query.isFetching && !query.isFetchingNextPage && Boolean(query.data)}
      actions={
        <AskAgentButton
          subject="os pedidos do recorte"
          question={ASK_BY_SORT[sort.id] ?? "Resumo dos pedidos do recorte e o que fazer?"}
        />
      }
    >
      <AsyncBody
        waking={query.waking}
        pending={query.isPending}
        error={query.error}
        down={query.down}
        onRetry={() => query.refetch()}
        what="os pedidos"
        height={460}
      >
        <div ref={scroller} className="content-reveal relative h-[460px] min-w-0 overflow-auto rounded-tick border border-rule" role="region" aria-label="Tabela de pedidos" tabIndex={0}>
          <div style={{ width, minWidth: "100%" }} className="text-aux tabular-nums" role="table" aria-rowcount={total}>
            <div className="sticky top-0 z-10 flex border-b border-rule bg-sunken" role="row">
              {table.getFlatHeaders().map((h) => {
                const active = sort.id === h.id;
                const sortable = SORTABLE.has(h.id);
                const isNumeric = NUMERIC_COLS.has(h.id);

                const sortPhrase = !active ? "sem ordem" : sort.desc ? "ordem decrescente" : "ordem crescente";
                return (
                  <div
                    key={h.id}
                    role="columnheader"
                    aria-sort={sortable ? (active ? (sort.desc ? "descending" : "ascending") : "none") : undefined}
                    style={{ width: h.getSize() }}
                    className={`flex shrink-0 items-center gap-1 px-2 py-2 text-aux font-semibold ${
                      isNumeric ? "justify-end text-right tabular-nums" : "justify-start"
                    }`}
                  >
                    {sortable ? (
                      <button
                        type="button"
                        onClick={() => setSort((s) => ({ id: h.id, desc: s.id === h.id ? !s.desc : true }))}
                        className={`hit-target inline-flex min-w-0 items-center gap-1 ${active ? "text-ink" : "text-muted hover:text-ink"}`}
                      >
                        <span className="truncate">{flexRender(h.column.columnDef.header, h.getContext())}</span>
                        {active && (sort.desc ? <ArrowDown className="icon-swap size-3 shrink-0" aria-hidden /> : <ArrowUp className="icon-swap size-3 shrink-0" aria-hidden />)}
                        <span className="sr-only">, {sortPhrase}</span>
                      </button>
                    ) : (
                      <span className="truncate text-muted">{flexRender(h.column.columnDef.header, h.getContext())}</span>
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
                    {row.getVisibleCells().map((cell) => {
                      const isNumeric = NUMERIC_COLS.has(cell.column.id);
                      return (
                        <div
                          key={cell.id}
                          role="cell"
                          style={{ width: cell.column.getSize() }}
                          className={`flex shrink-0 items-center px-2 ${isNumeric ? "justify-end text-right tabular-nums" : ""}`}
                        >
                          <span className="truncate">{flexRender(cell.column.columnDef.cell, cell.getContext())}</span>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
            {query.isFetchingNextPage && <p className="label px-2 py-2">Carregando mais pedidos…</p>}
            {query.isFetchNextPageError && (
              <div className="flex items-center gap-2 px-2 py-2 text-aux text-muted">
                <span>Falha ao carregar mais pedidos.</span>
                <button type="button" className="btn-ghost min-h-8 px-2 py-1 text-meta max-lg:min-h-11" onClick={() => query.fetchNextPage()}>
                  Tentar de novo
                </button>
              </div>
            )}
          </div>
        </div>
      </AsyncBody>
    </PanelContent>
  );
}

export default island(OrdersTableInner, panelFallback(460, { hint: true }));
