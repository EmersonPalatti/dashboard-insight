import { useStore } from "@nanostores/react";
import { ArrowRight, Check, ClipboardCopy, FileSpreadsheet, MessageSquareText } from "lucide-react";
import { $railAgentComandas, askAgentAbout, openComandaCount } from "@/lib/agentBridge";
import { $evidence } from "@/lib/evidence";
import { EXPORT_ACTIONS, useBriefingCopy, useCsvDownload } from "@/lib/exportActions";
import { fmt } from "@/lib/format";
import { $recorteEmpty, requestNextComanda } from "@/lib/investigation";
import { island, useRecorteQuery } from "@/lib/query";
import { comandaQuestion } from "./AlertsPanel";
import { ErrorState } from "./ui/Panel";
import { iconSwap, textSwap } from "./ui/swap";

const HEADING_ID = "fechamento-title";

function OperationalCloseSkeleton({ status }: { status?: string }) {
  return (
    <section aria-labelledby={HEADING_ID} aria-hidden={!status} className="panel p-4">
      <h2 id={HEADING_ID} className="section-title text-balance">
        Fechamento do recorte
      </h2>
      {status ? (
        <p className="label mt-1 text-pretty" role="status">
          {status}
        </p>
      ) : (
        <div className="mt-1.5 flex h-4 items-center" aria-hidden="true">
          <div className="skeleton h-3.5 w-72 max-w-full" />
        </div>
      )}
      <div className="no-print mt-4 flex flex-wrap gap-2" aria-hidden="true">
        <div className="skeleton h-9 w-40 rounded-card max-lg:h-11" />
        <div className="skeleton h-9 w-36 rounded-card max-lg:h-11" />
        <div className="skeleton h-9 w-44 rounded-card max-lg:h-11" />
        <div className="skeleton h-9 w-36 rounded-card max-lg:h-11" />
      </div>
    </section>
  );
}

