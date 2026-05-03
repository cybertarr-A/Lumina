"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { FileCode2, Loader2, Eye, EyeOff } from "lucide-react";
import { authApi } from "@/lib/api";
import { useAuthStore, useUIStore } from "@/lib/store";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const { setAuth } = useAuthStore();
  const { addNotification } = useUIStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await authApi.login({ email, password });
      const { access_token, refresh_token } = res.data;

      // Get user info
      localStorage.setItem("access_token", access_token);
      const meRes = await authApi.me();
      setAuth(meRes.data, access_token, refresh_token);

      addNotification("success", "Welcome back!");
      router.push("/dashboard");
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      addNotification("error", error.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[hsl(222,47%,6%)] relative overflow-hidden">
      {/* Glow orbs */}
      <div className="absolute top-1/4 left-1/4 w-72 h-72 bg-purple-600/15 rounded-full blur-3xl" />
      <div className="absolute bottom-1/4 right-1/4 w-72 h-72 bg-cyan-600/15 rounded-full blur-3xl" />

      <motion.div
        className="w-full max-w-md p-8 glass-card border border-white/15 mx-4"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
            <FileCode2 className="w-6 h-6 text-white" />
          </div>
          <div>
            <p className="font-bold text-white">Lumina</p>
            <p className="text-xs text-slate-400">Sign in to your account</p>
          </div>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="text-sm text-slate-400 block mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className="input-field"
            />
          </div>
          <div>
            <label className="text-sm text-slate-400 block mb-1.5">Password</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="input-field pr-12"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full justify-center py-3 mt-2 disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Sign In"}
          </button>
        </form>

        <p className="text-center text-sm text-slate-400 mt-6">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="text-purple-400 hover:text-purple-300 font-medium">
            Create account
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
