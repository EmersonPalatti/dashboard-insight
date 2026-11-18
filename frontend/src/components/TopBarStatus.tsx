/** Tema claro/escuro + estado da API (o plano grátis do Render "dorme" e leva ~40 s para acordar). */
import { useStore } from "@nanostores/react";
import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { island, useApiHealth } from "@/lib/query";
import { $theme, setTheme, syncTheme } from "@/lib/theme";

/* Troca sol/lua: os dois ícones ocupam a mesma célula; o que sai vai a 0.8, girado para um lado, e o que entra vem do outro. */
const ICON_BASE =
  "col-start-1 row-start-1 size-4 transition-[opacity,scale,rotate,filter] duration-(--duration-fast) ease-(--ease-in-out) motion-reduce:transition-none";
const ICON_SHOWN = "opacity-100 scale-100 rotate-0 blur-none";
const ICON_HIDDEN = "opacity-0 scale-[0.8] blur-(--blur-small)";

function TopBarStatusInner() {
  const theme = useStore($theme);
  const [slow, setSlow] = useState(false);
  const health = useApiHealth();

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

  const dark = theme === "dark";

  return (
    <div className="flex items-center gap-2">
      {/* Uma só região viva: o texto troca dentro dela, então a leitura de tela anuncia uma vez. */}
      <span className="inline-flex items-center gap-1.5 text-aux text-on-wine" role="status">
        <span
          className={`size-2 rounded-full transition-colors duration-(--duration-fast) motion-reduce:transition-none ${
            status === "ok"
              ? "bg-shell-good"
              : status === "down"
                ? "bg-shell-crit"
                : "animate-pulse bg-shell-warn motion-reduce:animate-none"
          }`}
          aria-hidden
        />
        {/* key no status: cada mudança remonta o texto, que entra de baixo com desfoque. Abaixo de sm, "API no ar" fica só para o leitor de tela; estados de alerta seguem visíveis. */}
        {status === "ok" && <span className="sr-only sm:hidden">{text}</span>}
        <span
          key={status}
          className={`truncate transition-[opacity,translate,filter] duration-(--duration-quick) ease-(--ease-in-out) starting:translate-y-(--distance-micro) starting:opacity-0 starting:blur-(--blur-small) motion-reduce:transition-none lg:max-w-[12rem] xl:max-w-none ${
            status === "ok" ? "hidden max-w-[7.5rem] sm:inline-block" : "inline-block max-w-[9.5rem]"
          }`}
        >
          {text}
        </span>
      </span>
      <button
        type="button"
        className="inline-flex size-10 items-center justify-center rounded-card text-on-wine transition-colors duration-(--duration-quick) hover:bg-wine-raised max-lg:-my-0.5 max-lg:size-11"
        onClick={() => setTheme(dark ? "light" : "dark")}
        aria-label={dark ? "Usar tema claro" : "Usar tema escuro"}
      >
        <span className="grid size-4 place-items-center" aria-hidden>
          <Sun className={`${ICON_BASE} ${dark ? ICON_SHOWN : `${ICON_HIDDEN} -rotate-45`}`} aria-hidden />
          <Moon className={`${ICON_BASE} ${dark ? `${ICON_HIDDEN} rotate-45` : ICON_SHOWN}`} aria-hidden />
        </span>
      </button>
    </div>
  );
}

function TopBarStatusFallback() {
  return (
    <div className="flex items-center gap-2" aria-hidden="true">
      <span className="inline-flex items-center gap-1.5 text-aux text-on-wine">
        <span className="size-2 rounded-full bg-shell-warn/40 animate-pulse motion-reduce:animate-none" />
        <span className="sr-only sm:not-sr-only sm:inline-block h-3.5 w-16 rounded-[4px] bg-on-wine/15 animate-pulse motion-reduce:animate-none" />
      </span>
      <div className="inline-flex size-10 rounded-card bg-on-wine/10 animate-pulse motion-reduce:animate-none max-lg:-my-0.5 max-lg:size-11" />
    </div>
  );
}

export default island(TopBarStatusInner, <TopBarStatusFallback />);
