import { Filter, SquareDashedMousePointer, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { BreakdownRow } from "@/lib/api/client";
import { EVIDENCE_DIM } from "@/lib/evidence";
import { LIST_CAP, patchFilters } from "@/lib/filters";
import { fmt } from "@/lib/format";
import { STORE_NAMES_HINT } from "@/lib/glossary";
import { island, useRecorteQuery } from "@/lib/query";
import { ScatterChart } from "echarts/charts";
import { BrushComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { ChartAccess, openStoreRanking } from "./charts/ChartAccess";
import { EChart, type ECInstance, type Tokens } from "./charts/EChart";
import { AskAgentButton } from "./ui/AskAgentButton";
import { EvidenceTag, useEvidence } from "./ui/EvidenceTag";
import { AsyncBody, Empty, panelFallback, PanelContent, Segmented } from "./ui/Panel";

// Módulos deste gráfico: dispersão, caixa de seleção (brush) e barra de ferramentas que a abriga.
echarts.use([ScatterChart, BrushComponent]);

/** Altura do gráfico e do skeleton. A barra de lojas selecionadas abaixo só aparece após uma seleção do usuário. */
const CHART_H = 340;

type Y = "cancel_rate" | "cycle_p50" | "sla_rate";
const Y_AXIS: Record<Y, { label: string; format: (v: number) => string }> = {
  cancel_rate: { label: "Cancelamento", format: fmt.pct },
  cycle_p50: { label: "Ciclo mediano", format: fmt.min },
  sla_rate: { label: "No prazo", format: fmt.pct },
};
// Pergunta por eixo: "lojas" leva ao ranking de lojas do agente local; "cancelam" à regra de cancelamento.
const ASK_BY_Y: Record<Y, string> = {
  cancel_rate: "Quais lojas cancelam mais neste recorte e o que fazer?",
  cycle_p50: "Quais lojas são mais lentas neste recorte e o que fazer?",
  sla_rate: "Quais lojas estão mais atrasadas neste recorte e o que fazer?",
};

function StoreScatterInner() {
  const [y, setY] = useState<Y>("cancel_rate");
  const [picked, setPicked] = useState<BreakdownRow[]>([]);
  const [brushing, setBrushing] = useState(false);
  const chartRef = useRef<ECInstance | null>(null);
  const { data, error, isPending, refetch, isPlaceholderData, waking, down } = useRecorteQuery("/api/breakdown", {
    by: "store",
    sort: "orders",
    limit: 1000,
    min_orders: 30,
  });
  const rows = useMemo(() => (data?.rows ?? []).filter((r) => r[y] !== null), [data, y]);

  // comanda aberta que aponta para lojas: o eixo vai para a métrica dela, as lojas ficam cheias e o resto recua
  const focus = useEvidence("scatter");
  const focusMetric = focus?.evidence.metric;
  const focusId = focus?.alertId;
  useEffect(() => {
    if (focusMetric && focusMetric !== "orders") {
      setY(focusMetric);
      setPicked([]);
      setBrushing(false);
    }
  }, [focusId, focusMetric]);

  const toggleBrush = () => {
    const next = !brushing;
    setBrushing(next);
    chartRef.current?.dispatchAction({
      type: "takeGlobalCursor",
      key: "brush",
      brushOption: next ? { brushType: "rect", brushMode: "single" } : false,
    });
  };
  const isMarked = useMemo(() => {
    const stores = new Set((focus?.evidence.stores ?? []).map(String));
    const hub = focus?.evidence.hub_label ?? null;
    return (r: BreakdownRow) => stores.has(String(r.key)) || (hub !== null && r.parent === hub);
  }, [focus]);
  const markedCount = useMemo(() => (focus ? rows.filter(isMarked).length : 0), [rows, isMarked, focus]);
  // poucas lojas marcadas: o nome aparece ao lado do ponto
  const nameMarked = markedCount > 0 && markedCount <= 3;
  const maxGmv = useMemo(() => Math.max(1, ...rows.map((r) => r.gmv)), [rows]);
  const hi = rows.reduce((best, row) => ((row[y] as number) > (best[y] as number) ? row : best), rows[0]);
  const lo = rows.reduce((best, row) => ((row[y] as number) < (best[y] as number) ? row : best), rows[0]);
  const axis = Y_AXIS[y];
  const summary =
    rows.length === 0
      ? ""
      : hi === lo
        ? `${hi.label}: ${axis.format(hi[y] as number)} em ${axis.label}.`
        : `Maior ${axis.label}: ${hi.label}, ${axis.format(hi[y] as number)}. Menor: ${lo.label}, ${axis.format(lo[y] as number)}.`;

  const option = useCallback(
    (t: Tokens) => ({
      grid: { left: 56, right: 20, top: 20, bottom: 44 },
      brush: {
        toolbox: [],
        xAxisIndex: 0,
        brushStyle: { color: `${t.ink}14`, borderColor: t.ink, borderWidth: 1 },
        outOfBrush: { colorAlpha: 0.2 },
        throttleType: "debounce",
        throttleDelay: 200,
      },
      tooltip: {
        formatter: (p: { dataIndex: number }) => {
          const r = rows[p.dataIndex];
          if (!r) return "";
          return `<b>${r.label}</b> · ${r.parent ?? ""}<br/>${fmt.int(r.orders)} pedidos · ${fmt.brl(r.gmv)}<br/>${Y_AXIS[y].label}: <b>${Y_AXIS[y].format(r[y] as number)}</b>`;
        },
      },
      xAxis: { type: "log", name: "Pedidos (escala log)", nameLocation: "middle", nameGap: 28, nameTextStyle: { color: t.muted }, splitLine: { show: false } },
      yAxis: { type: "value", name: Y_AXIS[y].label, nameTextStyle: { color: t.muted }, axisLabel: { formatter: (v: number) => Y_AXIS[y].format(v) } },
      series: [
        {
          type: "scatter",
          data: rows.map((r) => {
            if (!markedCount) return [r.orders, r[y]];
            const on = isMarked(r);
            return {
              value: [r.orders, r[y]],
              symbol: on ? "diamond" : "circle",
              itemStyle: on
                ? { color: t.ink, opacity: 1, borderColor: t.ink, borderWidth: 1.5 }
                : { opacity: EVIDENCE_DIM },
              label: on && nameMarked ? { show: true, position: "right", formatter: r.label, color: t.ink, fontWeight: "bold" } : undefined,
              z: on ? 3 : 2,
            };
          }),
          symbolSize: (_: unknown, p: { dataIndex: number }) => 5 + 18 * Math.sqrt((rows[p.dataIndex]?.gmv ?? 0) / maxGmv),
          itemStyle: { color: t.series, opacity: markedCount ? 1 : 0.55, borderColor: t.seriesDeep, borderWidth: 0.5 },
          emphasis: { itemStyle: { opacity: 1 } },
          large: rows.length > 2000,
        },
      ],
    }),
    [rows, y, maxGmv, markedCount, isMarked, nameMarked],
  );

  const onBrush = useCallback(
    (params: { batch?: { selected?: { dataIndex: number[] }[] }[] }, _c: ECInstance) => {
      const idx = params.batch?.[0]?.selected?.[0]?.dataIndex ?? [];
      setPicked(idx.map((i) => rows[i]).filter((r): r is BreakdownRow => Boolean(r)));
    },
    [rows],
  );

  return (
    <PanelContent
      note={
        focus && (
          <EvidenceTag
            focus={focus}
            note={markedCount === 0 ? `${focus.title} · loja fora deste gráfico` : undefined}
          />
        )
      }
      hint={STORE_NAMES_HINT}
      busy={isPlaceholderData}
      actions={
        <>
          <button
            type="button"
            aria-pressed={brushing}
            onClick={toggleBrush}
            className={`btn-ghost min-h-8 px-2.5 py-1 text-aux max-lg:min-h-11 ${brushing ? "border-ink bg-sunken" : ""}`}
          >
            <SquareDashedMousePointer className="size-3.5" aria-hidden />
            {brushing ? "Sair da seleção" : "Selecionar área"}
          </button>
          <button
            type="button"
            onClick={openStoreRanking}
            className="btn-ghost min-h-11 px-2.5 py-1 text-aux lg:hidden"
          >
            Filtrar no ranking
          </button>
          <Segmented
            label="Eixo vertical"
            value={y}
            onChange={(v) => {
              setY(v);
              setPicked([]);
              setBrushing(false);
            }}
            options={(Object.keys(Y_AXIS) as Y[]).map((k) => ({ value: k, label: Y_AXIS[k].label }))}
          />
          <AskAgentButton subject={`lojas por ${Y_AXIS[y].label.toLowerCase()}`} question={ASK_BY_Y[y]} />
        </>
      }
    >
      <AsyncBody
        waking={waking}
        pending={isPending}
        error={error}
        down={down}
        onRetry={() => refetch()}
        what="o gráfico de lojas"
        height={CHART_H}
        empty={rows.length === 0 ? <Empty>Nenhuma loja com 30+ pedidos no recorte.</Empty> : null}
      >
        <div className="content-reveal min-w-0">
          <EChart
            key={y}
            option={option}
            height={CHART_H}
            onReady={(c) => {
              chartRef.current = c;
            }}
            onEvents={{ brushselected: onBrush }}
            ariaLabel={`Dispersão de lojas: pedidos contra ${Y_AXIS[y].label}`}
          />
          <ChartAccess
            summary={summary}
            items={[
              {
                key: "ranking",
                label: "Filtrar uma loja no ranking, em Lojas",
                onSelect: openStoreRanking,
              },
            ]}
          />
          {picked.length > 0 && (() => {
            const overCap = picked.length > LIST_CAP;
            const targetStores = (overCap ? [...picked].sort((a, b) => b.orders - a.orders) : picked).slice(0, LIST_CAP);
            return (
              <div className="mt-2 flex flex-wrap items-center gap-2 rounded-card bg-sunken px-3 py-2">
                <p className="mr-auto text-pretty text-body">
                  {overCap ? (
                    <>
                      <span className="font-semibold text-warn">{picked.length} lojas na área</span>{" "}
                      <span className="text-muted">
                        (limite do filtro: {LIST_CAP}; aplica as {LIST_CAP} com mais pedidos — ou filtre antes por Cidade/Hub):{" "}
                      </span>
                    </>
                  ) : (
                    <>{picked.length} loja(s) selecionada(s): </>
                  )}
                  <span className="text-muted">
                    {targetStores
                      .slice(0, 4)
                      .map((r) => r.label)
                      .join(", ")}
                    {targetStores.length > 4 ? "…" : ""}
                  </span>
                </p>
                <button
                  type="button"
                  className="btn-ghost py-1 max-lg:min-h-11"
                  onClick={() => {
                    setPicked([]);
                    chartRef.current?.dispatchAction({ type: "brush", areas: [] });
                  }}
                >
                  <X className="size-3.5" aria-hidden /> Descartar
                </button>
                <button
                  type="button"
                  className="btn-ink py-1 max-lg:min-h-11"
                  onClick={() => {
                    patchFilters({ store: targetStores.map((r) => Number(r.key)) });
                    setPicked([]);
                    setBrushing(false);
                    chartRef.current?.dispatchAction({ type: "brush", areas: [] });
                    chartRef.current?.dispatchAction({ type: "takeGlobalCursor", key: "brush", brushOption: false });
                  }}
                >
                  <Filter className="size-3.5" aria-hidden />{" "}
                  {overCap ? `Filtrar top ${LIST_CAP} lojas` : "Filtrar estas lojas"}
                </button>
              </div>
            );
          })()}
        </div>
      </AsyncBody>
    </PanelContent>
  );
}

export default island(StoreScatterInner, panelFallback(CHART_H, { hint: true }));
