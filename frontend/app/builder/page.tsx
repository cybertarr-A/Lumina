"use client";

import { useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Cpu, Code2, Play, Shield, Save, Sparkles, ChevronDown,
  Loader2, CheckCircle2, XCircle, AlertTriangle, Copy, Download,
  RefreshCw, Zap
} from "lucide-react";
import { Sidebar } from "@/components/Layout/Sidebar";
import { SolidityEditor } from "@/components/Editor/MonacoEditor";
import { WalletConnect } from "@/components/Wallet/WalletConnect";
import TaskTracker from "@/components/ui/TaskTracker";
import { contractsApi, compileApi, auditApi, tasksApi } from "@/lib/api";
import { useEditorStore, useUIStore, useContractsStore, useJobsStore } from "@/lib/store";

const CONTRACT_TYPES = ["ERC20", "ERC721", "ERC1155", "DAO", "STAKING", "DEFI", "CUSTOM"];

export default function BuilderPage() {
  const { sourceCode, setSourceCode, compileResult, setCompileResult } = useEditorStore();
  const { addContract, updateContract } = useContractsStore();
  const { addNotification } = useUIStore();
  const { addJob, updateJob } = useJobsStore();

  const [prompt, setPrompt] = useState("");
  const [contractName, setContractName] = useState("MyContract");
  const [contractType, setContractType] = useState("ERC20");
  const [saving, setSaving] = useState(false);
  const [currentContractId, setCurrentContractId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"editor" | "output">("editor");

  // Async task tracking
  const [generateTaskId, setGenerateTaskId] = useState<string | null>(null);
  const [compileTaskId, setCompileTaskId] = useState<string | null>(null);
  const [criticalViolations, setCriticalViolations] = useState<unknown[]>([]);

  // ── AI Generation (async via Celery) ─────────────────────────────────────
  const handleGenerate = async () => {
    if (!prompt.trim()) {
      addNotification("error", "Please enter a prompt to generate a contract");
      return;
    }

    // Create a placeholder contract row first to get an ID for the Celery task
    let contractId = currentContractId;
    if (!contractId) {
      try {
        const res = await contractsApi.create({
          name: contractName,
          source_code: "// Generating...",
          contract_type: contractType,
        });
        contractId = res.data.id;
        setCurrentContractId(contractId);
        addContract(res.data);
      } catch {
        addNotification("error", "Failed to initialize contract record");
        return;
      }
    }

    try {
      // Enqueue generation as a Celery background task
      const res = await contractsApi.generate({
        prompt,
        contract_type: contractType,
        name: contractName,
      });

      // Backend still returns synchronous result for generation (via ai_service)
      // but if it returns a task_id, switch to async mode
      const data = res.data;
      if (data.task_id) {
        setGenerateTaskId(data.task_id);
        addJob({
          id: data.task_id,
          type: "generate",
          status: "pending",
          label: `Generating ${contractName}...`,
          contractId: contractId!,
          createdAt: Date.now(),
        });
      } else {
        // Synchronous response (mock mode or template)
        if (data.source_code) {
          setSourceCode(data.source_code);
          addNotification("success", "Contract generated!");
          if (data.warnings?.length) {
            data.warnings.forEach((w: string) => addNotification("info", w));
          }
        }
      }
    } catch {
      addNotification("error", "Failed to generate contract. Check your prompt and try again.");
      setGenerateTaskId(null);
    }
  };

  const handleGenerateSuccess = useCallback((result: unknown) => {
    const r = result as {
      source_code?: string;
      warnings?: string[];
      critical_violations?: unknown[];
      has_critical_issues?: boolean;
    };
    if (r?.source_code) {
      setSourceCode(r.source_code);
      addNotification("success", "Contract generated successfully!");
      if (r.warnings?.length) {
        r.warnings.forEach((w) => addNotification("info", w));
      }
      if (r.has_critical_issues && r.critical_violations?.length) {
        setCriticalViolations(r.critical_violations);
        addNotification("error", `⚠️ ${r.critical_violations.length} critical security pattern(s) detected in generated code!`);
      }
    }
    setGenerateTaskId(null);
  }, []);

  const handleGenerateError = useCallback((error: string) => {
    addNotification("error", `Generation failed: ${error}`);
    setGenerateTaskId(null);
  }, []);

  // ── Compile (async via Celery) ────────────────────────────────────────────
  const handleCompile = async () => {
    if (!sourceCode.trim()) {
      addNotification("error", "No source code to compile");
      return;
    }
    setActiveTab("output");
    setCompileResult(null);

    try {
      const endpoint = currentContractId
        ? compileApi.compileAndSave(currentContractId, { source_code: sourceCode })
        : compileApi.compile({ source_code: sourceCode, optimizer: true });
      const res = await endpoint;
      const { task_id } = res.data;
      setCompileTaskId(task_id);
      addJob({
        id: task_id,
        type: "compile",
        status: "pending",
        label: "Compiling Solidity...",
        contractId: currentContractId ?? undefined,
        createdAt: Date.now(),
      });
    } catch {
      addNotification("error", "Failed to enqueue compilation");
      setCompileTaskId(null);
    }
  };

  const handleCompileSuccess = useCallback((result: unknown) => {
    const r = result as { success: boolean; abi?: unknown[]; bytecode?: string; errors?: string[]; warnings?: string[] };
    setCompileResult(r);
    if (r?.success) {
      addNotification("success", "Compilation successful!");
    } else {
      addNotification("error", `Compilation failed: ${r?.errors?.[0] || "Unknown error"}`);
    }
    setCompileTaskId(null);
  }, []);

  const handleCompileError = useCallback((error: string) => {
    addNotification("error", `Compilation error: ${error}`);
    setCompileTaskId(null);
  }, []);

  // ── Save ──────────────────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!sourceCode.trim() || !contractName.trim()) return;
    setSaving(true);
    try {
      if (currentContractId) {
        const res = await contractsApi.update(currentContractId, {
          name: contractName,
          source_code: sourceCode,
          contract_type: contractType,
        });
        updateContract(res.data);
        addNotification("success", "Contract saved!");
      } else {
        const res = await contractsApi.create({
          name: contractName,
          source_code: sourceCode,
          contract_type: contractType,
        });
        setCurrentContractId(res.data.id);
        addContract(res.data);
        addNotification("success", "Contract created!");
      }
    } catch {
      addNotification("error", "Failed to save contract");
    } finally {
      setSaving(false);
    }
  };

  const handleCopyABI = () => {
    if (compileResult?.abi) {
      navigator.clipboard.writeText(JSON.stringify(compileResult.abi, null, 2));
      addNotification("success", "ABI copied to clipboard");
    }
  };

  const isGenerating = !!generateTaskId;
  const isCompiling = !!compileTaskId;

  return (
    <div className="flex min-h-screen bg-[hsl(222,47%,6%)]">
      <Sidebar />

      <main className="flex-1 ml-[240px] flex flex-col">
        {/* Top bar */}
        <div className="sticky top-0 z-30 flex items-center justify-between px-6 py-3 border-b border-white/10 backdrop-blur-xl bg-black/20">
          <div className="flex items-center gap-3">
            <Code2 className="w-5 h-5 text-purple-400" />
            <h1 className="text-lg font-bold text-white">Contract Builder</h1>
            {currentContractId && !isGenerating && (
              <span className="badge-success">
                <CheckCircle2 className="w-3 h-3" /> Saved
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <WalletConnect />
          </div>
        </div>

        {/* Split layout */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left panel — AI prompt + settings */}
          <div className="w-80 shrink-0 border-r border-white/10 flex flex-col overflow-y-auto">
            <div className="p-5 space-y-5">
              {/* Contract settings */}
              <div className="space-y-3">
                <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Contract Settings</h2>
                <input
                  type="text"
                  value={contractName}
                  onChange={(e) => setContractName(e.target.value)}
                  placeholder="Contract name"
                  className="input-field text-sm"
                  disabled={isGenerating}
                />
                <div className="relative">
                  <select
                    value={contractType}
                    onChange={(e) => setContractType(e.target.value)}
                    className="input-field text-sm appearance-none pr-10 cursor-pointer"
                    disabled={isGenerating}
                  >
                    {CONTRACT_TYPES.map((t) => (
                      <option key={t} value={t} className="bg-[#1e1e2e]">{t}</option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                </div>
              </div>

              {/* AI Prompt */}
              <div className="space-y-3">
                <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-purple-400" />
                  AI Generation
                </h2>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Describe your contract... e.g. 'Create an ERC-20 token with 1M supply, mintable by owner, with pause functionality'"
                  rows={6}
                  className="input-field text-sm resize-none"
                  disabled={isGenerating}
                />
                <button
                  onClick={handleGenerate}
                  disabled={isGenerating || !prompt.trim()}
                  className="btn-primary w-full justify-center text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isGenerating ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Queuing…</>
                  ) : (
                    <><Sparkles className="w-4 h-4" /> Generate Contract</>
                  )}
                </button>

                {/* Generation progress */}
                <AnimatePresence>
                  {generateTaskId && (
                    <motion.div
                      initial={{ opacity: 0, y: -8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                    >
                      <TaskTracker
                        taskId={generateTaskId}
                        label="Generating contract with AI..."
                        onSuccess={handleGenerateSuccess}
                        onError={handleGenerateError}
                        onComplete={() => updateJob(generateTaskId, { status: "success" })}
                      />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Critical violations warning */}
              <AnimatePresence>
                {criticalViolations.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="glass-card border border-red-500/40 p-4 space-y-2"
                  >
                    <div className="flex items-center gap-2 text-red-400 font-semibold text-sm">
                      <AlertTriangle className="w-4 h-4" />
                      Critical Patterns Detected
                    </div>
                    {(criticalViolations as Array<{ title: string; line?: number; severity: string }>).map((v, i) => (
                      <p key={i} className="text-xs text-red-300">
                        Line {v.line ?? "?"}: {v.title}
                      </p>
                    ))}
                    <p className="text-xs text-slate-400">Review these patterns before compiling or deploying.</p>
                    <button
                      onClick={() => setCriticalViolations([])}
                      className="text-xs text-slate-500 hover:text-white"
                    >
                      Dismiss
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Template picker */}
              <div className="space-y-3">
                <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Templates</h2>
                <div className="grid grid-cols-2 gap-2">
                  {CONTRACT_TYPES.filter(t => t !== "CUSTOM").map((type) => (
                    <button
                      key={type}
                      onClick={() => setContractType(type)}
                      className={`px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
                        contractType === type
                          ? "bg-purple-500/20 border-purple-500/50 text-purple-300"
                          : "glass border-white/10 text-slate-400 hover:border-white/25 hover:text-white"
                      }`}
                    >
                      {type}
                    </button>
                  ))}
                </div>
              </div>

              {/* Actions */}
              <div className="space-y-2">
                <button
                  onClick={handleCompile}
                  disabled={isCompiling || !sourceCode.trim() || isGenerating}
                  className="btn-ghost w-full justify-center text-sm border border-white/15 disabled:opacity-40"
                >
                  {isCompiling ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Compiling…</>
                  ) : (
                    <><Play className="w-4 h-4" /> Compile</>
                  )}
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving || !sourceCode.trim()}
                  className="btn-ghost w-full justify-center text-sm border border-white/15 disabled:opacity-40"
                >
                  {saving ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Saving…</>
                  ) : (
                    <><Save className="w-4 h-4" /> Save Contract</>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Right panel — Editor + output */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Tabs */}
            <div className="flex items-center gap-1 px-4 py-2 border-b border-white/10 bg-black/10">
              {[
                { id: "editor", label: "Editor", icon: Code2 },
                { id: "output", label: "Compile Output", icon: Play },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as "editor" | "output")}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    activeTab === tab.id
                      ? "bg-white/10 text-white border border-white/15"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  <tab.icon className="w-3.5 h-3.5" />
                  {tab.label}
                  {tab.id === "output" && compileResult && (
                    <span className={compileResult.success ? "badge-success" : "badge-danger"}>
                      {compileResult.success ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                    </span>
                  )}
                  {tab.id === "output" && isCompiling && (
                    <span className="badge-warning"><Loader2 className="w-3 h-3 animate-spin" /></span>
                  )}
                </button>
              ))}
            </div>

            {/* Editor */}
            {activeTab === "editor" && (
              <div className="flex-1 p-4">
                <SolidityEditor />
              </div>
            )}

            {/* Compile output */}
            {activeTab === "output" && (
              <div className="flex-1 p-6 overflow-y-auto space-y-4">
                {/* Compile task tracker */}
                <AnimatePresence>
                  {compileTaskId && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                      <TaskTracker
                        taskId={compileTaskId}
                        label="Compiling Solidity..."
                        onSuccess={handleCompileSuccess}
                        onError={handleCompileError}
                        onComplete={() => setCompileTaskId(null)}
                      />
                    </motion.div>
                  )}
                </AnimatePresence>

                {!compileResult && !compileTaskId ? (
                  <div className="flex flex-col items-center justify-center h-64 text-slate-500">
                    <Play className="w-12 h-12 mb-3 opacity-30" />
                    <p>Run compilation to see output</p>
                  </div>
                ) : compileResult ? (
                  <>
                    {/* Status */}
                    <div className={`glass-card border p-4 flex items-center gap-3 ${
                      compileResult.success ? "border-green-500/30" : "border-red-500/30"
                    }`}>
                      {compileResult.success ? (
                        <CheckCircle2 className="w-6 h-6 text-green-400 shrink-0" />
                      ) : (
                        <XCircle className="w-6 h-6 text-red-400 shrink-0" />
                      )}
                      <div>
                        <p className="font-semibold text-white">
                          {compileResult.success ? "Compilation Successful" : "Compilation Failed"}
                        </p>
                        {compileResult.success && (
                          <p className="text-sm text-slate-400">
                            ABI has {(compileResult.abi as unknown[])?.length || 0} entries ·{" "}
                            Bytecode: {Math.floor((compileResult.bytecode?.length || 0) / 2)} bytes
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Errors */}
                    {compileResult.errors && compileResult.errors.length > 0 && (
                      <div className="glass-card border border-red-500/30 p-4">
                        <h3 className="text-red-400 font-semibold mb-2 flex items-center gap-2">
                          <XCircle className="w-4 h-4" /> Errors
                        </h3>
                        {compileResult.errors.map((e: string, i: number) => (
                          <p key={i} className="text-sm text-red-300 mono mb-1">{e}</p>
                        ))}
                      </div>
                    )}

                    {/* Warnings */}
                    {compileResult.warnings && compileResult.warnings.length > 0 && (
                      <div className="glass-card border border-yellow-500/30 p-4">
                        <h3 className="text-yellow-400 font-semibold mb-2 flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4" /> Warnings
                        </h3>
                        {compileResult.warnings.map((w: string, i: number) => (
                          <p key={i} className="text-sm text-yellow-300 mono mb-1">{w}</p>
                        ))}
                      </div>
                    )}

                    {/* ABI */}
                    {compileResult.success && compileResult.abi && (
                      <div className="glass-card border border-white/10 p-4">
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="text-white font-semibold">Contract ABI</h3>
                          <button onClick={handleCopyABI} className="btn-ghost text-xs px-3 py-1.5 gap-1.5">
                            <Copy className="w-3.5 h-3.5" /> Copy ABI
                          </button>
                        </div>
                        <pre className="text-xs text-slate-300 mono bg-black/30 rounded-xl p-4 overflow-x-auto max-h-64 overflow-y-auto">
                          {JSON.stringify(compileResult.abi, null, 2)}
                        </pre>
                      </div>
                    )}
                  </>
                ) : null}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
