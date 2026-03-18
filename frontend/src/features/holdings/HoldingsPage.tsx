import { useDeferredValue, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";

import { api } from "../../api/client";
import type { Holding } from "../../api/types";
import { DeleteIcon, EditIcon, IconActionButton } from "../../components/IconActionButton";
import { formatCurrency, formatNumber, formatPercent, numeric } from "../../lib/format";

const holdingSchema = z.object({
  account_id: z.coerce.number().min(1),
  ticker: z.string().min(1),
  name: z.string().optional(),
  shares: z.coerce.number().positive(),
  cost_basis: z.coerce.number().positive(),
  purchase_date: z.string().min(1),
  security_type: z.string().default("equity"),
  market: z.string().default("us"),
  currency: z.string().default("USD"),
  notes: z.string().optional(),
});

type HoldingFormValues = z.infer<typeof holdingSchema>;

const emptyHolding: HoldingFormValues = {
  account_id: 0,
  ticker: "",
  name: "",
  shares: 0,
  cost_basis: 0,
  purchase_date: new Date().toISOString().slice(0, 10),
  security_type: "equity",
  market: "us",
  currency: "USD",
  notes: "",
};

export function HoldingsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [editingHolding, setEditingHolding] = useState<Holding | null>(null);
  const [sorting, setSorting] = useState<SortingState>([{ id: "current_value", desc: true }]);
  const deferredSearch = useDeferredValue(search);

  const accountsQuery = useQuery({
    queryKey: ["accounts"],
    queryFn: api.listAccounts,
  });
  const holdingsQuery = useQuery({
    queryKey: ["holdings", deferredSearch],
    queryFn: () => api.listHoldings({ search: deferredSearch }),
  });

  const form = useForm<HoldingFormValues>({
    resolver: zodResolver(holdingSchema),
    defaultValues: emptyHolding,
  });

  const createMutation = useMutation({
    mutationFn: api.createHolding,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["holdings"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      form.reset(emptyHolding);
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Record<string, unknown> }) =>
      api.updateHolding(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["holdings"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      setEditingHolding(null);
      form.reset(emptyHolding);
    },
  });
  const deleteMutation = useMutation({
    mutationFn: api.deleteHolding,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["holdings"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });

  function onSubmit(values: HoldingFormValues) {
    if (editingHolding) {
      updateMutation.mutate({ id: editingHolding.id, payload: values });
      return;
    }
    createMutation.mutate(values);
  }

  function beginEdit(holding: Holding) {
    setEditingHolding(holding);
    form.reset({
      account_id: holding.account_id,
      ticker: holding.ticker,
      name: holding.name ?? "",
      shares: numeric(holding.shares),
      cost_basis: numeric(holding.cost_basis),
      purchase_date: holding.purchase_date,
      security_type: holding.security_type,
      market: holding.market,
      currency: holding.currency,
      notes: holding.notes ?? "",
    });
  }

  const columns = useMemo(
    () => [
      {
        accessorKey: "ticker",
        header: "Ticker",
        cell: ({ row }: { row: { original: Holding } }) => row.original.ticker,
      },
      {
        accessorKey: "account_name",
        header: "Account",
      },
      {
        accessorKey: "shares",
        header: "Shares",
        cell: ({ row }: { row: { original: Holding } }) => formatNumber(row.original.shares),
      },
      {
        accessorKey: "current_value",
        header: "Value",
        cell: ({ row }: { row: { original: Holding } }) => formatCurrency(row.original.current_value),
      },
      {
        accessorKey: "gain_loss",
        header: "Gain / Loss",
        cell: ({ row }: { row: { original: Holding } }) => formatCurrency(row.original.gain_loss),
      },
      {
        accessorKey: "return_pct",
        header: "Return",
        cell: ({ row }: { row: { original: Holding } }) => formatPercent(row.original.return_pct),
      },
      {
        id: "actions",
        header: "Actions",
        cell: ({ row }: { row: { original: Holding } }) => (
          <div className="table-actions">
            <IconActionButton
              icon={<EditIcon />}
              label={`Edit ${row.original.ticker}`}
              onClick={() => beginEdit(row.original)}
            />
            <IconActionButton
              icon={<DeleteIcon />}
              label={`Delete ${row.original.ticker}`}
              tone="danger"
              onClick={() => deleteMutation.mutate(row.original.id)}
            />
          </div>
        ),
      },
    ],
    [deleteMutation],
  );

  const table = useReactTable({
    data: holdingsQuery.data ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="split-layout">
      <section className="panel">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Manual entry</p>
            <h2>{editingHolding ? "Edit holding" : "Add a holding"}</h2>
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
            Ticker
            <input {...form.register("ticker")} />
          </label>
          <label>
            Name
            <input {...form.register("name")} />
          </label>
          <label>
            Shares
            <input type="number" step="0.0001" {...form.register("shares")} />
          </label>
          <label>
            Cost basis
            <input type="number" step="0.01" {...form.register("cost_basis")} />
          </label>
          <label>
            Purchase date
            <input type="date" {...form.register("purchase_date")} />
          </label>
          <label>
            Security type
            <input {...form.register("security_type")} />
          </label>
          <label>
            Currency
            <input {...form.register("currency")} />
          </label>
          <label>
            Market
            <input {...form.register("market")} />
          </label>
          <label className="form-grid__full">
            Notes
            <textarea rows={3} {...form.register("notes")} />
          </label>
          <div className="form-actions">
            <button className="button button--primary" type="submit">
              {editingHolding ? "Save holding" : "Create holding"}
            </button>
            {editingHolding ? (
              <button
                className="button button--ghost"
                type="button"
                onClick={() => {
                  setEditingHolding(null);
                  form.reset(emptyHolding);
                }}
              >
                Cancel
              </button>
            ) : null}
          </div>
        </form>
      </section>

      <section className="panel">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Per-lot holdings</p>
            <h2>Search and sort across all accounts</h2>
          </div>
          <input
            className="search-input"
            placeholder="Search by ticker or account"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              {table.getHeaderGroups().map((group) => (
                <tr key={group.id}>
                  {group.headers.map((header) => (
                    <th
                      key={header.id}
                      onClick={header.column.getToggleSortingHandler()}
                      className={header.column.getCanSort() ? "sortable" : ""}
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {!holdingsQuery.data?.length ? <p className="empty-state">No holdings yet. Add one or import a CSV.</p> : null}
        </div>
      </section>
    </div>
  );
}
