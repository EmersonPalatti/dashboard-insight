/**
 * TanStack Query compartilhado entre ilhas: um único QueryClient no módulo,
 * e cada ilha monta seu próprio Provider apontando para ele. Duas ilhas que
 * pedem `/api/kpis` com o mesmo recorte reaproveitam a mesma requisição.
 */
import { keepPreviousData, QueryCache, QueryClient, QueryClientProvider, queryOptions, useQuery } from "@tanstack/react-query";
import { useStore } from "@nanostores/react";
import { atom } from "nanostores";
import { useEffect, useRef, useState, type ComponentType, type ReactNode } from "react";
import { ApiError, apiGet, type GetResponse, type Query } from "./api/client";
import { $filters, $ready, applyDimensionCatalog, catalogFromMeta, initFilters, toQuery, type Recorte } from "./filters";
import { ErrorBoundary, IslandErrorFallback, type IslandErrorVariant } from "@/components/ui/ErrorBoundary";

const HEALTH_KEY = ["/api/health"] as const;
const HEALTH_REFRESH_MS = 60_000;
const HEALTH_CHECK_TICK_MS = 15_000;
const HEALTH_CHECK_COOLDOWN_MS = 10_000;

let healthSucceededOnce = false;
let healthMonitorStarted = false;
let lastHealthCheck = 0;

/** Reconfere o health sem cancelar uma checagem em andamento (várias ilhas, uma requisição). */
function refreshHealth() {
  void queryClient.refetchQueries({ queryKey: HEALTH_KEY, type: "active" }, { cancelRefetch: false });
}

function isNonRetryableClientError(err: unknown): boolean {
  return err instanceof ApiError && err.status >= 400 && err.status < 500 && err.status !== 429;
}

function isServerUnavailableError(err: unknown): boolean {
  if (err instanceof DOMException && err.name === "AbortError") return false;
  if (err instanceof ApiError) {
    return err.status === 502 || err.status === 503 || err.status === 504;
  }
  return err instanceof Error;
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (err, query) => {
      if (query.queryKey[0] === HEALTH_KEY[0] || !isServerUnavailableError(err)) return;
      // Painel falhou por rede ou 502/503/504: o cabeçalho confere o servidor na hora (no máximo a cada 10 s).
      const now = Date.now();
      if (now - lastHealthCheck < HEALTH_CHECK_COOLDOWN_MS) return;
      lastHealthCheck = now;
      refreshHealth();
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 5 * 60_000,
      gcTime: 15 * 60_000,
      retry: (count, err) => {
        if (isNonRetryableClientError(err)) return false;
        return count < 2;
      },
      retryDelay: (n) => Math.min(1500 * 2 ** n, 8000),
      refetchOnWindowFocus: false,
    },
  },
});

/**
 * Um só sinal de saúde, o mesmo do cabeçalho. Oito tentativas a cada 4 s
 * cobrem o cold start (~40 s) sem cada painel repetir essa espera; depois que
 * respondeu uma vez, revalidações usam 2 tentativas curtas e atualizam a cada 60 s visível.
 */
const HEALTH_QUERY = queryOptions({
  queryKey: HEALTH_KEY,
  queryFn: async ({ signal }) => {
    const res = await apiGet("/api/health", {}, signal);
    healthSucceededOnce = true;
    return res;
  },
  retry: (count, err) => (isNonRetryableClientError(err) ? false : count < (healthSucceededOnce ? 2 : 8)),
  retryDelay: () => (healthSucceededOnce ? 2000 : 4000),
  staleTime: HEALTH_REFRESH_MS,
  refetchOnWindowFocus: (q) => (q.state.status === "error" ? "always" : true),
  refetchOnReconnect: "always",
});

/**
 * Um relógio só para a página, não um `refetchInterval` por observador: cada ilha que lê o
 * health teria o próprio timer e o servidor levaria uma checagem por ilha a cada minuto.
 * Só com a aba visível e depois do primeiro sucesso (o cold start é das tentativas acima).
 */
function startHealthMonitor() {
  if (healthMonitorStarted || typeof window === "undefined") return;
  healthMonitorStarted = true;
  window.setInterval(() => {
    if (document.visibilityState !== "visible") return;
    const state = queryClient.getQueryState(HEALTH_KEY);
    if (!state || state.status !== "success") return;
    if (Date.now() - state.dataUpdatedAt < HEALTH_REFRESH_MS) return;
    refreshHealth();
  }, HEALTH_CHECK_TICK_MS);
}

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

/** Verdadeiro depois que `/api/meta` valida os IDs e nomes do recorte pela primeira vez. */
export const $catalogReady = atom(false);

