import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
} from "chart.js";
import { Bar, Doughnut } from "react-chartjs-2";

import { api } from "../../api/client";
import type { AccountCategory, Transaction } from "../../api/types";
import { DeleteIcon, EditIcon, IconActionButton } from "../../components/IconActionButton";
import { formatCurrency, formatDate, formatNumber, formatPercent, numeric } from "../../lib/format";

ChartJS.register(ArcElement, BarElement, CategoryScale, Legend, LinearScale, Tooltip);

const transactionTypes = ["buy", "sell", "deposit", "withdrawal", "dividend"] as const;
const categories: AccountCategory[] = ["all", "brokerage", "retirement", "india"];
const currentYear = new Date().getFullYear();
const yearOptions = Array.from({ length: 5 }, (_, index) => currentYear - index);
const chartTextColor = "#d0c5af";
const chartGridColor = "rgba(77, 70, 53, 0.18)";

const transactionSchema = z.object({
  account_id: z.coerce.number().min(1),
  ticker: z.string().min(1),
  transaction_type: z.enum(transactionTypes),
  shares: z.coerce.number().min(0),
  price_per_share: z.coerce.number().min(0),
  total_amount: z.coerce.number().min(0),
  transaction_date: z.string().min(1),
  notes: z.string().optional(),
});

type TransactionFormValues = z.infer<typeof transactionSchema>;

const defaultValues: TransactionFormValues = {
  account_id: 0,
  ticker: "CASH",
  transaction_type: "buy",
  shares: 0,
  price_per_share: 0,
  total_amount: 0,
  transaction_date: new Date().toISOString().slice(0, 10),
  notes: "",
};

