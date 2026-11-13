import { Check, ClipboardCopy, FileSpreadsheet, Printer, X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef } from "react";
import { EXPORT_ACTIONS, printAfterClose, useBriefingCopy, useCsvDownload } from "@/lib/exportActions";

interface Props {
  open: boolean;
  onClose: () => void;
}

/**
 * Fechamento do modal: a transição dura --duration-quick (150ms); se transitionend não
 * disparar, o dialog fecha neste tempo (um pouco de folga além dos 150ms).
 */
const CLOSE_FALLBACK_MS = 170;

/*
 * Movimento do modal: abre com transição de entrada (@starting-style via starting:) e
 * fecha com data-closing, que troca o estado final. Reduzido: só opacidade, rápido.
 */
const DIALOG_MOTION = [
  "transition-[opacity,scale] duration-(--duration-fast) ease-(--ease-smooth-out)",
  "starting:opacity-0 motion-safe:starting:scale-(--scale-large)",
  "data-[closing]:pointer-events-none data-[closing]:opacity-0 data-[closing]:duration-(--duration-quick) motion-safe:data-[closing]:scale-(--scale-large)",
  "motion-reduce:duration-(--duration-quick)",
  "backdrop:bg-[color-mix(in_srgb,var(--ink)_40%,transparent)] backdrop:transition-opacity backdrop:duration-(--duration-fast) backdrop:ease-(--ease-smooth-out)",
  "starting:backdrop:opacity-0 data-[closing]:backdrop:opacity-0 data-[closing]:backdrop:duration-(--duration-quick)",
  "motion-reduce:backdrop:duration-(--duration-quick)",
].join(" ");

export function ExportDialog({ open, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  // Fechamento em curso: função que cancela o timer e o listener; null quando o modal não está fechando.
  const stopClosing = useRef<(() => void) | null>(null);
  const briefing = useBriefingCopy();
  const csv = useCsvDownload();

  /**
   * Fecha com animação: marca data-closing, espera o fim da transição (ou o fallback) e só
   * então chama dialog.close(), que dispara o evento close e, com ele, onClose.
   */
  const beginClose = () => {
    const dialog = ref.current;
    if (!dialog?.open || stopClosing.current) return;
    dialog.setAttribute("data-closing", "");
    const finish = () => {
      stop();
      dialog.close();
      dialog.removeAttribute("data-closing");
    };
    const onEnd = (e: TransitionEvent) => {
      // ignora transições de filhos e do ::backdrop; só o próprio dialog conta
      if (e.target === dialog && !e.pseudoElement) finish();
    };
    const timer = window.setTimeout(finish, CLOSE_FALLBACK_MS);
    const stop = () => {
      window.clearTimeout(timer);
      dialog.removeEventListener("transitionend", onEnd);
      stopClosing.current = null;
    };
    dialog.addEventListener("transitionend", onEnd);
    stopClosing.current = stop;
  };

  /** Reabrir durante o fechamento: cancela o timer e volta ao estado aberto. */
  const cancelClose = () => {
    stopClosing.current?.();
    ref.current?.removeAttribute("data-closing");
  };

  // Layout effect: data-closing entra antes da pintura, então o fechamento começa no mesmo quadro.
  useLayoutEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open) {
      cancelClose();
      if (!dialog.open) dialog.showModal();
    } else if (dialog.open) {
      beginClose();
    }
  }, [open]);

  // Desmontar no meio do fechamento limpa timer e listener.
  useEffect(() => () => stopClosing.current?.(), []);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      // Esc: o navegador fecharia na hora; impede, anima o fechamento e o evento close chama onClose.
      onCancel={(e) => {
        e.preventDefault();
        beginClose();
      }}
      onClick={(e) => e.target === ref.current && onClose()}
      className={`m-auto w-[min(32rem,calc(100vw-2rem))] rounded-card border border-rule bg-surface p-0 text-ink ${DIALOG_MOTION}`}
    >
      <div className="p-5">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="section-title">Exportar recorte</h2>
            <p className="label">Tudo segue os filtros ativos agora.</p>
          </div>
          <button type="button" onClick={onClose} className="btn-ghost px-2 max-lg:min-h-11 max-lg:min-w-11 max-lg:justify-center" aria-label="Fechar">
            <X className="size-4" aria-hidden />
          </button>
        </div>
        <div className="grid gap-2">
          <button type="button" className="btn-ghost justify-start py-3 text-left" onClick={() => void csv.download()} disabled={csv.busy || csv.blocked}>
            <FileSpreadsheet className="size-4 text-series" aria-hidden />
            <span>
              <span className="block font-semibold">{csv.title}</span>
              <span className="label">{csv.detail}</span>
            </span>
          </button>
          <button type="button" className="btn-ghost justify-start py-3 text-left" onClick={briefing.copy} disabled={briefing.state === "busy"}>
            {briefing.state === "done" ? <Check className="size-4 text-good" aria-hidden /> : <ClipboardCopy className="size-4 text-series" aria-hidden />}
            <span>
              <span className="block font-semibold">{briefing.title}</span>
              <span className="label">{EXPORT_ACTIONS.briefing.detail}</span>
            </span>
          </button>
          <button
            type="button"
            className="btn-ghost justify-start py-3 text-left"
            onClick={() => {
              onClose();
              printAfterClose();
            }}
          >
            <Printer className="size-4 text-series" aria-hidden />
            <span>
              <span className="block font-semibold">{EXPORT_ACTIONS.print.title}</span>
              <span className="label">{EXPORT_ACTIONS.print.detail}</span>
            </span>
          </button>
        </div>
      </div>
    </dialog>
  );
}
