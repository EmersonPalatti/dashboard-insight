import { Check, Link2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { shareUrl } from "@/lib/filters";

/** Ícone: cross-fade com escala e blur (icon swap), os dois ícones dividem uma célula. */
const iconState = (on: boolean) =>
  `col-start-1 row-start-1 size-3.5 transition-[opacity,scale,filter] duration-(--duration-fast) ease-(--ease-in-out) motion-reduce:transition-none ${
    on ? "opacity-100 scale-100" : "opacity-0 scale-[0.25] blur-(--blur-small)"
  }`;

/** Rótulo: sobe e some (text swap). Os dois rótulos dividem uma célula: o botão tem a largura do maior e não pula. */
const labelState = (on: boolean) =>
  `col-start-1 row-start-1 transition-[opacity,translate,visibility] duration-(--duration-quick) ease-(--ease-smooth-out) motion-reduce:transition-none ${
    on ? "" : "invisible translate-y-(--distance-micro) opacity-0"
  }`;

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
        <Link2 className={iconState(!copied)} />
        <Check className={`text-good ${iconState(copied)}`} />
      </span>
      <span className="grid">
        <span className={labelState(!copied)}>Copiar link</span>
        <span className={labelState(copied)}>Link copiado</span>
      </span>
    </button>
  );
}
