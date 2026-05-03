/**
 * Axios API client with JWT interceptors, automatic token refresh,
 * retry logic with exponential backoff, and task status polling.
 */
import axios, { AxiosInstance, InternalAxiosRequestConfig } from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ── Axios instance ────────────────────────────────────────────────────────────
export const api: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// ── JWT interceptor ───────────────────────────────────────────────────────────
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (token) config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ── Retry logic ───────────────────────────────────────────────────────────────
const RETRYABLE_STATUSES = [429, 502, 503, 504];
const MAX_RETRIES = 3;

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const config = error.config;
    if (!config) return Promise.reject(error);

    config._retryCount = config._retryCount || 0;
    const status = error.response?.status;

    // Retry on network errors or specific HTTP status codes
    const isRetryable =
      !error.response || // network error
      (RETRYABLE_STATUSES.includes(status) && config._retryCount < MAX_RETRIES);

    if (isRetryable && config._retryCount < MAX_RETRIES) {
      config._retryCount += 1;
      const delay = Math.min(1000 * 2 ** config._retryCount, 10000); // exponential backoff, max 10s
      await new Promise((r) => setTimeout(r, delay));
      return api(config);
    }

    // ── Auto token refresh on 401 ──────────────────────────────────────────
    if (status === 401 && !config._retry) {
      config._retry = true;

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          config.headers.Authorization = `Bearer ${token}`;
          return api(config);
        });
      }

      isRefreshing = true;
      try {
        const refreshToken = localStorage.getItem("refresh_token");
        if (!refreshToken) throw new Error("No refresh token");

        const response = await axios.post(`${API_BASE}/auth/refresh`, {
          refresh_token_str: refreshToken,
        });
        const { access_token, refresh_token } = response.data;
        localStorage.setItem("access_token", access_token);
        localStorage.setItem("refresh_token", refresh_token);

        failedQueue.forEach((p) => p.resolve(access_token));
        failedQueue = [];
        config.headers.Authorization = `Bearer ${access_token}`;
        return api(config);
      } catch (err) {
        failedQueue.forEach((p) => p.reject(err));
        failedQueue = [];
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

let isRefreshing = false;
let failedQueue: Array<{ resolve: (t: string) => void; reject: (e: unknown) => void }> = [];

// ── Auth API ──────────────────────────────────────────────────────────────────
export const authApi = {
  register: (data: { email: string; username: string; password: string }) =>
    api.post("/auth/register", data),
  login: (data: { email: string; password: string }) =>
    api.post("/auth/login", data),
  logout: () => api.post("/auth/logout"),
  me: () => api.get("/auth/me"),
};

// ── Tasks API (Celery job polling) ────────────────────────────────────────────
export type TaskStatus = "PENDING" | "STARTED" | "SUCCESS" | "FAILURE" | "RETRY" | "REVOKED";

export interface TaskResult {
  task_id: string;
  status: TaskStatus;
  step?: string;
  progress?: number;
  result?: unknown;
  error?: string;
}

export const tasksApi = {
  getStatus: (taskId: string) => api.get<TaskResult>(`/tasks/${taskId}`),
  revoke: (taskId: string) => api.delete(`/tasks/${taskId}`),

  /** Poll a task until it reaches a terminal state (SUCCESS or FAILURE). */
  poll: async (
    taskId: string,
    opts: {
      onProgress?: (result: TaskResult) => void;
      intervalMs?: number;
      timeoutMs?: number;
    } = {}
  ): Promise<TaskResult> => {
    const { onProgress, intervalMs = 2000, timeoutMs = 120000 } = opts;
    const deadline = Date.now() + timeoutMs;

    while (Date.now() < deadline) {
      const { data } = await tasksApi.getStatus(taskId);
      onProgress?.(data);
      if (data.status === "SUCCESS" || data.status === "FAILURE" || data.status === "REVOKED") {
        return data;
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }
    throw new Error(`Task ${taskId} timed out after ${timeoutMs}ms`);
  },
};

// ── Contracts API ─────────────────────────────────────────────────────────────
export const contractsApi = {
  generate: (data: {
    prompt: string;
    contract_type?: string;
    name: string;
    template_params?: Record<string, unknown>;
  }) => api.post("/contracts/generate", data),
  create: (data: Record<string, unknown>) => api.post("/contracts/", data),
  list: (params?: { skip?: number; limit?: number; contract_type?: string }) =>
    api.get("/contracts/", { params }),
  get: (id: string) => api.get(`/contracts/${id}`),
  update: (id: string, data: Record<string, unknown>) => api.put(`/contracts/${id}`, data),
  delete: (id: string) => api.delete(`/contracts/${id}`),
  versions: (id: string) => api.get(`/contracts/${id}/versions`),
  templates: () => api.get("/contracts/templates/list"),
};

// ── Compile API (async — returns task_id) ─────────────────────────────────────
export const compileApi = {
  compile: (data: { source_code: string; optimizer?: boolean }) =>
    api.post<{ task_id: string; poll_url: string }>("/compile/", data),
  compileAndSave: (contractId: string, data: { source_code: string }) =>
    api.post<{ task_id: string; poll_url: string }>(`/compile/save/${contractId}`, data),
};

// ── Audit API (async — returns task_id via report) ────────────────────────────
export const auditApi = {
  run: (contractId: string) =>
    api.post("/audit/", { contract_id: contractId }),
  get: (reportId: string) => api.get(`/audit/${reportId}`),
};

// ── Deploy API ────────────────────────────────────────────────────────────────
export const deployApi = {
  initiate: (data: {
    contract_id: string;
    network: string;
    deployer_address: string;
    constructor_args?: unknown[];
    signed_message?: string;
    signature?: string;
  }) => api.post("/deploy/", data),
  confirm: (deploymentId: string, txHash: string) =>
    api.post<{ task_id: string }>(`/deploy/${deploymentId}/confirm?tx_hash=${txHash}`),
  status: (deploymentId: string) => api.get(`/deploy/${deploymentId}/status`),
  history: () => api.get("/deploy/history/list"),
  networks: () => api.get("/deploy/networks"),
};
