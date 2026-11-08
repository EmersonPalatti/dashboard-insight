import { useStore } from "@nanostores/react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, ClipboardCopy, FileSpreadsheet, Printer, X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { copyBriefing, csvHref } from "@/lib/exportActions";
import { $filters } from "@/lib/filters";

interface Props {
  open: boolean;
  onClose: () => void;
}

/**
 * Fechamento do modal: a transição dura --duration-quick (150ms); se transitionend não
 * disparar, o dialog fecha neste tempo (um pouco de folga além dos 150ms).
 */
const CLOSE_FALLBACK_MS = 170;
/** A impressão espera o modal fechar (--duration-quick). */
const PRINT_DELAY_MS = 250;

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
  const filters = useStore($filters);
  const qc = useQueryClient();
  const [copied, setCopied] = useState<"idle" | "busy" | "done" | "error">("idle");

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

  const onCopyBriefing = async () => {
    setCopied("busy");
    try {
      await copyBriefing(qc, filters);
      setCopied("done");
    } catch {
      setCopied("error");
    }
  };

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
            <h2 className="text-lg font-semibold">Exportar recorte</h2>
            <p className="label">Tudo segue os filtros ativos agora.</p>
          </div>
          <button type="button" onClick={onClose} className="btn-ghost px-2 max-lg:min-h-11 max-lg:min-w-11 max-lg:justify-center" aria-label="Fechar">
            <X className="size-4" aria-hidden />
          </button>
        </div>
        <div className="grid gap-2">
          <a className="btn-ghost justify-start py-3" href={csvHref(filters)} download>
            <FileSpreadsheet className="size-4 text-series" aria-hidden />
            <span>
              <span className="block font-semibold">Pedidos em CSV</span>
              <span className="label">Uma linha por pedido, com o recorte atual.</span>
            </span>
          </a>
          <button type="button" className="btn-ghost justify-start py-3 text-left" onClick={onCopyBriefing} disabled={copied === "busy"}>
            {copied === "done" ? <Check className="size-4 text-good" aria-hidden /> : <ClipboardCopy className="size-4 text-series" aria-hidden />}
            <span>
              <span className="block font-semibold">
                {copied === "done" ? "Briefing copiado" : copied === "error" ? "Não deu para copiar" : "Copiar briefing (Markdown)"}
              </span>
              <span className="label">KPIs, alertas e ações, pronto para colar no Slack ou num doc.</span>
            </span>
          </button>
          <button
            type="button"
            className="btn-ghost justify-start py-3 text-left"
            onClick={() => {
              onClose();
              setTimeout(() => window.print(), PRINT_DELAY_MS);
            }}
          >
            <Printer className="size-4 text-series" aria-hidden />
            <span>
              <span className="block font-semibold">PDF da tela</span>
              <span className="label">Abre a impressão do navegador; escolha "Salvar como PDF".</span>
            </span>
          </button>
        </div>
      </div>
    </dialog>
  );
}
