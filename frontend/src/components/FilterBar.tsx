import { ChevronDown, Download, RotateCcw } from "lucide-react";
import { lazy, Suspense, useEffect, useRef, useState, type ComponentType, type ReactNode } from "react";
import { resetFilters } from "@/lib/filters";
import { useMediaQuery } from "@/lib/media";
import { island } from "@/lib/query";
import { AgentAskButton } from "./agent/AgentLauncher";
import { ExtraFields, PeriodFields, PlaceFields } from "./filters/FilterFields";
import { FiltersPopover } from "./filters/FiltersPopover";
import { MobileRecorte } from "./filters/MobileRecorte";
import { ShareMenu } from "./filters/ShareMenu";
import { useFilterModel, type FilterModel } from "./filters/useFilterModel";
import { ActiveChips } from "./ui/ActiveChips";
import { ErrorBoundary, IslandErrorFallback } from "./ui/ErrorBoundary";

// Só baixam quando usados: a folha só no mobile e no primeiro "Editar", o modal de exportação depois do primeiro clique.
// Os imports ficam em funções para o preload reaproveitar o mesmo módulo (import() cacheia).
const loadFilterSheet = () => import("./filters/FilterSheet").then((m) => ({ default: m.FilterSheet }));
const loadExportDialog = () => import("./ExportDialog").then((m) => ({ default: m.ExportDialog }));
/** Baixa o chunk do modal antes do clique. Erro de preload é ignorado: o lazy carrega (e mostra o erro, se houver) na abertura. */
const preloadExportDialog = () => void loadExportDialog().catch(() => {});

// React.lazy guarda a rejeição para sempre: cada tentativa ganha um lazy novo, que chama o import de novo
// (chunk velho depois de um deploy, rede caída). O `id` vira resetKey do limite de erro local.
interface LazyAttempt<P> {
  id: number;
  Component: ComponentType<P>;
}
function useLazyAttempt<P>(load: () => Promise<{ default: ComponentType<P> }>) {
  const [attempt, setAttempt] = useState<LazyAttempt<P>>(() => ({ id: 0, Component: lazy(load) }));
  const retry = () => setAttempt((prev) => ({ id: prev.id + 1, Component: lazy(load) }));
  return [attempt, retry] as const;
}

/** Falha do chunk fica neste bloco (a barra continua de pé) e "Tentar de novo" baixa o chunk outra vez. */
function LazyBoundary({ attemptId, onRetry, children }: { attemptId: number; onRetry: () => void; children: ReactNode }) {
  return (
    <ErrorBoundary
      resetKey={attemptId}
      fallback={(_reset, error) => <IslandErrorFallback error={error} onReset={onRetry} variant="compact" />}
    >
      <Suspense fallback={null}>{children}</Suspense>
    </ErrorBoundary>
  );
}

/**
 * Barra do desktop (lg e acima), em duas linhas com papéis separados:
 *  1. o que define o recorte (período, lugar, mais filtros) e, à direita, o agente;
 *  2. o recorte em si (chips, limpar) e, à direita, compartilhar.
 * Linha 1 em controles de 40px, linha 2 em 32px. O campo do agente cede
 * largura antes dos seletores de lugar: encolhe até "Agente" / "Aberta" + atalho,
 * mostra "Conversa aberta" quando cabe (~12.5rem+) e o convite completo a partir de 18rem.
 * Permanece ancorado na linha 1 mesmo com o painel lateral aberto, sem pular de linha.
 */
function DesktopBar({ m }: { m: FilterModel }) {
  return (
    <div className="@container flex min-w-0 flex-col gap-2">
      <div className="flex min-w-0 flex-nowrap items-center gap-x-2.5 @min-[75rem]:gap-x-4">
        <div className="shrink-0">
          <PeriodFields m={m} />
        </div>
        {/* Row 1 prioriza período e selects de recorte; Compartilhar fica na linha 2 */}
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <div className="grid min-w-0 flex-1 grid-cols-3 gap-2">
            <PlaceFields m={m} />
          </div>
          <div className="shrink-0">
            <FiltersPopover count={m.extraCount}>
              <ExtraFields m={m} />
            </FiltersPopover>
          </div>
        </div>
        {/* último da linha em telas largas: fica acima do canto onde o painel abre */}
        <div className="flex min-w-[9.5rem] max-w-[21rem] flex-[0_2_20.5rem] border-l border-rule pl-2.5 @min-[75rem]:pl-4">
          <AgentAskButton />
        </div>
      </div>

      <div className="flex min-h-8 flex-wrap items-center gap-x-3 gap-y-1.5">
        {m.chips.length > 0 ? (
          <>
            <ActiveChips chips={m.chips} />
            {m.active > 0 && (
              <button
                type="button"
                className="inline-flex h-8 items-center gap-1.5 rounded-tick px-1.5 text-aux font-medium text-muted transition-colors duration-(--duration-quick) hover:bg-sunken hover:text-ink"
                onClick={resetFilters}
              >
                <RotateCcw className="size-3.5" aria-hidden /> Limpar recorte
              </button>
            )}
          </>
        ) : (
          <p className="text-aux text-muted">Recorte completo: todos os pedidos.</p>
        )}
        <div className="ml-auto flex shrink-0 items-center gap-2">
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
  // a folha (e o chunk dela) só monta no primeiro "Editar" e fica montada depois, como o modal
  const [sheetMounted, setSheetMounted] = useState(false);
  const [sheetAttempt, retrySheet] = useLazyAttempt(loadFilterSheet);
  const [exportAttempt, retryExport] = useLazyAttempt(loadExportDialog);
  const FilterSheet = sheetAttempt.Component;
  const ExportDialog = exportAttempt.Component;
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

  const openSheet = () => {
    setSheetMounted(true);
    setSheetOpen(true);
  };
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
          <MobileRecorte summary={summary} activeCount={m.active} onOpen={openSheet} buttonRef={triggerRef} />
          {sheetMounted && (
            <LazyBoundary attemptId={sheetAttempt.id} onRetry={retrySheet}>
              <FilterSheet
                open={sheetOpen}
                onClose={() => setSheetOpen(false)}
                returnFocusRef={triggerRef}
                footer={
                  <>
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
                        Pedido: segmento, canal, modal e status
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
            </LazyBoundary>
          )}
        </>
      )}
      {exportMounted && (
        <LazyBoundary attemptId={exportAttempt.id} onRetry={retryExport}>
          <ExportDialog open={exportOpen} onClose={() => setExportOpen(false)} />
        </LazyBoundary>
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
const barSkeleton = <div className="skeleton h-11 w-full lg:h-20" aria-hidden />;

export default island(FilterBarInner, barSkeleton);
