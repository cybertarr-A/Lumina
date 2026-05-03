/**
 * Axios API client with JWT interceptors and automatic token refresh.
 */
import axios, { AxiosInstance, InternalAxiosRequestConfig } from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// Attach JWT on every request
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

let isRefreshing = false;
let failedQueue: Array<{ resolve: (t: string) => void; reject: (e: unknown) => void }> = [];

// Auto-refresh token on 401
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          original.headers.Authorization = `Bearer ${token}`;
          return api(original);
        });
      }

      original._retry = true;
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

        original.headers.Authorization = `Bearer ${access_token}`;
        return api(original);
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

// ── API Methods ───────────────────────────────────────────────────────────────

export const authApi = {
  register: (data: { email: string; username: string; password: string }) =>
    api.post("/auth/register", data),
  login: (data: { email: string; password: string }) =>
    api.post("/auth/login", data),
  logout: () => api.post("/auth/logout"),
  me: () => api.get("/auth/me"),
};

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

export const compileApi = {
  compile: (data: { source_code: string; optimizer?: boolean }) =>
    api.post("/compile/", data),
  compileAndSave: (contractId: string, data: { source_code: string }) =>
    api.post(`/compile/save/${contractId}`, data),
};

export const auditApi = {
  run: (contractId: string) => api.post("/audit/", { contract_id: contractId }),
  get: (reportId: string) => api.get(`/audit/${reportId}`),
};

export const deployApi = {
  initiate: (data: {
    contract_id: string;
    network: string;
    deployer_address: string;
    constructor_args?: unknown[];
  }) => api.post("/deploy/", data),
  confirm: (deploymentId: string, txHash: string) =>
    api.post(`/deploy/${deploymentId}/confirm?tx_hash=${txHash}`),
  status: (deploymentId: string) => api.get(`/deploy/${deploymentId}/status`),
  history: () => api.get("/deploy/history/list"),
  networks: () => api.get("/deploy/networks"),
};
