/**
 * Global state management using Zustand.
 * Stores: auth, contracts, editor, deployment state.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  username: string;
  is_active: boolean;
}

export interface Contract {
  id: string;
  name: string;
  contract_type: string;
  source_code: string;
  abi?: unknown[];
  bytecode?: string;
  is_compiled: boolean;
  ai_generated: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuditFinding {
  id: string;
  title: string;
  description: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";
  location?: string;
  suggestion: string;
}

export interface AuditReport {
  id: string;
  contract_id: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
  risk_score?: number;
  findings?: AuditFinding[];
  summary?: string;
}

// ── Auth Store ────────────────────────────────────────────────────────────────

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  setAuth: (user: User, accessToken: string, refreshToken: string) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      setAuth: (user, accessToken, refreshToken) => {
        localStorage.setItem("access_token", accessToken);
        localStorage.setItem("refresh_token", refreshToken);
        set({ user, accessToken, isAuthenticated: true });
      },
      clearAuth: () => {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        set({ user: null, accessToken: null, isAuthenticated: false });
      },
    }),
    { name: "auth-store", partialize: (state) => ({ user: state.user }) }
  )
);

// ── Editor Store ──────────────────────────────────────────────────────────────

interface EditorState {
  activeContractId: string | null;
  sourceCode: string;
  isDirty: boolean;
  compileResult: {
    success: boolean;
    abi?: unknown[];
    bytecode?: string;
    errors?: string[];
    warnings?: string[];
  } | null;
  setActiveContract: (id: string, code: string) => void;
  setSourceCode: (code: string) => void;
  setCompileResult: (result: EditorState["compileResult"]) => void;
  resetEditor: () => void;
}

export const useEditorStore = create<EditorState>()((set) => ({
  activeContractId: null,
  sourceCode: "",
  isDirty: false,
  compileResult: null,
  setActiveContract: (id, code) => set({ activeContractId: id, sourceCode: code, isDirty: false }),
  setSourceCode: (code) => set({ sourceCode: code, isDirty: true, compileResult: null }),
  setCompileResult: (result) => set({ compileResult: result }),
  resetEditor: () => set({ activeContractId: null, sourceCode: "", isDirty: false, compileResult: null }),
}));

// ── Contracts Store ───────────────────────────────────────────────────────────

interface ContractsState {
  contracts: Contract[];
  selectedContract: Contract | null;
  setContracts: (contracts: Contract[]) => void;
  addContract: (contract: Contract) => void;
  updateContract: (contract: Contract) => void;
  selectContract: (contract: Contract | null) => void;
  removeContract: (id: string) => void;
}

export const useContractsStore = create<ContractsState>()((set) => ({
  contracts: [],
  selectedContract: null,
  setContracts: (contracts) => set({ contracts }),
  addContract: (contract) => set((s) => ({ contracts: [contract, ...s.contracts] })),
  updateContract: (updated) =>
    set((s) => ({
      contracts: s.contracts.map((c) => (c.id === updated.id ? updated : c)),
    })),
  selectContract: (contract) => set({ selectedContract: contract }),
  removeContract: (id) =>
    set((s) => ({ contracts: s.contracts.filter((c) => c.id !== id) })),
}));

// ── UI Store ──────────────────────────────────────────────────────────────────

interface UIState {
  sidebarOpen: boolean;
  generatingContract: boolean;
  auditLoading: boolean;
  deployLoading: boolean;
  notifications: Array<{ id: string; type: "success" | "error" | "info"; message: string }>;
  toggleSidebar: () => void;
  setGenerating: (v: boolean) => void;
  setAuditLoading: (v: boolean) => void;
  setDeployLoading: (v: boolean) => void;
  addNotification: (type: "success" | "error" | "info", message: string) => void;
  removeNotification: (id: string) => void;
}

export const useUIStore = create<UIState>()((set) => ({
  sidebarOpen: true,
  generatingContract: false,
  auditLoading: false,
  deployLoading: false,
  notifications: [],
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setGenerating: (v) => set({ generatingContract: v }),
  setAuditLoading: (v) => set({ auditLoading: v }),
  setDeployLoading: (v) => set({ deployLoading: v }),
  addNotification: (type, message) => {
    const id = Date.now().toString();
    set((s) => ({ notifications: [...s.notifications, { id, type, message }] }));
    setTimeout(() => {
      set((s) => ({ notifications: s.notifications.filter((n) => n.id !== id) }));
    }, 5000);
  },
  removeNotification: (id) =>
    set((s) => ({ notifications: s.notifications.filter((n) => n.id !== id) })),
}));

// ── Jobs Store (Celery task tracking) ─────────────────────────────────────────

export type JobType = "generate" | "compile" | "audit" | "deploy";
export type JobStatus = "pending" | "running" | "success" | "error";

export interface Job {
  id: string;         // Celery task_id
  type: JobType;
  status: JobStatus;
  label: string;
  contractId?: string;
  result?: unknown;
  error?: string;
  createdAt: number;
}

interface JobsState {
  jobs: Job[];
  addJob: (job: Job) => void;
  updateJob: (taskId: string, updates: Partial<Job>) => void;
  removeJob: (taskId: string) => void;
  clearFinished: () => void;
  getJobByType: (type: JobType, contractId?: string) => Job | undefined;
}

export const useJobsStore = create<JobsState>()((set, get) => ({
  jobs: [],
  addJob: (job) => set((s) => ({ jobs: [job, ...s.jobs].slice(0, 20) })), // Keep last 20
  updateJob: (taskId, updates) =>
    set((s) => ({
      jobs: s.jobs.map((j) => (j.id === taskId ? { ...j, ...updates } : j)),
    })),
  removeJob: (taskId) =>
    set((s) => ({ jobs: s.jobs.filter((j) => j.id !== taskId) })),
  clearFinished: () =>
    set((s) => ({ jobs: s.jobs.filter((j) => j.status === "pending" || j.status === "running") })),
  getJobByType: (type, contractId) =>
    get().jobs.find((j) => j.type === type && (!contractId || j.contractId === contractId)),
}));