export function InvestmentsPage() {
  const queryClient = useQueryClient();
  const [category, setCategory] = useState<AccountCategory>("all");
  const [year, setYear] = useState(currentYear);
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null);

  const accountsQuery = useQuery({
    queryKey: ["accounts"],
    queryFn: api.listAccounts,
  });
  const transactionsQuery = useQuery({
    queryKey: ["transactions", category, year],
    queryFn: () => api.listTransactions({ category, year }),
  });
  const summaryQuery = useQuery({
    queryKey: ["investment-summary", category, year],
    queryFn: () => api.getInvestmentSummary(category, year),
  });
  const analyticsQuery = useQuery({
    queryKey: ["analytics", category],
    queryFn: () => api.getAnalytics(category),
  });

  const form = useForm<TransactionFormValues>({
    resolver: zodResolver(transactionSchema),
    defaultValues,
  });

  const createMutation = useMutation({
    mutationFn: api.createTransaction,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["investment-summary"] });
      form.reset(defaultValues);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Record<string, unknown> }) =>
      api.updateTransaction(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["investment-summary"] });
      setEditingTransaction(null);
      form.reset(defaultValues);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: api.deleteTransaction,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["investment-summary"] });
    },
  });

  function onSubmit(values: TransactionFormValues) {
    const payload = {
      ...values,
      ticker: values.ticker.toUpperCase(),
    };
    if (editingTransaction) {
      updateMutation.mutate({ id: editingTransaction.id, payload });
      return;
    }
    createMutation.mutate(payload);
  }

  function beginEdit(transaction: Transaction) {
    setEditingTransaction(transaction);
    form.reset({
      account_id: transaction.account_id,
      ticker: transaction.ticker,
      transaction_type: transaction.transaction_type as TransactionFormValues["transaction_type"],
      shares: numeric(transaction.shares),
      price_per_share: numeric(transaction.price_per_share),
      total_amount: numeric(transaction.total_amount),
      transaction_date: transaction.transaction_date,
      notes: transaction.notes ?? "",
    });
  }

  const summaryCards = useMemo(
    () =>
      summaryQuery.data
        ? [
            { label: "Net investment", value: formatCurrency(summaryQuery.data.net_investment) },
            { label: "Contributions", value: formatCurrency(summaryQuery.data.contributions) },
            { label: "Withdrawals", value: formatCurrency(summaryQuery.data.withdrawals) },
            { label: "Dividends", value: formatCurrency(summaryQuery.data.dividends) },
            { label: "Avg. monthly net", value: formatCurrency(summaryQuery.data.average_monthly_net) },
            {
              label: "Avg. monthly dividends",
              value: formatCurrency(summaryQuery.data.average_monthly_dividends),
            },
          ]
        : [],
    [summaryQuery.data],
  );

  const monthlyChartData = useMemo(
    () => ({
      labels: summaryQuery.data?.monthly.map((row) => row.month) ?? [],
      datasets: [
        {
          label: "Net investment",
          data: summaryQuery.data?.monthly.map((row) => numeric(row.net_investment)) ?? [],
          backgroundColor: "#f2ca50",
          borderRadius: 6,
        },
        {
          label: "Cumulative net",
          data: summaryQuery.data?.monthly.map((row) => numeric(row.cumulative_net_investment)) ?? [],
          backgroundColor: "#d4af37",
          borderRadius: 6,
        },
      ],
    }),
    [summaryQuery.data],
  );

  const typeBreakdownData = useMemo(
    () => ({
      labels: summaryQuery.data?.type_breakdown.map((item) => item.label) ?? [],
      datasets: [
        {
          data: summaryQuery.data?.type_breakdown.map((item) => numeric(item.amount)) ?? [],
          backgroundColor: ["#f2ca50", "#d4af37", "#ffbf00", "#858c72", "#b37a2e"],
          borderWidth: 0,
        },
      ],
    }),
    [summaryQuery.data],
  );

  if (accountsQuery.isLoading || transactionsQuery.isLoading || summaryQuery.isLoading || analyticsQuery.isLoading) {
    return <div className="panel">Loading investments...</div>;
  }

  if (accountsQuery.isError || transactionsQuery.isError || summaryQuery.isError || analyticsQuery.isError) {
    return (
      <div className="panel panel--danger">
        {(accountsQuery.error || transactionsQuery.error || summaryQuery.error || analyticsQuery.error)?.message}
      </div>
    );
  }

  const quantstats = analyticsQuery.data?.quantstats;

  return (
    <div className="stack">
      <section className="hero panel">
        <div>
          <p className="eyebrow">Investment tracking</p>
          <h2>Track contributions, withdrawals, trades, and dividends with real cash-flow context.</h2>
        </div>
        <p className="hero__meta">
          Net investment treats buys and deposits as inflows, and sells and withdrawals as outflows.
        </p>
      </section>

      <section className="toolbar panel">
        <div className="pill-row">
          {categories.map((item) => (
            <button
              key={item}
              className={`pill${category === item ? " pill--active" : ""}`}
              onClick={() => setCategory(item)}
            >
              {item}
            </button>
          ))}
        </div>
        <div className="panel__header">
          <div>
            <p className="status-line">Filter the summary and transaction list by category and year.</p>
          </div>
          <select
            className="search-input year-select"
            value={year}
            onChange={(event) => setYear(Number(event.target.value))}
          >
            {yearOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
      </section>

      <section className="summary-grid">
        {summaryCards.map((card) => (
          <article key={card.label} className="summary-card">
            <p>{card.label}</p>
            <strong>{card.value}</strong>
            <span>{summaryQuery.data?.transaction_count ?? 0} transactions</span>
          </article>
        ))}
      </section>

      <section className="panel">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Cadence</p>
            <h2>How steady the investing rhythm looks this year</h2>
          </div>
        </div>
        <div className="insight-grid">
          <article className="insight-card">
            <p>Active months</p>
            <strong>{summaryQuery.data?.active_months ?? 0}</strong>
            <span>Months with contributions, withdrawals, or dividends</span>
          </article>
          <article className="insight-card">
            <p>Best month</p>
            <strong>
              {summaryQuery.data?.best_month
                ? `${summaryQuery.data.best_month.month} ${formatCurrency(summaryQuery.data.best_month.amount)}`
                : "None"}
            </strong>
            <span>Highest net investment month</span>
          </article>
          <article className="insight-card">
            <p>Largest outflow</p>
            <strong>
              {summaryQuery.data?.largest_outflow_month
                ? `${summaryQuery.data.largest_outflow_month.month} ${formatCurrency(summaryQuery.data.largest_outflow_month.amount)}`
                : "None"}
            </strong>
            <span>Most negative net investment month</span>
          </article>
        </div>
      </section>

      <section className="dashboard-grid">
        <article className="panel panel--chart">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Cash flow trend</p>
              <h2>{year} monthly and cumulative net investment</h2>
            </div>
          </div>
          <div className="chart-wrap">
            <Bar
              data={monthlyChartData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: {
                    position: "bottom",
                    labels: {
                      color: chartTextColor,
                    },
                  },
                },
                scales: {
                  x: {
                    ticks: {
                      color: chartTextColor,
                    },
                    grid: {
                      display: false,
                    },
                  },
                  y: {
                    ticks: {
                      color: chartTextColor,
                    },
                    grid: {
                      color: chartGridColor,
                    },
                  },
                },
              }}
            />
          </div>
        </article>

        <article className="panel panel--chart">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Transaction mix</p>
              <h2>Which activity is driving the year</h2>
            </div>
          </div>
          {summaryQuery.data?.type_breakdown.length ? (
            <>
              <div className="chart-wrap chart-wrap--compact">
                <Doughnut
                  data={typeBreakdownData}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                      legend: {
                        position: "bottom",
                        labels: {
                          color: chartTextColor,
                        },
                      },
                    },
                  }}
                />
              </div>
              <div className="exposure-list">
                {summaryQuery.data.type_breakdown.map((item) => (
                  <div key={item.label} className="exposure-row">
                    <div>
                      <strong>{item.label}</strong>
                      <p>{item.count} entries</p>
                    </div>
                    <span className="metric-badge">{formatCurrency(item.amount)}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="empty-state">No transaction mix yet for the selected view.</p>
          )}
        </article>
      </section>

      <section className="panel">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Return quality</p>
            <h2>How this sleeve behaves once cash flows are stripped out</h2>
          </div>
        </div>
        {quantstats ? (
          <div className="insight-grid">
            <article className="insight-card">
              <p>Sharpe</p>
              <strong>{formatNumber(quantstats.sharpe_ratio)}</strong>
              <span>{quantstats.trading_days} trading days</span>
            </article>
            <article className="insight-card">
              <p>CAGR</p>
              <strong>{formatPercent(quantstats.cagr_pct)}</strong>
              <span>Trailing {quantstats.period.toUpperCase()} annualized</span>
            </article>
            <article className="insight-card">
              <p>Win rate</p>
              <strong>{formatPercent(quantstats.win_rate_pct)}</strong>
              <span>Positive daily sessions</span>
            </article>
            <article className="insight-card">
              <p>VaR / CVaR</p>
              <strong>
                {formatPercent(quantstats.value_at_risk_pct)} / {formatPercent(quantstats.conditional_value_at_risk_pct)}
              </strong>
              <span>Left-tail daily loss estimate</span>
            </article>
          </div>
        ) : (
          <p className="empty-state">Return quality metrics will appear once enough daily history is available.</p>
        )}
      </section>

      <section className="split-layout">
        <article className="panel">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Transaction entry</p>
              <h2>{editingTransaction ? "Edit transaction" : "Add transaction"}</h2>
            </div>
          </div>
          <form className="form-grid" onSubmit={form.handleSubmit(onSubmit)}>
            <label>
              Account
              <select {...form.register("account_id")}>
                <option value={0}>Select an account</option>
                {accountsQuery.data?.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Type
              <select {...form.register("transaction_type")}>
                {transactionTypes.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Ticker
              <input {...form.register("ticker")} />
            </label>
            <label>
              Date
              <input type="date" {...form.register("transaction_date")} />
            </label>
            <label>
              Shares
              <input type="number" step="0.0001" {...form.register("shares")} />
            </label>
            <label>
              Price per share
              <input type="number" step="0.01" {...form.register("price_per_share")} />
            </label>
            <label>
              Total amount
              <input type="number" step="0.01" {...form.register("total_amount")} />
            </label>
            <label className="form-grid__full">
              Notes
              <textarea rows={3} {...form.register("notes")} />
            </label>
            <div className="form-actions">
              <button className="button button--primary" type="submit">
                {editingTransaction ? "Save transaction" : "Create transaction"}
              </button>
              {editingTransaction ? (
                <button
                  className="button button--ghost"
                  type="button"
                  onClick={() => {
                    setEditingTransaction(null);
                    form.reset(defaultValues);
                  }}
                >
                  Cancel
                </button>
              ) : null}
            </div>
          </form>
        </article>

        <article className="panel">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Monthly view</p>
              <h2>{year} investment ladder</h2>
            </div>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Month</th>
                  <th>Contributions</th>
                  <th>Withdrawals</th>
                  <th>Dividends</th>
                  <th>Net</th>
                  <th>Cumulative</th>
                </tr>
              </thead>
              <tbody>
                {summaryQuery.data?.monthly.map((row) => (
                  <tr key={row.month}>
                    <td>{row.month}</td>
                    <td>{formatCurrency(row.contributions)}</td>
                    <td>{formatCurrency(row.withdrawals)}</td>
                    <td>{formatCurrency(row.dividends)}</td>
                    <td>{formatCurrency(row.net_investment)}</td>
                    <td>{formatCurrency(row.cumulative_net_investment)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>

      <section className="panel">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Transactions</p>
            <h2>{transactionsQuery.data?.length ?? 0} entries in the selected view</h2>
          </div>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Account</th>
                <th>Ticker</th>
                <th>Type</th>
                <th>Amount</th>
                <th>Notes</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {transactionsQuery.data?.map((transaction) => (
                <tr key={transaction.id}>
                  <td>{formatDate(transaction.transaction_date)}</td>
                  <td>{transaction.account_name}</td>
                  <td>{transaction.ticker}</td>
                  <td>{transaction.transaction_type}</td>
                  <td>{formatCurrency(transaction.total_amount)}</td>
                  <td>{transaction.notes || "—"}</td>
                  <td>
                    <div className="table-actions">
                      <IconActionButton
                        icon={<EditIcon />}
                        label={`Edit ${transaction.ticker} transaction`}
                        onClick={() => beginEdit(transaction)}
                      />
                      <IconActionButton
                        icon={<DeleteIcon />}
                        label={`Delete ${transaction.ticker} transaction`}
                        tone="danger"
                        onClick={() => deleteMutation.mutate(transaction.id)}
                      />
                    </div>
                  </td>
                </tr>
              ))}
              {!transactionsQuery.data?.length ? (
                <tr>
                  <td colSpan={7}>
                    <p className="empty-state">Add your first transaction to start tracking yearly investments.</p>
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
