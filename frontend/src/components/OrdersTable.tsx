/**
 * Pedidos brutos do recorte: paginação e ordenação no servidor (DuckDB),
 * rolagem infinita com TanStack Query e só as linhas visíveis no DOM via
 * TanStack Virtual. Centenas de milhares de linhas sem travar o navegador.
 */
import { useStore } from "@nanostores/react";
import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";
import { flexRender, getCoreRowModel, useReactTable, createColumnHelper } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowDown, ArrowUp, ChevronRight, Filter, X } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { apiGet, type OrderRow } from "@/lib/api/client";
import { askAgentAbout } from "@/lib/agentBridge";
import { $filters, $ready, applyDrilldown, toQuery } from "@/lib/filters";
import { fmt, label } from "@/lib/format";
import { STORE_NAMES_HINT } from "@/lib/glossary";
import { prefersReducedMotion, useMediaQuery } from "@/lib/media";
import { gated, island, useApiGate, useMeta } from "@/lib/query";
import { AskAgentButton } from "./ui/AskAgentButton";
import { AsyncBody, Empty, PanelContent, panelFallback } from "./ui/Panel";

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
const ROW_H_DESKTOP = 34;
const ROW_H_MOBILE = 44;
const GMV_OUTLIER = 5000;
const col = createColumnHelper<OrderRow>();
const SORTABLE = new Set(["created_at", "amount", "delivery_fee", "cycle_min", "production_min", "transit_min", "distance_m", "store_name", "hub_name", "city", "status"]);
const NUMERIC_COLS = new Set(["amount", "cycle_min", "production_min", "transit_min", "distance_m"]);

