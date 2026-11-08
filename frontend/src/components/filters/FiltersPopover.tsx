import { SlidersHorizontal } from "lucide-react";
import type { ReactNode } from "react";
import { Popover } from "./Popover";

/** "Mais filtros" no desktop: Segmento, Canal e Modal num popover, com a contagem do que está ativo. */
export function FiltersPopover({ count, children }: { count: number; children: ReactNode }) {
  return (
    <Popover
      id="filtros-extra"
      triggerClassName={`btn-ghost h-10 whitespace-nowrap ${count > 0 ? "border-ink" : ""}`}
      trigger={
        <>
          <SlidersHorizontal className="size-3.5" aria-hidden />
          Mais filtros
          {count > 0 && <span className="tabular-nums text-muted">· {count}</span>}
        </>
      }
    >
      <div className="grid gap-2">{children}</div>
    </Popover>
  );
}
