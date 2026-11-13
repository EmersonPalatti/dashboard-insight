import { ChevronDown, Download, RotateCcw } from "lucide-react";
import { lazy, Suspense, useEffect, useLayoutEffect, useRef, useState } from "react";
import { resetFilters } from "@/lib/filters";
import { useMediaQuery } from "@/lib/media";
import { island } from "@/lib/query";
import { AgentAskButton } from "./agent/AgentLauncher";
import { CopyLinkButton } from "./filters/CopyLinkButton";
import { ExtraFields, PeriodFields, PlaceFields } from "./filters/FilterFields";
import { FiltersPopover } from "./filters/FiltersPopover";
import { MobileRecorte } from "./filters/MobileRecorte";
import { ShareMenu } from "./filters/ShareMenu";
import { useFilterModel, type FilterModel } from "./filters/useFilterModel";
import { ActiveChips } from "./ui/ActiveChips";

// Só baixam quando usados: a folha existe só no mobile e o modal de exportação só depois do primeiro clique.
// Os imports ficam em funções para o preload reaproveitar o mesmo módulo (import() cacheia).
const loadFilterSheet = () => import("./filters/FilterSheet").then((m) => ({ default: m.FilterSheet }));
const FilterSheet = lazy(loadFilterSheet);
const loadExportDialog = () => import("./ExportDialog").then((m) => ({ default: m.ExportDialog }));
const ExportDialog = lazy(loadExportDialog);
/** Baixa o chunk do modal antes do clique. Erro de preload é ignorado: o lazy carrega (e mostra o erro, se houver) na abertura. */
const preloadExportDialog = () => void loadExportDialog().catch(() => {});

/**
 * Barra do desktop (lg e acima), em duas linhas com papéis separados:
 *  1. o que define o recorte (período, lugar, mais filtros) e, à direita, o agente;
 *  2. o recorte em si (chips, limpar) e, à direita, compartilhar.
 * Linha 1 em controles de 40px, linha 2 em 32px. O campo do agente cede
 * largura antes dos seletores de lugar: encolhe até "Agente" + atalho, e só
 * volta ao convite inteiro quando o miolo do botão chega a 18rem.
 * Sem espaço na linha 1 (entre lg e xl, ou com o painel lateral aberto),
 * o agente desce para o fim da linha 2, em 32px, e a barra continua com duas linhas (80px).
 */
function DesktopBar({ m }: { m: FilterModel }) {
  return (
    <div className="@container flex min-w-0 flex-col gap-2">
      <div className="flex min-w-0 items-center gap-x-4">
        <div className="shrink-0">
          <PeriodFields m={m} />
        </div>
        {/* basis largo: cidade, hub e loja ficam com o nome inteiro; o agente encolhe primeiro */}
        <div className="flex min-w-0 flex-[1_1_42rem] items-center gap-2">
          <div className="grid min-w-0 flex-1 grid-cols-3 gap-2">
            <PlaceFields m={m} />
          </div>
          <div className="shrink-0">
            <FiltersPopover count={m.extraCount}>
              <ExtraFields m={m} />
            </FiltersPopover>
          </div>
        </div>
        {/* último da linha: fica acima do canto onde o painel solto abre. shrink alto: cede antes do lugar. */}
        <div className="hidden min-w-[11rem] max-w-[22rem] flex-[0_100_22rem] border-l border-rule pl-4 @min-[70rem]:flex">
          <AgentAskButton />
        </div>
      </div>

      <div className="flex min-h-8 flex-wrap items-center gap-x-3 gap-y-1.5">
        {m.chips.length === 0 ? (
          <p className="label text-pretty">Recorte completo: todos os pedidos do período.</p>
        ) : (
          <ActiveChips chips={m.chips} />
        )}
        {m.active > 0 && (
          <button
            type="button"
            className="inline-flex h-8 items-center gap-1.5 rounded-tick px-1.5 text-aux font-medium text-muted transition-colors duration-(--duration-quick) hover:bg-sunken hover:text-ink"
            onClick={resetFilters}
          >
            <RotateCcw className="size-3.5" aria-hidden /> Limpar recorte
          </button>
        )}
        <div className="ml-auto flex items-center gap-2">
          <ShareMenu />
          <div className="w-44 shrink-0 @min-[70rem]:hidden">
            <AgentAskButton compact />
          </div>
        </div>
      </div>
    </div>
  );
}

