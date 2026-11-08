import { Check, Link2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { shareUrl } from "@/lib/filters";
import { iconSwap, textSwap } from "../ui/swap";

/** Copia o link do recorte. O estado "copiado" dura 1,8 s. */
export function CopyLinkButton({ className = "" }: { className?: string }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl());
      setCopied(true);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard negado: o link continua na barra de endereço */
    }
  };

  return (
    <button type="button" onClick={copy} className={`btn-ghost whitespace-nowrap ${className}`}>
      <span className="grid place-items-center" aria-hidden>
        <Link2 className={iconSwap(!copied)} />
        <Check className={`text-good ${iconSwap(copied)}`} />
      </span>
      <span className="grid">
        <span className={textSwap(!copied)}>Copiar link</span>
        <span className={textSwap(copied)}>Link copiado</span>
      </span>
    </button>
  );
}
