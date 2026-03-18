import { startTransition, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArcElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from "chart.js";
import { Doughnut, Line } from "react-chartjs-2";

import { api } from "../../api/client";
import type { AccountCategory, Period } from "../../api/types";
import { SummaryCards } from "../../components/SummaryCards";
import { formatCurrency, formatDate, formatNumber, formatPercent, numeric } from "../../lib/format";

ChartJS.register(ArcElement, CategoryScale, Filler, Legend, LineElement, LinearScale, PointElement, Tooltip);

const categories: AccountCategory[] = ["brokerage", "retirement", "india", "all"];
const periods: Period[] = ["1d", "1w", "1m", "3m", "6m", "1y", "ytd", "all"];

export function DashboardPage() {
  const currentYear = new Date().getFullYear();
  const [category, setCategory] = useState<AccountCategory>("brokerage");
  const [period, setPeriod] = useState<Period>("6m");
  const [benchmarkVisibility, setBenchmarkVisibility] = useState<Record<string, boolean>>({});

  const portfolioQuery = useQuery({
    queryKey: ["portfolio", category],
    queryFn: () => api.getPortfolio(category),
  });
  const performanceQuery = useQuery({
    queryKey: ["performance", category, period],
    queryFn: () => api.getPerformance(category, period),
  });
  const analyticsQuery = useQuery({
    queryKey: ["analytics", category],
    queryFn: () => api.getAnalytics(category),
  });
  const categoryPerformanceQuery = useQuery({
    queryKey: ["category-performance", period],
    queryFn: () => api.getCategoryPerformance(period),
  });
  const investmentSummaryQuery = useQuery({
    queryKey: ["investment-summary", category, currentYear],
    queryFn: () => api.getInvestmentSummary(category, currentYear),
  });

  useEffect(() => {
    const benchmarkNames = Object.keys(performanceQuery.data?.points[0]?.benchmarks ?? {});
    if (!benchmarkNames.length) return;
    setBenchmarkVisibility((current) => {
      const next = Object.fromEntries(
        benchmarkNames.map((name) => [name, current[name] ?? name !== "FTSE 100"]),
      );
      const keysChanged =
        benchmarkNames.length !== Object.keys(current).length ||
        benchmarkNames.some((name) => !(name in current));
      return keysChanged ? next : current;
    });
  }, [performanceQuery.data]);

  const performancePoints = performanceQuery.data?.points ?? [];
  const allocationSlices = portfolioQuery.data?.allocation.slice(0, 10) ?? [];
  const sectorSlices = analyticsQuery.data?.sector_allocation.slice(0, 6) ?? [];

  const performanceData = useMemo(() => {
    const benchmarkNames = Object.keys(performancePoints[0]?.benchmarks ?? {});
    const palette = ["#ff7f50", "#0b7fab", "#1f9f6f", "#9166ff", "#d14d72"];
    return {
      labels: performancePoints.map((point) => formatDate(point.date)),
      datasets: [
        {
          label: "Portfolio",
          data: performancePoints.map((point) => numeric(point.percent_change)),
          borderColor: "#0b7fab",
          backgroundColor: "rgba(11, 127, 171, 0.15)",
          fill: true,
          tension: 0.25,
        },
        ...benchmarkNames
          .filter((name) => benchmarkVisibility[name])
          .map((name, index) => ({
            label: name,
            data: performancePoints.map((point) =>
              point.benchmarks[name] == null ? null : numeric(point.benchmarks[name]),
            ),
            borderColor: palette[index % palette.length],
            backgroundColor: "transparent",
            tension: 0.25,
            spanGaps: true,
          })),
      ],
    };
  }, [benchmarkVisibility, performancePoints]);

  const allocationData = useMemo(
    () => ({
      labels: allocationSlices.map((slice) => slice.ticker),
      datasets: [
        {
          data: allocationSlices.map((slice) => numeric(slice.value)),
          backgroundColor: [
            "#0b7fab",
            "#1f9f6f",
            "#ff7f50",
            "#ffcb77",
            "#7d8eff",
            "#e16f7c",
            "#7a9e9f",
            "#b8c480",
            "#485696",
            "#f6bd60",
          ],
          borderWidth: 0,
        },
      ],
    }),
    [allocationSlices],
  );

  const sectorData = useMemo(
    () => ({
      labels: sectorSlices.map((slice) => slice.label),
      datasets: [
        {
          data: sectorSlices.map((slice) => numeric(slice.value)),
          backgroundColor: ["#0b7fab", "#1f9f6f", "#ff7f50", "#ffcb77", "#7d8eff", "#e16f7c"],
          borderWidth: 0,
        },
      ],
    }),
    [sectorSlices],
  );

  if (
    portfolioQuery.isLoading ||
    performanceQuery.isLoading ||
    analyticsQuery.isLoading ||
    categoryPerformanceQuery.isLoading ||
    investmentSummaryQuery.isLoading
  ) {
    return <div className="panel">Loading the dashboard...</div>;
  }

  if (
    portfolioQuery.isError ||
    performanceQuery.isError ||
    analyticsQuery.isError ||
    categoryPerformanceQuery.isError ||
    investmentSummaryQuery.isError
  ) {
    return (
      <div className="panel panel--danger">
        {(
          portfolioQuery.error ||
          performanceQuery.error ||
          analyticsQuery.error ||
          categoryPerformanceQuery.error ||
          investmentSummaryQuery.error
        )?.message}
      </div>
    );
  }

  const summary = portfolioQuery.data!.summary;
  const analytics = analyticsQuery.data!;
  const categoryPerformance = categoryPerformanceQuery.data!;
  const investmentSummary = investmentSummaryQuery.data!;
  const quantstats = analytics.quantstats;
  const analyticsCards = [
    {
      label: "TWRR YTD",
      value: formatPercent(analytics.time_weighted_return_ytd),
      meta: "Flow-adjusted return",
    },
    {
      label: "TWRR 1Y",
      value: formatPercent(analytics.time_weighted_return_1y),
      meta: "Trailing 12 months",
    },
    {
      label: "Portfolio Yield",
      value: formatPercent(analytics.portfolio_yield_pct),
      meta: "Forward income yield",
    },
    {
      label: "Max Drawdown 1Y",
      value: formatPercent(analytics.max_drawdown_1y),
      meta: "Peak-to-trough move",
    },
    {
      label: "Top 3 Concentration",
      value: formatPercent(analytics.top_three_concentration_pct),
      meta: "Largest positions combined",
    },
    {
      label: "Net Investment YTD",
      value: formatCurrency(investmentSummary.net_investment),
      meta: `${currentYear} net cash flow`,
    },
  ];
  const categoryPulse = categoryPerformance.series.map((series) => ({
    category: series.category,
    latest: series.points.at(-1),
  }));
  const quantstatsCards = quantstats
    ? [
        {
          label: "Sharpe",
          value: formatNumber(quantstats.sharpe_ratio),
          meta: `${quantstats.trading_days} trading days`,
        },
        {
          label: "Sortino",
          value: formatNumber(quantstats.sortino_ratio),
          meta: "Downside-aware return",
        },
        {
          label: "CAGR",
          value: formatPercent(quantstats.cagr_pct),
          meta: `Trailing ${quantstats.period.toUpperCase()}`,
        },
        {
          label: "Volatility",
          value: formatPercent(quantstats.volatility_pct),
          meta: "Annualized daily-return vol",
        },
      ]
    : [];

  return (
    <div className="stack">
      <section className="hero panel">
        <div>
          <p className="eyebrow">Default view: Brokerage + 6M</p>
          <h2>See the whole household portfolio without brokerage hopping.</h2>
        </div>
        <p className="hero__meta">
          Last price refresh: {formatDate(portfolioQuery.data?.last_updated)}
          <br />
          {currentYear} contributions and rebalancing: {formatCurrency(investmentSummary.net_investment)}
        </p>
      </section>

      <section className="toolbar panel">
        <div className="pill-row">
          {categories.map((item) => (
            <button
              key={item}
              className={`pill${category === item ? " pill--active" : ""}`}
              onClick={() => startTransition(() => setCategory(item))}
            >
              {item}
            </button>
          ))}
        </div>
        <div className="pill-row">
          {periods.map((item) => (
            <button
              key={item}
              className={`pill${period === item ? " pill--active" : ""}`}
              onClick={() => startTransition(() => setPeriod(item))}
            >
              {item.toUpperCase()}
            </button>
          ))}
        </div>
      </section>

      <SummaryCards summary={summary} subtitle={`Category: ${category}`} />

      <section className="dashboard-grid">
        <article className="panel panel--chart">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Performance</p>
              <h3>Portfolio vs. benchmarks</h3>
            </div>
            <div className="benchmark-list">
              {Object.keys(benchmarkVisibility).map((name) => (
                <label key={name} className="benchmark-toggle">
                  <input
                    type="checkbox"
                    checked={benchmarkVisibility[name]}
                    onChange={() =>
                      setBenchmarkVisibility((current) => ({ ...current, [name]: !current[name] }))
                    }
                  />
                  {name}
                </label>
              ))}
            </div>
          </div>
          {performancePoints.length ? (
            <div className="chart-wrap">
              <Line
                key={`performance-${category}-${period}`}
                data={performanceData}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  interaction: {
                    mode: "index",
                    intersect: false,
                  },
                  plugins: { legend: { display: false } },
                  scales: {
                    x: {
                      ticks: {
                        autoSkip: true,
                        maxTicksLimit: 8,
                      },
                      grid: {
                        display: false,
                      },
                    },
                    y: {
                      ticks: {
                        callback: (value) => `${value}%`,
                      },
                    },
                  },
                }}
              />
            </div>
          ) : (
            <p className="empty-state">No performance data yet. Refresh prices to populate the chart.</p>
          )}
        </article>

        <article className="panel panel--chart">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Allocation</p>
              <h3>Top holdings by value</h3>
            </div>
          </div>
          {allocationSlices.length ? (
            <div className="chart-wrap">
              <Doughnut
                key={`allocation-${category}`}
                data={allocationData}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: { legend: { position: "bottom" } },
                }}
              />
            </div>
          ) : (
            <p className="empty-state">No holdings available for allocation yet.</p>
          )}
        </article>
      </section>

      <section className="dashboard-grid">
        <article className="panel">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Advanced analytics</p>
              <h3>Risk, income, and flow-adjusted return</h3>
            </div>
            <p className="metric-badge">Diversification {analytics.diversification_score}</p>
          </div>
          <div className="insight-grid">
            {analyticsCards.map((card) => (
              <article key={card.label} className="insight-card">
                <p>{card.label}</p>
                <strong>{card.value}</strong>
                <span>{card.meta}</span>
              </article>
            ))}
          </div>
          <div className="panel__subsection">
            <div className="panel__header">
              <div>
                <p className="eyebrow">Dividend outlook</p>
                <h3>Estimated annual income {formatCurrency(analytics.annual_dividend_income)}</h3>
              </div>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Income</th>
                  <th>Yield</th>
                  <th>Contribution</th>
                </tr>
              </thead>
              <tbody>
                {analytics.top_dividend_positions.map((item) => (
                  <tr key={item.ticker}>
                    <td>{item.ticker}</td>
                    <td>{formatCurrency(item.annual_income)}</td>
                    <td>{formatPercent(item.dividend_yield)}</td>
                    <td>{formatPercent(item.contribution_pct)}</td>
                  </tr>
                ))}
                {!analytics.top_dividend_positions.length ? (
                  <tr>
                    <td colSpan={4}>
                      <p className="empty-state">No dividend data available yet for this category.</p>
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
          <div className="panel__subsection">
            <div className="panel__header">
              <div>
                <p className="eyebrow">Benchmark spread</p>
                <h3>Relative edge over the past year</h3>
              </div>
            </div>
            <div className="exposure-list">
              {analytics.benchmark_spread_1y.map((item) => (
                <div key={item.label} className="exposure-row">
                  <div>
                    <strong>{item.label}</strong>
                    <p>
                      Portfolio {formatPercent(item.portfolio_return)} vs benchmark{" "}
                      {formatPercent(item.benchmark_return)}
                    </p>
                  </div>
                  <span className="metric-badge">{formatPercent(item.spread_pct)}</span>
                </div>
              ))}
              {!analytics.benchmark_spread_1y.length ? (
                <p className="empty-state">Benchmark spread data will appear after a full 1Y history refresh.</p>
              ) : null}
            </div>
          </div>
          <div className="panel__subsection">
            <div className="panel__header">
              <div>
                <p className="eyebrow">QuantStats-grade return profile</p>
                <h3>Daily return quality over the trailing year</h3>
              </div>
            </div>
            {quantstats ? (
              <div className="stack">
                <div className="insight-grid">
                  {quantstatsCards.map((card) => (
                    <article key={card.label} className="insight-card">
                      <p>{card.label}</p>
                      <strong>{card.value}</strong>
                      <span>{card.meta}</span>
                    </article>
                  ))}
                </div>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th>Value</th>
                      <th>Metric</th>
                      <th>Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Win rate</td>
                      <td>{formatPercent(quantstats.win_rate_pct)}</td>
                      <td>Calmar</td>
                      <td>{formatNumber(quantstats.calmar_ratio)}</td>
                    </tr>
                    <tr>
                      <td>Best day</td>
                      <td>{formatPercent(quantstats.best_day_pct)}</td>
                      <td>Worst day</td>
                      <td>{formatPercent(quantstats.worst_day_pct)}</td>
                    </tr>
                    <tr>
                      <td>Average day</td>
                      <td>{formatPercent(quantstats.avg_return_pct)}</td>
                      <td>Average win</td>
                      <td>{formatPercent(quantstats.avg_win_pct)}</td>
                    </tr>
                    <tr>
                      <td>Average loss</td>
                      <td>{formatPercent(quantstats.avg_loss_pct)}</td>
                      <td>Ulcer index</td>
                      <td>{formatNumber(quantstats.ulcer_index)}</td>
                    </tr>
                    <tr>
                      <td>VaR</td>
                      <td>{formatPercent(quantstats.value_at_risk_pct)}</td>
                      <td>CVaR</td>
                      <td>{formatPercent(quantstats.conditional_value_at_risk_pct)}</td>
                    </tr>
                    <tr>
                      <td>Payoff ratio</td>
                      <td>{formatNumber(quantstats.payoff_ratio)}</td>
                      <td>Profit factor</td>
                      <td>{formatNumber(quantstats.profit_factor)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="empty-state">
                QuantStats metrics will appear once the portfolio has enough daily history to evaluate.
              </p>
            )}
          </div>
        </article>

        <article className="panel panel--chart">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Exposure</p>
              <h3>Sector mix and index proxy view</h3>
            </div>
          </div>
          {sectorSlices.length ? (
            <div className="chart-wrap chart-wrap--compact">
              <Doughnut
                key={`sector-${category}`}
                data={sectorData}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: { legend: { position: "bottom" } },
                }}
              />
            </div>
          ) : (
            <p className="empty-state">No sector allocation available yet.</p>
          )}
          <div className="exposure-list">
            {analytics.index_exposure.map((exposure) => (
              <div key={exposure.label} className="exposure-row">
                <div>
                  <strong>{exposure.label}</strong>
                  <p>{formatCurrency(exposure.value)}</p>
                </div>
                <span className="metric-badge">{formatPercent(exposure.exposure_pct)}</span>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="dashboard-grid">
        <article className="panel">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Category pulse</p>
              <h3>{period.toUpperCase()} household sleeves at a glance</h3>
            </div>
          </div>
          <div className="insight-grid">
            {categoryPulse.map((item) => (
              <article key={item.category} className="insight-card">
                <p>{item.category}</p>
                <strong>{formatPercent(item.latest?.percent_change ?? 0)}</strong>
                <span>{formatCurrency(item.latest?.portfolio_value ?? 0)} current value</span>
              </article>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Top movers</p>
              <h3>Gainers and losers</h3>
            </div>
            <p className="metric-badge">{currentYear} flows {formatCurrency(investmentSummary.net_investment)}</p>
          </div>
          <div className="split-table">
            <div>
              <h4>Top gainers</h4>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th>Return</th>
                    <th>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {analytics.top_gainers.map((item) => (
                    <tr key={item.ticker}>
                      <td>{item.ticker}</td>
                      <td>{formatPercent(item.return_pct)}</td>
                      <td>{formatCurrency(item.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <h4>Top losers</h4>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th>Return</th>
                    <th>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {analytics.top_losers.map((item) => (
                    <tr key={item.ticker}>
                      <td>{item.ticker}</td>
                      <td>{formatPercent(item.return_pct)}</td>
                      <td>{formatCurrency(item.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </article>

        <article className="panel">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Accounts</p>
              <h3>Breakdown by account</h3>
            </div>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Account</th>
                <th>Category</th>
                <th>Value</th>
                <th>Return</th>
              </tr>
            </thead>
            <tbody>
              {portfolioQuery.data?.account_breakdown.map((account) => (
                <tr key={account.account_id}>
                  <td>{account.account_name}</td>
                  <td>{account.category}</td>
                  <td>{formatCurrency(account.value)}</td>
                  <td>{formatPercent(account.return_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
      </section>
    </div>
  );
}