function OperationalCloseInner() {
  const { data, error, isPending, refetch, isPlaceholderData, waking, down } = useRecorteQuery("/api/alerts");
  const recorteEmpty = useStore($recorteEmpty);
  const railAgents = useStore($railAgentComandas);
  const focus = useStore($evidence);
  const briefing = useBriefingCopy();
  const csv = useCsvDownload();

  if (waking || isPending) {
    return <OperationalCloseSkeleton status={waking ? "Acordando o servidor (até ~40 s)…" : undefined} />;
  }

  if (error) {
    return (
      <section aria-labelledby={HEADING_ID} className="panel p-4">
        <h2 id={HEADING_ID} className="section-title text-balance">
          Fechamento do recorte
        </h2>
        <ErrorState error={error} onRetry={() => refetch()} what="o fechamento do recorte" down={down} />
      </section>
    );
  }

  if (recorteEmpty || data?.orders === 0) {
    return null;
  }

  const alerts = data?.alerts ?? [];
  const high = alerts.filter((a) => a.severity === "high").length;
  const medium = alerts.filter((a) => a.severity === "medium").length;
  const total = openComandaCount(alerts.length, railAgents.length);

  const countText = total === 1 ? "1 comanda aberta" : `${fmt.int(total)} comandas abertas`;
  const highText = high === 0 ? "nenhuma crítica" : high === 1 ? "1 crítica" : `${fmt.int(high)} críticas`;
  const mediumText = medium === 0 ? "" : ` · ${fmt.int(medium)} em atenção`;
  const agentSide = railAgents.length === 0 ? "" : railAgents.length === 1 ? "1 do agente" : `${fmt.int(railAgents.length)} do agente`;

  const statusLine =
    total === 0
      ? "Nenhuma comanda aberta neste recorte."
      : alerts.length > 0
        ? `${countText} · ${highText}${mediumText}${agentSide ? ` · ${agentSide}` : ""}`
        : `${countText} · ${agentSide}`;

  const nextLabel = total === 1 ? "Ir para a comanda" : "Próxima comanda";
  const agentQuestion = focus
    ? comandaQuestion(focus.title)
    : total > 0
      ? "Quais os alertas e o que fazer hoje?"
      : "O que merece atenção neste recorte hoje?";

  const csvArmed = csv.title === "Baixar mesmo assim";
  const announce = csv.error
    ? csv.detail
    : csvArmed
      ? csv.detail
      : briefing.state === "done"
        ? EXPORT_ACTIONS.briefing.doneTitle
        : briefing.state === "error"
          ? EXPORT_ACTIONS.briefing.errorTitle
          : "";

  return (
    <section
      aria-labelledby={HEADING_ID}
      className={`panel p-4 transition-opacity ${isPlaceholderData ? "opacity-60" : ""}`}
    >
      <div className="content-reveal">
        <h2 id={HEADING_ID} className="section-title text-balance">
          Fechamento do recorte
        </h2>
        <p className="mt-1 text-body text-pretty text-ink/85">{statusLine}</p>

        {focus && (
          <div className="mt-3">
            <p className="text-body font-semibold text-pretty text-ink">
              <span className="font-normal text-muted">Em foco:</span>{" "}
              <span className="tabular-nums">{focus.number}</span> · {focus.title}
            </p>
            {focus.action && (
              <div className="action-block mt-2 max-w-[72ch] rounded-card px-3.5 py-2.5">
                <p className="text-aux font-semibold opacity-70">Ação</p>
                <p className="mt-0.5 text-body leading-snug text-pretty">{focus.action}</p>
              </div>
            )}
          </div>
        )}

        <div className="no-print mt-4 flex flex-wrap items-center gap-2">
          {total > 0 && (
            <button
              type="button"
              className="btn-ink max-lg:min-h-11 lg:min-h-9"
              onClick={() => requestNextComanda()}
            >
              {nextLabel}
              <ArrowRight className="size-3.5 shrink-0" aria-hidden />
            </button>
          )}

          <button
            type="button"
            className="btn-ghost max-lg:min-h-11 lg:min-h-9"
            onClick={briefing.copy}
            disabled={briefing.state === "busy"}
          >
            <span className="grid size-3.5 shrink-0 place-items-center" aria-hidden>
              <ClipboardCopy className={iconSwap(briefing.state !== "done", "size-3.5")} />
              <Check className={`text-good ${iconSwap(briefing.state === "done", "size-3.5")}`} />
            </span>
            <span className="grid text-left">
              <span className={textSwap(briefing.state === "idle")}>Copiar briefing</span>
              <span className={textSwap(briefing.state === "busy")}>{EXPORT_ACTIONS.briefing.busyTitle}</span>
              <span className={textSwap(briefing.state === "done")}>{EXPORT_ACTIONS.briefing.doneTitle}</span>
              <span className={textSwap(briefing.state === "error")}>{EXPORT_ACTIONS.briefing.errorTitle}</span>
            </span>
          </button>

          <button
            type="button"
            className="btn-ghost max-lg:min-h-11 lg:min-h-9"
            onClick={() => askAgentAbout(agentQuestion)}
          >
            <MessageSquareText className="size-3.5 shrink-0" aria-hidden /> Perguntar ao agente
          </button>

          <button
            type="button"
            className="btn-ghost max-lg:min-h-11 lg:min-h-9"
            disabled={csv.busy || csv.blocked}
            title={csv.detail}
            onClick={() => void csv.download()}
          >
            <FileSpreadsheet className="size-3.5 shrink-0" aria-hidden /> {csv.title}
          </button>
        </div>

        {(csv.blocked || csv.error || csvArmed) && (
          <p className="no-print mt-2 text-aux text-pretty text-muted">{csv.detail}</p>
        )}

        <span className="sr-only" aria-live="polite">
          {announce}
        </span>
      </div>
    </section>
  );
}

export default island(OperationalCloseInner, <OperationalCloseSkeleton />);
