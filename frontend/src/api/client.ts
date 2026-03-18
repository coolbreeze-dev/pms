import type {
  Account,
  AccountCategory,
  AnalyticsResponse,
  AuthLoginResponse,
  AuthSession,
  BackgroundJob,
  BrokerageSyncConnectResponse,
  BrokerageSyncConfig,
  BrokerageSyncRunResponse,
  BrokerageSyncStatusResponse,
  CategoryPerformanceResponse,
  Holding,
  ImportCommitResponse,
  ImportPreviewResponse,
  InvestmentSummaryResponse,
  ObservabilityResponse,
  Period,
  PerformanceResponse,
  PortfolioResponse,
  Transaction,
} from "./types";

function resolveApiRoot() {
  const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (configuredBaseUrl) {
    return `${configuredBaseUrl.replace(/\/$/, "")}/api`;
  }
  if (import.meta.env.DEV) {
    return "http://127.0.0.1:8000/api";
  }
  if (typeof window !== "undefined") {
    return `${window.location.origin.replace(/\/$/, "")}/api`;
  }
  return "http://127.0.0.1:8000/api";
}

const API_ROOT = resolveApiRoot();
const AUTH_TOKEN_STORAGE_KEY = "portfolio.auth.token";

function getAuthToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
}

function setAuthToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (!token) {
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const authToken = getAuthToken();
  if (authToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    if (response.status === 401) {
      setAuthToken(null);
    }
    const payload = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(payload.detail ?? "Request failed");
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function upload<T>(path: string, file: File): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);
  const headers = new Headers();
  const authToken = getAuthToken();
  if (authToken) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }
  const response = await fetch(`${API_ROOT}${path}`, {
    method: "POST",
    body: formData,
    headers,
  });
  if (!response.ok) {
    if (response.status === 401) {
      setAuthToken(null);
    }
    const payload = await response.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(payload.detail ?? "Upload failed");
  }
  return (await response.json()) as T;
}

export const api = {
  getAuthSession: () => request<AuthSession>("/auth/session"),
  login: async (password: string) => {
    const response = await request<AuthLoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    });
    if (response.token) {
      setAuthToken(response.token);
    }
    return response;
  },
  logout: () => setAuthToken(null),
  listAccounts: () => request<Account[]>("/accounts"),
  createAccount: (payload: Omit<Account, "id" | "created_at">) =>
    request<Account>("/accounts", { method: "POST", body: JSON.stringify(payload) }),
  updateAccount: (id: number, payload: Partial<Omit<Account, "id" | "created_at">>) =>
    request<Account>(`/accounts/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteAccount: (id: number) => request<void>(`/accounts/${id}`, { method: "DELETE" }),
  listHoldings: (params: { category?: AccountCategory | ""; search?: string } = {}) => {
    const query = new URLSearchParams();
    if (params.category) query.set("category", params.category);
    if (params.search) query.set("search", params.search);
    return request<Holding[]>(`/holdings${query.size ? `?${query.toString()}` : ""}`);
  },
  createHolding: (payload: Record<string, unknown>) =>
    request<Holding>("/holdings", { method: "POST", body: JSON.stringify(payload) }),
  updateHolding: (id: number, payload: Record<string, unknown>) =>
    request<Holding>(`/holdings/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteHolding: (id: number) => request<void>(`/holdings/${id}`, { method: "DELETE" }),
  listTransactions: (params: { category?: AccountCategory | ""; year?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.category) query.set("category", params.category);
    if (params.year) query.set("year", String(params.year));
    return request<Transaction[]>(`/transactions${query.size ? `?${query.toString()}` : ""}`);
  },
  createTransaction: (payload: Record<string, unknown>) =>
    request<Transaction>("/transactions", { method: "POST", body: JSON.stringify(payload) }),
  updateTransaction: (id: number, payload: Record<string, unknown>) =>
    request<Transaction>(`/transactions/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteTransaction: (id: number) => request<void>(`/transactions/${id}`, { method: "DELETE" }),
  getInvestmentSummary: (category: AccountCategory, year: number) =>
    request<InvestmentSummaryResponse>(`/investments/summary?category=${category}&year=${year}`),
  getPortfolio: (category: AccountCategory) =>
    request<PortfolioResponse>(`/portfolio?category=${category}`),
  getPerformance: (category: AccountCategory, period: Period) =>
    request<PerformanceResponse>(`/performance?category=${category}&period=${period}`),
  getCategoryPerformance: (period: Period) =>
    request<CategoryPerformanceResponse>(`/category-performance?period=${period}`),
  getAnalytics: (category: AccountCategory) =>
    request<AnalyticsResponse>(`/portfolio-analytics?category=${category}`),
  getObservability: () => request<ObservabilityResponse>("/ops/observability"),
  getBrokerageSyncConfig: () => request<BrokerageSyncConfig>("/settings/brokerage-sync-config"),
  updateBrokerageSyncConfig: (payload: Record<string, unknown>) =>
    request<BrokerageSyncConfig>("/settings/brokerage-sync-config", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  getBrokerageSyncStatus: () => request<BrokerageSyncStatusResponse>("/brokerage-sync/status"),
  createBrokerageSyncPortal: () =>
    request<BrokerageSyncConnectResponse>("/brokerage-sync/connect", { method: "POST" }),
  runBrokerageSync: () =>
    request<BrokerageSyncRunResponse>("/brokerage-sync/sync", { method: "POST" }),
  previewImport: (file: File) => upload<ImportPreviewResponse>("/imports/preview", file),
  commitImport: (jobId: number, payload: Record<string, unknown>) =>
    request<ImportCommitResponse>(`/imports/${jobId}/commit`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createRefreshJob: () =>
    request<BackgroundJob>("/jobs/refresh-prices", {
      method: "POST",
      body: JSON.stringify({ tickers: [], include_benchmarks: true }),
    }),
  getJob: (jobId: string) => request<BackgroundJob>(`/jobs/${jobId}`),
};
