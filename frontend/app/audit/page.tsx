"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Shield, AlertTriangle, CheckCircle2, Info, Loader2, ChevronDown, XCircle } from "lucide-react";
import { Sidebar } from "@/components/Layout/Sidebar";
import { WalletConnect } from "@/components/Wallet/WalletConnect";
import { contractsApi, auditApi } from "@/lib/api";
import { useContractsStore, useUIStore } from "@/lib/store";
import { Contract, AuditFinding, AuditReport } from "@/lib/store";

const SEVERITY_CONFIG: Record<string, { label: string; cls: string; icon: React.ElementType }> = {
  CRITICAL: { label: "Critical", cls: "badge-danger border-red-600/50 bg-red-900/20", icon: XCircle },
  HIGH: { label: "High", cls: "badge-danger", icon: AlertTriangle },
  MEDIUM: { label: "Medium", cls: "badge-warning", icon: AlertTriangle },
  LOW: { label: "Low", cls: "badge-success", icon: Info },
  INFO: { label: "Info", cls: "badge-info", icon: Info },
};

function RiskGauge({ score }: { score: number }) {
  const color = score >= 70 ? "#ef4444" : score >= 40 ? "#f97316" : score >= 20 ? "#eab308" : "#22c55e";
  const dashArray = 283; // 2*PI*45
  const dashOffset = dashArray * (1 - score / 100);

  return (
    <div className="flex flex-col items-center">
      <svg width={120} height={120} viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="45" fill="none" stroke="#ffffff10" strokeWidth="10" />
        <circle
          cx="60" cy="60" r="45"
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeDasharray={dashArray}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
          transform="rotate(-90 60 60)"
          style={{ transition: "stroke-dashoffset 1s ease, stroke 0.5s ease" }}
        />
        <text x="60" y="58" textAnchor="middle" fill="white" fontSize="20" fontWeight="800">
          {Math.round(score)}
        </text>
        <text x="60" y="74" textAnchor="middle" fill="#94a3b8" fontSize="10">
          Risk Score
        </text>
      </svg>
      <p className="text-sm font-semibold mt-2" style={{ color }}>
        {score >= 70 ? "CRITICAL" : score >= 40 ? "HIGH RISK" : score >= 20 ? "MEDIUM RISK" : score > 0 ? "LOW RISK" : "SAFE"}
      </p>
    </div>
  );
}

