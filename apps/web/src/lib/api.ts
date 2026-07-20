import type { ApiEnvelope, CommandCard, GlobalIQAnswer, TimelineStep, UniversalRecord, UserSession } from "../types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1";

let accessToken = window.localStorage.getItem("bcaz_access_token") ?? "";

export function setAccessToken(token: string) {
  accessToken = token;
  window.localStorage.setItem("bcaz_access_token", token);
}

export function clearAccessToken() {
  accessToken = "";
  window.localStorage.removeItem("bcaz_access_token");
}

export function hasAccessToken() {
  return Boolean(accessToken);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<ApiEnvelope<T>> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include"
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = body?.error?.message ?? "Request failed";
    if (response.status === 401) clearAccessToken();
    throw new Error(message);
  }
  return body;
}

export const api = {
  async login(email: string, password: string) {
    const response = await request<{ user: UserSession; access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
    setAccessToken(response.data.access_token);
    return response.data.user;
  },
  async me() {
    return (await request<UserSession>("/auth/me")).data;
  },
  async list<T extends UniversalRecord>(domain: string, limit = 100) {
    return request<T[]>(`/${domain}?limit=${limit}`);
  },
  async get<T>(domain: string, id: string) {
    return (await request<T>(`/${domain}/${id}`)).data;
  },
  async create<T>(domain: string, payload: Record<string, unknown>, idempotencyKey?: string) {
    return (
      await request<T>(`/${domain}`, {
        method: "POST",
        headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey }: undefined,
        body: JSON.stringify(payload)
      })
    ).data;
  },
  async patch<T>(domain: string, id: string, payload: Record<string, unknown>) {
    return (
      await request<T>(`/${domain}/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload)
      })
    ).data;
  },
  async commandBoard() {
    return (await request<CommandCard[]>("/command-board")).data;
  },
  async actOnCommandCard(id: string, action: string) {
    return (await request<CommandCard>(`/command-board/${id}/${action}`, { method: "POST" })).data;
  },
  async timeline(orderId: string) {
    return (await request<{ order: UniversalRecord; timeline: TimelineStep[] }>(`/procure-to-pay/${orderId}/timeline`)).data;
  },
  async completeReceiving(sessionId: string) {
    return (await request<UniversalRecord>(`/receiving/sessions/${sessionId}/complete`, { method: "POST" })).data;
  },
  async matchInvoice(invoiceId: string) {
    return (await request<UniversalRecord>(`/invoices/${invoiceId}/match`, { method: "POST" })).data;
  },
  async recipeCost(recipeId: string) {
    return (await request<Record<string, unknown>>(`/recipes/${recipeId}/cost`)).data;
  },
  async askGlobalIQ(question: string) {
    return (await request<GlobalIQAnswer>("/global-iq/query", { method:"POST", body: JSON.stringify({ question }) })).data;
  },
  async queueSync(payload: Record<string, unknown>) {
    return (await request<UniversalRecord>("/sync/queue", { method: "POST", body: JSON.stringify(payload) })).data;
  }
};

export { API_BASE };
