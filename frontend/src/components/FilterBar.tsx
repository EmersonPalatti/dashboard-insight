import { Download, RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { resetFilters } from "@/lib/filters";
import { island } from "@/lib/query";
import { ExportDialog } from "./ExportDialog";
import { CopyLinkButton } from "./filters/CopyLinkButton";
import { ActiveChips, ExtraFields, PeriodFields, PlaceFields } from "./filters/FilterFields";
import { FilterSheet } from "./filters/FilterSheet";
import { FiltersPopover } from "./filters/FiltersPopover";
import { MobileRecorte } from "./filters/MobileRecorte";
import { useMediaQuery } from "./filters/media";
import { useFilterModel, type FilterModel } from "./filters/useFilterModel";

/** Barra do desktop (lg e acima): todos os controles, com "Mais filtros" em popover. */
function DesktopBar({ m, onExport }: { m: FilterModel; onExport: () => void }) {
  return (
    <>
      <div className="flex flex-wrap items-end gap-2">
        <PeriodFields m={m} />
        <div className="grid min-w-0 flex-1 basis-[36rem] grid-cols-4 gap-1.5">
          <PlaceFields m={m} />
          <FiltersPopover count={m.extraCount}>
            <ExtraFields m={m} />
          </FiltersPopover>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {m.chips.length === 0 ? (
          <p className="label mr-auto">Recorte completo: todos os pedidos do período.</p>
        ) : (
          <div className="mr-auto flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1.5">
            <ActiveChips chips={m.chips} />
            <p className="label">Tudo abaixo segue este recorte.</p>
          </div>
        )}
        {m.active > 0 && (
          <button type="button" className="btn-ghost" onClick={resetFilters}>
            <RotateCcw className="size-3.5" aria-hidden /> Limpar recorte
          </button>
        )}
        <CopyLinkButton />
        <button type="button" className="btn-ink" onClick={onExport}>
          <Download className="size-3.5" aria-hidden /> Exportar
        </button>
      </div>
    </>
  );
}

function FilterBarInner() {
  const m = useFilterModel();
  const desktop = useMediaQuery("(min-width: 1024px)");
  const [exportOpen, setExportOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // a folha só existe no mobile: se a janela crescer com ela aberta, ela fecha
  useEffect(() => {
    if (desktop) setSheetOpen(false);
  }, [desktop]);

  const openExport = () => setExportOpen(true);
  const summary =
    m.chips.length === 0 ? "Todos os pedidos" : m.chips.length === 1 ? m.chips[0].value : `${m.chips[0].value} +${m.chips.length - 1}`;

  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      {desktop ? (
        <DesktopBar m={m} onExport={openExport} />
      ) : (
        <>
          <MobileRecorte summary={summary} activeCount={m.active} onOpen={() => setSheetOpen(true)} buttonRef={triggerRef} />
          <FilterSheet
            open={sheetOpen}
            onClose={() => setSheetOpen(false)}
            returnFocusRef={triggerRef}
            footer={
              <>
                <CopyLinkButton className="min-h-11 justify-center" />
                <button type="button" className="btn-ghost min-h-11 justify-center whitespace-nowrap" onClick={openExport}>
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
                <PeriodFields m={m} />
              </div>
              <div className="grid gap-1.5">
                <PlaceFields m={m} />
                <ExtraFields m={m} />
              </div>
              <div className="grid gap-2">
                {m.chips.length === 0 ? (
                  <p className="label">Recorte completo: todos os pedidos do período.</p>
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
        </>
      )}
      <ExportDialog open={exportOpen} onClose={() => setExportOpen(false)} />
    </div>
  );
}

export default island(FilterBarInner, 96);
