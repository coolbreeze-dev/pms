import type { PortfolioSummary } from "../api/types";
import { formatCurrency, formatPercent } from "../lib/format";

interface SummaryCardsProps {
  summary: PortfolioSummary;
  subtitle?: string;
}

export function SummaryCards({ summary, subtitle }: SummaryCardsProps) {
  const cards = [
    { label: "Portfolio Value", value: formatCurrency(summary.total_value) },
    { label: "Gain / Loss", value: formatCurrency(summary.gain_loss) },
    { label: "Return", value: formatPercent(summary.return_pct) },
    { label: "Est. Dividends", value: formatCurrency(summary.estimated_dividends) },
  ];

  return (
    <section className="summary-grid">
      {cards.map((card) => (
        <article key={card.label} className="summary-card">
          <p>{card.label}</p>
          <strong>{card.value}</strong>
          {subtitle ? <span>{subtitle}</span> : null}
        </article>
      ))}
    </section>
  );
}

