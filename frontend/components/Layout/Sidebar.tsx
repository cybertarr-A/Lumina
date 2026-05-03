"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  FileCode2, LayoutDashboard, Code2, Rocket, Shield,
  History, Settings, ChevronLeft, ChevronRight, LogOut, Users,
} from "lucide-react";
import { useAuthStore, useUIStore } from "@/lib/store";
import { authApi } from "@/lib/api";
import { WalletConnect } from "@/components/Wallet/WalletConnect";

const NAV_ITEMS = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/builder", icon: Code2, label: "Contract Builder" },
  { href: "/deploy", icon: Rocket, label: "Deploy" },
  { href: "/audit", icon: Shield, label: "Audit" },
  { href: "/history", icon: History, label: "History" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen, toggleSidebar } = useUIStore();
  const { user, clearAuth } = useAuthStore();

  const handleLogout = async () => {
    try { await authApi.logout(); } catch {}
    clearAuth();
    window.location.href = "/login";
  };

  return (
    <motion.aside
      animate={{ width: sidebarOpen ? 240 : 72 }}
      transition={{ duration: 0.25, ease: "easeInOut" }}
      className="fixed left-0 top-0 h-full z-40 flex flex-col bg-[hsl(222,47%,7%)] border-r border-white/10 overflow-hidden"
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-white/10 min-h-[72px]">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center shrink-0">
          <FileCode2 className="w-5 h-5 text-white" />
        </div>
        {sidebarOpen && (
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-base font-bold gradient-text whitespace-nowrap"
          >
            Lumina
          </motion.span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`sidebar-item ${isActive ? "active" : ""} ${!sidebarOpen ? "justify-center" : ""}`}
              title={!sidebarOpen ? item.label : undefined}
            >
              <item.icon className="w-5 h-5 shrink-0" />
              {sidebarOpen && (
                <motion.span
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-sm font-medium"
                >
                  {item.label}
                </motion.span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Bottom section */}
      <div className="border-t border-white/10 px-3 py-4 space-y-2">
        {sidebarOpen && user && (
          <div className="px-4 py-3 rounded-xl bg-white/5 border border-white/10 mb-2">
            <p className="text-xs text-slate-500 mb-0.5">Signed in as</p>
            <p className="text-sm text-white font-medium truncate">{user.username}</p>
            <p className="text-xs text-slate-500 truncate">{user.email}</p>
          </div>
        )}

        <button
          onClick={handleLogout}
          className={`sidebar-item text-red-400 hover:text-red-300 hover:bg-red-500/10 w-full ${!sidebarOpen ? "justify-center" : ""}`}
          title={!sidebarOpen ? "Sign out" : undefined}
        >
          <LogOut className="w-5 h-5 shrink-0" />
          {sidebarOpen && <span className="text-sm font-medium">Sign Out</span>}
        </button>

        {/* Collapse toggle */}
        <button
          onClick={toggleSidebar}
          className={`sidebar-item justify-center w-full`}
          title="Toggle sidebar"
        >
          {sidebarOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
      </div>
    </motion.aside>
  );
}
