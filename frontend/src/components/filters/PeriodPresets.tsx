import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
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
  /** Nome acessível quando não há rótulo visível (barra). Na folha, o id do título. */
  labelId?: string;
  /**
   * Último segmento (Datas). Recebe tabIndex e checked para entrar no mesmo
   * radiogroup: um só tab stop, setas movem o foco.
   */
  extra?: (state: { tabIndex: number; checked: boolean }) => ReactNode;
}

/** Classe de um segmento; exportada para o botão Datas, que vive fora deste componente. */
export const presetClass = (on: boolean) =>
  `relative z-[1] flex h-full min-w-0 items-center gap-1.5 rounded-t-[4px] border-b-2 border-transparent px-2.5 text-aux font-medium whitespace-nowrap transition-colors duration-(--duration-quick) max-lg:min-h-11 max-lg:flex-1 max-lg:justify-center max-lg:px-1.5 disabled:cursor-not-allowed disabled:opacity-50 ${
    on ? "text-ink" : "text-muted hover:text-ink disabled:hover:text-muted"
  }`;

/**
 * Presets de período com indicador deslizante (tabs sliding). Só transform e
 * opacity animam: a largura do indicador é fixada na medição, e a troca de
 * posição vai do retângulo antigo ao novo por translate + scaleX (origem à esquerda).
 */
export function PeriodPresets({ presets, activeId, onSelect, labelId, extra }: Props) {
  const groupRef = useRef<HTMLDivElement>(null);
  const indicatorRef = useRef<HTMLSpanElement>(null);
  // Foco que as setas moveram. Sem isso, o tab stop volta ao preset aplicado.
  const [rovingId, setRovingId] = useState<string | null>(null);
  const tabId = rovingId ?? activeId ?? presets.find((p) => !p.disabled)?.id;
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

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    if (!target.closest("[data-preset]")) return;
    const buttons = [...(groupRef.current?.querySelectorAll<HTMLButtonElement>("[data-preset]") ?? [])].filter((b) => !b.disabled);
    const i = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (i < 0) return;
    const last = buttons.length - 1;
    let next = i;
    switch (e.key) {
      case "ArrowRight":
      case "ArrowDown":
        next = i === last ? 0 : i + 1;
        break;
      case "ArrowLeft":
      case "ArrowUp":
        next = i === 0 ? last : i - 1;
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = last;
        break;
      default:
        return;
    }
    e.preventDefault();
    const btn = buttons[next];
    const id = btn.dataset.preset ?? null;
    const preset = presets.find((p) => p.id === id);
    // Datas não aplica um intervalo nem abre sozinho com seta: Enter/Space abre o calendário (botão nativo).
    if (preset) onSelect(preset);
    setRovingId(id);
    btn.focus();
  };

  return (
    <div
      ref={groupRef}
      role="radiogroup"
      aria-label={labelId ? undefined : "Período"}
      aria-labelledby={labelId}
      aria-orientation="horizontal"
      onKeyDown={onKeyDown}
      onFocus={(e) => {
        const btn = (e.target as HTMLElement).closest<HTMLElement>("[data-preset]");
        if (!btn || !groupRef.current?.contains(btn)) return;
        if (btn.dataset.preset) setRovingId(btn.dataset.preset);
      }}
      onBlur={(e) => {
        const next = e.relatedTarget as Node | null;
        if (!next || !e.currentTarget.contains(next)) setRovingId(null);
      }}
      className="relative inline-flex h-10 max-w-full items-stretch rounded-card border border-rule bg-sunken p-0.5 max-lg:h-auto max-lg:w-full max-lg:min-w-0 max-lg:p-0"
    >
      <span
        ref={indicatorRef}
        aria-hidden
        className="pointer-events-none absolute top-0.5 bottom-0.5 left-0 origin-left rounded-t-[4px] border-b-2 border-ink bg-surface opacity-0 transition-[opacity,transform] duration-(--duration-fast) ease-(--ease-smooth-out) max-lg:top-0 max-lg:bottom-0 motion-reduce:transition-none"
      />
      {presets.map((p) => {
        const on = p.id === activeId;
        return (
          <button
            key={p.id}
            type="button"
            role="radio"
            data-preset={p.id}
            aria-label={p.label}
            aria-checked={on}
            tabIndex={p.id === tabId ? 0 : -1}
            disabled={p.disabled}
            onClick={() => onSelect(p)}
            className={presetClass(on)}
          >
            <span className="min-w-0 truncate">{p.short}</span>
          </button>
        );
      })}
      {extra?.({ tabIndex: tabId === "dates" ? 0 : -1, checked: activeId === "dates" })}
    </div>
  );
}
