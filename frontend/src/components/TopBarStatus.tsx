/** Tema claro/escuro + estado da API (o plano grátis do Render "dorme" e leva ~40 s para acordar). */
import { useStore } from "@nanostores/react";
import { useQuery } from "@tanstack/react-query";
import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api/client";
import { island } from "@/lib/query";
import { $theme, setTheme, syncTheme } from "@/lib/theme";

function TopBarStatusInner() {
  const theme = useStore($theme);
  const [slow, setSlow] = useState(false);
  const health = useQuery({
    queryKey: ["/api/health"],
    queryFn: ({ signal }) => apiGet("/api/health", {}, signal),
    retry: 8,
    retryDelay: 4000,
    staleTime: 60_000,
  });

  useEffect(syncTheme, []);
  useEffect(() => {
    if (health.isSuccess) return setSlow(false);
    const t = setTimeout(() => setSlow(true), 2500);
    return () => clearTimeout(t);
  }, [health.isSuccess]);

  const status = health.isSuccess ? "ok" : health.isError ? "down" : slow ? "waking" : "checking";
  const text = {
    ok: "API no ar",
    checking: "Conectando…",
    waking: "Acordando o servidor (até ~40 s)…",
    down: "API fora do ar",
  }[status];

  return (
    <div className="flex items-center gap-2">
      <span className="inline-flex items-center gap-1.5 text-[0.8rem] text-muted" role="status">
        <span
          className={`size-2 rounded-full ${
            status === "ok" ? "bg-good" : status === "down" ? "bg-chili" : "animate-pulse bg-amber"
          }`}
          aria-hidden
        />
        {text}
      </span>
      <button
        type="button"
        className="btn-ghost px-2"
        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        aria-label={theme === "dark" ? "Usar tema claro" : "Usar tema escuro"}
      >
        {theme === "dark" ? <Sun className="size-4" aria-hidden /> : <Moon className="size-4" aria-hidden />}
      </button>
    </div>
  );
}

export default island(TopBarStatusInner, 32);
