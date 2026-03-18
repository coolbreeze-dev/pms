export function formatCurrency(value: string | number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

export function formatPercent(value: string | number): string {
  const numeric = Number(value || 0);
  return `${numeric >= 0 ? "+" : ""}${numeric.toFixed(2)}%`;
}

export function formatDate(value?: string | null): string {
  if (!value) return "Never";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(
    new Date(value),
  );
}

export function numeric(value: string | number): number {
  return Number(value || 0);
}

export function formatNumber(value: string | number, digits = 2): string {
  return Number(value || 0).toFixed(digits);
}
