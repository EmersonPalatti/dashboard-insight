const nf0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const brlCompact = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  maximumFractionDigits: 1,
});
const intCompact = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });

type N = number | null | undefined;
const nil = (v: N): v is null | undefined => v === null || v === undefined || Number.isNaN(v);

export const fmt = {
  int: (v: N) => (nil(v) ? "—" : nf0.format(v)),
  intCompact: (v: N) => (nil(v) ? "—" : intCompact.format(v)),
  brl: (v: N) => (nil(v) ? "—" : brl.format(v)),
  brlCompact: (v: N) => (nil(v) ? "—" : brlCompact.format(v)),
  pct: (v: N) => (nil(v) ? "—" : `${nf1.format(v * 100)}%`),
  min: (v: N) => (nil(v) ? "—" : `${nf1.format(v)} min`),
  km: (v: N) => (nil(v) ? "—" : `${nf1.format(v)} km`),
  num1: (v: N) => (nil(v) ? "—" : nf1.format(v)),
  date: (iso: string | null | undefined) => {
    if (!iso) return "—";
    const [y, m, d] = iso.slice(0, 10).split("-");
    return `${d}/${m}/${y}`;
  },
  dateTime: (iso: string) =>
    new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }),
};

export const LABELS: Record<string, string> = {
  food: "Food",
  good: "Goods",
  marketplace: "Marketplace",
  own: "Canal próprio",
  moto: "Moto",
  bike: "Bike",
  freelance: "Freelancer",
  operator: "Operador logístico",
  delivered: "Entregue",
  canceled: "Cancelado",
};

export const label = (v: string | number | null | undefined) =>
  v === null || v === undefined ? "—" : (LABELS[String(v)] ?? String(v).replaceAll("_", " "));

export const WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

/**
 * Período do recorte inteiro fora da base (datas ISO; limites vêm de /api/meta).
 * Devolve a frase com o intervalo da base, ou null quando o período a toca ou os limites ainda não chegaram.
 */
export function outsideBaseNote(
  period: { start: string | null; end: string | null },
  base: { min_date?: string; max_date?: string } | undefined,
): string | null {
  if (!base?.min_date || !base.max_date) return null;
  const after = period.start !== null && period.start > base.max_date;
  const before = period.end !== null && period.end < base.min_date;
  if (!after && !before) return null;
  return `A base vai de ${fmt.date(base.min_date)} a ${fmt.date(base.max_date)}; o período escolhido fica fora dela.`;
}
