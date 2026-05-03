"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  FileCode2, Rocket, Shield, CheckCircle2, Clock, AlertTriangle,
  Plus, ChevronRight, Activity, TrendingUp, Zap
} from "lucide-react";
import Link from "next/link";
import { Sidebar } from "@/components/Layout/Sidebar";
import { WalletConnect } from "@/components/Wallet/WalletConnect";
import { contractsApi, deployApi } from "@/lib/api";
import { useContractsStore, useUIStore } from "@/lib/store";
import { Contract } from "@/lib/store";

const STAT_CARDS = [
  { label: "Total Contracts", icon: FileCode2, color: "from-purple-500/20 to-purple-500/5", border: "border-purple-500/30" },
  { label: "Deployed", icon: Rocket, color: "from-green-500/20 to-green-500/5", border: "border-green-500/30" },
  { label: "Audited", icon: Shield, color: "from-blue-500/20 to-blue-500/5", border: "border-blue-500/30" },
  { label: "AI Generated", icon: Zap, color: "from-yellow-500/20 to-yellow-500/5", border: "border-yellow-500/30" },
];

export default function DashboardPage() {
  const { contracts, setContracts } = useContractsStore();
  const { addNotification } = useUIStore();
  const [deployments, setDeployments] = useState<unknown[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [contractsRes, deploymentsRes] = await Promise.all([
          contractsApi.list({ limit: 10 }),
          deployApi.history(),
        ]);
        setContracts(contractsRes.data);
        setDeployments(deploymentsRes.data);
      } catch (err: unknown) {
        const error = err as { response?: { status: number } };
        if (error?.response?.status === 401) {
          window.location.href = "/login";
        } else {
          addNotification("error", "Failed to load dashboard data");
        }
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const stats = [
    contracts.length,
    deployments.filter((d: unknown) => (d as { status: string }).status === "SUCCESS").length,
    contracts.filter((c: Contract) => c.is_compiled).length,
    contracts.filter((c: Contract) => c.ai_generated).length,
  ];

  const typeColors: Record<string, string> = {
    ERC20: "badge-info",
    ERC721: "badge-warning",
    ERC1155: "badge-success",
    DAO: "badge-danger",
    STAKING: "badge-success",
    DEFI: "badge-info",
    CUSTOM: "badge-info",
  };

  return (
    <div className="flex min-h-screen bg-[hsl(222,47%,6%)]">
      <Sidebar />

      <main className="flex-1 ml-[240px] transition-all duration-250">
        {/* Top bar */}
        <div className="sticky top-0 z-30 flex items-center justify-between px-8 py-4 border-b border-white/10 backdrop-blur-xl bg-black/20">
          <div>
            <h1 className="text-xl font-bold text-white">Dashboard</h1>
            <p className="text-sm text-slate-400">Welcome back! Here's your workspace overview.</p>
          </div>
          <div className="flex items-center gap-4">
            <WalletConnect showNetworkSwitcher />
            <Link href="/builder" className="btn-primary text-sm px-4 py-2">
              <Plus className="w-4 h-4" />
              New Contract
            </Link>
          </div>
        </div>

        <div className="p-8 space-y-8">
          {/* Stats */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {STAT_CARDS.map((card, i) => (
              <motion.div
                key={card.label}
                className={`glass-card border ${card.border} p-6`}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08 }}
              >
                <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${card.color} border ${card.border} flex items-center justify-center mb-3`}>
                  <card.icon className="w-5 h-5 text-white" />
                </div>
                <div className="text-2xl font-black text-white">
                  {loading ? <div className="h-8 w-12 bg-white/10 rounded animate-pulse" /> : stats[i]}
                </div>
                <p className="text-sm text-slate-400 mt-1">{card.label}</p>
              </motion.div>
            ))}
          </div>

          {/* Recent contracts + deployments */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Contracts */}
            <div className="glass-card border border-white/10 p-6">
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <FileCode2 className="w-5 h-5 text-purple-400" />
                  Recent Contracts
                </h2>
                <Link href="/builder" className="text-xs text-slate-400 hover:text-purple-400 flex items-center gap-1">
                  View all <ChevronRight className="w-3.5 h-3.5" />
                </Link>
              </div>

              {loading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-14 bg-white/5 rounded-xl animate-pulse" />
                  ))}
                </div>
              ) : contracts.length === 0 ? (
                <div className="text-center py-12">
                  <FileCode2 className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                  <p className="text-slate-500 text-sm">No contracts yet</p>
                  <Link href="/builder" className="btn-primary text-xs px-4 py-2 mt-4 inline-flex">
                    <Plus className="w-3.5 h-3.5" /> Create First Contract
                  </Link>
                </div>
              ) : (
                <div className="space-y-2">
                  {contracts.slice(0, 5).map((contract) => (
                    <Link
                      key={contract.id}
                      href={`/builder?id=${contract.id}`}
                      className="flex items-center justify-between p-3 rounded-xl hover:bg-white/5 border border-transparent hover:border-white/10 transition-all group"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-purple-500/20 border border-purple-500/30 flex items-center justify-center">
                          <FileCode2 className="w-4 h-4 text-purple-400" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-white group-hover:text-purple-300 transition-colors">
                            {contract.name}
                          </p>
                          <p className="text-xs text-slate-500">
                            {new Date(contract.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={typeColors[contract.contract_type] || "badge-info"}>
                          {contract.contract_type}
                        </span>
                        {contract.is_compiled && (
                          <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />
                        )}
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {/* Deployments */}
            <div className="glass-card border border-white/10 p-6">
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <Rocket className="w-5 h-5 text-green-400" />
                  Recent Deployments
                </h2>
                <Link href="/deploy" className="text-xs text-slate-400 hover:text-green-400 flex items-center gap-1">
                  Deploy new <ChevronRight className="w-3.5 h-3.5" />
                </Link>
              </div>

              {loading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-14 bg-white/5 rounded-xl animate-pulse" />
                  ))}
                </div>
              ) : deployments.length === 0 ? (
                <div className="text-center py-12">
                  <Rocket className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                  <p className="text-slate-500 text-sm">No deployments yet</p>
                  <Link href="/deploy" className="btn-primary text-xs px-4 py-2 mt-4 inline-flex">
                    <Rocket className="w-3.5 h-3.5" /> Deploy Contract
                  </Link>
                </div>
              ) : (
                <div className="space-y-2">
                  {(deployments as Array<{
                    id: string;
                    status: string;
                    network: string;
                    contract_address?: string;
                    created_at: string;
                  }>).slice(0, 5).map((d) => (
                    <div key={d.id} className="flex items-center justify-between p-3 rounded-xl bg-white/3 border border-white/5">
                      <div className="flex items-center gap-3">
                        <div className={`w-2 h-2 rounded-full ${
                          d.status === "SUCCESS" ? "bg-green-400" :
                          d.status === "DEPLOYING" ? "bg-yellow-400 animate-pulse" :
                          d.status === "FAILED" ? "bg-red-400" : "bg-slate-400"
                        }`} />
                        <div>
                          <p className="text-sm font-medium text-white">{d.network}</p>
                          {d.contract_address && (
                            <p className="text-xs text-slate-500 mono">
                              {d.contract_address.slice(0, 10)}…{d.contract_address.slice(-6)}
                            </p>
                          )}
                        </div>
                      </div>
                      <span className={`text-xs ${
                        d.status === "SUCCESS" ? "badge-success" :
                        d.status === "FAILED" ? "badge-danger" :
                        d.status === "DEPLOYING" ? "badge-warning" : "badge-info"
                      }`}>
                        {d.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Quick actions */}
          <div className="glass-card border border-white/10 p-6">
            <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-cyan-400" />
              Quick Actions
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: "Generate with AI", href: "/builder", icon: Zap, color: "text-purple-400" },
                { label: "Deploy Contract", href: "/deploy", icon: Rocket, color: "text-green-400" },
                { label: "Run Audit", href: "/audit", icon: Shield, color: "text-red-400" },
                { label: "View History", href: "/history", icon: Clock, color: "text-blue-400" },
              ].map((action) => (
                <Link
                  key={action.label}
                  href={action.href}
                  className="glass border border-white/10 rounded-xl p-4 hover:border-white/20 transition-all group hover:scale-105"
                >
                  <action.icon className={`w-6 h-6 ${action.color} mb-2 group-hover:scale-110 transition-transform`} />
                  <p className="text-sm font-medium text-slate-300 group-hover:text-white transition-colors">
                    {action.label}
                  </p>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
