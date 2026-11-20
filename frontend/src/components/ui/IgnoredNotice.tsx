import { useStore } from "@nanostores/react";
import { useState } from "react";
import { $ignored, ignoredMessage } from "@/lib/filters";

/** Avisa uma vez quais valores da URL não entraram no recorte. Some ao fechar. */
export function IgnoredNotice() {
  const items = useStore($ignored);
  const message = ignoredMessage(items);
  const [hidden, setHidden] = useState<string | null>(null);
  if (!message || hidden === message) return null;
  return (
    <div className="mb-2.5 flex items-start gap-3 rounded-card border border-rule bg-sunken px-3 py-2" role="status">
      <p className="min-w-0 flex-1 text-pretty text-aux text-ink">{message}</p>
      <button type="button" className="btn-ghost shrink-0 px-2 py-1 text-aux" onClick={() => setHidden(message)}>
        Fechar aviso
      </button>
    </div>
  );
}
