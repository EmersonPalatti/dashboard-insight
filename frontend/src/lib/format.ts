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
  dateTime: (() => {
    const opts = { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" } as const;
    const utc = new Intl.DateTimeFormat("pt-BR", { ...opts, timeZone: "UTC" });
    const sp = new Intl.DateTimeFormat("pt-BR", { ...opts, timeZone: "America/Sao_Paulo" });
    return (iso: string) => {
      if (!iso) return "—";
      if (/(?:Z|[+-]\d{2}:?\d{2})$/i.test(iso)) {
        const d = new Date(iso);
        return Number.isNaN(d.getTime()) ? "—" : sp.format(d);
      }
      const normalized = iso.includes("T") ? iso : iso.replace(" ", "T");
      const d = new Date(`${normalized}Z`);
      return Number.isNaN(d.getTime()) ? "—" : utc.format(d);
    };
  })(),
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
  online: "Online",
  debit: "Débito",
  credit: "Crédito",
  money: "Dinheiro",
  voucher: "Voucher",
  meal_benefit: "Vale-refeição",
  payment_link: "Link de pagamento",
  store_direct_payment: "Pagamento na loja",
  debit_store: "Débito na loja",
  credit_store: "Crédito na loja",
  voucher_store: "Voucher na loja",
  installment_credit_store: "Crédito parcelado na loja",
  voucher_dc: "Voucher DC",
  voucher_ol: "Voucher OL",
  bank_transfer_dc: "Transferência bancária",
};

export const label = (v: string | number | null | undefined) =>
  v === null || v === undefined ? "—" : (LABELS[String(v)] ?? String(v).replaceAll("_", " "));

export const WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

type ScopeOption = { value: string | number; label: string; parent?: string | number | null };

/**
 * Período ou combinação de filtros do recorte inteiro fora da base (limites vêm de /api/meta).
 * Devolve a frase diagnóstica pt-BR, ou null quando não há incompatibilidade óbvia.
 */
export function outsideBaseNote(
  period: { start: string | null; end: string | null; city?: string[]; hub?: number[]; store?: number[] },
  base: { min_date?: string; max_date?: string; hubs?: ScopeOption[]; stores?: ScopeOption[] } | undefined,
): string | null {
  if (base?.min_date && base.max_date) {
    const after = period.start !== null && period.start > base.max_date;
    const before = period.end !== null && period.end < base.min_date;
    if (after || before) {
      return `A base vai de ${fmt.date(base.min_date)} a ${fmt.date(base.max_date)}; o período escolhido fica fora dela.`;
    }
  }
  if (base?.hubs && period.hub?.length && period.city?.length) {
    const citySet = new Set(period.city);
    const selectedHubs = period.hub
      .map((id) => base.hubs!.find((h) => Number(h.value) === id))
      .filter((h): h is ScopeOption => Boolean(h));
    const mismatch = selectedHubs.find((h) => h.parent != null && !citySet.has(String(h.parent)));
    if (mismatch && selectedHubs.every((h) => h.parent != null && !citySet.has(String(h.parent)))) {
      return `O hub ${mismatch.label} fica em ${mismatch.parent}, fora de ${period.city.join(", ")}. Tire um dos filtros.`;
    }
  }
  if (base?.stores && period.store?.length && period.hub?.length) {
    const hubSet = new Set(period.hub);
    const selectedStores = period.store
      .map((id) => base.stores!.find((s) => Number(s.value) === id))
      .filter((s): s is ScopeOption => Boolean(s));
    const mismatch = selectedStores.find((s) => s.parent != null && !hubSet.has(Number(s.parent)));
    if (mismatch && selectedStores.every((s) => s.parent != null && !hubSet.has(Number(s.parent)))) {
      return `A loja ${mismatch.label} pertence a outro hub fora do filtro atual. Tire um dos filtros.`;
    }
  }
  if (base?.stores && base?.hubs && period.store?.length && period.city?.length) {
    const citySet = new Set(period.city);
    const selectedStores = period.store
      .map((id) => base.stores!.find((s) => Number(s.value) === id))
      .filter((s): s is ScopeOption => Boolean(s));
    const storeHubs = selectedStores.map((s) => ({
      store: s,
      hub: s.parent != null ? base.hubs!.find((h) => Number(h.value) === Number(s.parent)) : undefined,
    }));
    const mismatch = storeHubs.find((x) => x.hub?.parent != null && !citySet.has(String(x.hub.parent)));
    if (mismatch && storeHubs.every((x) => x.hub?.parent != null && !citySet.has(String(x.hub.parent)))) {
      return `A loja ${mismatch.store.label} fica em ${mismatch.hub!.parent}, fora de ${period.city.join(", ")}. Tire um dos filtros.`;
    }
  }
  return null;
}
