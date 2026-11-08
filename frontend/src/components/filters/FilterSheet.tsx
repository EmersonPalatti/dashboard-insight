import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode, type RefObject } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
  /** Botão que abriu a folha: recebe o foco quando ela fecha. */
  returnFocusRef: RefObject<HTMLButtonElement | null>;
  children: ReactNode;
  footer: ReactNode;
}

/**
 * Folha de recorte no mobile: native <dialog> com showModal (foco preso, Esc,
 * ::backdrop). A animação de saída é CSS (allow-discrete em .recorte-sheet), então
 * não há timer: o dialog segue na top layer até a saída terminar.
 * Esc, o X, o clique no véu e o botão "Ver resultado" passam todos por onClose.
 */
export function FilterSheet({ open, onClose, returnFocusRef, children, footer }: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  // o evento close chega do Esc (nativo) e do nosso fechamento: devolve o foco nos dois casos
  const handleClose = () => {
    onClose();
    returnFocusRef.current?.focus({ preventScroll: true });
  };

  return (
    <dialog
      ref={ref}
      aria-labelledby="recorte-sheet-title"
      onClose={handleClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className="recorte-sheet fixed inset-x-0 top-auto bottom-0 m-0 w-full max-w-full rounded-t-card border-t border-rule bg-surface p-0 text-ink"
    >
      <div className="flex max-h-[85dvh] flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-rule px-4 py-3">
          <h2 id="recorte-sheet-title" className="section-title">
            Recorte
          </h2>
          <button type="button" onClick={onClose} aria-label="Fechar" className="btn-ghost min-h-11 min-w-11 justify-center px-2">
            <X className="size-4" aria-hidden />
          </button>
        </header>
        {/* o corpo rola; o rodapé fica fora da rolagem, então sempre visível */}
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4">{children}</div>
        <footer className="grid grid-cols-2 gap-2 border-t border-rule bg-surface px-4 py-3">{footer}</footer>
      </div>
    </dialog>
  );
}
