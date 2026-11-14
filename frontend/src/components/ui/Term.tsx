import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

/**
 * Termo com definição. O botão abre no clique, no Enter e no toque.
 * O texto sai num portal para não ser cortado por overflow dos cartões.
 */
export function Term({ term, definition, ariaLabel }: { term: string; definition: string; ariaLabel?: string }) {
  const btn = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLSpanElement>(null);
  const panelId = useId();
  const [open, setOpen] = useState(false);
  const [box, setBox] = useState<{ top: number; left: number } | null>(null);

  useLayoutEffect(() => {
    if (!open || !btn.current) return;
    const place = () => {
      const rect = btn.current?.getBoundingClientRect();
      if (!rect) return;
      const width = 240;
      setBox({
        top: rect.bottom + 4,
        left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)),
      });
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    const onPointer = (event: PointerEvent) => {
      const target = event.target as Node;
      if (btn.current?.contains(target) || panel.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  return (
    <>
      <button
        ref={btn}
        type="button"
        className="hit-target underline decoration-dotted decoration-ink underline-offset-[3px]"
        aria-label={ariaLabel}
        aria-expanded={open}
        aria-describedby={open ? panelId : undefined}
        onClick={() => setOpen((value) => !value)}
      >
        {term}
      </button>
      {open &&
        box &&
        createPortal(
          <span
            ref={panel}
            id={panelId}
            role="tooltip"
            style={{ top: box.top, left: box.left }}
            className="fixed z-40 w-60 rounded-card border border-ink bg-surface p-2 text-left text-meta font-normal tracking-normal text-ink normal-case"
          >
            {definition}
          </span>,
          document.body,
        )}
    </>
  );
}
