import { useEffect, useLayoutEffect, useRef, type ReactNode } from "react";
import { prefersReducedMotion } from "@/lib/media";
import type { PresetOption } from "./useFilterModel";

interface Rect {
  x: number;
  w: number;
}

/** Põe o indicador num transform sem animar: desliga a transição, fixa o estilo e religa. */
function snap(el: HTMLElement, transform: string) {
  el.style.transition = "none";
  el.style.transform = transform;
  void el.offsetWidth; // força o estilo antes de religar a transição
  el.style.transition = "";
}

interface Props {
  presets: PresetOption[];
  /** Preset ativo, ou "dates" quando o período é personalizado. */
  activeId?: string;
  onSelect: (preset: PresetOption) => void;
  /** Último segmento (Datas): um botão com data-preset="dates" e a classe de presetClass. */
  extra?: ReactNode;
}

/** Classe de um segmento; exportada para o botão Datas, que vive fora deste componente. */
export const presetClass = (on: boolean) =>
  `relative flex items-center gap-1.5 rounded-t-[4px] border-b-2 border-transparent px-2.5 text-[0.88rem] whitespace-nowrap transition-colors duration-(--duration-quick) disabled:cursor-not-allowed disabled:opacity-50 ${
    on ? "text-ink" : "text-muted hover:text-ink disabled:hover:text-muted"
  }`;

/**
 * Presets de período com indicador deslizante (tabs sliding). Só transform e
 * opacity animam: a largura do indicador é fixada na medição, e a troca de
 * posição vai do retângulo antigo ao novo por translate + scaleX (origem à esquerda).
 */
export function PeriodPresets({ presets, activeId, onSelect, extra }: Props) {
  const groupRef = useRef<HTMLDivElement>(null);
  const indicatorRef = useRef<HTMLSpanElement>(null);
  // último retângulo pintado: undefined = nunca medido; null = sem preset (datas personalizadas)
  const shownRef = useRef<Rect | null | undefined>(undefined);
  // o ResizeObserver lê o preset atual por ref: não é recriado a cada troca (o disparo inicial dele cortaria o deslize)
  const activeRef = useRef(activeId);

  // pelo retângulo e não por offsetLeft: o botão Datas fica dentro do popover, que é outro offsetParent
  const measure = (id: string | undefined): Rect | null => {
    const group = groupRef.current;
    const btn = id ? group?.querySelector<HTMLElement>(`[data-preset="${id}"]`) : null;
    if (!group || !btn) return null;
    const x = btn.getBoundingClientRect().left - group.getBoundingClientRect().left - group.clientLeft;
    return { x, w: btn.offsetWidth };
  };

  useLayoutEffect(() => {
    activeRef.current = activeId;
    const ind = indicatorRef.current;
    if (!ind) return;
    const next = measure(activeId);
    if (!next) {
      // sem preset (datas personalizadas): o indicador esmaece no lugar
      shownRef.current = null;
      ind.style.opacity = "0";
      return;
    }
    // grupo oculto (ex.: folha fechada) mede zero: espera o ResizeObserver medir de verdade
    if (next.w === 0) return;
    const prev = shownRef.current;
    shownRef.current = next;
    ind.style.width = `${next.w}px`;
    if (prev && !prefersReducedMotion()) {
      // desliza: começa no retângulo antigo (esticado até a largura nova) e chega ao novo
      snap(ind, `translateX(${prev.x}px) scaleX(${prev.w / next.w})`);
      ind.style.transform = `translateX(${next.x}px)`;
    } else {
      // primeira posição, volta de datas personalizadas (fade-in) ou movimento reduzido
      snap(ind, `translateX(${next.x}px)`);
    }
    ind.style.opacity = "1";
  }, [activeId]);

  // fonte carregando ou grupo voltando de display:none mudam as larguras: reposiciona sem animar
  useEffect(() => {
    const group = groupRef.current;
    if (!group || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => {
      const ind = indicatorRef.current;
      const next = measure(activeRef.current);
      if (!ind || !next || next.w === 0) return;
      shownRef.current = next;
      ind.style.width = `${next.w}px`;
      snap(ind, `translateX(${next.x}px)`);
      ind.style.opacity = "1";
    });
    ro.observe(group);
    return () => ro.disconnect();
  }, []);

  return (
    <div ref={groupRef} className="relative inline-flex h-10 items-stretch rounded-card border border-rule bg-sunken p-0.5 max-lg:h-11">
      <span
        ref={indicatorRef}
        aria-hidden
        className="pointer-events-none absolute top-0.5 bottom-0.5 left-0 origin-left rounded-t-[4px] border-b-2 border-ink bg-surface opacity-0 transition-[opacity,transform] duration-(--duration-fast) ease-(--ease-smooth-out) motion-reduce:transition-none"
      />
      {presets.map((p) => {
        const on = p.id === activeId;
        return (
          <button
            key={p.id}
            type="button"
            data-preset={p.id}
            aria-label={p.label}
            aria-pressed={on}
            disabled={p.disabled}
            onClick={() => onSelect(p)}
            className={presetClass(on)}
          >
            {p.short}
          </button>
        );
      })}
      {extra}
    </div>
  );
}
