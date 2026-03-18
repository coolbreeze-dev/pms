import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";

import { api } from "../api/client";
import { IconActionButton, LockIcon, UnlockIcon } from "./IconActionButton";
import { formatDate } from "../lib/format";

const navItems = [
  { to: "/", label: "Dashboard" },
  { to: "/accounts", label: "Accounts" },
  { to: "/holdings", label: "Holdings" },
  { to: "/investments", label: "Investments" },
  { to: "/settings", label: "Settings" },
];

export function AppShell() {
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");
  const sessionQuery = useQuery({
    queryKey: ["auth-session"],
    queryFn: api.getAuthSession,
  });
  const loginMutation = useMutation({
    mutationFn: api.login,
    onSuccess: () => {
      setPassword("");
      queryClient.invalidateQueries({ queryKey: ["auth-session"] });
    },
  });

  function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    loginMutation.mutate(password);
  }

  if (sessionQuery.isLoading) {
    return <div className="shell"><div className="panel">Checking session...</div></div>;
  }

  if (sessionQuery.isError) {
    return (
      <div className="shell">
        <div className="panel panel--danger">{sessionQuery.error.message}</div>
      </div>
    );
  }

  if (sessionQuery.data?.enabled && !sessionQuery.data.authenticated) {
    return (
      <div className="shell shell--auth">
        <section className="panel auth-panel">
          <div>
            <p className="eyebrow">Protected session</p>
            <h1>Household Portfolio Tracker</h1>
            <p className="hero__meta">Enter the app password to unlock the local portfolio workspace.</p>
          </div>
          <form className="form-grid" onSubmit={handleLogin}>
            <label className="form-grid__full">
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
              />
            </label>
            <div className="form-actions">
              <button
                className="button button--primary button--icon-label"
                type="submit"
                disabled={loginMutation.isPending || !password}
              >
                <UnlockIcon />
                <span>{loginMutation.isPending ? "Unlocking..." : "Unlock"}</span>
              </button>
            </div>
            {loginMutation.isError ? (
              <p className="status-line status-line--error">{loginMutation.error.message}</p>
            ) : null}
          </form>
        </section>
      </div>
    );
  }

  return (
    <div className="shell">
      <header className="shell__header">
        <div>
          <p className="eyebrow">Local-first portfolio command center</p>
          <h1>Household Portfolio Tracker</h1>
          {sessionQuery.data?.enabled ? (
            <p className="status-line">
              Session active until {sessionQuery.data.expires_at ? formatDate(sessionQuery.data.expires_at) : "soon"}
            </p>
          ) : null}
        </div>
        <div className="shell__actions">
          <nav className="shell__nav" aria-label="Primary">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) => `shell__nav-link${isActive ? " shell__nav-link--active" : ""}`}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          {sessionQuery.data?.enabled ? (
            <IconActionButton
              className="shell__session-action"
              icon={<LockIcon />}
              label="Lock app"
              onClick={() => {
                api.logout();
                queryClient.invalidateQueries({ queryKey: ["auth-session"] });
              }}
            />
          ) : null}
        </div>
      </header>
      <main className="shell__content">
        <Outlet />
      </main>
    </div>
  );
}
