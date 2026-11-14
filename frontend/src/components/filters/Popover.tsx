import type { ReactNode } from "react";
import { useDisclosure } from "./useDisclosure";

interface Props {
  /** id do painel (aria-controls do botão). */
  id: string;
  /** Conteúdo do botão. */
  trigger: ReactNode;
  triggerClassName: string;
  /** Atributos extras do botão, ex.: data-preset e aria-checked do período. */
  triggerProps?: Record<string, string | number | boolean | undefined>;
  /** Lado em que o painel se ancora; a escala parte do mesmo canto. */
  align?: "left" | "right";
  panelClassName?: string;
  /** Classes da raiz (botão + painel), ex.: o segmento Datas crescer na folha. */
  rootClassName?: string;
  children: ReactNode;
}

/**
 * Popover não modal ancorado no botão (Mais filtros, Datas). Esc fecha e devolve
 * o foco ao botão; clique fora ou Tab para fora também fecham. Sem overflow
 * hidden, então os seletores e calendários de dentro não são cortados.
 */
export function Popover({
  id,
  trigger,
  triggerClassName,
  triggerProps,
  align = "right",
  panelClassName = "w-72",
  rootClassName = "",
  children,
}: Props) {
  const d = useDisclosure();

  return (
    <div ref={d.rootRef} className={`relative flex min-w-0 ${rootClassName}`} onKeyDown={d.onKeyDown} onBlur={d.onBlur}>
      <button
        ref={d.buttonRef}
        type="button"
        aria-expanded={d.isOpen}
        aria-controls={id}
        onClick={d.toggle}
        className={triggerClassName}
        {...triggerProps}
      >
        {trigger}
      </button>
      <div
        id={id}
        data-align={align}
        {...d.panelProps}
        className={`recorte-popover absolute top-full z-30 mt-1.5 max-w-[calc(100vw-2rem)] rounded-card border border-ink bg-surface p-3 ${
          align === "left" ? "left-0" : "right-0"
        } ${panelClassName} ${d.phase === "closed" ? "hidden" : ""}`}
      >
        {children}
      </div>
    </div>
  );
}
