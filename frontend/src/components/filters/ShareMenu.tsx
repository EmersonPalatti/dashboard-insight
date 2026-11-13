import { Check, ChevronDown, ClipboardCopy, FileSpreadsheet, Link2, Printer, Share2 } from "lucide-react";
import { useEffect, useId, useRef, type KeyboardEvent } from "react";
import { EXPORT_ACTIONS, printAfterClose, useBriefingCopy, useCopyLink, useCsvDownload } from "@/lib/exportActions";
import { iconSwap } from "../ui/swap";
import { useDisclosure } from "./useDisclosure";

const itemClass =
  "flex w-full items-start gap-2.5 rounded-tick px-2.5 py-2 text-left transition-colors duration-(--duration-quick) hover:bg-sunken focus-visible:bg-sunken disabled:pointer-events-none disabled:opacity-50";

/** Itens navegáveis do menu, na ordem do DOM (botões habilitados e links). */
function menuItems(panel: HTMLElement | null): HTMLElement[] {
  if (!panel) return [];
  return Array.from(panel.querySelectorAll<HTMLElement>('[role="menuitem"]:not(:disabled)'));
}

function ItemText({ title, detail }: { title: string; detail: string }) {
  return (
    <span className="grid min-w-0 gap-0.5">
      <span className="text-body font-medium text-ink">{title}</span>
      <span className="text-aux text-muted">{detail}</span>
    </span>
  );
}

/**
 * "Compartilhar" no desktop: menu não modal ancorado no botão, com link, CSV,
 * briefing e PDF. Esc fecha e devolve o foco ao botão; clique fora ou Tab para fora também fecham.
 * Setas, Home e End percorrem os itens.
 */
export function ShareMenu() {
  const d = useDisclosure();
  const link = useCopyLink();
  const briefing = useBriefingCopy();
  const csv = useCsvDownload();
  const panelRef = useRef<HTMLDivElement>(null);
  const uid = useId();
  const panelId = `${uid}-menu`;

  // ao abrir, o foco vai para o primeiro item
  useEffect(() => {
    if (d.phase === "open") menuItems(panelRef.current)[0]?.focus();
  }, [d.phase]);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    d.onKeyDown(e); // Esc
    if (!d.isOpen || e.defaultPrevented) return;
    const list = menuItems(panelRef.current);
    const i = list.indexOf(document.activeElement as HTMLElement);
    const last = list.length - 1;
    const go = (n: number) => {
      e.preventDefault();
      list[n]?.focus();
    };
    switch (e.key) {
      case "ArrowDown":
        go(i < 0 || i === last ? 0 : i + 1);
        break;
      case "ArrowUp":
        go(i <= 0 ? last : i - 1);
        break;
      case "Home":
        go(0);
        break;
      case "End":
        go(last);
        break;
    }
  };

  // o aviso para leitores de tela segue o feedback visível
  const announce = csv.error
    ? csv.detail
    : briefing.state === "done"
      ? EXPORT_ACTIONS.briefing.doneTitle
      : link.copied
        ? EXPORT_ACTIONS.link.copiedTitle
        : "";

  return (
    <div ref={d.rootRef} className="relative flex min-w-0" onKeyDown={onKeyDown} onBlur={d.onBlur}>
      <button
        ref={d.buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={d.isOpen}
        aria-controls={panelId}
        onClick={d.toggle}
        className="btn-ghost h-8 whitespace-nowrap"
      >
        <Share2 className="size-3.5" aria-hidden />
        Compartilhar
        <ChevronDown
          className={`size-3.5 text-muted transition-[rotate] duration-(--duration-fast) ease-(--ease-smooth-out) motion-reduce:transition-none ${
            d.isOpen ? "rotate-180" : ""
          }`}
          aria-hidden
        />
      </button>
      <span className="sr-only" aria-live="polite">
        {announce}
      </span>
      <div
        ref={panelRef}
        id={panelId}
        role="menu"
        aria-label="Compartilhar recorte"
        {...d.panelProps}
        className={`recorte-popover absolute top-full right-0 z-30 mt-1.5 w-80 max-w-[calc(100vw-2rem)] rounded-card border border-rule bg-surface p-1.5 ${
          d.phase === "closed" ? "hidden" : ""
        }`}
      >
        <div role="none" className="grid gap-0.5">
          <button type="button" role="menuitem" className={itemClass} onClick={link.copy}>
            <span className="mt-0.5 grid size-4 shrink-0 place-items-center" aria-hidden>
              <Link2 className={`text-series ${iconSwap(!link.copied, "size-4")}`} />
              <Check className={`text-good ${iconSwap(link.copied, "size-4")}`} />
            </span>
            <ItemText
              title={link.copied ? EXPORT_ACTIONS.link.copiedTitle : EXPORT_ACTIONS.link.title}
              detail={EXPORT_ACTIONS.link.detail}
            />
          </button>

          <button
            type="button"
            role="menuitem"
            className={itemClass}
            disabled={csv.busy || csv.blocked}
            onClick={async () => {
              const ok = await csv.download();
              if (ok) d.dismiss(true);
            }}
          >
            <FileSpreadsheet className="mt-0.5 size-4 shrink-0 text-series" aria-hidden />
            <ItemText title={csv.title} detail={csv.detail} />
          </button>

          <button type="button" role="menuitem" className={itemClass} onClick={briefing.copy} disabled={briefing.state === "busy"}>
            <span className="mt-0.5 grid size-4 shrink-0 place-items-center" aria-hidden>
              <ClipboardCopy className={`text-series ${iconSwap(briefing.state !== "done", "size-4")}`} />
              <Check className={`text-good ${iconSwap(briefing.state === "done", "size-4")}`} />
            </span>
            <ItemText title={briefing.title} detail={EXPORT_ACTIONS.briefing.detail} />
          </button>

          <button
            type="button"
            role="menuitem"
            className={itemClass}
            onClick={() => {
              d.dismiss(true);
              printAfterClose();
            }}
          >
            <Printer className="mt-0.5 size-4 shrink-0 text-series" aria-hidden />
            <ItemText title={EXPORT_ACTIONS.print.title} detail={EXPORT_ACTIONS.print.detail} />
          </button>
        </div>
      </div>
    </div>
  );
}