const columns = [
  col.accessor("created_at", { header: "Criado em", cell: (c) => fmt.dateTime(c.getValue()), size: 120 }),
  col.accessor("status", {
    header: "Status",
    size: 96,
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
  col.accessor("hub_name", { header: "Hub", size: 144 }),
  col.accessor("store_name", { header: "Loja", size: 148 }),
  col.accessor("segment", { header: "Segmento", size: 96, cell: (c) => label(c.getValue()) }),
  col.accessor("channel", { header: "Canal", size: 108 }),
  col.accessor("modal", { header: "Modal", size: 78, cell: (c) => label(c.getValue()) }),
  col.accessor("amount", {
    header: "Valor",
    size: 108,
    cell: (c) => {
      const v = c.getValue();
      return v > GMV_OUTLIER ? (
        <span
          className="inline-flex items-center gap-1 font-semibold text-ink"
          title="Acima de R$ 5 mil: fora do GMV e do ticket médio"
        >
          <ArrowUp className="size-3 shrink-0" aria-hidden />
          {fmt.brl(v)}
          <span className="sr-only"> fora do GMV</span>
        </span>
      ) : (
        fmt.brl(v)
      );
    },
  }),
  col.accessor("cycle_min", {
    header: "Ciclo",
    size: 104,
    cell: (c) =>
      c.row.original.on_time === false ? (
        <span className="inline-flex items-center gap-1 font-semibold text-ink" title="Fora do SLA">
          <ArrowUp className="size-3 shrink-0" aria-hidden />
          {fmt.min(c.getValue())}
          <span className="sr-only"> fora do SLA</span>
        </span>
      ) : (
        fmt.min(c.getValue())
      ),
  }),
  col.accessor("production_min", { header: "Preparo", size: 88, cell: (c) => fmt.min(c.getValue()) }),
  col.accessor("transit_min", { header: "Trânsito", size: 88, cell: (c) => fmt.min(c.getValue()) }),
  col.accessor("distance_m", { header: "Distância", size: 88, cell: (c) => (c.getValue() === null ? "—" : fmt.km(c.getValue()! / 1000)) }),
];

function OrdersTableInner() {
  const filters = useStore($filters);
  const ready = useStore($ready);
  const gate = useApiGate();
  const meta = useMeta().data;
  const desktop = useMediaQuery("(min-width: 1024px)");
  const rowH = desktop ? ROW_H_DESKTOP : ROW_H_MOBILE;
  const [sort, setSort] = useState<{ id: string; desc: boolean }>({ id: "created_at", desc: true });
  const [selectedOrder, setSelectedOrder] = useState<OrderRow | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const detailId = useId();
  const detailRef = useRef<HTMLDivElement>(null);
  const originOrderIdRef = useRef<number | null>(null);
  const shouldReturnFocusRef = useRef(false);

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
    estimateSize: () => rowH,
    overscan: 12,
  });
  const items = virtual.getVirtualItems();

  useEffect(() => {
    virtual.measure();
  }, [virtual, rowH]);

  // chegou perto do fim do que já foi carregado: busca a próxima página
  const lastIndex = items.at(-1)?.index ?? 0;
  useEffect(() => {
    if (lastIndex >= rows.length - 30 && query.hasNextPage && !query.isFetchingNextPage && !query.isFetchNextPageError) {
      query.fetchNextPage();
    }
  }, [lastIndex, rows.length, query.hasNextPage, query.isFetchingNextPage, query.isFetchNextPageError, query.fetchNextPage]);

  // recorte ou ordenação novos: volta ao topo e limpa a seleção
  useEffect(() => {
    scroller.current?.scrollTo({ top: 0 });
  }, [filters, sort]);

  useEffect(() => {
    shouldReturnFocusRef.current = false;
    originOrderIdRef.current = null;
    setSelectedOrder(null);
  }, [filters]);

  const openOrder = (order: OrderRow) => {
    originOrderIdRef.current = order.order_id;
    shouldReturnFocusRef.current = false;
    setSelectedOrder(order);
  };

  const closeDetail = (returnFocus: boolean) => {
    shouldReturnFocusRef.current = returnFocus;
    setSelectedOrder(null);
  };

  useEffect(() => {
    if (selectedOrder) {
      const detailEl = detailRef.current;
      if (!detailEl) return;
      detailEl.scrollIntoView({
        block: "nearest",
        behavior: prefersReducedMotion() ? "auto" : "smooth",
      });
      detailEl.focus({ preventScroll: true });
    } else if (shouldReturnFocusRef.current && originOrderIdRef.current !== null) {
      shouldReturnFocusRef.current = false;
      const targetId = originOrderIdRef.current;
      const rowEl = scroller.current?.querySelector<HTMLElement>(`[data-order-id="${targetId}"]`);
      if (rowEl) {
        rowEl.scrollIntoView({
          block: "nearest",
          behavior: prefersReducedMotion() ? "auto" : "smooth",
        });
        rowEl.focus({ preventScroll: true });
      } else {
        const idx = rows.findIndex((r) => r.order_id === targetId);
        if (idx >= 0) {
          virtual.scrollToIndex(idx, { align: "auto" });
          requestAnimationFrame(() => {
            scroller.current?.querySelector<HTMLElement>(`[data-order-id="${targetId}"]`)?.focus({ preventScroll: true });
          });
        }
      }
    }
  }, [selectedOrder?.order_id]);

  const selectedHubId = selectedOrder
    ? meta?.hubs.find((h) => h.label === selectedOrder.hub_name)?.value
    : undefined;
  const selectedStoreId = selectedOrder
    ? meta?.stores.find(
        (s) =>
          s.label === selectedOrder.store_name &&
          (selectedHubId === undefined || Number(s.parent) === Number(selectedHubId)),
      )?.value ?? meta?.stores.find((s) => s.label === selectedOrder.store_name)?.value
    : undefined;

  const width = table.getTotalSize();

  return (
    <PanelContent
      hint={
        query.data
          ? `${fmt.int(total)} pedidos · ${fmt.int(rows.length)} carregados. Clique em um pedido para inspecionar; role para buscar mais e clique nos cabeçalhos para ordenar. ↑ fora do SLA ou do GMV (> R$ 5 mil). ${STORE_NAMES_HINT}`
          : `Paginação e ordenação no servidor. Clique em um pedido para inspecionar. ↑ fora do SLA ou do GMV (> R$ 5 mil). ${STORE_NAMES_HINT}`
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
        empty={query.data && total === 0 ? <Empty>Sem pedidos neste recorte.</Empty> : null}
      >
        {selectedOrder && (
          <div
            ref={detailRef}
            id={detailId}
            role="region"
            tabIndex={-1}
            aria-label={`Detalhes do pedido ${selectedOrder.order_id}`}
            style={{ scrollMarginTop: "calc(var(--sticky-bar, 6.5rem) + 0.75rem)" }}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                e.stopPropagation();
                closeDetail(true);
              }
            }}
            className="mb-3 rounded-card border border-rule bg-sunken/70 p-3.5 text-aux"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rule pb-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-ink tabular-nums">Pedido #{selectedOrder.order_id}</span>
                <span className="text-muted">{fmt.dateTime(selectedOrder.created_at)}</span>
                {/* Fora do SLA em tinta com peso e seta, como na célula: o vermelho fica com as comandas. */}
                <span
                  className={`inline-flex items-center gap-1 rounded-tick px-1.5 py-0.5 text-meta font-semibold ${
                    selectedOrder.on_time === false
                      ? "border border-ink bg-surface text-ink"
                      : selectedOrder.status === "canceled"
                        ? "bg-sunken-strong text-ink"
                        : "bg-surface text-ink"
                  }`}
                >
                  {selectedOrder.on_time === false && <ArrowUp className="size-3 shrink-0" aria-hidden />}
                  {selectedOrder.on_time === false
                    ? "Fora do SLA"
                    : selectedOrder.on_time === true
                      ? "No prazo"
                      : label(selectedOrder.status)}
                </span>
                <span className="text-muted">
                  {label(selectedOrder.segment)} · {selectedOrder.channel} · {label(selectedOrder.modal)}
                </span>
              </div>
              <button
                type="button"
                onClick={() => closeDetail(true)}
                aria-label="Fechar detalhes do pedido"
                className="btn-ghost min-h-8 gap-1 px-2 py-1 text-meta max-lg:min-h-11"
              >
                <X className="size-3.5" aria-hidden /> Fechar
              </button>
            </div>
            <dl className="mt-2.5 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4 lg:grid-cols-6">
              <div>
                <dt className="text-meta text-muted">Cidade / Hub</dt>
                <dd className="font-medium text-ink">
                  {selectedOrder.city} · {selectedOrder.hub_name}
                </dd>
              </div>
              <div>
                <dt className="text-meta text-muted">Loja</dt>
                <dd className="font-medium text-ink">{selectedOrder.store_name}</dd>
              </div>
              <div>
                <dt className="text-meta text-muted">Valor / Frete</dt>
                <dd className="tabular-nums font-medium text-ink">
                  {fmt.brl(selectedOrder.amount)} · frete {fmt.brl(selectedOrder.delivery_fee)}
                </dd>
              </div>
              <div>
                <dt className="text-meta text-muted">Pagamento</dt>
                <dd className="font-medium text-ink">{label(selectedOrder.payment_method)}</dd>
              </div>
              <div>
                <dt className="text-meta text-muted">Ciclo (Preparo + Trânsito)</dt>
                <dd className="tabular-nums font-medium text-ink">
                  {fmt.min(selectedOrder.cycle_min)} ({fmt.min(selectedOrder.production_min)} +{" "}
                  {fmt.min(selectedOrder.transit_min)})
                </dd>
              </div>
              <div>
                <dt className="text-meta text-muted">Distância</dt>
                <dd className="tabular-nums font-medium text-ink">
                  {selectedOrder.distance_m === null ? "—" : fmt.km(selectedOrder.distance_m / 1000)}
                </dd>
              </div>
            </dl>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {selectedHubId !== undefined && (
                <button
                  type="button"
                  className="btn-ink min-h-8 gap-1.5 px-2.5 py-1 text-meta max-lg:min-h-11"
                  onClick={() => applyDrilldown({ city: [selectedOrder.city], hub: [Number(selectedHubId)] })}
                >
                  <Filter className="size-3" aria-hidden /> Filtrar hub {selectedOrder.hub_name}
                </button>
              )}
              {selectedStoreId !== undefined && (
                <button
                  type="button"
                  className="btn-ghost min-h-8 gap-1.5 px-2.5 py-1 text-meta max-lg:min-h-11"
                  onClick={() =>
                    applyDrilldown({
                      city: [selectedOrder.city],
                      ...(selectedHubId !== undefined ? { hub: [Number(selectedHubId)] } : {}),
                      store: [Number(selectedStoreId)],
                    })
                  }
                >
                  <Filter className="size-3" aria-hidden /> Filtrar loja {selectedOrder.store_name}
                </button>
              )}
              <button
                type="button"
                className="btn-ghost min-h-8 px-2.5 py-1 text-meta max-lg:min-h-11"
                onClick={() =>
                  askAgentAbout(
                    `Analise o pedido #${selectedOrder.order_id} na loja ${selectedOrder.store_name} (${selectedOrder.hub_name}, ${selectedOrder.city}), ciclo de ${fmt.min(selectedOrder.cycle_min)} e status ${label(selectedOrder.status).toLowerCase()}: é caso isolado ou padrão do recorte?`,
                  )
                }
              >
                Perguntar ao agente
              </button>
            </div>
          </div>
        )}
        <div ref={scroller} className="content-reveal relative h-[460px] min-w-0 overflow-auto rounded-tick border border-rule" role="region" aria-label="Tabela de pedidos" tabIndex={0}>
          <div style={{ width, minWidth: "100%" }} className="text-aux tabular-nums" role="grid" aria-label="Pedidos do recorte" aria-rowcount={total + 1}>
            <div className="sticky top-0 z-20 flex border-b border-rule bg-sunken" role="row">
              {table.getFlatHeaders().map((h) => {
                const active = sort.id === h.id;
                const sortable = SORTABLE.has(h.id);
                const isNumeric = NUMERIC_COLS.has(h.id);
                const isPinned = h.id === "created_at";

                const sortPhrase = !active ? "sem ordem" : sort.desc ? "ordem decrescente" : "ordem crescente";
                return (
                  <div
                    key={h.id}
                    role="columnheader"
                    aria-sort={sortable ? (active ? (sort.desc ? "descending" : "ascending") : "none") : undefined}
                    style={{ width: h.getSize() }}
                    className={`flex shrink-0 items-center gap-1 px-2 py-2 text-aux font-semibold ${
                      isNumeric ? "justify-end text-right tabular-nums" : "justify-start"
                    } ${isPinned ? "sticky left-0 z-10 border-r border-rule bg-sunken" : ""}`}
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
                const isSelected = selectedOrder?.order_id === row.original.order_id;
                const toggleRow = () => (isSelected ? closeDetail(false) : openOrder(row.original));
                return (
                  <div
                    key={row.id}
                    role="row"
                    tabIndex={0}
                    data-order-id={row.original.order_id}
                    aria-selected={isSelected}
                    aria-rowindex={item.index + 2}
                    onClick={toggleRow}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        toggleRow();
                      }
                    }}
                    className={`group/row absolute left-0 flex w-full cursor-pointer border-b border-rule/50 transition-colors duration-(--duration-quick) ${
                      isSelected ? "bg-sunken" : "hover:bg-sunken/60"
                    }`}
                    style={{ height: rowH, transform: `translateY(${item.start}px)` }}
                  >
                    {row.getVisibleCells().map((cell) => {
                      const isNumeric = NUMERIC_COLS.has(cell.column.id);
                      const isPinned = cell.column.id === "created_at";
                      return (
                        <div
                          key={cell.id}
                          role="gridcell"
                          style={{ width: cell.column.getSize() }}
                          className={`flex shrink-0 items-center px-2 ${
                            isNumeric ? "justify-end text-right tabular-nums" : ""
                          } ${
                            isPinned
                              ? `sticky left-0 z-10 justify-between gap-1 border-r border-rule ${isSelected ? "bg-sunken" : "bg-surface group-hover/row:bg-sunken"}`
                              : ""
                          }`}
                        >
                          <span className="truncate">{flexRender(cell.column.columnDef.cell, cell.getContext())}</span>
                          {isPinned && (
                            <ChevronRight
                              className={`size-3.5 shrink-0 transition-transform duration-(--duration-fast) motion-reduce:transition-none ${
                                isSelected ? "rotate-90 text-ink" : "text-muted group-hover/row:text-ink"
                              }`}
                              aria-hidden
                            />
                          )}
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

export default island(OrdersTableInner, panelFallback(460, { hint: 2, hintMobile: 5 }));
