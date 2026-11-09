import { Check, Link2 } from "lucide-react";
import { EXPORT_ACTIONS, useCopyLink } from "@/lib/exportActions";
import { iconSwap, textSwap } from "../ui/swap";

/** Copia o link do recorte; o estado "copiado" dura FEEDBACK_MS (1,8 s), igual ao menu Compartilhar. */
export function CopyLinkButton({ className = "" }: { className?: string }) {
  const { copied, copy } = useCopyLink();

  return (
    <button type="button" onClick={copy} className={`btn-ghost whitespace-nowrap ${className}`}>
      <span className="grid place-items-center" aria-hidden>
        <Link2 className={iconSwap(!copied)} />
        <Check className={`text-good ${iconSwap(copied)}`} />
      </span>
      <span className="grid">
        <span className={textSwap(!copied)}>{EXPORT_ACTIONS.link.title}</span>
        <span className={textSwap(copied)}>{EXPORT_ACTIONS.link.copiedTitle}</span>
      </span>
    </button>
  );
}