function FilterBarInner() {
  const m = useFilterModel();
  const desktop = useMediaQuery("(min-width: 1024px)");
  const [exportOpen, setExportOpen] = useState(false);
  // o modal monta no primeiro clique e fica montado depois: a animação de fechamento precisa do nó
  const [exportMounted, setExportMounted] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [pedidoOpen, setPedidoOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const exportWasOpen = useRef(false);

  // filtro de pedido em uso (ex.: veio pela URL): o grupo abre para o filtro não ficar escondido
  useEffect(() => {
    if (m.extraCount > 0) setPedidoOpen(true);
  }, [m.extraCount]);

  // a folha só existe no mobile: se a janela crescer com ela aberta, ela fecha
  useEffect(() => {
    if (desktop) setSheetOpen(false);
  }, [desktop]);

  // A barra é sticky: a folga dos âncoras acompanha a altura real (chips, quebra de linha).
  useLayoutEffect(() => {
    const bar = document.querySelector<HTMLElement>("[data-filter-bar]");
    if (!bar) return;
    const apply = () => {
      document.documentElement.style.setProperty("--sticky-bar", `${bar.offsetHeight}px`);
    };
    apply();
    const ro = new ResizeObserver(apply);
    ro.observe(bar);
    return () => ro.disconnect();
  }, [desktop, m.chips.length]);

  // O diálogo de exportação abre depois que a folha fecha. O foco volta para o botão que abriu a folha,
  // depois da animação de saída (o close nativo também devolve, este é o reforço).
  useEffect(() => {
    if (!exportWasOpen.current || exportOpen) {
      exportWasOpen.current = exportOpen;
      return;
    }
    exportWasOpen.current = false;
    const id = window.setTimeout(() => triggerRef.current?.focus({ preventScroll: true }), 200);
    return () => window.clearTimeout(id);
  }, [exportOpen]);

  const openExport = () => {
    setSheetOpen(false);
    setExportMounted(true);
    setExportOpen(true);
  };
  const summary =
    m.chips.length === 0 ? "Todos os pedidos" : m.chips.length === 1 ? m.chips[0].value : `${m.chips[0].value} +${m.chips.length - 1}`;

  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      {desktop ? (
        <DesktopBar m={m} />
      ) : (
        <>
          <MobileRecorte summary={summary} activeCount={m.active} onOpen={() => setSheetOpen(true)} buttonRef={triggerRef} />
          <Suspense fallback={null}>
            <FilterSheet
              open={sheetOpen}
              onClose={() => setSheetOpen(false)}
              returnFocusRef={triggerRef}
              footer={
                <>
                  <CopyLinkButton className="min-h-11 justify-center" />
                  <button
                    type="button"
                    className="btn-ghost min-h-11 justify-center whitespace-nowrap"
                    onClick={openExport}
                    onPointerDown={preloadExportDialog}
                    onFocus={preloadExportDialog}
                  >
                    <Download className="size-3.5" aria-hidden /> Exportar
                  </button>
                  <button type="button" className="btn-ink col-span-2 min-h-11 justify-center whitespace-nowrap" onClick={() => setSheetOpen(false)}>
                    Ver resultado
                  </button>
                </>
              }
            >
              <div className="grid min-w-0 gap-5">
                <div className="grid min-w-0 gap-2">
                  <p id="periodo-titulo" className="text-aux font-semibold text-ink">
                    Período
                  </p>
                  <PeriodFields m={m} variant="sheet" labelId="periodo-titulo" />
                </div>
                <div role="group" aria-labelledby="lugar-titulo" className="grid min-w-0 gap-1.5">
                  <p id="lugar-titulo" className="text-aux font-semibold text-ink">
                    Lugar
                  </p>
                  <PlaceFields m={m} />
                </div>
                {/* Segmento, canal e modal: recolhidos como o "Mais filtros" do desktop; abrem sozinhos quando há filtro neles. */}
                <details
                  open={pedidoOpen}
                  onToggle={(e) => setPedidoOpen(e.currentTarget.open)}
                  className="group min-w-0 border-t border-rule"
                >
                  <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 text-aux font-semibold text-ink [&::-webkit-details-marker]:hidden">
                    <span>
                      Pedido: segmento, canal e modal
                      {m.extraCount > 0 && <span className="font-normal text-muted"> · {m.extraCount} em uso</span>}
                    </span>
                    <ChevronDown className="size-4 shrink-0 text-muted group-open:rotate-180" aria-hidden />
                  </summary>
                  <div className="grid min-w-0 gap-1.5 pb-1">
                    <ExtraFields m={m} />
                  </div>
                </details>
                <div className="grid min-w-0 gap-2">
                  {m.chips.length === 0 ? (
                    <p className="label text-pretty">Recorte completo: todos os pedidos do período.</p>
                  ) : (
                    <ActiveChips chips={m.chips} />
                  )}
                  {m.active > 0 && (
                    <button type="button" className="btn-ghost min-h-11 justify-self-start px-3" onClick={resetFilters}>
                      <RotateCcw className="size-3.5" aria-hidden /> Limpar recorte
                    </button>
                  )}
                </div>
              </div>
            </FilterSheet>
          </Suspense>
        </>
      )}
      {exportMounted && (
        <Suspense fallback={null}>
          <ExportDialog open={exportOpen} onClose={() => setExportOpen(false)} />
        </Suspense>
      )}
    </div>
  );
}

/**
 * Fallback do SSR com a altura da barra em cada breakpoint. No mobile o resumo ocupa a
 * largura toda e o atalho de comandas vai na linha de baixo (duas faixas de 44px + respiro).
 * No desktop, 80px: duas linhas (40px + 8px de respiro + 32px). O breakpoint é o mesmo de
 * `useMediaQuery("(min-width: 1024px)")`, o lg do Tailwind, então a troca não empurra o layout.
 */
const barSkeleton = <div className="skeleton h-24 w-full lg:h-20" aria-hidden />;

export default island(FilterBarInner, barSkeleton);
