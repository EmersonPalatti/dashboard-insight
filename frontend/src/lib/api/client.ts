/**
 * Cliente HTTP tipado a partir de `schema.d.ts` (gerado do OpenAPI do FastAPI).
 * Se um schema Pydantic mudar, `npm run gen:api` + `astro check` quebram aqui.
 */
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type Filters = Schemas["Filters"];
export type Metrics = Schemas["Metrics"];
export type KpiResponse = Schemas["KpiResponse"];
export type Alert = Schemas["Alert"];
export type AlertsResponse = Schemas["AlertsResponse"];
export type BreakdownRow = Schemas["BreakdownRow"];
export type Dimension = Schemas["BreakdownResponse"]["by"];
export type Meta = Schemas["Meta"];
export type OrderRow = Schemas["OrderRow"];
export type ChatResponse = Schemas["ChatResponse"];
export type ChatTurn = Schemas["ChatTurn"];

type GetPaths = {
  [P in keyof paths]: paths[P] extends { get: { responses: { 200: { content: { "application/json": unknown } } } } }
    ? P
    : never;
}[keyof paths];

export type GetResponse<P extends GetPaths> = paths[P] extends {
  get: { responses: { 200: { content: { "application/json": infer R } } } };
}
  ? R
  : never;

type QueryValue = string | number | boolean | null | undefined | (string | number)[];
export type Query = Record<string, QueryValue>;

export const API_URL = (import.meta.env.PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export function toSearchParams(query: Query): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => params.append(key, String(v)));
    else params.set(key, String(value));
  }
  return params;
}

export function apiUrl(path: string, query: Query = {}): string {
  const qs = toSearchParams(query).toString();
  return `${API_URL}${path}${qs ? `?${qs}` : ""}`;
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* corpo não-JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export async function apiGet<P extends GetPaths>(path: P, query: Query = {}, signal?: AbortSignal) {
  return handle<GetResponse<P>>(await fetch(apiUrl(path, query), { signal }));
}

export async function askAgent(body: Schemas["ChatRequest"], signal?: AbortSignal): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/api/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  return handle<ChatResponse>(res);
}