function hasDimensionFilters(f: Recorte): boolean {
  return (
    f.city.length > 0 ||
    f.hub.length > 0 ||
    f.store.length > 0 ||
    f.segment.length > 0 ||
    f.channel_type.length > 0 ||
    f.modal.length > 0
  );
}

const META_QUERY = queryOptions({
  queryKey: ["/api/meta"] as const,
  queryFn: async ({ signal }) => {
    const meta = await apiGet("/api/meta", {}, signal);
    applyDimensionCatalog(catalogFromMeta(meta));
    $catalogReady.set(true);
    return meta;
  },
  staleTime: Infinity,
});

/**
 * O SSR do Astro não conhece a URL nem o cache do cliente. Para não haver
 * hydration mismatch, a ilha renderiza o mesmo skeleton no servidor e no
 * primeiro render do navegador, e só depois monta o conteúdo real.
 */
export function Island({
  children,
  fallback,
  reservedHeight,
}: {
  children: ReactNode;
  fallback?: ReactNode;
  reservedHeight?: number;
}) {
  const [mounted, setMounted] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [layout, setLayout] = useState<{ height: number; variant: IslandErrorVariant }>({
    height: reservedHeight ?? 0,
    variant: "block",
  });
  const markerRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    initFilters();
    startHealthMonitor();
    const host = markerRef.current?.parentElement;
    let height = reservedHeight ?? 0;
    let variant: IslandErrorVariant = "block";
    if (host) {
      if (host.closest("header")) {
        variant = "header";
      } else if (host.closest("section.panel-frame")) {
        variant = "panel";
      }
      if (reservedHeight === undefined) {
        let minTop = Infinity;
        let maxBottom = -Infinity;
        for (const el of Array.from(host.children)) {
          if (el === markerRef.current) continue;
          const rect = el.getBoundingClientRect();
          if (rect.height <= 0) continue;
          if (rect.top < minTop) minTop = rect.top;
          if (rect.bottom > maxBottom) maxBottom = rect.bottom;
        }
        if (maxBottom > minTop) height = Math.round(maxBottom - minTop);
      }
      if (variant === "block" && height > 0 && height < 100) {
        variant = "compact";
      }
    }
    setLayout({ height, variant });
    setMounted(true);
  }, [reservedHeight]);

  return (
    <QueryClientProvider client={queryClient}>
      {mounted ? (
        <ErrorBoundary
          key={retryCount}
          fallback={(reset, error) => (
            <IslandErrorFallback
              error={error}
              minHeight={layout.height}
              variant={layout.variant}
              onReset={() => {
                setRetryCount((c) => c + 1);
                reset();
              }}
            />
          )}
        >
          {children}
        </ErrorBoundary>
      ) : (
        <>
          <span ref={markerRef} hidden aria-hidden />
          {fallback}
        </>
      )}
    </QueryClientProvider>
  );
}

/**
 * Envolve um componente de ilha com o Provider compartilhado e o fallback do SSR.
 * `fallback` é a altura de um skeleton simples, ou o próprio nó (ex.: `panelFallback(340)`,
 * ou um skeleton com classes por breakpoint), para a troca skeleton → conteúdo não empurrar o layout.
 */
export function island<P extends object>(Component: ComponentType<P>, fallback: number | ReactNode = 320) {
  const reservedHeight = typeof fallback === "number" ? fallback : undefined;
  const node =
    typeof fallback === "number" ? <div className="skeleton w-full" style={{ height: fallback }} aria-hidden /> : fallback;
  const Wrapped = (props: P) => (
    <Island fallback={node} reservedHeight={reservedHeight}>
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
 * Quando a URL traz dimensões (cidade, hub, loja…), espera `/api/meta` validar os IDs antes de disparar.
 */
export function useRecorteQuery<P extends ApiPath>(path: P, extra: Query = {}, enabled = true) {
  const filters = useStore($filters);
  const ready = useStore($ready);
  const catalogReady = useStore($catalogReady);
  const gate = useApiGate();
  const needsCatalog = hasDimensionFilters(filters);
  const metaQuery = useQuery({
    ...META_QUERY,
    enabled: ready && enabled && gate.up && needsCatalog && !catalogReady,
  });
  const catalogOk = !needsCatalog || catalogReady || metaQuery.isError;
  const query = useQuery<GetResponse<P>>({
    queryKey: [path, filters, extra],
    queryFn: ({ signal }) => apiGet(path, { ...toQuery(filters), ...extra }, signal),
    enabled: ready && enabled && gate.up && catalogOk,
    placeholderData: keepPreviousData,
  });
  return gated(gate, query);
}

export function useMeta() {
  const gate = useApiGate();
  const query = useQuery({
    ...META_QUERY,
    enabled: gate.up,
  });
  return gated(gate, query);
}
