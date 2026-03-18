import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { api } from "../../api/client";
import type { Account } from "../../api/types";
import { DeleteIcon, EditIcon, IconActionButton } from "../../components/IconActionButton";
import { knownBrokerages } from "../../lib/brokerages";

const accountSchema = z.object({
  name: z.string().min(1),
  account_type: z.string().min(1),
  category: z.enum(["brokerage", "retirement", "india"]),
  brokerage: z.string().min(1),
});

type AccountFormValues = z.infer<typeof accountSchema>;

const defaultValues: AccountFormValues = {
  name: "",
  account_type: "Individual Brokerage",
  category: "brokerage",
  brokerage: "Vanguard",
};

export function AccountsPage() {
  const queryClient = useQueryClient();
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const { data, isLoading, error } = useQuery({
    queryKey: ["accounts"],
    queryFn: api.listAccounts,
  });

  const form = useForm<AccountFormValues>({
    resolver: zodResolver(accountSchema),
    defaultValues,
  });

  const createMutation = useMutation({
    mutationFn: api.createAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      form.reset(defaultValues);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<AccountFormValues> }) =>
      api.updateAccount(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      setEditingAccount(null);
      form.reset(defaultValues);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: api.deleteAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      queryClient.invalidateQueries({ queryKey: ["holdings"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });

  function onSubmit(values: AccountFormValues) {
    if (editingAccount) {
      updateMutation.mutate({ id: editingAccount.id, payload: values });
      return;
    }
    createMutation.mutate(values);
  }

  function beginEdit(account: Account) {
    setEditingAccount(account);
    form.reset({
      name: account.name,
      account_type: account.account_type,
      category: account.category,
      brokerage: account.brokerage,
    });
  }

  const brokerageGroups = useMemo(() => {
    const groups = new Map<string, Account[]>();
    for (const account of data ?? []) {
      const current = groups.get(account.brokerage) ?? [];
      current.push(account);
      groups.set(account.brokerage, current);
    }
    return Array.from(groups.entries()).sort(([left], [right]) => left.localeCompare(right));
  }, [data]);

  if (isLoading) return <div className="panel">Loading accounts...</div>;
  if (error) return <div className="panel panel--danger">{error.message}</div>;

  return (
    <div className="split-layout">
      <section className="panel">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Account management</p>
            <h2>{editingAccount ? "Edit account" : "Add an account"}</h2>
          </div>
        </div>
        <form className="form-grid" onSubmit={form.handleSubmit(onSubmit)}>
          <label>
            Name
            <input {...form.register("name")} />
          </label>
          <label>
            Account type
            <input {...form.register("account_type")} />
          </label>
          <label>
            Category
            <select {...form.register("category")}>
              <option value="brokerage">Brokerage</option>
              <option value="retirement">Retirement</option>
              <option value="india">India</option>
            </select>
          </label>
          <label>
            Brokerage
            <input {...form.register("brokerage")} list="brokerage-options" />
          </label>
          <datalist id="brokerage-options">
            {knownBrokerages.map((brokerage) => (
              <option key={brokerage} value={brokerage} />
            ))}
          </datalist>
          <div className="form-actions">
            <button className="button button--primary" type="submit">
              {editingAccount ? "Save account" : "Create account"}
            </button>
            {editingAccount ? (
              <button
                className="button button--ghost"
                type="button"
                onClick={() => {
                  setEditingAccount(null);
                  form.reset(defaultValues);
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
            <p className="eyebrow">Current accounts</p>
            <h2>{data?.length ?? 0} accounts tracked</h2>
          </div>
        </div>
        <div className="card-list">
          {brokerageGroups.map(([brokerage, accounts]) => (
            <section key={brokerage} className="stack">
              <div className="panel__header">
                <div>
                  <p className="eyebrow">Brokerage group</p>
                  <h3>{brokerage}</h3>
                </div>
                <p className="metric-badge">{accounts.length} account{accounts.length === 1 ? "" : "s"}</p>
              </div>
              {accounts.map((account) => (
                <article key={account.id} className="account-card">
                  <div>
                    <h3>{account.name}</h3>
                    <p>
                      {account.account_type} · {account.brokerage}
                    </p>
                    <span className="pill pill--soft">{account.category}</span>
                  </div>
                  <div className="card-actions">
                    <IconActionButton icon={<EditIcon />} label={`Edit ${account.name}`} onClick={() => beginEdit(account)} />
                    <IconActionButton
                      icon={<DeleteIcon />}
                      label={`Delete ${account.name}`}
                      tone="danger"
                      onClick={() => deleteMutation.mutate(account.id)}
                    />
                  </div>
                </article>
              ))}
            </section>
          ))}
          {!data?.length ? <p className="empty-state">Create your first account to start tracking holdings.</p> : null}
        </div>
      </section>
    </div>
  );
}
