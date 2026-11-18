/**
 * TanStack Query compartilhado entre ilhas: um único QueryClient no módulo,
 * e cada ilha monta seu próprio Provider apontando para ele. Duas ilhas que
 * pedem `/api/kpis` com o mesmo recorte reaproveitam a mesma requisição.
 */
import { keepPreviousData, QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useStore } from "@nanostores/react";
import { useEffect, useState, type ComponentType, type ReactNode } from "react";
import { apiGet, type GetResponse, type Query } from "./api/client";
import { $filters, $ready, initFilters, toQuery } from "./filters";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60_000,
      gcTime: 15 * 60_000,
      retry: 2,
      retryDelay: (n) => Math.min(1500 * 2 ** n, 8000),
      refetchOnWindowFocus: false,
    },
  },
});

/**
 * Um só sinal de saúde, o mesmo do cabeçalho. Oito tentativas a cada 4 s
 * cobrem o cold start (~40 s) sem cada painel repetir essa espera.
 */
const HEALTH_QUERY = {
  queryKey: ["/api/health"] as const,
  queryFn: ({ signal }: { signal: AbortSignal }) => apiGet("/api/health", {}, signal),
  retry: 8,
  retryDelay: 4000,
  staleTime: 60_000,
};

export function useApiHealth() {
  return useQuery(HEALTH_QUERY);
}

/** `waking` enquanto o health não fechou; `down` só quando as tentativas acabaram. */
export function useApiGate() {
  const health = useApiHealth();
  const waking = !health.isSuccess && (health.isFetching || !health.isError);
  const down = health.isError && !health.isFetching;
  return { waking, down, up: health.isSuccess, error: health.error };
}

type GatedQuery = { isPending: boolean; error: unknown };

/** Enquanto o servidor não respondeu, a query fica parada e o painel mostra a espera, não o erro. */
export function gated<T extends GatedQuery>(gate: ReturnType<typeof useApiGate>, query: T) {
  return {
    ...query,
    waking: gate.waking,
    down: gate.down,
    isPending: gate.down ? false : gate.waking || query.isPending,
    error: gate.down ? (gate.error ?? query.error) : gate.waking ? null : query.error,
  };
}

/**
 * O SSR do Astro não conhece a URL nem o cache do cliente. Para não haver
 * hydration mismatch, a ilha renderiza o mesmo skeleton no servidor e no
 * primeiro render do navegador, e só depois monta o conteúdo real.
 */
export function Island({ children, fallback }: { children: ReactNode; fallback?: ReactNode }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    initFilters();
    setMounted(true);
  }, []);
  return <QueryClientProvider client={queryClient}>{mounted ? children : fallback}</QueryClientProvider>;
}

/**
 * Envolve um componente de ilha com o Provider compartilhado e o fallback do SSR.
 * `fallback` é a altura de um skeleton simples, ou o próprio nó (ex.: `panelFallback(340)`,
 * ou um skeleton com classes por breakpoint), para a troca skeleton → conteúdo não empurrar o layout.
 */
export function island<P extends object>(Component: ComponentType<P>, fallback: number | ReactNode = 320) {
  const node =
    typeof fallback === "number" ? <div className="skeleton w-full" style={{ height: fallback }} aria-hidden /> : fallback;
  const Wrapped = (props: P) => (
    <Island fallback={node}>
      <Component {...props} />
    </Island>
  );
  Wrapped.displayName = `Island(${Component.displayName ?? Component.name})`;
  return Wrapped;
}

type ApiPath = Parameters<typeof apiGet>[0];

/**
 * GET tipado com o recorte atual. A chave inclui o recorte, então mudar um
 * filtro dispara nova busca e o `signal` cancela a anterior (sem race condition).
 */
export function useRecorteQuery<P extends ApiPath>(path: P, extra: Query = {}, enabled = true) {
  const filters = useStore($filters);
  const ready = useStore($ready);
  const gate = useApiGate();
  const query = useQuery<GetResponse<P>>({
    queryKey: [path, filters, extra],
    queryFn: ({ signal }) => apiGet(path, { ...toQuery(filters), ...extra }, signal),
    enabled: ready && enabled && gate.up,
    placeholderData: keepPreviousData,
  });
  return gated(gate, query);
}

export function useMeta() {
  const gate = useApiGate();
  const query = useQuery({
    queryKey: ["/api/meta"],
    queryFn: ({ signal }) => apiGet("/api/meta", {}, signal),
    enabled: gate.up,
    staleTime: Infinity,
  });
  return gated(gate, query);
}
