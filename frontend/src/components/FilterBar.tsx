import { Download, RotateCcw } from "lucide-react";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
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
 * Linha 1 em controles de 40px, linha 2 em 32px. A barra é um container: o
 * agente encolhe para "Agente" quando ela estreita (painel lateral aberto).
 */
function DesktopBar({ m }: { m: FilterModel }) {
  return (
    <div className="@container flex min-w-0 flex-col gap-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <PeriodFields m={m} />
        <div className="flex min-w-0 flex-1 basis-[24rem] items-center gap-2">
          <div className="grid min-w-0 flex-1 grid-cols-3 gap-2">
            <PlaceFields m={m} />
          </div>
          <FiltersPopover count={m.extraCount}>
            <ExtraFields m={m} />
          </FiltersPopover>
        </div>
        {/* último da linha: fica acima do canto onde o painel solto abre */}
        <div className="flex min-w-0 border-l border-rule pl-4">
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
            className="inline-flex h-8 items-center gap-1.5 rounded-tick px-1.5 text-[0.88rem] text-muted transition-colors duration-(--duration-quick) hover:bg-sunken hover:text-ink"
            onClick={resetFilters}
          >
            <RotateCcw className="size-3.5" aria-hidden /> Limpar recorte
          </button>
        )}
        <div className="ml-auto">
          <ShareMenu />
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
  const triggerRef = useRef<HTMLButtonElement>(null);

  // a folha só existe no mobile: se a janela crescer com ela aberta, ela fecha
  useEffect(() => {
    if (desktop) setSheetOpen(false);
  }, [desktop]);

  const openExport = () => {
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
              <div className="grid gap-5">
                <div className="grid gap-2">
                  <p className="cond text-[0.8rem] font-bold text-ink">Período</p>
                  <PeriodFields m={m} variant="sheet" />
                </div>
                <div className="grid gap-1.5">
                  <PlaceFields m={m} />
                  <ExtraFields m={m} />
                </div>
                <div className="grid gap-2">
                  {m.chips.length === 0 ? (
                    <p className="label text-pretty">Recorte completo: todos os pedidos do período.</p>
                  ) : (
                    <ActiveChips chips={m.chips} />
                  )}
                  {m.active > 0 && (
                    <button type="button" className="btn-ghost justify-self-start" onClick={resetFilters}>
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
 * Fallback do SSR com a altura da barra em cada breakpoint: 44px no mobile (MobileRecorte, min-h-11)
 * e 80px no desktop (duas linhas: 40px + 8px de respiro + 32px). O breakpoint é o mesmo de
 * `useMediaQuery("(min-width: 1024px)")`, o lg do Tailwind, então a troca não empurra o layout.
 */
const barSkeleton = <div className="skeleton h-11 w-full lg:h-20" aria-hidden />;

export default island(FilterBarInner, barSkeleton);
