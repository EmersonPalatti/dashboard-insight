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

/** Envolve um componente de ilha com o Provider compartilhado e um skeleton de altura fixa. */
export function island<P extends object>(Component: ComponentType<P>, fallbackHeight = 320) {
  const fallback = <div className="skeleton w-full" style={{ height: fallbackHeight }} aria-hidden />;
  const Wrapped = (props: P) => (
    <Island fallback={fallback}>
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
  return useQuery<GetResponse<P>>({
    queryKey: [path, filters, extra],
    queryFn: ({ signal }) => apiGet(path, { ...toQuery(filters), ...extra }, signal),
    enabled: ready && enabled,
    placeholderData: keepPreviousData,
  });
}

export function useMeta() {
  return useQuery({
    queryKey: ["/api/meta"],
    queryFn: ({ signal }) => apiGet("/api/meta", {}, signal),
    staleTime: Infinity,
  });
}