function FindingCard({ finding }: { finding: AuditFinding }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.INFO;

  return (
    <div className="glass border border-white/10 rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className={cfg.cls}><cfg.icon className="w-3.5 h-3.5" /> {cfg.label}</span>
          <p className="text-sm font-medium text-white text-left">{finding.title}</p>
        </div>
        <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${expanded ? "rotate-180" : ""}`} />
      </button>
      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-white/10">
          {finding.location && (
            <p className="text-xs mono text-slate-400 bg-black/20 px-3 py-1.5 rounded-lg">{finding.location}</p>
          )}
          <p className="text-sm text-slate-300 leading-relaxed">{finding.description}</p>
          <div className="flex items-start gap-2 bg-green-500/10 border border-green-500/20 rounded-xl p-3">
            <CheckCircle2 className="w-4 h-4 text-green-400 shrink-0 mt-0.5" />
            <p className="text-xs text-green-300 leading-relaxed">{finding.suggestion}</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AuditPage() {
  const { contracts } = useContractsStore();
  const { addNotification } = useUIStore();

  const [selectedContract, setSelectedContract] = useState<Contract | null>(null);
  const [report, setReport] = useState<AuditReport | null>(null);
  const [running, setRunning] = useState(false);
  const [polling, setPolling] = useState(false);
  const [filterSeverity, setFilterSeverity] = useState<string>("ALL");

  const startAudit = async () => {
    if (!selectedContract) {
      addNotification("error", "Select a contract to audit");
      return;
    }
    setRunning(true);
    setReport(null);
    try {
      const res = await auditApi.run(selectedContract.id);
      const reportId = res.data.id;
      setReport(res.data);
      setPolling(true);

      // Poll for completion
      const interval = setInterval(async () => {
        const statusRes = await auditApi.get(reportId);
        const r = statusRes.data;
        setReport(r);
        if (r.status === "COMPLETED" || r.status === "FAILED") {
          clearInterval(interval);
          setPolling(false);
          setRunning(false);
          if (r.status === "COMPLETED") {
            addNotification("success", `Audit completed. Risk score: ${r.risk_score?.toFixed(0)}/100`);
          } else {
            addNotification("error", "Audit failed to complete");
          }
        }
      }, 3000);
    } catch {
      addNotification("error", "Failed to start audit");
      setRunning(false);
    }
  };

  const findings = report?.findings || [];
  const filtered = filterSeverity === "ALL"
    ? findings
    : findings.filter((f) => f.severity === filterSeverity);

  const counts: Record<string, number> = {};
  findings.forEach((f) => { counts[f.severity] = (counts[f.severity] || 0) + 1; });

  return (
    <div className="flex min-h-screen bg-[hsl(222,47%,6%)]">
      <Sidebar />
      <main className="flex-1 ml-[240px] overflow-y-auto">
        {/* Top bar */}
        <div className="sticky top-0 z-30 flex items-center justify-between px-8 py-4 border-b border-white/10 backdrop-blur-xl bg-black/20">
          <div className="flex items-center gap-3">
            <Shield className="w-5 h-5 text-red-400" />
            <h1 className="text-xl font-bold text-white">Security Audit</h1>
          </div>
          <WalletConnect />
        </div>

        <div className="p-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Setup */}
          <div className="space-y-5">
            {/* Select contract */}
            <div className="glass-card border border-white/10 p-5">
              <h2 className="font-bold text-white mb-4">Select Contract</h2>
              {contracts.length === 0 ? (
                <p className="text-slate-500 text-sm">No contracts available</p>
              ) : (
                <div className="space-y-2">
                  {contracts.slice(0, 8).map((c) => (
                    <button
                      key={c.id}
                      onClick={() => setSelectedContract(c)}
                      className={`w-full flex items-center gap-3 p-3 rounded-xl border text-left transition-all ${
                        selectedContract?.id === c.id
                          ? "bg-red-500/15 border-red-500/40 text-white"
                          : "glass border-white/10 text-slate-300 hover:border-white/25"
                      }`}
                    >
                      <div className="w-7 h-7 rounded-lg bg-red-500/20 flex items-center justify-center shrink-0">
                        <Shield className="w-3.5 h-3.5 text-red-400" />
                      </div>
                      <div>
                        <p className="text-sm font-medium">{c.name}</p>
                        <p className="text-xs text-slate-500">{c.contract_type}</p>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <button
              onClick={startAudit}
              disabled={running || !selectedContract}
              className="btn-primary w-full justify-center py-3 disabled:opacity-40"
              style={{ background: "linear-gradient(135deg, #ef4444 0%, #f97316 100%)" }}
            >
              {running || polling ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Analyzing…</>
              ) : (
                <><Shield className="w-4 h-4" /> Run Security Audit</>
              )}
            </button>

            {/* Legend */}
            <div className="glass-card border border-white/10 p-4 space-y-2">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Severity Levels</p>
              {Object.entries(SEVERITY_CONFIG).map(([key, cfg]) => (
                <div key={key} className="flex items-center gap-2">
                  <cfg.icon className="w-3.5 h-3.5 text-slate-400" />
                  <span className={`text-xs ${cfg.cls}`}>{cfg.label}</span>
                  {counts[key] !== undefined && (
                    <span className="ml-auto text-xs text-slate-400">{counts[key]}</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Right: Results */}
          <div className="lg:col-span-2 space-y-5">
            {!report ? (
              <div className="glass-card border border-white/10 p-12 text-center">
                <Shield className="w-16 h-16 text-slate-600 mx-auto mb-4" />
                <p className="text-slate-400 text-lg">Select a contract and run an audit</p>
                <p className="text-slate-500 text-sm mt-1">
                  Detects reentrancy, overflow, access control issues, and more
                </p>
              </div>
            ) : (
              <>
                {/* Report header */}
                <div className="glass-card border border-white/10 p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-xl font-bold text-white mb-2">Audit Report</h2>
                      <p className={`text-sm ${
                        report.status === "COMPLETED" ? "text-green-400" :
                        report.status === "RUNNING" ? "text-yellow-400" :
                        report.status === "FAILED" ? "text-red-400" : "text-slate-400"
                      }`}>
                        Status: {report.status}
                        {(report.status === "PENDING" || report.status === "RUNNING") && (
                          <Loader2 className="w-3.5 h-3.5 inline ml-2 animate-spin" />
                        )}
                      </p>
                      {report.summary && (
                        <p className="text-slate-400 text-sm mt-2 max-w-lg">{report.summary}</p>
                      )}
                    </div>
                    {report.risk_score !== undefined && report.risk_score !== null && (
                      <RiskGauge score={report.risk_score} />
                    )}
                  </div>
                </div>

                {/* Findings */}
                {findings.length > 0 && (
                  <div className="glass-card border border-white/10 p-6">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-bold text-white">{findings.length} Findings</h3>
                      <div className="flex gap-2">
                        {["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"].map((s) => (
                          <button
                            key={s}
                            onClick={() => setFilterSeverity(s)}
                            className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                              filterSeverity === s
                                ? "bg-white/15 text-white border border-white/25"
                                : "text-slate-400 hover:text-white"
                            }`}
                          >
                            {s}
                            {s !== "ALL" && counts[s] ? ` (${counts[s]})` : ""}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="space-y-3">
                      {filtered.map((f) => (
                        <FindingCard key={f.id} finding={f} />
                      ))}
                    </div>
                  </div>
                )}

                {report.status === "COMPLETED" && findings.length === 0 && (
                  <div className="glass-card border border-green-500/30 p-8 text-center">
                    <CheckCircle2 className="w-12 h-12 text-green-400 mx-auto mb-3" />
                    <p className="text-green-300 font-bold text-lg">No Issues Found</p>
                    <p className="text-slate-400 text-sm mt-1">Contract appears secure based on static analysis</p>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
