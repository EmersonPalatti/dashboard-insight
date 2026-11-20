import { Component, type ErrorInfo, type ReactNode } from "react";
import { TriangleAlert } from "lucide-react";

export interface ErrorBoundaryProps {
  fallback?: (reset: () => void, error: Error) => ReactNode;
  resetKey?: unknown;
  onError?: (error: Error, info: ErrorInfo) => void;
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Limite de erro de cada ilha (montado por `island()` em lib/query.tsx): uma falha de render
 * ou de chunk lazy troca só aquele bloco por um aviso com "Tentar de novo", sem derrubar a página.
 * `resetKey` diferente limpa o erro; `fallback` recebe `reset` para tentar de novo.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: unknown): ErrorBoundaryState {
    return { error: error instanceof Error ? error : new Error(String(error)) };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info);
    this.props.onError?.(error, info);
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    if (this.state.error !== null && !Object.is(prevProps.resetKey, this.props.resetKey)) {
      this.setState({ error: null });
    }
  }

  reset = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (error) {
      if (this.props.fallback) return this.props.fallback(this.reset, error);
      return <IslandErrorFallback error={error} onReset={this.reset} />;
    }
    return this.props.children;
  }
}

export type IslandErrorVariant = "panel" | "header" | "compact" | "block";

export function IslandErrorFallback({
  error,
  onReset,
  minHeight = 0,
  variant = "block",
}: {
  error: Error;
  onReset: () => void;
  minHeight?: number;
  variant?: IslandErrorVariant;
}) {
  if (variant === "header") {
    return (
      <div role="alert" className="inline-flex items-center gap-2 text-aux text-on-wine">
        <span>Erro no status.</span>
        <button
          type="button"
          onClick={onReset}
          className="rounded-card border border-on-wine/30 px-2 py-1 text-meta font-medium text-on-wine transition-colors duration-(--duration-quick) hover:bg-wine-raised"
        >
          Tentar de novo
        </button>
      </div>
    );
  }

  if (variant === "compact") {
    return (
      <div
        role="alert"
        className="flex w-full flex-wrap items-center justify-between gap-2 rounded-card border border-rule bg-surface px-3 py-1.5 text-aux text-ink"
        style={minHeight > 0 ? { minHeight } : undefined}
      >
        <span className="inline-flex items-center gap-1.5">
          <TriangleAlert className="size-4 shrink-0 text-ink" aria-hidden />
          <span>Algo falhou ao exibir este bloco.</span>
        </span>
        <button type="button" className="btn-ghost h-8 px-2.5 text-aux" onClick={onReset}>
          Tentar de novo
        </button>
      </div>
    );
  }

  const detail = error.message.trim();
  const wrapperClass =
    variant === "panel"
      ? "panel-body flex flex-col items-center justify-center gap-2 px-4 text-center"
      : "tile flex w-full flex-col items-center justify-center gap-2 px-4 py-4 text-center";

  return (
    <div role="alert" className={wrapperClass} style={minHeight > 0 ? { minHeight } : undefined}>
      <TriangleAlert className="size-5 text-ink" aria-hidden />
      <p className="max-w-md text-pretty text-aux text-ink">Algo falhou ao exibir este bloco.</p>
      <button type="button" className="btn-ghost" onClick={onReset}>
        Tentar de novo
      </button>
      {detail && (
        <details className="max-w-md text-left">
          <summary className="cursor-pointer text-meta text-muted">Detalhe técnico</summary>
          <p className="mt-1 text-pretty text-meta break-all text-muted">{detail}</p>
        </details>
      )}
    </div>
  );
}
