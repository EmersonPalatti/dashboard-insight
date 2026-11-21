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
